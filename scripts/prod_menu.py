#!/usr/bin/env python3
"""
Production ops menu for MotoShop RMS (Ubuntu systemd + Nginx).

After first-time setup (`sudo ./scripts/run_ubuntu_https.sh`), use this to:
  start / stop / restart services, deploy code changes, Cloudflare Tunnel, check status, view logs.

Usage:
  ./scripts/run_prod_menu.sh
  cd scripts && bash run_prod_menu.sh
  python3 scripts/prod_menu.py
  python3 scripts/prod_menu.py 5    # jump to option 5
  python3 scripts/prod_menu.py 13   # database backup submenu
"""

from __future__ import annotations

import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
IS_LINUX = sys.platform.startswith("linux")

LOGS = ROOT / "logs"
TUNNEL_PID = LOGS / "prod_tunnel.pid"
TUNNEL_LOG = LOGS / "prod_tunnel.log"
TUNNEL_URL = LOGS / "prod_tunnel_url.txt"
CLOUDFLARE_DIR = ROOT / "cloudflare"

UNITS = ("rms-api", "rms-web", "nginx")


def run(cmd: list[str], *, check: bool = False, capture: bool = False, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print(f"\n→ {' '.join(cmd)}")
    merged = os.environ.copy()
    # Prefer user-local cloudflared (~/.local/bin) when present
    local_bin = str(Path.home() / ".local" / "bin")
    path = merged.get("PATH", "")
    if local_bin not in path.split(":"):
        merged["PATH"] = f"{local_bin}:{path}" if path else local_bin
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        check=check,
        text=True,
        capture_output=capture,
        env=merged,
    )


def have_sudo() -> bool:
    return os.geteuid() == 0 or shutil.which("sudo") is not None


def syscmd(*args: str) -> list[str]:
    """Prefix with sudo when not root."""
    if os.geteuid() == 0:
        return list(args)
    return ["sudo", *args]


def current_login_user() -> str:
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "jrparreno"


def user_can_access_path(username: str, path: Path) -> bool:
    """True if `username` can traverse the repo and read `path`."""
    if not path.exists():
        return False
    if os.geteuid() == 0:
        return True
    if not shutil.which("sudo"):
        return username == os.environ.get("USER")
    cmd = (
        f"test -x {shlex.quote(str(ROOT))} && "
        f"test -r {shlex.quote(str(path))}"
    )
    probe = subprocess.run(
        ["sudo", "-u", username, "bash", "-lc", cmd],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def resolve_deploy_user(preferred: str = "rms") -> str | None:
    """Use `rms` for deploy only when that user can read the repo; else current user."""
    import pwd

    try:
        pwd.getpwnam(preferred)
    except KeyError:
        print(f"  User '{preferred}' not found — deploy runs as {current_login_user()}")
        return None

    deploy_script = ROOT / "scripts" / "prod_deploy.py"
    if user_can_access_path(preferred, deploy_script):
        return preferred

    print(
        f"  Permission: user '{preferred}' cannot read {ROOT}\n"
        f"  Deploy will run as {current_login_user()} instead.\n"
        f"  After deploy, use menu option 11 to set systemd User= to your login,\n"
        f"  or: sudo chown -R {preferred}:{preferred} {ROOT}"
    )
    return None


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
    tunnel = read_tunnel_url()
    if tunnel_running() and tunnel:
        print(f"  Tunnel:    {tunnel}")
        print("             ↑ Cloudflare HTTPS (works without port forward / on CGNAT)")
    elif tunnel_running():
        print("  Tunnel:    running (URL in logs/prod_tunnel.log)")
    else:
        print("  Tunnel:    off  (menu option 12)")
    print("  API docs:  /docs  (via Nginx)")
    print("  Login:     admin / admin123")


def cloudflared_path() -> Path | None:
    which = shutil.which("cloudflared")
    candidates = []
    if which:
        candidates.append(Path(which))
    candidates.extend(
        [
            Path.home() / ".local" / "bin" / "cloudflared",
            Path("/usr/local/bin/cloudflared"),
            Path("/usr/bin/cloudflared"),
        ]
    )
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_tunnel_pid() -> int | None:
    if not TUNNEL_PID.exists():
        return None
    try:
        pid = int(TUNNEL_PID.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def tunnel_running() -> bool:
    return read_tunnel_pid() is not None


def read_tunnel_url() -> str | None:
    if TUNNEL_URL.exists():
        try:
            url = TUNNEL_URL.read_text(encoding="utf-8").strip().splitlines()[0].strip()
            if url.startswith("https://"):
                return url
        except OSError:
            pass
    if TUNNEL_LOG.exists():
        import re

        try:
            text = TUNNEL_LOG.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        matches = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", text, re.I)
        if matches:
            return matches[-1]
    return None


def ensure_apps_for_tunnel() -> bool:
    """Start rms-api/rms-web if needed before opening a tunnel."""
    missing = [n for n in ("rms-api", "rms-web") if unit_exists(n) and not unit_active(n)]
    if not missing:
        ok, _ = check_http("http://127.0.0.1:3000")
        if ok:
            return True
        print("  Web not responding on :3000 — start services first (option 2).")
        return False
    print(f"  Starting {' + '.join(missing)} (required for tunnel)…")
    for name in missing:
        run(syscmd("systemctl", "reset-failed", name), check=False)
        run(syscmd("systemctl", "start", name))
    time.sleep(2)
    ok, detail = check_http("http://127.0.0.1:3000")
    if not ok:
        print(f"  Web still down ({detail}). Fix with option 1 / 2, then retry.")
        return False
    return True


def action_tunnel_start(mode: str) -> None:
    label = "quick (trycloudflare.com)" if mode == "quick" else "named (config.yml)"
    print(f"\n=== Cloudflare Tunnel — start {label} ===")
    if not cloudflared_path():
        print(
            "cloudflared not found.\n"
            "Install once:\n"
            "  mkdir -p ~/.local/bin\n"
            "  curl -fsSL -o ~/.local/bin/cloudflared \\\n"
            "    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64\n"
            "  chmod +x ~/.local/bin/cloudflared\n"
            "See also: cloudflare/README.md"
        )
        return
    if mode == "named" and not (CLOUDFLARE_DIR / "config.yml").exists():
        print(
            f"Missing {CLOUDFLARE_DIR / 'config.yml'}.\n"
            f"  cp {CLOUDFLARE_DIR / 'config.example.yml'} {CLOUDFLARE_DIR / 'config.yml'}\n"
            "  Fill tunnel UUID + credentials, then:\n"
            "  cloudflared tunnel route dns rms your.hostname\n"
            "See cloudflare/README.md"
        )
        return
    if not ensure_apps_for_tunnel():
        return
    if tunnel_running():
        url = read_tunnel_url()
        print(f"  Restarting existing tunnel{f' ({url})' if url else ''}…")

    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "prod_deploy.py"),
            "--tunnel-only",
            mode,
        ],
        check=False,
    )
    url = read_tunnel_url()
    if url:
        print(f"\n  Open: {url}")
        print("  Local/LAN URLs still work while the tunnel is up.")


def action_tunnel_stop() -> None:
    print("\n=== Cloudflare Tunnel — stop ===")
    pid = read_tunnel_pid()
    if not pid:
        # Clear stale pid/url
        TUNNEL_PID.unlink(missing_ok=True)
        print("  Tunnel was not running.")
        return
    print(f"  Stopping PID {pid}…")
    try:
        os.kill(pid, 15)
    except OSError as exc:
        print(f"  kill failed: {exc}")
    time.sleep(1)
    if pid_alive(pid):
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    TUNNEL_PID.unlink(missing_ok=True)
    print("  Tunnel stopped. Local/LAN access unchanged.")


def action_tunnel_status() -> None:
    print("\n=== Cloudflare Tunnel — status ===")
    cf = cloudflared_path()
    print(f"  cloudflared: {cf or 'NOT FOUND'}")
    pid = read_tunnel_pid()
    if pid:
        print(f"  Process:     running (PID {pid})")
    else:
        print("  Process:     stopped")
    url = read_tunnel_url()
    print(f"  Public URL:  {url or '(none yet)'}")
    named = CLOUDFLARE_DIR / "config.yml"
    print(f"  Named cfg:   {'yes' if named.exists() else 'no'} ({named})")
    if TUNNEL_LOG.exists():
        print(f"  Log:         {TUNNEL_LOG}")


def action_cloudflare_tunnel() -> None:
    print(
        """
=== Cloudflare Tunnel ===
  Exposes the app on HTTPS without router port-forward (good for Converge/CGNAT).
  Local + LAN URLs keep working.

  1) Start quick tunnel (temporary trycloudflare.com URL)
  2) Start named tunnel (cloudflare/config.yml + your domain)
  3) Stop tunnel
  4) Status / show URL
  0) Back
"""
    )
    try:
        choice = input("Select: ").strip()
    except EOFError:
        return
    if choice == "1":
        action_tunnel_start("quick")
    elif choice == "2":
        action_tunnel_start("named")
    elif choice == "3":
        action_tunnel_stop()
    elif choice == "4":
        action_tunnel_status()
    else:
        print("Back.")


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

    if tunnel_running():
        print(f"  {'tunnel':10}  active")
    else:
        print(f"  {'tunnel':10}  inactive")

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
    if tunnel_running() and confirm("Also stop Cloudflare Tunnel?", default=True):
        action_tunnel_stop()
    # Stop any leftover prod_deploy detached processes (apps only if still up)
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
    """Pull optional, migrate, seed catalogs, rebuild frontend, restart services."""
    print("\n=== Deploy / apply code changes ===")
    if not confirm("git pull from origin?"):
        print("  Skipping git pull")
    else:
        run(["git", "pull", "--ff-only"], check=False)

    deploy_user = resolve_deploy_user("rms")
    deploy_py = str(ROOT / "scripts" / "prod_deploy.py")

    print("\nBuilding / migrating…")
    if deploy_user:
        run(
            ["sudo", "-u", deploy_user, "python3", deploy_py],
            check=False,
        )
        run(
            ["sudo", "-u", deploy_user, "python3", deploy_py, "--stop-only"],
            check=False,
        )
    else:
        run([sys.executable, deploy_py], check=False)
        run([sys.executable, deploy_py, "--stop-only"], check=False)

    # Only chown when services actually run as rms and we built as rms
    if deploy_user == "rms":
        run(syscmd("chown", "-R", f"{deploy_user}:{deploy_user}", str(ROOT)), check=False)

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
  6) Cloudflare Tunnel log
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
    elif choice == "6":
        if TUNNEL_LOG.exists():
            run(["tail", "-f", "-n", "80", str(TUNNEL_LOG)], check=False)
        else:
            print(f"  No tunnel log yet ({TUNNEL_LOG})")
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


def action_db_backup() -> None:
    """Nightly dump / restore helpers for the single local Postgres."""
    script = ROOT / "scripts" / "db_backup.py"
    if not script.is_file():
        raise SystemExit(f"Missing {script}")

    print(
        """
=== Database backup (local Postgres) ===
  Recommended: one primary DB + nightly dumps + optional offsite copy.
  1) Status
  2) Backup now
  3) List dumps
  4) Restore latest (destructive)
  5) Install nightly cron (02:00)
  6) Uninstall nightly cron
  0) Back
"""
    )
    try:
        choice = input("Select: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    mapping = {
        "1": ["status"],
        "2": ["backup"],
        "3": ["list"],
        "4": ["restore", "latest"],
        "5": ["install-cron"],
        "6": ["uninstall-cron"],
    }
    if choice in ("0", "q", "quit", "back"):
        return
    args = mapping.get(choice)
    if not args:
        print("Unknown option.")
        return

    if choice == "5":
        offsite = input(
            "Offsite copy directory (Enter to skip, e.g. /mnt/usb/rms-backups): "
        ).strip()
        cmd = [sys.executable, str(script), *args]
        if offsite:
            cmd.extend(["--offsite", offsite])
        run(cmd, check=False)
        return

    run([sys.executable, str(script), *args], check=False)


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
║ 12  Cloudflare Tunnel (public HTTPS)     ║
║ 13  Database backup / restore            ║
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
    "12": action_cloudflare_tunnel,
    "13": action_db_backup,
}


def main() -> None:
    os.chdir(ROOT)

    if not IS_LINUX:
        print("WARNING: Production menu is meant for Ubuntu/Pop!_OS with systemd.\n")
    elif os.geteuid() != 0 and not shutil.which("sudo"):
        print(
            "WARNING: sudo not found — start/stop/deploy may fail with permission errors.\n"
        )

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
