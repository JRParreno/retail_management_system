#!/usr/bin/env python3
"""
RMS launcher menu for Windows + Linux (Pop!_OS / Ubuntu).

Usage:
  python scripts/dev_menu.py
  ./scripts/local_run.sh          # Linux/macOS
  .\\scripts\\local_run.ps1         # Windows PowerShell
  .\\scripts\\local_run.bat         # Windows CMD
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(ROOT / "scripts"))

from platform_util import (  # noqa: E402
    IS_LINUX,
    IS_WIN,
    firewall_lan_hint,
    generate_self_signed_pem,
    mkcert_ca_paths,
    npm_install_hint,
    open_lan_firewall,
    open_new_terminal as _open_new_terminal,
    pids_on_port,
    remove_tree,
    stop_pid,
    tailwind_oxide_ok,
    venv_install_hint,
    venv_python,
)

DEV_API_PORT = 8000
DEV_APP_PORT = 3000


def py_exe() -> Path:
    return venv_python(BACKEND / ".venv")


def npm_cmd() -> str:
    """Prefer nvm Node 20+ npm when system Node is too old for Tailwind 4."""
    if not IS_WIN:
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
    raise SystemExit(f"npm not found. {npm_install_hint()}")


def node_cmd() -> str:
    npm = Path(npm_cmd())
    node = npm.parent / ("node.exe" if IS_WIN else "node")
    if node.is_file():
        return str(node)
    path = shutil.which("node")
    if path:
        return path
    raise SystemExit("node not found (need Node 20+)")


def frontend_shell_prefix() -> str:
    """Ensure nvm Node is first on PATH for spawned frontend terminals (Linux)."""
    if IS_WIN:
        return ""
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

    if IS_WIN or not shutil.which("sg"):
        raise SystemExit(
            "Docker permission denied / daemon not reachable.\n"
            + (
                "  Start Docker Desktop and wait until it is running, then retry."
                if IS_WIN
                else '  sudo usermod -aG docker "$USER"\n'
                "Then log out/in, or run: newgrp docker"
            )
        )

    print("Docker socket not accessible in this shell — retrying via `sg docker`…")
    cmd = ["sg", "docker", "-c", "docker " + " ".join(shlex.quote(a) for a in args)]
    print(f"\n→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
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
        if ready.returncode != 0 and shutil.which("sg") and not docker_accessible() and not IS_WIN:
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
        "  Try menu option 2, or: docker compose up -d"
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


def unit_active(name: str) -> bool:
    if IS_WIN or not shutil.which("systemctl"):
        return False
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
    if IS_WIN or not shutil.which("systemctl"):
        return
    print(f"  Stopping systemd {', '.join(units)} (if installed)…")
    cmd = ["systemctl", "stop", *units]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    run(cmd, check=False)
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
        if IS_WIN:
            hint = (
                "  Close any leftover CMD/PowerShell windows for Backend/Frontend,\n"
                "  or: taskkill /F /PID <pid>"
            )
        else:
            hint = (
                "  Run this, then choose 5 again:\n"
                "    sudo systemctl stop rms-api rms-web\n"
                "    sudo systemctl disable --now rms-api rms-web   # optional while developing"
            )
        print(
            f"  WARNING: still in use: {', '.join(holders) or still}\n{hint}"
        )
        raise SystemExit("Ports still busy — refusing to start duplicate API/UI.")


def open_new_terminal(title: str, command: str, cwd: Path) -> None:
    _open_new_terminal(title, command, cwd, logs_dir=ROOT / "logs")


def lan_ipv4_addresses() -> list[str]:
    """Best-effort Wi‑Fi / Ethernet LAN IPv4 addresses (skip Docker virt)."""
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
        print("  (could not detect LAN IP — check ipconfig / ip a)")
        print(f"  App:  https://<your-pc-ip>:{app_port}")
        print(f"  API:  http://<your-pc-ip>:{api_port}/docs")
    else:
        for ip in ips:
            print(f"  App:  https://{ip}:{app_port}")
            print(f"  API:  http://{ip}:{api_port}/docs")
    print("  First visit: accept the certificate warning on the phone/tablet.")
    print("  Port 3000 is HTTPS-only — http://…:3000 will fail with an empty reply.")
    hint = firewall_lan_hint(app_port, api_port)
    if hint:
        print(hint)


def action_open_lan_firewall() -> None:
    """Open 3000/8000 so phones/tablets on Wi‑Fi can reach the app."""
    open_lan_firewall(DEV_APP_PORT, DEV_API_PORT)
    print_lan_urls()


def ensure_lan_https_cert() -> None:
    """Keep Next experimental-https cert SANs in sync with current LAN IPs."""
    cert_dir = FRONTEND / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert = cert_dir / "localhost.pem"
    key = cert_dir / "localhost-key.pem"
    ca_cert, ca_key = mkcert_ca_paths()

    ips = ["127.0.0.1", "0.0.0.0", "::1", *lan_ipv4_addresses()]
    seen: set[str] = set()
    unique_ips: list[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)

    need_regen = True
    if cert.is_file() and key.is_file():
        lan = lan_ipv4_addresses()
        marker = cert_dir / ".lan_ips"
        current = ",".join(lan)
        try:
            if shutil.which("openssl"):
                text = subprocess.check_output(
                    ["openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                missing = [
                    ip
                    for ip in lan
                    if f"IP Address:{ip}" not in text and f"IP:{ip}" not in text
                ]
                need_regen = bool(missing)
            else:
                need_regen = not marker.exists() or marker.read_text(encoding="utf-8") != current
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
        (cert_dir / ".lan_ips").write_text(",".join(lan_ipv4_addresses()), encoding="utf-8")
        return

    if ca_cert.is_file() and ca_key.is_file() and shutil.which("openssl"):
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
            print(f"  Cert SANs include: {', '.join(unique_ips)}")
            (cert_dir / ".lan_ips").write_text(",".join(lan_ipv4_addresses()), encoding="utf-8")
        except (OSError, subprocess.CalledProcessError) as err:
            print(f"Warning: HTTPS cert refresh failed: {err}")
        finally:
            for p in (cnf_path, csr_path):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
        return

    # Fallback: self-signed via cryptography (works on Windows without openssl/mkcert)
    print("Refreshing HTTPS cert for LAN access (self-signed)…")
    # Prefer cryptography from backend venv if host Python lacks it
    ok = generate_self_signed_pem(cert, key, ips=unique_ips)
    if not ok and py_exe().exists():
        helper = (
            "import sys; sys.path.insert(0, r'{scripts}'); "
            "from platform_util import generate_self_signed_pem; "
            "from pathlib import Path; "
            "ok = generate_self_signed_pem(Path(r'{cert}'), Path(r'{key}'), ips={ips!r}); "
            "raise SystemExit(0 if ok else 1)"
        ).format(
            scripts=str(ROOT / "scripts"),
            cert=str(cert),
            key=str(key),
            ips=unique_ips,
        )
        r = subprocess.run([str(py_exe()), "-c", helper], check=False)
        ok = r.returncode == 0
    if ok:
        print(f"  Cert SANs include: {', '.join(unique_ips)}")
        (cert_dir / ".lan_ips").write_text(",".join(lan_ipv4_addresses()), encoding="utf-8")
        print("  Accept the browser certificate warning on first visit.")
    else:
        print(
            "Warning: could not create HTTPS cert. Install mkcert or ensure "
            "backend venv has cryptography, then retry option 5/7."
        )


def ensure_backend_venv() -> None:
    """Create .venv if needed, bootstrap pip, and install requirements.txt."""
    python = py_exe()
    if not python.exists():
        print("Creating backend virtualenv…")
        try:
            venv.create(BACKEND / ".venv", with_pip=True)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                f"Failed to create virtualenv: {exc}\n{venv_install_hint()}"
            ) from exc
        python = py_exe()

    if not python.exists():
        raise SystemExit(f"Virtualenv python missing at {python}")

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
                f"{venv_install_hint()}\n"
                "Then delete backend\\.venv (or backend/.venv) and re-run setup."
            )
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND)

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
    needs_install = not modules.exists() or not tailwind_oxide_ok(modules)
    if not needs_install:
        return
    if modules.exists() and not tailwind_oxide_ok(modules):
        print("Frontend deps look incomplete (missing Tailwind native binding)…")
        print("Reinstalling node_modules…")
        remove_tree(modules, FRONTEND / ".next")
    print("Installing frontend npm packages…")
    if run([npm_cmd(), "ci"], cwd=FRONTEND, check=False) != 0:
        run([npm_cmd(), "install"], cwd=FRONTEND)


def backend_cmd_str() -> str:
    if IS_WIN:
        return (
            f".venv\\Scripts\\python.exe -m uvicorn app.main:app --reload "
            f"--host 0.0.0.0 --port {DEV_API_PORT}"
        )
    return (
        f".venv/bin/python -m uvicorn app.main:app --reload "
        f"--host 0.0.0.0 --port {DEV_API_PORT}"
    )


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
    open_new_terminal("RMS Backend", backend_cmd_str(), BACKEND)
    print(f"Backend → http://127.0.0.1:{DEV_API_PORT}  (docs: /docs)")
    print("  Listening on 0.0.0.0 — reachable on your local network.")
    print_lan_urls()


def action_frontend() -> None:
    ensure_frontend_deps()
    ensure_lan_https_cert()
    free_dev_ports(ports=(DEV_APP_PORT,))
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
    free_dev_ports(ports=(DEV_APP_PORT, DEV_API_PORT))
    action_docker_up()
    ensure_backend_venv()
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=False)
    open_new_terminal("RMS Backend", backend_cmd_str(), BACKEND)
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
    print(f"OS: {'Windows' if IS_WIN else 'Linux' if IS_LINUX else sys.platform}")
    print(f"Root: {ROOT}")
    print(f"Docker binary: {'yes' if shutil.which('docker') else 'NO'}")
    print(f"Docker access: {'yes' if docker_accessible() else 'NO (start Docker Desktop)'}")
    print(f"Backend venv: {'yes' if py_exe().exists() else 'no'}")
    print(f"Frontend node_modules: {'yes' if (FRONTEND / 'node_modules').exists() else 'no'}")
    try:
        node = node_cmd()
        ver = subprocess.check_output([node, "-v"], text=True).strip()
        print(f"Node: {node} ({ver})")
    except Exception:  # noqa: BLE001
        print("Node: NO")
    try:
        print(f"npm: {npm_cmd()}")
    except SystemExit:
        print("npm: NO")
    hint = firewall_lan_hint(DEV_APP_PORT, DEV_API_PORT)
    print(f"Firewall tip: {'see below' if hint else 'none'}")
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
║  A) Open LAN firewall ports              ║
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
