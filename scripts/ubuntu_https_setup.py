#!/usr/bin/env python3
"""
Ubuntu production edge setup for MotoShop RMS — Nginx by IP (no domain).

Default: HTTP on port 80 via Nginx → Next.js (:3000) + FastAPI (:8000).
Optional: --self-signed for HTTPS on 443 (browser warning; good for tablet camera).

No DNS, no Certbot, no domain name required.

Usage (from repo root on Ubuntu):
  sudo ./scripts/run_ubuntu_https.sh
  sudo ./scripts/run_ubuntu_https.sh --yes
  sudo ./scripts/run_ubuntu_https.sh --self-signed --yes
  sudo ./scripts/run_ubuntu_https.sh --skip-build --self-signed
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import pwd
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "deploy" / "ubuntu"
SSL_DIR = Path("/etc/ssl/rms")
ASSUME_YES = False


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def info(msg: str) -> None:
    print(f"==> {msg}")


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
        env=env,
    )


def require_root() -> None:
    if os.geteuid() != 0:
        die("Run as root: sudo ./scripts/run_ubuntu_https.sh")


def require_ubuntu() -> None:
    if not sys.platform.startswith("linux"):
        die("This script is for Ubuntu/Linux only.")
    if not Path("/etc/os-release").exists():
        die("Cannot read /etc/os-release")
    text = Path("/etc/os-release").read_text(encoding="utf-8")
    if "Ubuntu" not in text and "Debian" not in text:
        print("WARNING: Not detected as Ubuntu/Debian; continuing anyway.")


def render(template_name: str, mapping: dict[str, str]) -> str:
    path = TEMPLATES / template_name
    if not path.exists():
        die(f"Missing template: {path}")
    text = path.read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace(f"__{key}__", value)
    leftover = [
        tok
        for tok in (
            "__SSL_CERT__",
            "__SSL_KEY__",
            "__REPO_ROOT__",
            "__SERVICE_USER__",
            "__NODE__",
            "__NODE_BIN__",
        )
        if tok in text
    ]
    if leftover:
        die(f"Unreplaced placeholders in {template_name}: {leftover}")
    return text


def write_file(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)
    info(f"Wrote {path}")


def prompt(msg: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        value = ""
    if not value and default is not None:
        return default
    return value


def confirm(msg: str, default: bool = True) -> bool:
    if ASSUME_YES:
        print(f"{msg} → yes (--yes)")
        return True
    yn = "Y/n" if default else "y/N"
    ans = prompt(f"{msg} ({yn})", "y" if default else "n").lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def fetch_public_ipv4(timeout: float = 8.0) -> str | None:
    for url in (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8").strip()
                ipaddress.IPv4Address(ip)
                return ip
        except Exception:
            continue
    return None


def lan_ipv4_addresses() -> list[str]:
    found: list[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127."):
            return
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            return
        if addr.is_private and not addr.is_link_local:
            if ip not in found:
                found.append(ip)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    return found


def apt_install(packages: list[str]) -> None:
    if not packages:
        return
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    run(["apt-get", "update"], env=env)
    run(["apt-get", "install", "-y", *packages], env=env)


def ensure_service_user(username: str, repo: Path) -> None:
    try:
        pwd.getpwnam(username)
        info(f"User {username} exists")
    except KeyError:
        run(
            [
                "useradd",
                "--system",
                "--create-home",
                "--home-dir",
                f"/home/{username}",
                "--shell",
                "/usr/sbin/nologin",
                username,
            ]
        )
    run(["usermod", "-aG", "docker", username], check=False)
    run(["chown", "-R", f"{username}:{username}", str(repo)])


def write_upgrade_map() -> None:
    write_file(
        Path("/etc/nginx/conf.d/rms-upgrade-map.conf"),
        "map $http_upgrade $connection_upgrade {\n"
        "    default upgrade;\n"
        "    ''      close;\n"
        "}\n",
    )


def install_nginx_site(content: str, name: str = "rms") -> None:
    available = Path(f"/etc/nginx/sites-available/{name}")
    enabled = Path(f"/etc/nginx/sites-enabled/{name}")
    write_file(available, content)
    if enabled.exists() or enabled.is_symlink():
        enabled.unlink()
    enabled.symlink_to(available)
    default = Path("/etc/nginx/sites-enabled/default")
    if default.exists() or default.is_symlink():
        default.unlink()
        info("Disabled Nginx default site")
    write_upgrade_map()
    run(["nginx", "-t"])
    run(["systemctl", "enable", "--now", "nginx"])
    run(["systemctl", "reload", "nginx"])


def resolve_node(user: str) -> Path:
    """Find node for the service user (supports nvm / fnm / apt / nodesource)."""
    probes = [
        ["sudo", "-u", user, "-H", "bash", "-lc", "command -v node"],
        ["bash", "-lc", "command -v node"],
    ]
    for cmd in probes:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception:
            continue
        path = (r.stdout or "").strip().splitlines()
        if path:
            p = Path(path[-1].strip())
            if p.is_file():
                return p

    for candidate in (
        Path("/usr/bin/node"),
        Path("/usr/local/bin/node"),
    ):
        if candidate.is_file():
            return candidate

    die(
        f"Node.js not found for user '{user}'.\n"
        "Install Node 20+ (nodesource or nvm), then re-run.\n"
        "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -\n"
        "  sudo apt-get install -y nodejs"
    )


def install_systemd_units(repo: Path, user: str) -> None:
    node = resolve_node(user)
    next_bin = repo / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.exists():
        die(
            f"Next.js binary missing: {next_bin}\n"
            "Run a frontend build first (npm ci && npm run build), or omit --skip-build."
        )
    mapping = {
        "REPO_ROOT": str(repo),
        "SERVICE_USER": user,
        "NODE": str(node),
        "NODE_BIN": str(node.parent),
    }
    info(f"Using node: {node}")
    write_file(
        Path("/etc/systemd/system/rms-api.service"),
        render("rms-api.service.template", mapping),
    )
    write_file(
        Path("/etc/systemd/system/rms-web.service"),
        render("rms-web.service.template", mapping),
    )
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "rms-api", "rms-web"])


def configure_ufw(*, https: bool) -> None:
    if not shutil.which("ufw"):
        apt_install(["ufw"])
    run(["ufw", "default", "deny", "incoming"], check=False)
    run(["ufw", "default", "allow", "outgoing"], check=False)
    run(["ufw", "allow", "OpenSSH"], check=False)
    run(["ufw", "allow", "80/tcp"], check=False)
    if https:
        run(["ufw", "allow", "443/tcp"], check=False)
    run(["ufw", "--force", "enable"], check=False)
    run(["ufw", "status", "verbose"], check=False)


def stop_prod_deploy_pids(repo: Path) -> None:
    logs = repo / "logs"
    for name in ("prod_backend.pid", "prod_frontend.pid", "prod_tunnel.pid"):
        pid_file = logs / name
        if not pid_file.exists():
            continue
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            continue
        try:
            os.kill(pid, 15)
            info(f"Stopped old PID {pid} ({name})")
            time.sleep(0.5)
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        pid_file.unlink(missing_ok=True)


def prepare_app(repo: Path, user: str, *, skip_build: bool) -> None:
    if skip_build:
        info("Skipping app build (--skip-build)")
        stop_prod_deploy_pids(repo)
        return

    info("Running production migrate + build (prod_deploy.py)…")
    run(
        [
            "sudo",
            "-u",
            user,
            "python3",
            str(repo / "scripts" / "prod_deploy.py"),
        ],
        check=False,
    )
    stop_prod_deploy_pids(repo)
    run(
        [
            "sudo",
            "-u",
            user,
            "python3",
            str(repo / "scripts" / "prod_deploy.py"),
            "--stop-only",
        ],
        check=False,
    )


def start_app_services() -> None:
    run(["systemctl", "restart", "rms-api", "rms-web"])
    time.sleep(2)
    run(["systemctl", "--no-pager", "status", "rms-api"], check=False)
    run(["systemctl", "--no-pager", "status", "rms-web"], check=False)


def wait_local(url: str, timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            time.sleep(1)
    return False


def ensure_self_signed_cert(sans: list[str]) -> tuple[Path, Path]:
    SSL_DIR.mkdir(parents=True, exist_ok=True)
    cert = SSL_DIR / "rms.crt"
    key = SSL_DIR / "rms.key"
    conf = SSL_DIR / "openssl.cnf"

    alt_names = ["DNS:localhost", "IP:127.0.0.1"]
    for item in sans:
        item = item.strip()
        if not item:
            continue
        try:
            ipaddress.ip_address(item)
            alt_names.append(f"IP:{item}")
        except ValueError:
            alt_names.append(f"DNS:{item}")

    # Dedupe preserving order
    seen: set[str] = set()
    unique_alts: list[str] = []
    for a in alt_names:
        if a not in seen:
            seen.add(a)
            unique_alts.append(a)

    dns_i = 1
    ip_i = 1
    alt_lines: list[str] = []
    for v in unique_alts:
        if v.startswith("DNS:"):
            alt_lines.append(f"DNS.{dns_i} = {v[4:]}")
            dns_i += 1
        else:
            alt_lines.append(f"IP.{ip_i} = {v[3:]}")
            ip_i += 1

    conf.write_text(
        "[req]\n"
        "default_bits = 2048\n"
        "prompt = no\n"
        "default_md = sha256\n"
        "distinguished_name = dn\n"
        "x509_extensions = v3_req\n\n"
        "[dn]\n"
        "CN = MotoShop-RMS\n\n"
        "[v3_req]\n"
        "subjectAltName = @alt\n"
        "keyUsage = digitalSignature, keyEncipherment\n"
        "extendedKeyUsage = serverAuth\n\n"
        "[alt]\n"
        + "\n".join(alt_lines)
        + "\n",
        encoding="utf-8",
    )

    info(f"Generating self-signed certificate (SANs: {', '.join(unique_alts)})")
    run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "825",
            "-config",
            str(conf),
        ]
    )
    os.chmod(key, 0o600)
    os.chmod(cert, 0o644)
    return cert, key


def setup_nginx(*, self_signed: bool) -> None:
    apt_install(["nginx", "openssl"])
    configure_ufw(https=self_signed)

    if not wait_local("http://127.0.0.1:3000", 45):
        print("WARNING: Next.js not responding on :3000 yet")
    if not wait_local("http://127.0.0.1:8000/health", 45):
        print("WARNING: API not responding on :8000/health yet")

    if self_signed:
        sans = lan_ipv4_addresses()
        pub = fetch_public_ipv4()
        if pub:
            sans.append(pub)
        cert, key = ensure_self_signed_cert(sans)
        site = render(
            "nginx-ip-ssl.conf.template",
            {"SSL_CERT": str(cert), "SSL_KEY": str(key)},
        )
    else:
        site = (TEMPLATES / "nginx-ip.conf.template").read_text(encoding="utf-8")

    install_nginx_site(site, "rms")


def verify(*, self_signed: bool) -> None:
    info("Local health checks")
    api_ok = wait_local("http://127.0.0.1:8000/health", 30)
    web_ok = wait_local("http://127.0.0.1:3000", 30)
    print(f"  API  :8000/health → {'OK' if api_ok else 'FAIL'}")
    print(f"  Web  :3000        → {'OK' if web_ok else 'FAIL'}")

    scheme = "https" if self_signed else "http"
    urls = [f"{scheme}://127.0.0.1"]
    for ip in lan_ipv4_addresses():
        urls.append(f"{scheme}://{ip}")

    print("\n=== Setup complete (Nginx, no domain) ===")
    print("  Open one of:")
    for u in urls:
        print(f"    {u}")
    if self_signed:
        print("  First visit: accept the self-signed certificate warning.")
        print("  (Needed for tablet camera barcode scanning.)")
    else:
        print("  Camera barcode needs HTTPS — re-run with --self-signed")
        print("  or use Manual / Bluetooth gun on HTTP.")
    print("  Login:  admin / admin123  (change immediately)")
    print("  Logs:   journalctl -u rms-api -u rms-web -u nginx -f")
    print("          tail -f /var/log/nginx/rms.error.log")


def main() -> None:
    global ASSUME_YES

    parser = argparse.ArgumentParser(
        description="Ubuntu Nginx edge setup — by IP, no domain (MotoShop RMS)"
    )
    parser.add_argument(
        "--self-signed",
        action="store_true",
        help="Enable HTTPS on 443 with a self-signed cert (no Let's Encrypt / no domain)",
    )
    parser.add_argument(
        "--service-user",
        default=None,
        help="Linux user for systemd app units (default: $SUDO_USER, else rms)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip prod_deploy migrate/build (app already prepared)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Assume yes for confirmations",
    )
    args = parser.parse_args()
    ASSUME_YES = args.yes

    require_root()
    require_ubuntu()

    if not (TEMPLATES / "nginx-ip.conf.template").exists():
        die(f"Templates missing under {TEMPLATES}")

    info(f"Repo root: {ROOT}")
    lan = lan_ipv4_addresses()
    pub = fetch_public_ipv4()
    if lan:
        info(f"LAN IPs: {', '.join(lan)}")
    if pub:
        info(f"Public IP (internet view): {pub} (not used for DNS; info only)")

    mode = "HTTPS (self-signed)" if args.self_signed else "HTTP"
    print(f"\nNginx by IP — {mode} — no domain required\n")
    if not confirm("Continue?", True):
        die("Aborted.")

    service_user = args.service_user
    if not service_user:
        service_user = os.environ.get("SUDO_USER") or "rms"
        # Repo under /home/<user> → must run as that user (rms cannot CHDIR)
        if str(ROOT).startswith("/home/") and service_user == "rms":
            parts = Path(str(ROOT)).parts
            if len(parts) >= 3 and parts[1] == "home":
                service_user = parts[2]
                info(
                    f"Repo is under /home/{service_user} — "
                    f"using systemd User={service_user} (avoids CHDIR permission errors)"
                )
    info(f"Service user: {service_user}")

    apt_install(["curl", "ca-certificates", "gnupg", "ufw", "openssl"])
    ensure_service_user(service_user, ROOT)
    prepare_app(ROOT, service_user, skip_build=args.skip_build)
    install_systemd_units(ROOT, service_user)
    start_app_services()
    setup_nginx(self_signed=args.self_signed)
    verify(self_signed=args.self_signed)


if __name__ == "__main__":
    main()
