#!/usr/bin/env python3
"""
RMS launcher menu for Linux (Pop!_OS / Ubuntu).

Usage:
  python scripts/dev_menu.py
  ./local_run.sh
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

DEV_API_PORT = 8000
DEV_APP_PORT = 3000


def py_exe() -> Path:
    return BACKEND / ".venv" / "bin" / "python"


def pip_exe() -> Path:
    return BACKEND / ".venv" / "bin" / "pip"


def npm_cmd() -> str:
    """Prefer nvm Node 20+ npm when system Node is too old for Tailwind 4."""
    nvm_npm = Path.home() / ".nvm" / "versions" / "node"
    if nvm_npm.is_dir():
        versions = sorted(
            (p for p in nvm_npm.iterdir() if p.is_dir() and p.name.startswith("v")),
            key=lambda p: [int(x) for x in p.name.lstrip("v").split(".")],
            reverse=True,
        )
        for ver in versions:
            major = int(ver.name.lstrip("v").split(".")[0])
            cand = ver / "bin" / "npm"
            if major >= 20 and cand.is_file():
                return str(cand)
    path = shutil.which("npm")
    if path:
        return path
    raise SystemExit(
        "npm not found. Install Node 20+:\n"
        "  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash\n"
        "  source ~/.nvm/nvm.sh && nvm install 20"
    )


def node_cmd() -> str:
    npm = Path(npm_cmd())
    node = npm.parent / "node"
    if node.is_file():
        return str(node)
    path = shutil.which("node")
    if path:
        return path
    raise SystemExit("node not found (need Node 20+)")


def frontend_shell_prefix() -> str:
    """Ensure nvm Node is first on PATH for spawned frontend terminals."""
    nvm = Path.home() / ".nvm" / "nvm.sh"
    if nvm.is_file():
        return (
            f'export NVM_DIR="{Path.home() / ".nvm"}"; '
            f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; '
            "nvm use 20 >/dev/null 2>&1 || true; "
        )
    return ""


def docker_accessible() -> bool:
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


def run_docker(args: list[str], *, check: bool = True) -> int:
    """Run docker/compose, using `sg docker` when the current shell lacks the group."""
    if docker_accessible():
        return run(["docker", *args], check=check)

    if not shutil.which("sg"):
        raise SystemExit(
            "Docker permission denied.\n"
            "  sudo usermod -aG docker \"$USER\"\n"
            "Then log out/in, or run: newgrp docker"
        )

    print("Docker socket not accessible in this shell — retrying via `sg docker`…")
    cmd = ["sg", "docker", "-c", "docker " + " ".join(shlex.quote(a) for a in args)]
    print(f"\n→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        if result.returncode != 0:
            raise SystemExit(
                "Docker failed. If you were just added to the docker group, log out/in "
                "or run: newgrp docker"
            )
    return result.returncode


def wait_for_postgres(*, timeout_s: int = 60) -> None:
    print("Waiting for Postgres on localhost:5432…")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ready = subprocess.run(
            ["docker", "exec", "rms-postgres", "pg_isready", "-U", "postgres", "-d", "rms"],
            capture_output=True,
            text=True,
            check=False,
        )
        if ready.returncode != 0 and shutil.which("sg") and not docker_accessible():
            ready = subprocess.run(
                ["sg", "docker", "-c", "docker exec rms-postgres pg_isready -U postgres -d rms"],
                capture_output=True,
                text=True,
                check=False,
            )
        if ready.returncode == 0:
            print("Postgres is ready.")
            return
        try:
            with socket.create_connection(("127.0.0.1", 5432), timeout=1):
                time.sleep(1)
                print("Postgres is ready.")
                return
        except OSError:
            time.sleep(1)
    raise SystemExit(
        "Postgres did not become ready in time.\n"
        "  Try menu option 2, or: sg docker -c 'docker compose up -d'"
    )


def ensure_postgres() -> None:
    """Start Compose Postgres if needed and wait until it accepts connections."""
    run_docker(["compose", "up", "-d"])
    wait_for_postgres()



def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    print(f"\n→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), check=False)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
    return result.returncode


def pids_on_port(port: int) -> list[int]:
    pids: list[int] = []
    if shutil.which("lsof"):
        probe = subprocess.run(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        for token in re.split(r"[\s,]+", (probe.stdout or "").strip()):
            if token.isdigit():
                pid = int(token)
                if pid not in pids:
                    pids.append(pid)
        if pids:
            return pids

    if shutil.which("fuser"):
        probe = subprocess.run(
            ["fuser", f"{port}/tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (probe.stdout or "") + (probe.stderr or "")
        for token in re.split(r"[\s,]+", text.strip()):
            if token.isdigit():
                pid = int(token)
                if pid not in pids:
                    pids.append(pid)
        if pids:
            return pids

    if shutil.which("ss"):
        probe = subprocess.run(
            ["ss", "-ltnp"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (probe.stdout or "").splitlines():
            # Local address column contains *:3000 / 0.0.0.0:3000 / [::]:3000
            if re.search(rf"[:\]]{port}\b", line) is None:
                continue
            for match in re.finditer(r"pid=(\d+)", line):
                pid = int(match.group(1))
                if pid not in pids:
                    pids.append(pid)
    return pids


def stop_pid(pid: int) -> None:
    if pid <= 1:
        return
    try:
        # Kill process group when possible (next/uvicorn often spawn children)
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            os.kill(pid, signal.SIGTERM)
        time.sleep(0.8)
        try:
            os.kill(pid, 0)
        except OSError:
            return
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def unit_active(name: str) -> bool:
    r = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip() == "active"


def stop_conflicting_systemd(
    *, units: tuple[str, ...] = ("rms-api", "rms-web")
) -> None:
    """Stop production units (Restart=always) so they cannot reclaim :3000/:8000."""
    # Always attempt both — "activating" / race can miss a single is-active check.
    print(f"  Stopping systemd {', '.join(units)} (if installed)…")
    cmd = ["systemctl", "stop", *units]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    run(cmd, check=False)
    # Clear failed/start-limit so a flaky unit does not immediately bounce back
    reset = ["systemctl", "reset-failed", *units]
    if os.geteuid() != 0:
        reset = ["sudo", *reset]
    subprocess.run(reset, capture_output=True, check=False)


def wait_ports_free(ports: tuple[int, ...], *, timeout_s: float = 8.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        busy = [p for p in ports if pids_on_port(p)]
        if not busy:
            return True
        # If systemd came back, stop again
        if any(unit_active(u) for u in ("rms-api", "rms-web")):
            stop_conflicting_systemd()
        for port in busy:
            for pid in pids_on_port(port):
                print(f"  Waiting — stopping PID {pid} on :{port}")
                stop_pid(pid)
        time.sleep(0.5)
    return not any(pids_on_port(p) for p in ports)


def free_dev_ports(*, ports: tuple[int, ...] = (DEV_APP_PORT, DEV_API_PORT)) -> None:
    """Always clear previous API/UI listeners before starting local sessions."""
    print("\n=== Closing existing API/UI sessions ===")
    stop_conflicting_systemd()

    for port in ports:
        for pid in pids_on_port(port):
            print(f"  Stopping PID {pid} (port {port})")
            stop_pid(pid)

    if wait_ports_free(ports):
        print(f"  Freed: {', '.join(str(p) for p in ports)}")
    else:
        still = [p for p in ports if pids_on_port(p)]
        holders = []
        for port in still:
            for pid in pids_on_port(port):
                holders.append(f":{port}→PID {pid}")
        print(
            f"  WARNING: still in use: {', '.join(holders) or still}\n"
            "  Run this, then choose 5 again:\n"
            "    sudo systemctl stop rms-api rms-web\n"
            "    sudo systemctl disable --now rms-api rms-web   # optional while developing"
        )
        raise SystemExit("Ports still busy — refusing to start duplicate API/UI.")


def open_new_terminal(title: str, command: str, cwd: Path) -> None:
    """Open a dedicated terminal window/tab for long-running services."""
    shells = [
        ["gnome-terminal", "--title", title, "--working-directory", str(cwd), "--", "bash", "-lc", f"{command}; exec bash"],
        ["x-terminal-emulator", "-T", title, "-e", f"bash -lc 'cd \"{cwd}\" && {command}; exec bash'"],
        ["konsole", "--workdir", str(cwd), "-e", "bash", "-lc", f"{command}; exec bash"],
        ["xfce4-terminal", f"--working-directory={cwd}", "-T", title, "-e", f"bash -lc '{command}; exec bash'"],
    ]
    for args in shells:
        if shutil.which(args[0]):
            subprocess.Popen(args)
            return

    # Headless / SSH fallback: background process
    log = ROOT / "logs"
    log.mkdir(exist_ok=True)
    safe = title.lower().replace(" ", "_")
    out = open(log / f"{safe}.log", "a", encoding="utf-8")
    subprocess.Popen(
        ["bash", "-lc", command],
        cwd=str(cwd),
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"  (no GUI terminal found — running in background, log: logs/{safe}.log)")


def lan_ipv4_addresses() -> list[str]:
    """Best-effort Wi‑Fi / Ethernet LAN IPv4 addresses (skip Docker virt)."""
    found: list[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127."):
            return
        # Prefer real LAN; Docker often uses 172.16–31.x
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
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass

    return found


def print_lan_urls(*, app_port: int = 3000, api_port: int = 8000) -> None:
    ips = lan_ipv4_addresses()
    print("\nLocal network (same Wi‑Fi / LAN) — use HTTPS (not http):")
    if not ips:
        print("  (could not detect LAN IP — check `ip a`)")
        print(f"  App:  https://<your-pc-ip>:{app_port}")
        print(f"  API:  http://<your-pc-ip>:{api_port}/docs")
    else:
        for ip in ips:
            print(f"  App:  https://{ip}:{app_port}")
            print(f"  API:  http://{ip}:{api_port}/docs")
    print("  First visit: accept the certificate warning on the phone/tablet.")
    print("  Port 3000 is HTTPS-only — http://…:3000 will fail with an empty reply.")
    if ufw_enabled():
        print("\n  ⚠ UFW firewall is ON — phones often cannot connect until ports are open.")
        print("    Run menu option A, or:")
        print(f"    sudo ufw allow {app_port}/tcp && sudo ufw allow {api_port}/tcp && sudo ufw reload")


def ufw_enabled() -> bool:
    conf = Path("/etc/ufw/ufw.conf")
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in text.splitlines():
        if line.strip().upper().startswith("ENABLED="):
            return line.split("=", 1)[1].strip().lower() in {"yes", "true", "1"}
    return False


def action_open_lan_firewall() -> None:
    """Open 3000/8000 in UFW so phones/tablets on Wi‑Fi can reach the app."""
    if not shutil.which("ufw"):
        print("ufw not installed — nothing to do.")
        return
    if not ufw_enabled():
        print("UFW is not enabled. If phones still fail, check Wi‑Fi client/AP isolation.")
        return
    print(
        "This opens TCP 3000 (app) and 8000 (API) for LAN devices.\n"
        "You will be asked for your sudo password.\n"
    )
    cmds = [
        ["sudo", "ufw", "allow", f"{DEV_APP_PORT}/tcp", "comment", "RMS frontend"],
        ["sudo", "ufw", "allow", f"{DEV_API_PORT}/tcp", "comment", "RMS API"],
        ["sudo", "ufw", "reload"],
        ["sudo", "ufw", "status", "numbered"],
    ]
    for cmd in cmds:
        print(f"→ {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print("Failed — run the commands manually in a terminal.")
            return
    print("\nDone. On the phone open:")
    print_lan_urls()


def ensure_lan_https_cert() -> None:
    """Keep Next experimental-https cert SANs in sync with current LAN IPs.

    Without the LAN IP in the certificate, phones/tablets often refuse
    https://192.168.x.x:3000 even though the server is listening.
    """
    cert_dir = FRONTEND / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert = cert_dir / "localhost.pem"
    key = cert_dir / "localhost-key.pem"
    ca_root = Path.home() / ".local" / "share" / "mkcert"
    ca_cert = ca_root / "rootCA.pem"
    ca_key = ca_root / "rootCA-key.pem"

    ips = ["127.0.0.1", "0.0.0.0", "::1", *lan_ipv4_addresses()]
    # Dedupe while preserving order
    seen: set[str] = set()
    unique_ips: list[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)

    need_regen = True
    if cert.is_file() and key.is_file():
        try:
            text = subprocess.check_output(
                ["openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            # Require every current LAN IPv4 (skip wildcards / loopback already covered)
            missing = [
                ip
                for ip in lan_ipv4_addresses()
                if f"IP Address:{ip}" not in text and f"IP:{ip}" not in text
            ]
            need_regen = bool(missing)
        except (OSError, subprocess.CalledProcessError):
            need_regen = True

    if not need_regen:
        return

    mkcert = shutil.which("mkcert")
    if mkcert:
        cmd = [
            mkcert,
            "-cert-file",
            str(cert),
            "-key-file",
            str(key),
            "localhost",
            *unique_ips,
        ]
        print("Refreshing HTTPS cert for LAN access (mkcert)…")
        run(cmd, cwd=FRONTEND, check=False)
        return

    if not (ca_cert.is_file() and ca_key.is_file()):
        print(
            "Warning: cannot refresh HTTPS cert (mkcert CA missing). "
            "LAN IP access may show browser certificate errors."
        )
        return

    print("Refreshing HTTPS cert for LAN access (openssl + mkcert CA)…")
    san_lines = ["DNS.1 = localhost"]
    for i, ip in enumerate(unique_ips, start=1):
        san_lines.append(f"IP.{i} = {ip}")
    cnf = (
        "[req]\n"
        "default_bits = 2048\n"
        "prompt = no\n"
        "default_md = sha256\n"
        "distinguished_name = dn\n"
        "req_extensions = req_ext\n"
        "\n"
        "[dn]\n"
        "O = mkcert development certificate\n"
        "CN = localhost\n"
        "\n"
        "[req_ext]\n"
        "subjectAltName = @alt_names\n"
        "\n"
        "[alt_names]\n"
        + "\n".join(san_lines)
        + "\n"
    )
    cnf_path = cert_dir / ".san.cnf"
    csr_path = cert_dir / ".localhost.csr"
    try:
        cnf_path.write_text(cnf, encoding="utf-8")
        subprocess.check_call(
            ["openssl", "genrsa", "-out", str(key), "2048"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(key),
                "-out",
                str(csr_path),
                "-config",
                str(cnf_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(csr_path),
                "-CA",
                str(ca_cert),
                "-CAkey",
                str(ca_key),
                "-CAcreateserial",
                "-out",
                str(cert),
                "-days",
                "825",
                "-extensions",
                "req_ext",
                "-extfile",
                str(cnf_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.chmod(key, 0o600)
        os.chmod(cert, 0o644)
        print(f"  Cert SANs include: {', '.join(unique_ips)}")
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"Warning: HTTPS cert refresh failed: {err}")
    finally:
        for p in (cnf_path, csr_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def ensure_backend_venv() -> None:
    """Create .venv if needed, bootstrap pip, and install requirements.txt."""
    python = py_exe()
    if not python.exists():
        print("Creating backend virtualenv…")
        try:
            venv.create(BACKEND / ".venv", with_pip=True)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                f"Failed to create virtualenv: {exc}\n"
                "Install: sudo apt install -y python3-venv python3-pip"
            ) from exc
        python = py_exe()

    if not python.exists():
        raise SystemExit(f"Virtualenv python missing at {python}")

    # Prefer `python -m pip` — the standalone pip script is often missing on Linux.
    ensure = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        check=False,
    )
    if ensure.returncode != 0:
        print("Bootstrapping pip into virtualenv…")
        code = run([str(python), "-m", "ensurepip", "--upgrade"], cwd=BACKEND, check=False)
        if code != 0:
            raise SystemExit(
                "Could not bootstrap pip in backend/.venv.\n"
                "Install: sudo apt install -y python3-venv python3-pip\n"
                "Then: rm -rf backend/.venv && ./local_run.sh"
            )
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND)

    # Install/repair deps when missing (empty venvs are common on fresh Linux installs).
    probe = subprocess.run(
        [str(python), "-c", "import sqlalchemy, fastapi, alembic"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        print("Installing backend requirements…")
        if run([str(python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=BACKEND) != 0:
            raise SystemExit("Failed to install backend/requirements.txt")



def ensure_frontend_deps() -> None:
    modules = FRONTEND / "node_modules"
    oxide = modules / "@tailwindcss" / "oxide-linux-x64-gnu"
    needs_install = not modules.exists() or (
        sys.platform.startswith("linux") and not oxide.exists()
    )
    if not needs_install:
        return
    if modules.exists() and not oxide.exists():
        print("Frontend deps look incomplete (missing Tailwind Linux native binding)…")
        print("Reinstalling node_modules…")
        run(["rm", "-rf", "node_modules", ".next"], cwd=FRONTEND, check=False)
    print("Installing frontend npm packages…")
    if run([npm_cmd(), "ci"], cwd=FRONTEND, check=False) != 0:
        run([npm_cmd(), "install"], cwd=FRONTEND)



def action_docker_up() -> None:
    ensure_postgres()


def action_docker_down() -> None:
    run_docker(["compose", "down"])


def action_migrate_seed() -> None:
    ensure_postgres()
    ensure_backend_venv()
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    run([str(py_exe()), "-m", "app.scripts.seed"], cwd=BACKEND)
    run([str(py_exe()), "-m", "app.scripts.seed_admin"], cwd=BACKEND)


def action_seed_admin() -> None:
    ensure_postgres()
    ensure_backend_venv()
    run([str(py_exe()), "-m", "app.scripts.seed_admin"], cwd=BACKEND)



def action_backend() -> None:
    ensure_backend_venv()
    free_dev_ports(ports=(DEV_API_PORT,))
    cmd = (
        f".venv/bin/python -m uvicorn app.main:app --reload "
        f"--host 0.0.0.0 --port {DEV_API_PORT}"
    )
    open_new_terminal("RMS Backend", cmd, BACKEND)
    print(f"Backend → http://127.0.0.1:{DEV_API_PORT}  (docs: /docs)")
    print("  Listening on 0.0.0.0 — reachable on your local network.")
    print_lan_urls()


def action_frontend() -> None:
    ensure_frontend_deps()
    ensure_lan_https_cert()
    free_dev_ports(ports=(DEV_APP_PORT,))
    # package.json "dev" already binds 0.0.0.0 for LAN tablets/phones
    prefix = frontend_shell_prefix()
    cmd = f"{prefix}npm run dev"
    open_new_terminal("RMS Frontend", cmd, FRONTEND)
    print(f"Frontend → https://127.0.0.1:{DEV_APP_PORT}  (self-signed HTTPS)")
    print("  Listening on 0.0.0.0 — open the LAN URL below on phones/tablets.")
    print_lan_urls()


def action_setup() -> None:
    action_docker_up()
    ensure_backend_venv()
    action_migrate_seed()
    ensure_frontend_deps()
    print("\nSetup complete. Use menu option 5 to start API + UI (LAN shared).")


def action_start_all() -> None:
    # Always replace leftover local or production listeners on 3000/8000
    free_dev_ports(ports=(DEV_APP_PORT, DEV_API_PORT))
    action_docker_up()
    ensure_backend_venv()
    # migrate quietly if needed
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=False)
    # Ports already freed above — skip per-service free in nested calls
    cmd = (
        f".venv/bin/python -m uvicorn app.main:app --reload "
        f"--host 0.0.0.0 --port {DEV_API_PORT}"
    )
    open_new_terminal("RMS Backend", cmd, BACKEND)
    print(f"Backend → http://127.0.0.1:{DEV_API_PORT}  (docs: /docs)")
    print("  Listening on 0.0.0.0 — reachable on your local network.")
    print_lan_urls()
    time.sleep(1)
    ensure_frontend_deps()
    ensure_lan_https_cert()
    prefix = frontend_shell_prefix()
    open_new_terminal("RMS Frontend", f"{prefix}npm run dev", FRONTEND)
    print(f"Frontend → https://127.0.0.1:{DEV_APP_PORT}  (self-signed HTTPS)")
    print("  Listening on 0.0.0.0 — open the LAN URL below on phones/tablets.")
    print(
        "\nAll services launching (shared on local network).\n"
        f"  This PC:  https://127.0.0.1:{DEV_APP_PORT}\n"
        f"  API docs: http://127.0.0.1:{DEV_API_PORT}/docs\n"
        "  Login: admin / admin123  or  cashier / cashier123"
    )
    print_lan_urls()


def action_status() -> None:
    print("OS: Linux")
    print(f"Root: {ROOT}")
    print(f"Docker binary: {'yes' if shutil.which('docker') else 'NO'}")
    print(f"Docker access: {'yes' if docker_accessible() else 'NO (need newgrp docker / re-login)'}")
    print(f"Backend venv: {'yes' if py_exe().exists() else 'no'}")
    print(f"Frontend node_modules: {'yes' if (FRONTEND / 'node_modules').exists() else 'no'}")
    try:
        node = node_cmd()
        ver = subprocess.check_output([node, "-v"], text=True).strip()
        print(f"Node: {node} ({ver})")
    except Exception:  # noqa: BLE001
        print("Node: NO")
    print(f"npm: {npm_cmd()}")
    print(f"UFW firewall: {'ON (phones need option A)' if ufw_enabled() else 'off / unknown'}")
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            print("Postgres :5432: listening")
    except OSError:
        print("Postgres :5432: not listening")
    print_lan_urls()


MENU = """
╔══════════════════════════════════════════╗
║     MotoShop RMS — Dev Launcher          ║
╠══════════════════════════════════════════╣
║  1) First-time setup (Docker+migrate+    ║
║     seed+npm install)                    ║
║  2) Start Postgres (docker compose)      ║
║  3) Stop Postgres                        ║
║  4) Migrate + seed database              ║
║  5) Start ALL (Postgres + API + UI)      ║
║     — frees :3000/:8000 first, LAN share ║
║  6) Start backend only (port 8000)       ║
║  7) Start frontend only (port 3000)      ║
║  8) Status check                         ║
║  9) Seed / reset ADMIN only              ║
║  A) Open LAN firewall ports (ufw sudo)   ║
║  0) Exit                                 ║
╚══════════════════════════════════════════╝
"""


def main() -> None:
    os.chdir(ROOT)
    actions = {
        "1": action_setup,
        "2": action_docker_up,
        "3": action_docker_down,
        "4": action_migrate_seed,
        "5": action_start_all,
        "6": action_backend,
        "7": action_frontend,
        "8": action_status,
        "9": action_seed_admin,
        "a": action_open_lan_firewall,
        "A": action_open_lan_firewall,
    }

    # Non-interactive: python scripts/dev_menu.py 5
    if len(sys.argv) > 1:
        choice = sys.argv[1].strip()
        if choice in actions:
            actions[choice]()
            return
        if choice in {"0", "exit", "quit"}:
            return
        print(f"Unknown option: {choice}")
        sys.exit(1)

    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        if choice in {"0", "q", "quit", "exit"}:
            print("Bye.")
            return
        action = actions.get(choice)
        if not action:
            print("Invalid option.")
            continue
        try:
            action()
        except SystemExit as exc:
            print(exc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")
        input("\nPress Enter to return to menu…")


if __name__ == "__main__":
    main()
