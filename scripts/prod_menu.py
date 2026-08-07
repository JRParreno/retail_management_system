#!/usr/bin/env python3
"""
Production ops menu for MotoShop RMS (Ubuntu systemd + Nginx).

After first-time setup (`sudo ./run_ubuntu_https.sh`), use this to:
  start / stop / restart services, deploy code changes, check status, view logs.

Usage:
  ./run_prod_menu.sh
  python3 scripts/prod_menu.py
  python3 scripts/prod_menu.py 5    # jump to option 5
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
IS_LINUX = sys.platform.startswith("linux")

UNITS = ("rms-api", "rms-web", "nginx")


def run(cmd: list[str], *, check: bool = False, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"\n→ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        check=check,
        text=True,
        capture_output=capture,
    )


def have_sudo() -> bool:
    return os.geteuid() == 0 or shutil.which("sudo") is not None


def syscmd(*args: str) -> list[str]:
    """Prefix with sudo when not root."""
    if os.geteuid() == 0:
        return list(args)
    return ["sudo", *args]


def unit_exists(name: str) -> bool:
    path = Path(f"/etc/systemd/system/{name}.service")
    if path.exists():
        return True
    # nginx is usually packaged
    if name == "nginx":
        return Path("/lib/systemd/system/nginx.service").exists() or shutil.which("nginx") is not None
    r = subprocess.run(
        ["systemctl", "cat", f"{name}.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0


def unit_active(name: str) -> bool:
    r = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip() == "active"


def lan_ipv4_addresses() -> list[str]:
    found: list[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127."):
            return
        if ip.startswith("192.168.") or ip.startswith("10."):
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


def https_enabled() -> bool:
    if Path("/etc/ssl/rms/rms.crt").exists():
        return True
    site = Path("/etc/nginx/sites-available/rms")
    if site.exists():
        return "ssl_certificate" in site.read_text(encoding="utf-8", errors="ignore")
    return False


def fetch_public_ipv4(timeout: float = 5.0) -> str | None:
    import urllib.request

    for url in (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip and all(c.isdigit() or c == "." for c in ip):
                    return ip
        except Exception:
            continue
    return None


def unit_failed(name: str) -> bool:
    r = subprocess.run(
        ["systemctl", "is-failed", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip() == "failed"


def recent_chdir_error(name: str) -> bool:
    r = subprocess.run(
        ["journalctl", "-u", name, "-n", "20", "--no-pager"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (r.stdout or "") + (r.stderr or "")
    return "CHDIR" in text or "Changing to the requested working directory failed" in text


def print_urls() -> None:
    scheme = "https" if https_enabled() else "http"
    public_ip = fetch_public_ipv4()
    print(f"  Local:     {scheme}://127.0.0.1")
    for ip in lan_ipv4_addresses():
        print(f"  LAN:       {scheme}://{ip}")
    if public_ip:
        print(f"  Public IP: {public_ip}")
        print(f"  Public:    {scheme}://{public_ip}")
        print("             ↑ works from outside only if router forwards TCP 80/443")
        print("               to this PC's LAN IP (see docs/production-https-ubuntu.md)")
    else:
        print("  Public IP: (could not detect — try: curl -4 ifconfig.me)")
    print("  API docs:  /docs  (via Nginx)")
    print("  Login:     admin / admin123")


def check_http(url: str, *, timeout: float = 3.0) -> tuple[bool, str]:
    """Local health probe. Accepts self-signed TLS (Nginx --self-signed setup)."""
    import ssl
    import urllib.error
    import urllib.request

    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        # Reached the server; 4xx/5xx still means Nginx is up
        if 400 <= exc.code < 600:
            return True, f"HTTP {exc.code}"
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def action_status() -> None:
    print("\n=== Status ===")
    if not IS_LINUX:
        print("This menu targets Ubuntu/Pop!_OS with systemd.")
        return

    problems: list[str] = []
    for name in UNITS:
        if not unit_exists(name):
            print(f"  {name:10}  not installed")
            continue
        if unit_active(name):
            state = "active"
        elif unit_failed(name):
            state = "failed"
            problems.append(name)
        else:
            state = "inactive"
        print(f"  {name:10}  {state}")

    print("\nURLs:")
    print_urls()

    # Quick health — Nginx HTTP redirects to HTTPS when --self-signed was used
    scheme = "https" if https_enabled() else "http"
    print("\nHealth:")
    checks = (
        ("API", "http://127.0.0.1:8000/health"),
        ("Web", "http://127.0.0.1:3000"),
        ("Nginx", f"{scheme}://127.0.0.1/health"),
    )
    for label, url in checks:
        ok, detail = check_http(url)
        mark = "OK" if ok else "FAIL"
        print(f"  {label:5}  {mark}  {detail}  ({url})")
    if https_enabled():
        print("  (self-signed HTTPS: browsers will warn once — that is expected)")

    if problems:
        print("\n⚠ Failed units:")
        for name in problems:
            if recent_chdir_error(name):
                print(
                    f"  {name}: Permission denied on WorkingDirectory (CHDIR).\n"
                    "  Cause: service User=rms cannot enter a path under /home/<you>/.\n"
                    "  Fix (run once):\n"
                    f"    sudo sed -i 's/^User=.*/User={os.environ.get('USER', 'jrparreno')}/' "
                    "/etc/systemd/system/rms-api.service /etc/systemd/system/rms-web.service\n"
                    f"    sudo sed -i 's/^Group=.*/Group={os.environ.get('USER', 'jrparreno')}/' "
                    "/etc/systemd/system/rms-api.service /etc/systemd/system/rms-web.service\n"
                    "    sudo systemctl daemon-reload\n"
                    "    sudo systemctl restart rms-api rms-web\n"
                    "  Or use menu option 11 (Fix service user / permissions)."
                )
            else:
                print(f"  {name}: see journalctl -u {name} -n 50 --no-pager")


def action_start() -> None:
    print("\n=== Start production services ===")
    for name in UNITS:
        if unit_exists(name):
            run(syscmd("systemctl", "start", name))
        else:
            print(f"  skip {name} (not installed)")
    time.sleep(1)
    action_status()


def action_stop() -> None:
    print("\n=== Stop production services ===")
    # Stop app units; leave nginx optional
    for name in ("rms-web", "rms-api"):
        if unit_exists(name):
            run(syscmd("systemctl", "stop", name))
    if unit_exists("nginx") and confirm("Also stop Nginx?"):
        run(syscmd("systemctl", "stop", "nginx"))
    # Stop any leftover prod_deploy detached processes
    run([sys.executable, str(ROOT / "scripts" / "prod_deploy.py"), "--stop-only"], check=False)
    print("Stopped.")


def action_restart() -> None:
    print("\n=== Restart production services ===")
    for name in ("rms-api", "rms-web"):
        if unit_exists(name):
            run(syscmd("systemctl", "restart", name))
    if unit_exists("nginx"):
        run(syscmd("systemctl", "reload", "nginx"), check=False)
        if not unit_active("nginx"):
            run(syscmd("systemctl", "restart", "nginx"))
    time.sleep(1)
    action_status()


def action_restart_api() -> None:
    print("\n=== Restart API only ===")
    run(syscmd("systemctl", "restart", "rms-api"))
    time.sleep(1)
    run(syscmd("systemctl", "--no-pager", "status", "rms-api"), check=False)


def action_restart_web() -> None:
    print("\n=== Restart Web only ===")
    run(syscmd("systemctl", "restart", "rms-web"))
    time.sleep(1)
    run(syscmd("systemctl", "--no-pager", "status", "rms-web"), check=False)


def action_reload_nginx() -> None:
    print("\n=== Reload Nginx ===")
    run(syscmd("nginx", "-t"))
    run(syscmd("systemctl", "reload", "nginx"))


def action_deploy() -> None:
    """Pull optional, migrate, rebuild frontend, restart services."""
    print("\n=== Deploy / apply code changes ===")
    if not confirm("git pull from origin?"):
        print("  Skipping git pull")
    else:
        run(["git", "pull", "--ff-only"], check=False)

    user = "rms"
    # Prefer running build as rms if user exists
    import pwd

    try:
        pwd.getpwnam(user)
        as_user = True
    except KeyError:
        as_user = False
        print(f"  User '{user}' not found — building as current user")

    # Migrate + rebuild via prod_deploy, then stop detached procs so systemd owns ports
    print("\nBuilding / migrating…")
    if as_user:
        run(
            [
                "sudo",
                "-u",
                user,
                "python3",
                str(ROOT / "scripts" / "prod_deploy.py"),
            ],
            check=False,
        )
        run(
            [
                "sudo",
                "-u",
                user,
                "python3",
                str(ROOT / "scripts" / "prod_deploy.py"),
                "--stop-only",
            ],
            check=False,
        )
    else:
        run([sys.executable, str(ROOT / "scripts" / "prod_deploy.py")], check=False)
        run(
            [sys.executable, str(ROOT / "scripts" / "prod_deploy.py"), "--stop-only"],
            check=False,
        )

    # Ensure ownership for systemd user
    if as_user:
        run(syscmd("chown", "-R", f"{user}:{user}", str(ROOT)), check=False)

    action_restart()
    print("\nDeploy done.")


def action_logs() -> None:
    print(
        """
=== Logs ===
  1) API (rms-api) follow
  2) Web (rms-web) follow
  3) Nginx follow
  4) All three (combined)
  5) Nginx error file (tail)
  0) Back
"""
    )
    choice = input("Select: ").strip()
    if choice == "1":
        run(syscmd("journalctl", "-u", "rms-api", "-f", "-n", "100"))
    elif choice == "2":
        run(syscmd("journalctl", "-u", "rms-web", "-f", "-n", "100"))
    elif choice == "3":
        run(syscmd("journalctl", "-u", "nginx", "-f", "-n", "100"))
    elif choice == "4":
        run(syscmd("journalctl", "-u", "rms-api", "-u", "rms-web", "-u", "nginx", "-f", "-n", "80"))
    elif choice == "5":
        run(syscmd("tail", "-f", "/var/log/nginx/rms.error.log"), check=False)
    else:
        print("Back.")


def action_setup_nginx() -> None:
    next_bin = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
    has_build = next_bin.is_file() and (FRONTEND / ".next").exists()
    if has_build:
        print("\n=== Re-run Nginx edge setup (skip app build) ===")
        extra = ["--skip-build", "--yes"]
    else:
        print("\n=== Nginx edge setup (frontend not built yet — will install + build) ===")
        if not shutil.which("npm"):
            print(
                "ERROR: npm is not installed.\n"
                "  sudo apt install -y npm\n"
                "  # or Node 20+: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -\n"
                "  #             sudo apt install -y nodejs\n"
                "Then re-run this option."
            )
            return
        extra = ["--yes"]
    script = ROOT / "scripts" / "ubuntu_https_setup.py"
    if confirm("Enable self-signed HTTPS? (needed for tablet camera)"):
        extra.append("--self-signed")
    run(syscmd(sys.executable if os.geteuid() == 0 else "python3", str(script), *extra), check=False)


def confirm(msg: str, default: bool = True) -> bool:
    yn = "Y/n" if default else "y/N"
    try:
        ans = input(f"{msg} ({yn}): ").strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans in ("y", "yes")


def resolve_node_for_user(user: str) -> Path | None:
    probes = [
        ["sudo", "-u", user, "-H", "bash", "-lc", "command -v node"],
        ["bash", "-lc", "command -v node"],
    ]
    for cmd in probes:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        lines = (r.stdout or "").strip().splitlines()
        if lines:
            p = Path(lines[-1].strip())
            if p.is_file():
                return p
    for candidate in (Path("/usr/bin/node"), Path("/usr/local/bin/node")):
        if candidate.is_file():
            return candidate
    return None


def rewrite_systemd_unit(path: Path, *, user: str, node: Path | None = None) -> None:
    if not path.exists():
        print(f"  missing {path}")
        return
    text = path.read_text(encoding="utf-8")
    lines: list[str] = []
    repo = str(ROOT)
    node_bin = str(node.parent) if node else ""
    next_bin = f"{repo}/frontend/node_modules/next/dist/bin/next"
    saw_path_env = False
    for line in text.splitlines():
        if line.startswith("User="):
            lines.append(f"User={user}")
        elif line.startswith("Group="):
            lines.append(f"Group={user}")
        elif line.startswith("Environment=PATH=") and node:
            lines.append(
                f"Environment=PATH={node_bin}:{repo}/frontend/node_modules/.bin:"
                "/usr/local/bin:/usr/bin:/bin"
            )
            saw_path_env = True
        elif line.startswith("ExecStart=") and path.name == "rms-web.service" and node:
            lines.append(
                f"ExecStart={node} {next_bin} start --hostname 127.0.0.1 --port 3000"
            )
        elif "npm" in line and line.startswith("ExecStart=") and node:
            lines.append(
                f"ExecStart={node} {next_bin} start --hostname 127.0.0.1 --port 3000"
            )
        else:
            lines.append(line)

    if path.name == "rms-web.service" and node and not saw_path_env:
        # Insert PATH after WorkingDirectory / Environment block
        out: list[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.startswith("Environment=BACKEND_URL="):
                out.append(
                    f"Environment=PATH={node_bin}:{repo}/frontend/node_modules/.bin:"
                    "/usr/local/bin:/usr/bin:/bin"
                )
                inserted = True
        lines = out

    content = "\n".join(lines) + "\n"
    subprocess.run(syscmd("tee", str(path)), input=content, text=True, check=False)
    print(f"  Updated {path} → User={user}" + (f", node={node}" if node else ""))


def action_fix_service_user() -> None:
    """Fix User=/Group= and Node ExecStart (nvm / missing /usr/bin/npm)."""
    print("\n=== Fix service user + Node path ===")
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "jrparreno"
    try:
        ans = input(f"Run systemd units as user [{user}]: ").strip()
    except EOFError:
        ans = ""
    if ans:
        user = ans

    node = resolve_node_for_user(user)
    if not node:
        print(
            "ERROR: node not found.\n"
            "Install Node 20+, e.g.:\n"
            "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -\n"
            "  sudo apt-get install -y nodejs\n"
            "Or ensure nvm is loaded for this user, then re-run option 11."
        )
        return
    print(f"  Found node: {node}")

    next_bin = ROOT / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.exists():
        print(
            f"ERROR: missing {next_bin}\n"
            "Build the frontend first (menu option 5 Deploy)."
        )
        return

    for unit in ("rms-api", "rms-web"):
        rewrite_systemd_unit(
            Path(f"/etc/systemd/system/{unit}.service"),
            user=user,
            node=node if unit == "rms-web" else None,
        )

    run(syscmd("systemctl", "daemon-reload"))
    run(syscmd("systemctl", "reset-failed", "rms-api", "rms-web"), check=False)
    run(syscmd("systemctl", "restart", "rms-api", "rms-web"))
    time.sleep(2)
    action_status()


def menu_text() -> str:
    return """
╔══════════════════════════════════════════╗
║     MotoShop RMS — Production menu       ║
╠══════════════════════════════════════════╣
║  1  Status (includes public IP)          ║
║  2  Start services                       ║
║  3  Stop services                        ║
║  4  Restart all (API + Web + Nginx)      ║
║  5  Deploy / apply code changes          ║
║  6  Restart API only                     ║
║  7  Restart Web only                     ║
║  8  Reload Nginx                         ║
║  9  Logs                                 ║
║ 10  Re-run Nginx setup (no domain)       ║
║ 11  Fix service user + Node path         ║
║  0  Exit                                 ║
╚══════════════════════════════════════════╝
"""


ACTIONS = {
    "1": action_status,
    "2": action_start,
    "3": action_stop,
    "4": action_restart,
    "5": action_deploy,
    "6": action_restart_api,
    "7": action_restart_web,
    "8": action_reload_nginx,
    "9": action_logs,
    "10": action_setup_nginx,
    "11": action_fix_service_user,
}


def main() -> None:
    os.chdir(ROOT)

    if not IS_LINUX:
        print("WARNING: Production menu is meant for Ubuntu/Pop!_OS with systemd.\n")

    jump = sys.argv[1] if len(sys.argv) > 1 else None

    while True:
        if jump:
            choice = jump
            jump = None
        else:
            print(menu_text())
            try:
                choice = input("Select option: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

        if choice in ("0", "q", "quit", "exit"):
            print("Bye.")
            break

        action = ACTIONS.get(choice)
        if not action:
            print("Unknown option.")
            continue

        try:
            action()
        except KeyboardInterrupt:
            print("\n(interrupted)")
        except Exception as exc:
            print(f"ERROR: {exc}")

        if len(sys.argv) > 1:
            # One-shot mode when invoked with an option number
            break

        try:
            input("\nPress Enter to continue…")
        except EOFError:
            break


if __name__ == "__main__":
    main()
