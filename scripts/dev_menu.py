#!/usr/bin/env python3
"""
Cross-platform RMS launcher menu (Windows + Ubuntu).

Usage:
  python scripts/dev_menu.py
  ./run.sh          # Ubuntu / Git Bash
  run.cmd           # Windows
"""

from __future__ import annotations

import os
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
IS_WIN = os.name == "nt"


def py_exe() -> Path:
    if IS_WIN:
        return BACKEND / ".venv" / "Scripts" / "python.exe"
    return BACKEND / ".venv" / "bin" / "python"


def pip_exe() -> Path:
    if IS_WIN:
        return BACKEND / ".venv" / "Scripts" / "pip.exe"
    return BACKEND / ".venv" / "bin" / "pip"


def npm_cmd() -> str:
    return "npm.cmd" if IS_WIN else "npm"


def docker_cmd() -> list[str]:
    if shutil.which("docker"):
        return ["docker", "compose"]
    raise SystemExit("Docker not found. Install Docker Desktop (Windows) or Docker Engine (Ubuntu).")


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    print(f"\n→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), check=False)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
    return result.returncode


def open_new_terminal(title: str, command: str, cwd: Path) -> None:
    """Open a dedicated terminal window/tab for long-running services."""
    if IS_WIN:
        # CREATE_NEW_CONSOLE avoids `start "title"` quoting bugs on Windows.
        # `cwd` is set, so commands can use relative paths (no nested quotes).
        subprocess.Popen(
            ["cmd.exe", "/k", f"title {title} && {command}"],
            cwd=str(cwd),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return

    # Ubuntu / Linux: try common terminal emulators, else background
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
    """Best-effort Wi‑Fi / Ethernet LAN IPv4 addresses (skip Docker/WSL virt)."""
    found: list[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127."):
            return
        # Prefer real LAN; Docker Desktop / WSL often use 172.16–31.x
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
    print("\nLocal network (same Wi‑Fi / LAN) — use HTTPS for tablet camera scan:")
    if not ips:
        print("  (could not detect LAN IP — check `ipconfig` / `ip a`)")
        print(f"  App:  https://<your-pc-ip>:{app_port}")
        print(f"  API:  http://<your-pc-ip>:{api_port}/docs")
    else:
        for ip in ips:
            print(f"  App:  https://{ip}:{app_port}")
            print(f"  API:  http://{ip}:{api_port}/docs")
    print("  First visit: accept the self-signed certificate warning on the tablet.")
    print("  Allow Windows Firewall for ports 3000 and 8000 if phones cannot connect.")


def ensure_backend_venv() -> None:
    if py_exe().exists():
        return
    print("Creating backend virtualenv…")
    venv.create(BACKEND / ".venv", with_pip=True)
    run([str(py_exe()), "-m", "pip", "install", "-r", "requirements.txt"], cwd=BACKEND)


def ensure_frontend_deps() -> None:
    if (FRONTEND / "node_modules").exists():
        return
    print("Installing frontend npm packages…")
    run([npm_cmd(), "install"], cwd=FRONTEND)


def action_docker_up() -> None:
    run(docker_cmd() + ["up", "-d"])
    print("Waiting for Postgres…")
    time.sleep(3)
    print("Postgres should be up on localhost:5432")


def action_docker_down() -> None:
    run(docker_cmd() + ["down"])


def action_migrate_seed() -> None:
    ensure_backend_venv()
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    run([str(py_exe()), "-m", "app.scripts.seed"], cwd=BACKEND)
    run([str(py_exe()), "-m", "app.scripts.seed_admin"], cwd=BACKEND)


def action_seed_admin() -> None:
    ensure_backend_venv()
    run([str(py_exe()), "-m", "app.scripts.seed_admin"], cwd=BACKEND)



def action_backend() -> None:
    ensure_backend_venv()
    if IS_WIN:
        cmd = r".venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    else:
        cmd = ".venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    open_new_terminal("RMS Backend", cmd, BACKEND)
    print("Backend → http://127.0.0.1:8000  (docs: /docs)")
    print("  Listening on 0.0.0.0 — reachable on your local network.")
    print_lan_urls()


def action_frontend() -> None:
    ensure_frontend_deps()
    # package.json "dev" already binds 0.0.0.0 for LAN tablets/phones
    cmd = "npm.cmd run dev" if IS_WIN else "npm run dev"
    open_new_terminal("RMS Frontend", cmd, FRONTEND)
    print("Frontend → http://127.0.0.1:3000")
    print("  Listening on 0.0.0.0 — open the LAN URL below on phones/tablets.")
    print_lan_urls()


def action_setup() -> None:
    action_docker_up()
    ensure_backend_venv()
    action_migrate_seed()
    ensure_frontend_deps()
    print("\nSetup complete. Use menu option 5 to start API + UI (LAN shared).")


def action_start_all() -> None:
    action_docker_up()
    ensure_backend_venv()
    # migrate quietly if needed
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=False)
    action_backend()
    time.sleep(1)
    action_frontend()
    print(
        "\nAll services launching (shared on local network).\n"
        "  This PC:  http://127.0.0.1:3000\n"
        "  API docs: http://127.0.0.1:8000/docs\n"
        "  Login: admin / admin123  or  cashier / cashier123"
    )
    print_lan_urls()


def action_status() -> None:
    print(f"OS: {'Windows' if IS_WIN else 'Unix/Linux'}")
    print(f"Root: {ROOT}")
    print(f"Docker: {'yes' if shutil.which('docker') else 'NO'}")
    print(f"Backend venv: {'yes' if py_exe().exists() else 'no'}")
    print(f"Frontend node_modules: {'yes' if (FRONTEND / 'node_modules').exists() else 'no'}")
    print(f"Node: {shutil.which('node') or 'NO'}")
    print(f"npm: {shutil.which(npm_cmd()) or 'NO'}")


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
║     — also shared on local Wi‑Fi / LAN   ║
║  6) Start backend only (port 8000)       ║
║  7) Start frontend only (port 3000)      ║
║  8) Status check                         ║
║  9) Seed / reset ADMIN only              ║
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
