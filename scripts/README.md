# Scripts — MotoShop RMS

All launchers and Python tooling live in this folder.

## Entry points (from repo root)

| Task | Linux / macOS | Windows (CMD / recommended) | Windows PowerShell |
|------|---------------|-----------------------------|--------------------|
| Dev menu | `./scripts/local_run.sh` | `scripts\local_run.bat` | `.\scripts\local_run.ps1` |
| Production deploy | `./scripts/run_prod.sh` | `scripts\run_prod.bat` | `.\scripts\run_prod.ps1` |
| DB backup | `./scripts/run_db_backup.sh` | `scripts\run_db_backup.bat` | `.\scripts\run_db_backup.ps1` |
| Ubuntu ops menu | `./scripts/run_prod_menu.sh` | — (Linux only) | — |
| Ubuntu Nginx setup | `sudo ./scripts/run_ubuntu_https.sh` | — (Linux only) | — |

On Windows, prefer the `.bat` files if PowerShell says scripts are disabled. Or once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Python modules

| File | Role |
|------|------|
| `dev_menu.py` | Local/dev interactive menu (Postgres, migrate, API, UI) |
| `prod_deploy.py` | Production build, migrate, seed catalogs + admin, start servers, optional tunnel |
| `prod_menu.py` | Ubuntu day-to-day ops (systemd / Nginx / deploy / logs) |
| `ubuntu_https_setup.py` | First-time Ubuntu Nginx + systemd edge |
| `db_backup.py` | Postgres dump / restore / nightly schedule |
| `delete_all_products.ps1` / `.sh` / `.bat` | Hard-delete every product (yes/no prompts) |
| `platform_util.py` | Shared Windows + Linux helpers (ports, venv, firewall, certs) |

Direct invoke:

```bash
python scripts/dev_menu.py 5
python scripts/prod_deploy.py --skip-build
python scripts/db_backup.py status
# Hard-delete all products (asks yes/no twice):
./scripts/delete_all_products.sh
# Windows:
.\scripts\delete_all_products.ps1
```

## Docs

- Windows: [`docs/windows-setup.md`](../docs/windows-setup.md)
- Ubuntu HTTPS: [`docs/production-https-ubuntu.md`](../docs/production-https-ubuntu.md)
- Cloudflare Tunnel: [`cloudflare/README.md`](../cloudflare/README.md)
