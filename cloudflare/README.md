# Cloudflare Tunnel for MotoShop RMS

Expose your local production app to the internet **without opening router ports**.
The tunnel targets the Next.js UI on `http://127.0.0.1:3000` (API is reached via `/api/proxy`).

## Install `cloudflared`

Follow [Cloudflare install docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) for Linux / Ubuntu / Pop!_OS.

## Option A — Quick tunnel (testing)

No Cloudflare account DNS needed. URL changes every restart.

```bash
# Deploy + tunnel together:
python scripts/prod_deploy.py --with-tunnel quick
# Reuse existing build:
./run_prod.sh --skip-build --with-tunnel quick

# App already running — only start/restart the tunnel:
./run_prod.sh --tunnel-only quick
```

Look in the console / `logs/prod_tunnel_url.txt` / `logs/prod_tunnel.log` for a URL like:

`https://random-words.trycloudflare.com`

## Option B — Named tunnel (real shop domain)

1. `cloudflared tunnel login`
2. `cloudflared tunnel create rms`
3. Copy `config.example.yml` → `config.yml` and set:
   - `tunnel:` UUID from create
   - `credentials-file:` path to the JSON credentials file
   - `hostname:` e.g. `rms.yourdomain.com`
4. `cloudflared tunnel route dns rms rms.yourdomain.com`
5. Deploy with tunnel:

```bash
python scripts/prod_deploy.py --with-tunnel named
```

## Security

- Change the default `admin` password after first login.
- Keep `SECRET_KEY` strong in `backend/.env`.
- Prefer a named tunnel + your domain for real use; quick tunnels are temporary.
