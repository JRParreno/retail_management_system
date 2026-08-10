#!/usr/bin/env python3
"""Cross-platform helpers for Windows + Linux launchers."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def venv_python(venv_dir: Path) -> Path:
    if IS_WIN:
        return venv_dir / "Scripts" / "python.exe"
    unix = venv_dir / "bin" / "python"
    if unix.exists():
        return unix
    return venv_dir / "bin" / "python3"


def venv_install_hint() -> str:
    if IS_WIN:
        return (
            "Install Python 3 from https://www.python.org/downloads/ "
            "(check 'Add python.exe to PATH'), then retry."
        )
    return "Install: sudo apt install -y python3-venv python3-pip"


def npm_install_hint() -> str:
    if IS_WIN:
        return (
            "Install Node 20+ LTS from https://nodejs.org/\n"
            "  or: winget install OpenJS.NodeJS.LTS"
        )
    return (
        "Install Node 20+:\n"
        "  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash\n"
        "  source ~/.nvm/nvm.sh && nvm install 20"
    )


def docker_install_hint() -> str:
    if IS_WIN:
        return (
            "Install Docker Desktop for Windows, start it, then retry.\n"
            "  https://docs.docker.com/desktop/setup/install/windows-install/"
        )
    return "Install Docker Engine and ensure the daemon is running."


def pids_on_port(port: int) -> list[int]:
    pids: list[int] = []

    if IS_WIN:
        probe = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (probe.stdout or "").splitlines():
            if "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            # TCP  0.0.0.0:3000  0.0.0.0:0  LISTENING  12345
            local = parts[1]
            if not (local.endswith(f":{port}") or local.endswith(f"]:{port}")):
                continue
            try:
                pid = int(parts[-1])
            except ValueError:
                continue
            if pid > 0 and pid not in pids:
                pids.append(pid)
        return pids

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
            if re.search(rf"[:\]]{port}\b", line) is None:
                continue
            for match in re.finditer(r"pid=(\d+)", line):
                pid = int(match.group(1))
                if pid not in pids:
                    pids.append(pid)
    return pids


def stop_pid(pid: int) -> None:
    if pid <= 0 or (not IS_WIN and pid <= 1):
        return

    if IS_WIN:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return

    try:
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


def open_new_terminal(title: str, command: str, cwd: Path, *, logs_dir: Path) -> None:
    """Open a dedicated terminal for a long-running service."""
    if IS_WIN:
        # Prefer Windows Terminal when available
        if shutil.which("wt"):
            subprocess.Popen(
                [
                    "wt",
                    "-w",
                    "0",
                    "new-tab",
                    "--title",
                    title,
                    "-d",
                    str(cwd),
                    "cmd",
                    "/k",
                    command,
                ]
            )
            return
        # Classic console window
        subprocess.Popen(
            ["cmd", "/c", "start", title, "cmd", "/k", f"cd /d {cwd} && {command}"],
            cwd=str(cwd),
        )
        return

    shells = [
        [
            "gnome-terminal",
            "--title",
            title,
            "--working-directory",
            str(cwd),
            "--",
            "bash",
            "-lc",
            f"{command}; exec bash",
        ],
        [
            "x-terminal-emulator",
            "-T",
            title,
            "-e",
            f"bash -lc 'cd \"{cwd}\" && {command}; exec bash'",
        ],
        ["konsole", "--workdir", str(cwd), "-e", "bash", "-lc", f"{command}; exec bash"],
        [
            "xfce4-terminal",
            f"--working-directory={cwd}",
            "-T",
            title,
            "-e",
            f"bash -lc '{command}; exec bash'",
        ],
    ]
    for args in shells:
        if shutil.which(args[0]):
            subprocess.Popen(args)
            return

    logs_dir.mkdir(exist_ok=True)
    safe = title.lower().replace(" ", "_")
    out = open(logs_dir / f"{safe}.log", "a", encoding="utf-8")
    subprocess.Popen(
        ["bash", "-lc", command],
        cwd=str(cwd),
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"  (no GUI terminal found — running in background, log: logs/{safe}.log)")


def start_detached(cmd: list[str], *, cwd: Path, log_file: Path, pid_file: Path) -> int:
    log_file.parent.mkdir(exist_ok=True)
    log_fh = open(log_file, "a", encoding="utf-8")
    log_fh.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    log_fh.flush()

    kwargs: dict = {
        "args": cmd,
        "cwd": str(cwd),
        "stdout": log_fh,
        "stderr": subprocess.STDOUT,
    }
    if IS_WIN:
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP so the deploy script can exit
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
        kwargs["close_fds"] = False
    else:
        kwargs["start_new_session"] = True
        kwargs["close_fds"] = True

    proc = subprocess.Popen(**kwargs)
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"  Started PID {proc.pid} → log {log_file}")
    return proc.pid


def firewall_lan_hint(app_port: int, api_port: int) -> str | None:
    if IS_WIN:
        return (
            "\n  Windows Firewall may block phones/tablets.\n"
            f"  Run menu option A (as Administrator), or in elevated PowerShell:\n"
            f'    New-NetFirewallRule -DisplayName "RMS Frontend" -Direction Inbound '
            f"-Protocol TCP -LocalPort {app_port} -Action Allow\n"
            f'    New-NetFirewallRule -DisplayName "RMS API" -Direction Inbound '
            f"-Protocol TCP -LocalPort {api_port} -Action Allow"
        )
    conf = Path("/etc/ufw/ufw.conf")
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    enabled = False
    for line in text.splitlines():
        if line.strip().upper().startswith("ENABLED="):
            enabled = line.split("=", 1)[1].strip().lower() in {"yes", "true", "1"}
            break
    if not enabled:
        return None
    return (
        "\n  ⚠ UFW firewall is ON — phones often cannot connect until ports are open.\n"
        "    Run menu option A, or:\n"
        f"    sudo ufw allow {app_port}/tcp && sudo ufw allow {api_port}/tcp && sudo ufw reload"
    )


def open_lan_firewall(app_port: int, api_port: int) -> None:
    if IS_WIN:
        print(
            "Opening Windows Firewall inbound rules for TCP "
            f"{app_port} (app) and {api_port} (API).\n"
            "If this fails, re-run PowerShell / CMD as Administrator.\n"
        )
        rules = [
            (
                "RMS Frontend",
                app_port,
            ),
            (
                "RMS API",
                api_port,
            ),
        ]
        for name, port in rules:
            # Remove old rule with same name (ignore errors), then add
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"],
                capture_output=True,
                check=False,
            )
            cmd = [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={name}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ]
            print(f"→ {' '.join(cmd)}")
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(
                    "Failed — open an Administrator terminal and re-run menu option A,\n"
                    "or use New-NetFirewallRule in elevated PowerShell (see status)."
                )
                return
        print("\nDone. On the phone open the LAN HTTPS URL from status / start-all.")
        return

    if not shutil.which("ufw"):
        print("ufw not installed — nothing to do.")
        return
    conf = Path("/etc/ufw/ufw.conf")
    enabled = False
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.strip().upper().startswith("ENABLED="):
                enabled = line.split("=", 1)[1].strip().lower() in {"yes", "true", "1"}
                break
    except OSError:
        pass
    if not enabled:
        print("UFW is not enabled. If phones still fail, check Wi‑Fi client/AP isolation.")
        return
    print(
        "This opens TCP ports for LAN devices.\n"
        "You will be asked for your sudo password.\n"
    )
    cmds = [
        ["sudo", "ufw", "allow", f"{app_port}/tcp", "comment", "RMS frontend"],
        ["sudo", "ufw", "allow", f"{api_port}/tcp", "comment", "RMS API"],
        ["sudo", "ufw", "reload"],
        ["sudo", "ufw", "status", "numbered"],
    ]
    for cmd in cmds:
        print(f"→ {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print("Failed — run the commands manually in a terminal.")
            return
    print("\nDone.")


def mkcert_ca_paths() -> tuple[Path, Path]:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "mkcert"
    else:
        base = Path.home() / ".local" / "share" / "mkcert"
    return base / "rootCA.pem", base / "rootCA-key.pem"


def cloudflared_candidates() -> list[Path]:
    candidates: list[Path] = []
    which = shutil.which("cloudflared")
    if which:
        candidates.append(Path(which))
    if IS_WIN:
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "cloudflared" / "cloudflared.exe"
        candidates.append(local)
        candidates.append(Path.home() / "cloudflared.exe")
        candidates.append(Path("C:/Program Files/cloudflared/cloudflared.exe"))
    else:
        candidates.append(Path.home() / ".local" / "bin" / "cloudflared")
        candidates.append(Path("/usr/local/bin/cloudflared"))
        candidates.append(Path("/usr/bin/cloudflared"))
    return candidates


def cloudflared_install_hint() -> str:
    if IS_WIN:
        return (
            "cloudflared not found.\n"
            "  winget install --id Cloudflare.cloudflared\n"
            "  or download from:\n"
            "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/\n"
            "Then re-run with --with-tunnel quick|named"
        )
    return (
        "cloudflared not found.\n"
        "  Install: see cloudflare/README.md\n"
        "  Or: curl -fsSL -o ~/.local/bin/cloudflared \\\n"
        "       https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64\n"
        "     chmod +x ~/.local/bin/cloudflared\n"
        "Then re-run with --with-tunnel quick|named"
    )


def tailwind_oxide_ok(modules: Path) -> bool:
    if not modules.exists():
        return False
    if IS_WIN:
        return (modules / "@tailwindcss" / "oxide-win32-x64-msvc").exists()
    if IS_LINUX:
        return (modules / "@tailwindcss" / "oxide-linux-x64-gnu").exists()
    # macOS / other — assume ok if node_modules exists
    return True


def remove_tree(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def generate_self_signed_pem(
    cert: Path,
    key: Path,
    *,
    ips: list[str],
    dns_names: list[str] | None = None,
) -> bool:
    """Write a self-signed cert/key using cryptography (backend dep)."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime
        import ipaddress
    except ImportError:
        return False

    dns_names = dns_names or ["localhost"]
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MotoShop RMS Dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )
    alt_names: list[x509.GeneralName] = [
        x509.DNSName(name) for name in dns_names
    ]
    for raw in ips:
        if raw in {"0.0.0.0", "::"}:
            continue
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(raw)))
        except ValueError:
            continue

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
    )
    certificate = builder.sign(private_key, hashes.SHA256())

    key.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return True
