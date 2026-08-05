#!/usr/bin/env python3
"""
Production deploy / restart for MotoShop RMS.

- Checks required tools
- Starts Postgres (Docker)
- Installs backend + frontend deps
- Migrates DB
- Seeds Main branch + admin only (NO demo products/mechanics/cashier)
- Builds Next.js
- Stops old app processes and starts production servers

Usage (from repo root):
  python scripts/prod_deploy.py
  python scripts/prod_deploy.py --skip-build
  python scripts/prod_deploy.py --with-tunnel quick
  python scripts/prod_deploy.py --with-tunnel named
  ./run_prod.sh
  .\\run_prod.ps1
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
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
CLOUDFLARE = ROOT / "cloudflare"
LOGS = ROOT / "logs"
IS_WIN = os.name == "nt"

BACKEND_PID = LOGS / "prod_backend.pid"
FRONTEND_PID = LOGS / "prod_frontend.pid"
TUNNEL_PID = LOGS / "prod_tunnel.pid"
BACKEND_LOG = LOGS / "prod_backend.log"
FRONTEND_LOG = LOGS / "prod_frontend.log"
TUNNEL_LOG = LOGS / "prod_tunnel.log"

API_PORT = 8000
APP_PORT = 3000


def py_exe() -> Path:
    if IS_WIN:
        return BACKEND / ".venv" / "Scripts" / "python.exe"
    unix = BACKEND / ".venv" / "bin" / "python"
    if unix.exists():
        return unix
    return BACKEND / ".venv" / "bin" / "python3"


def ensure_backend_venv() -> None:
    if not py_exe().exists():
        print("Creating backend virtualenv…")
        venv.create(BACKEND / ".venv", with_pip=True)

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
        run([str(python), "-m", "ensurepip", "--upgrade"], cwd=BACKEND, check=False)
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND)

    run([str(python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=BACKEND)


def npm_cmd() -> str:
    return "npm.cmd" if IS_WIN else "npm"


def docker_cmd() -> list[str]:
    if shutil.which("docker"):
        return ["docker", "compose"]
    raise SystemExit("Docker not found. Install Docker Desktop / Docker Engine.")


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> int:
    print(f"\n→ {' '.join(cmd)}")
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), check=False, env=merged)
    if check and result.returncode != 0:
        raise SystemExit(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result.returncode


def which_or_fail(name: str, *, alts: list[str] | None = None) -> str:
    candidates = [name, *(alts or [])]
    for cand in candidates:
        path = shutil.which(cand)
        if path:
            return path
    raise SystemExit(
        f"Missing required tool: {name}"
        + (f" (also tried: {', '.join(alts)})" if alts else "")
    )


def host_python() -> str:
    """Python used to run this script, or python3/python/py on PATH."""
    if sys.executable:
        return sys.executable
    for name in ("python3", "python", "py"):
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit(
        "Missing required tool: Python 3 (install python3, or run via `python3 scripts/prod_deploy.py`)"
    )


def check_requirements() -> None:
    print("\n=== Checking requirements ===")
    host_py = host_python()
    which_or_fail("node")
    which_or_fail(npm_cmd(), alts=["npm"])
    which_or_fail("docker")

    try:
        py_v = subprocess.check_output(
            [host_py, "--version"], text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception:
        py_v = "Python 3"
    node_v = subprocess.check_output(
        ["node", "-v"], text=True, stderr=subprocess.STDOUT
    ).strip()
    npm_v = subprocess.check_output(
        [npm_cmd(), "-v"], text=True, stderr=subprocess.STDOUT
    ).strip()
    print(f"  Python: {py_v} ({host_py})")
    print(f"  Node:   {node_v}")
    print(f"  npm:    {npm_v}")
    print("  Docker: OK")

    # Docker daemon reachable?
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise SystemExit(
            "Docker is installed but the daemon is not running. "
            "Start Docker Desktop / dockerd, then retry."
        )
    print("  Docker daemon: OK")


def ensure_backend_env() -> None:
    env_path = BACKEND / ".env"
    example = BACKEND / ".env.example"
    if not env_path.exists():
        if not example.exists():
            raise SystemExit("backend/.env.example missing — cannot create .env")
        text = example.read_text(encoding="utf-8")
        # Production defaults
        text = re.sub(r"(?m)^DEBUG=.*$", "DEBUG=false", text)
        if "LOG_LEVEL=" not in text:
            text += "\nLOG_LEVEL=INFO\n"
        else:
            text = re.sub(r"(?m)^LOG_LEVEL=.*$", "LOG_LEVEL=INFO", text)
        if "SECRET_KEY=change-me" in text or "SECRET_KEY=change-me-to-a-long-random-string" in text:
            text = re.sub(
                r"(?m)^SECRET_KEY=.*$",
                f"SECRET_KEY={secrets.token_urlsafe(48)}",
                text,
            )
        env_path.write_text(text, encoding="utf-8")
        print(f"Created {env_path} from example (DEBUG=false, new SECRET_KEY)")
        return

    # Existing .env — nudge toward production without wiping secrets
    text = env_path.read_text(encoding="utf-8")
    original = text
    if re.search(r"(?m)^DEBUG=true\s*$", text):
        text = re.sub(r"(?m)^DEBUG=true\s*$", "DEBUG=false", text)
        print("Set DEBUG=false in backend/.env for production")
    if "SECRET_KEY=change-me-to-a-long-random-string" in text:
        text = text.replace(
            "SECRET_KEY=change-me-to-a-long-random-string",
            f"SECRET_KEY={secrets.token_urlsafe(48)}",
        )
        print("Replaced default SECRET_KEY in backend/.env")
    if text != original:
        env_path.write_text(text, encoding="utf-8")


def ensure_frontend_env() -> None:
    env_local = FRONTEND / ".env.local"
    if env_local.exists():
        return
    env_local.write_text(
        "BACKEND_URL=http://127.0.0.1:8000\n"
        "NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    print(f"Created {env_local}")


def wait_for_postgres(*, timeout_s: int = 60) -> None:
    print("Waiting for Postgres…")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ready = subprocess.run(
            [
                "docker",
                "exec",
                "rms-postgres",
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "rms",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if ready.returncode == 0:
            print("Postgres is ready.")
            return
        try:
            with socket.create_connection(("127.0.0.1", 5432), timeout=1):
                # Port is open; give Postgres a moment if pg_isready is flaky
                time.sleep(1)
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit("Postgres did not become ready in time.")


def start_postgres() -> None:
    print("\n=== Starting Postgres ===")
    run(docker_cmd() + ["up", "-d"], cwd=ROOT)
    wait_for_postgres()


def migrate_and_seed() -> None:
    print("\n=== Migrate + production seed (admin only) ===")
    run([str(py_exe()), "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    run([str(py_exe()), "-m", "app.scripts.seed_production"], cwd=BACKEND)


def build_frontend() -> None:
    print("\n=== Building frontend ===")
    ensure_frontend_env()
    if not (FRONTEND / "node_modules").exists():
        run([npm_cmd(), "ci"], cwd=FRONTEND, check=False)
        if not (FRONTEND / "node_modules").exists():
            run([npm_cmd(), "install"], cwd=FRONTEND)
    else:
        run([npm_cmd(), "install"], cwd=FRONTEND)
    run([npm_cmd(), "run", "build"], cwd=FRONTEND)


def pids_on_port(port: int) -> list[int]:
    pids: list[int] = []
    if IS_WIN:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.STDOUT, errors="ignore"
        )
        for line in out.splitlines():
            if f":{port}" not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                pid = int(parts[-1])
            except ValueError:
                continue
            if pid > 0 and pid not in pids:
                pids.append(pid)
        return pids

    for tool in (["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"], ["fuser", f"{port}/tcp"]):
        if not shutil.which(tool[0]):
            continue
        probe = subprocess.run(tool, capture_output=True, text=True, check=False)
        if probe.returncode != 0:
            continue
        for token in re.split(r"[\s,]+", probe.stdout.strip()):
            if token.isdigit():
                pid = int(token)
                if pid not in pids:
                    pids.append(pid)
        if pids:
            return pids
    return pids


def stop_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if IS_WIN:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    except OSError:
        pass


def read_pid_file(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def stop_production_servers() -> None:
    print("\n=== Stopping existing production servers ===")
    for path in (BACKEND_PID, FRONTEND_PID, TUNNEL_PID):
        pid = read_pid_file(path)
        if pid:
            print(f"  Stopping PID {pid} from {path.name}")
            stop_pid(pid)
            path.unlink(missing_ok=True)

    for port in (API_PORT, APP_PORT):
        for pid in pids_on_port(port):
            print(f"  Freeing port {port} (PID {pid})")
            stop_pid(pid)
    time.sleep(1)


def cloudflared_exe() -> str:
    path = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if not path:
        raise SystemExit(
            "cloudflared not found.\n"
            "  Windows: winget install Cloudflare.cloudflared\n"
            "  Linux:   see cloudflare/README.md\n"
            "Then re-run with --with-tunnel quick|named"
        )
    return path


def start_cloudflare_tunnel(mode: str) -> None:
    """mode: 'quick' (trycloudflare.com) or 'named' (cloudflare/config.yml)."""
    print(f"\n=== Starting Cloudflare Tunnel ({mode}) ===")
    cf = cloudflared_exe()
    if mode == "quick":
        cmd = [
            cf,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{APP_PORT}",
            "--no-autoupdate",
        ]
    elif mode == "named":
        config = CLOUDFLARE / "config.yml"
        if not config.exists():
            example = CLOUDFLARE / "config.example.yml"
            raise SystemExit(
                f"Missing {config}.\n"
                f"Copy {example} → config.yml, fill tunnel UUID + credentials, "
                "then route DNS (see cloudflare/README.md)."
            )
        cmd = [
            cf,
            "tunnel",
            "--config",
            str(config),
            "--no-autoupdate",
            "run",
        ]
    else:
        raise SystemExit(f"Unknown tunnel mode: {mode}")

    if TUNNEL_LOG.exists():
        # Truncate so we can find the fresh quick-tunnel URL
        TUNNEL_LOG.write_text("", encoding="utf-8")

    start_detached(cmd, cwd=ROOT, log_file=TUNNEL_LOG, pid_file=TUNNEL_PID)
    if mode == "quick":
        url = wait_for_quick_tunnel_url(timeout_s=45)
        if url:
            print(f"  Public URL: {url}")
            (LOGS / "prod_tunnel_url.txt").write_text(url + "\n", encoding="utf-8")
        else:
            print(
                "  Quick tunnel started — check logs/prod_tunnel.log for the "
                "https://*.trycloudflare.com URL"
            )
    else:
        print(f"  Named tunnel using {CLOUDFLARE / 'config.yml'}")
        print("  Open your configured hostname (HTTPS via Cloudflare).")


def wait_for_quick_tunnel_url(*, timeout_s: int = 45) -> str | None:
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if TUNNEL_LOG.exists():
            text = TUNNEL_LOG.read_text(encoding="utf-8", errors="ignore")
            match = pattern.search(text)
            if match:
                return match.group(0)
        time.sleep(1)
    return None


def start_detached(cmd: list[str], *, cwd: Path, log_file: Path, pid_file: Path) -> int:
    LOGS.mkdir(exist_ok=True)
    log_fh = open(log_file, "a", encoding="utf-8")
    log_fh.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    log_fh.flush()

    if IS_WIN:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"  Started PID {proc.pid} → log {log_file}")
    return proc.pid


def start_production_servers() -> None:
    print("\n=== Starting production servers ===")
    backend_cmd = [
        str(py_exe()),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(API_PORT),
        "--workers",
        "2",
    ]
    frontend_cmd = [
        npm_cmd(),
        "run",
        "start",
    ]

    start_detached(backend_cmd, cwd=BACKEND, log_file=BACKEND_LOG, pid_file=BACKEND_PID)
    time.sleep(2)
    # package.json "start" already binds 0.0.0.0:3000
    start_detached(
        frontend_cmd, cwd=FRONTEND, log_file=FRONTEND_LOG, pid_file=FRONTEND_PID
    )


def wait_http(url: str, *, timeout_s: int = 45) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            # stdlib only
            import urllib.request

            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


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


def print_summary(*, tunnel_mode: str | None = None) -> None:
    print("\n=== Production deploy complete ===")
    print(f"  This PC:  http://127.0.0.1:{APP_PORT}")
    print(f"  API:      http://127.0.0.1:{API_PORT}/docs")
    for ip in lan_ipv4_addresses():
        print(f"  LAN app:  http://{ip}:{APP_PORT}")
        print(f"  LAN API:  http://{ip}:{API_PORT}/docs")
    if tunnel_mode == "quick":
        url_file = LOGS / "prod_tunnel_url.txt"
        if url_file.exists():
            print(f"  Tunnel:   {url_file.read_text(encoding='utf-8').strip()}")
        else:
            print("  Tunnel:   see logs/prod_tunnel.log for trycloudflare.com URL")
    elif tunnel_mode == "named":
        print("  Tunnel:   named (cloudflare/config.yml hostname)")
    print("  Login:    admin / admin123")
    print("  Note:     No demo products/mechanics/cashier were seeded.")
    print(f"  Logs:     {BACKEND_LOG}")
    print(f"           {FRONTEND_LOG}")
    if tunnel_mode:
        print(f"           {TUNNEL_LOG}")
        print("  Cloudflare Tunnel gives public HTTPS (good for tablet camera).")
        print("  Change the admin password before sharing the public URL widely.")
    else:
        print("  Tablet camera scan needs HTTPS — use --with-tunnel quick|named,")
        print("  or open Manual / Bluetooth gun on HTTP for now.")


def main() -> None:
    parser = argparse.ArgumentParser(description="MotoShop RMS production deploy")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip npm install/build (restart servers only after migrate/seed)",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip alembic + production seed",
    )
    parser.add_argument(
        "--stop-only",
        action="store_true",
        help="Only stop production servers (and tunnel)",
    )
    parser.add_argument(
        "--with-tunnel",
        choices=("quick", "named"),
        default=None,
        help=(
            "Start Cloudflare Tunnel after the app is up: "
            "'quick' = temporary trycloudflare.com URL; "
            "'named' = cloudflare/config.yml permanent hostname"
        ),
    )
    parser.add_argument(
        "--tunnel-only",
        choices=("quick", "named"),
        default=None,
        help="Only (re)start the Cloudflare Tunnel; app must already be running",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    LOGS.mkdir(exist_ok=True)

    if args.stop_only:
        stop_production_servers()
        print("Stopped.")
        return

    if args.tunnel_only:
        # Stop previous tunnel only, keep app
        pid = read_pid_file(TUNNEL_PID)
        if pid:
            stop_pid(pid)
            TUNNEL_PID.unlink(missing_ok=True)
        if not wait_http(f"http://127.0.0.1:{APP_PORT}", timeout_s=5):
            raise SystemExit(
                f"App not reachable on http://127.0.0.1:{APP_PORT}. "
                "Start production first, then use --tunnel-only."
            )
        start_cloudflare_tunnel(args.tunnel_only)
        print_summary(tunnel_mode=args.tunnel_only)
        return

    check_requirements()
    start_postgres()
    ensure_backend_venv()
    ensure_backend_env()

    if not args.skip_migrate:
        migrate_and_seed()

    if not args.skip_build:
        build_frontend()
    elif not (FRONTEND / ".next").exists():
        raise SystemExit("No frontend build found (.next). Run without --skip-build.")

    stop_production_servers()
    start_production_servers()

    print("\nWaiting for health checks…")
    api_ok = wait_http(f"http://127.0.0.1:{API_PORT}/health")
    app_ok = wait_http(f"http://127.0.0.1:{APP_PORT}")
    print(f"  API health: {'OK' if api_ok else 'NOT READY (check logs)'}")
    print(f"  App:        {'OK' if app_ok else 'NOT READY (check logs)'}")

    tunnel_mode = args.with_tunnel
    if tunnel_mode:
        if not app_ok:
            print("  Skipping tunnel — app is not ready.")
            tunnel_mode = None
        else:
            start_cloudflare_tunnel(tunnel_mode)

    print_summary(tunnel_mode=tunnel_mode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
