#!/usr/bin/env python3
"""
Postgres backup / restore for MotoShop RMS (single local Docker DB).

Recommended for local production + internet view-only:
  nightly dump → keep N days locally → optional copy to another drive/PC.

Usage:
  python3 scripts/db_backup.py backup
  python3 scripts/db_backup.py list
  python3 scripts/db_backup.py restore latest
  python3 scripts/db_backup.py install-cron
  python3 scripts/db_backup.py uninstall-cron
  python3 scripts/db_backup.py status

Env (optional):
  RMS_BACKUP_DIR     default: /opt/rms/backups (else <repo>/backups)
  RMS_BACKUP_OFFSITE directory to copy each new dump (USB/NAS/other disk)
  RMS_BACKUP_KEEP_DAYS  retention days (default 14)
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"
CONTAINER = "rms-postgres"
DEFAULT_KEEP_DAYS = 14
CRON_MARKER = "# rms-db-backup"
DUMP_GLOB = "rms_*.sql.gz"


def docker_accessible() -> bool:
    return (
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def run_docker(args: list[str], *, check: bool = True, input_data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run docker, falling back to `sg docker` when the shell lacks group access."""
    if docker_accessible():
        cmd = ["docker", *args]
        print(f"→ {' '.join(cmd)}")
        return subprocess.run(cmd, input=input_data, check=check, capture_output=True)

    if not shutil.which("sg"):
        raise SystemExit(
            "Docker permission denied.\n"
            '  sudo usermod -aG docker "$USER"\n'
            "Then log out/in, or run: newgrp docker"
        )

    inner = "docker " + " ".join(shlex.quote(a) for a in args)
    cmd = ["sg", "docker", "-c", inner]
    print(f"→ {' '.join(cmd)}")
    return subprocess.run(cmd, input=input_data, check=check, capture_output=True)


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip("'").strip('"')
    return out


def db_credentials() -> tuple[str, str, str]:
    """Return (user, password, database) from backend/.env or defaults."""
    env = load_dotenv(BACKEND_ENV)
    url = os.environ.get("DATABASE_URL") or env.get("DATABASE_URL") or ""
    user, password, database = "postgres", "postgres", "rms"
    if url:
        # sqlalchemy style: postgresql+psycopg://user:pass@host:5432/db
        cleaned = re.sub(r"^postgresql\+\w+", "postgresql", url)
        parsed = urlparse(cleaned)
        if parsed.username:
            user = unquote(parsed.username)
        if parsed.password is not None:
            password = unquote(parsed.password)
        if parsed.path and parsed.path != "/":
            database = unquote(parsed.path.lstrip("/"))
    return user, password, database


def default_backup_dir() -> Path:
    env = os.environ.get("RMS_BACKUP_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    preferred = Path("/opt/rms/backups")
    if preferred.is_dir() or preferred.parent.is_dir():
        return preferred

    return (ROOT / "backups").resolve()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dump_paths(backup_dir: Path) -> list[Path]:
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob(DUMP_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)


def container_ready(user: str, database: str) -> None:
    probe = run_docker(
        ["exec", CONTAINER, "pg_isready", "-U", user, "-d", database],
        check=False,
    )
    if probe.returncode != 0:
        raise SystemExit(
            f"Postgres container `{CONTAINER}` is not ready.\n"
            "  Start it with: docker compose up -d\n"
            "  Or: ./run_prod_menu.sh / ./local_run.sh (Postgres option)"
        )


def prune_old(backup_dir: Path, keep_days: int) -> int:
    if keep_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - keep_days * 86400
    removed = 0
    for path in dump_paths(backup_dir):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
            print(f"  pruned {path.name}")
    return removed


def copy_offsite(src: Path, offsite: Path | None) -> None:
    if not offsite:
        return
    ensure_dir(offsite)
    dest = offsite / src.name
    shutil.copy2(src, dest)
    print(f"  offsite copy → {dest}")


def cmd_backup(*, keep_days: int, offsite: Path | None, quiet: bool = False) -> Path:
    user, _password, database = db_credentials()
    backup_dir = default_backup_dir()
    ensure_dir(backup_dir)
    container_ready(user, database)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = backup_dir / f"rms_{stamp}.sql.gz"

    if not quiet:
        print(f"Backing up `{database}` from `{CONTAINER}` → {out}")

    dump = run_docker(
        [
            "exec",
            CONTAINER,
            "pg_dump",
            "-U",
            user,
            "-d",
            database,
            "--clean",
            "--if-exists",
        ],
        check=True,
    )
    with gzip.open(out, "wb") as fh:
        fh.write(dump.stdout)

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"OK: {out.name} ({size_mb:.2f} MiB)")

    pruned = prune_old(backup_dir, keep_days)
    if pruned and not quiet:
        print(f"Retention: removed {pruned} dump(s) older than {keep_days} day(s)")

    copy_offsite(out, offsite)
    return out


def cmd_list() -> None:
    backup_dir = default_backup_dir()
    files = dump_paths(backup_dir)
    print(f"Backup dir: {backup_dir}")
    if not files:
        print("(no dumps yet)")
        return
    for path in files:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  {path.name}  {size_mb:7.2f} MiB  {mtime}")


def resolve_dump(name: str) -> Path:
    backup_dir = default_backup_dir()
    if name in ("latest", "last"):
        files = dump_paths(backup_dir)
        if not files:
            raise SystemExit(f"No dumps in {backup_dir}")
        return files[0]

    candidate = Path(name)
    if candidate.is_file():
        return candidate.resolve()

    in_dir = backup_dir / name
    if in_dir.is_file():
        return in_dir

    raise SystemExit(f"Dump not found: {name}\n  Looked in {backup_dir}")


def cmd_restore(name: str, *, yes: bool) -> None:
    user, _password, database = db_credentials()
    dump = resolve_dump(name)
    container_ready(user, database)

    print(f"Restore `{dump}` into `{database}` on `{CONTAINER}`.")
    print("WARNING: this replaces current data in that database.")
    if not yes:
        answer = input("Type YES to continue: ").strip()
        if answer != "YES":
            print("Aborted.")
            return

    with gzip.open(dump, "rb") as fh:
        payload = fh.read()

    # Terminate other sessions so restore can DROP objects cleanly.
    run_docker(
        [
            "exec",
            CONTAINER,
            "psql",
            "-U",
            user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            (
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{database}' AND pid <> pg_backend_pid();"
            ),
        ],
        check=False,
    )

    restore = run_docker(
        [
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            user,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        check=False,
        input_data=payload,
    )
    if restore.returncode != 0:
        err = (restore.stderr or b"").decode("utf-8", errors="replace")
        raise SystemExit(f"Restore failed:\n{err}")

    print("OK: restore complete. Restart API/Web if they were running.")


def crontab_get() -> str:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return ""
    return r.stdout or ""


def crontab_set(body: str) -> None:
    subprocess.run(["crontab", "-"], input=body, text=True, check=True)


def cron_line(*, hour: int, minute: int, keep_days: int, offsite: Path | None) -> str:
    py = shutil.which("python3") or sys.executable
    script = ROOT / "scripts" / "db_backup.py"
    parts = [
        f"{minute} {hour} * * *",
        f"cd {shlex.quote(str(ROOT))} &&",
        f"{shlex.quote(py)} {shlex.quote(str(script))} backup",
        f"--keep-days {keep_days}",
        "--quiet",
    ]
    if offsite:
        parts.append(f"--offsite {shlex.quote(str(offsite))}")
    parts.append(f">> {shlex.quote(str(default_backup_dir() / 'backup.log'))} 2>&1")
    parts.append(CRON_MARKER)
    return " ".join(parts)


def cmd_install_cron(*, hour: int, minute: int, keep_days: int, offsite: Path | None) -> None:
    ensure_dir(default_backup_dir())
    existing = crontab_get()
    lines = [ln for ln in existing.splitlines() if CRON_MARKER not in ln]
    lines.append(cron_line(hour=hour, minute=minute, keep_days=keep_days, offsite=offsite))
    body = "\n".join(lines).rstrip() + "\n"
    crontab_set(body)
    print(f"Installed nightly cron at {hour:02d}:{minute:02d} local time.")
    print(f"Dumps → {default_backup_dir()}")
    if offsite:
        print(f"Offsite → {offsite}")
    print("Log →", default_backup_dir() / "backup.log")


def cmd_uninstall_cron() -> None:
    existing = crontab_get()
    lines = [ln for ln in existing.splitlines() if CRON_MARKER not in ln]
    crontab_set(("\n".join(lines).rstrip() + "\n") if lines else "")
    print("Removed rms-db-backup cron entry (if present).")


def cmd_status() -> None:
    backup_dir = default_backup_dir()
    offsite = os.environ.get("RMS_BACKUP_OFFSITE", "").strip()
    keep = os.environ.get("RMS_BACKUP_KEEP_DAYS", str(DEFAULT_KEEP_DAYS))
    user, _, database = db_credentials()

    print(f"Repo:          {ROOT}")
    print(f"Container:     {CONTAINER}")
    print(f"Database:      {database} (user={user})")
    print(f"Backup dir:    {backup_dir}")
    print(f"Keep days:     {keep}")
    print(f"Offsite env:   {offsite or '(not set — pass --offsite or RMS_BACKUP_OFFSITE)'}")

    ready = run_docker(
        ["exec", CONTAINER, "pg_isready", "-U", user, "-d", database],
        check=False,
    )
    print(f"Postgres:      {'ready' if ready.returncode == 0 else 'not ready'}")

    files = dump_paths(backup_dir)
    if files:
        latest = files[0]
        mtime = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"Latest dump:   {latest.name} ({mtime})")
        print(f"Dump count:    {len(files)}")
    else:
        print("Latest dump:   (none)")

    cron = crontab_get()
    installed = any(CRON_MARKER in ln for ln in cron.splitlines())
    print(f"Nightly cron:  {'installed' if installed else 'not installed'}")
    if installed:
        for ln in cron.splitlines():
            if CRON_MARKER in ln:
                print(f"  {ln}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MotoShop RMS Postgres backup / restore")
    p.add_argument(
        "--keep-days",
        type=int,
        default=int(os.environ.get("RMS_BACKUP_KEEP_DAYS", DEFAULT_KEEP_DAYS)),
        help=f"delete dumps older than N days (default {DEFAULT_KEEP_DAYS})",
    )
    offsite_env = os.environ.get("RMS_BACKUP_OFFSITE", "").strip()
    p.add_argument(
        "--offsite",
        type=Path,
        default=Path(offsite_env).expanduser() if offsite_env else None,
        help="copy each new dump here (USB/NAS/other disk)",
    )

    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="create a gzipped SQL dump")
    b.add_argument("--quiet", action="store_true")

    sub.add_parser("list", help="list local dumps")

    r = sub.add_parser("restore", help="restore a dump (replaces DB data)")
    r.add_argument("name", help="filename, path, or 'latest'")
    r.add_argument("--yes", action="store_true", help="skip confirmation")

    c = sub.add_parser("install-cron", help="install nightly backup cron (default 02:00)")
    c.add_argument("--hour", type=int, default=2)
    c.add_argument("--minute", type=int, default=0)

    sub.add_parser("uninstall-cron", help="remove nightly backup cron")
    sub.add_parser("status", help="show backup config and latest dump")

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    offsite = args.offsite.resolve() if getattr(args, "offsite", None) else None
    keep_days = max(0, int(args.keep_days))

    if args.command == "backup":
        cmd_backup(keep_days=keep_days, offsite=offsite, quiet=bool(args.quiet))
    elif args.command == "list":
        cmd_list()
    elif args.command == "restore":
        cmd_restore(args.name, yes=bool(args.yes))
    elif args.command == "install-cron":
        cmd_install_cron(hour=args.hour, minute=args.minute, keep_days=keep_days, offsite=offsite)
    elif args.command == "uninstall-cron":
        cmd_uninstall_cron()
    elif args.command == "status":
        cmd_status()
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
