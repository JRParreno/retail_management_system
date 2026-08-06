# Production HTTPS on a home Ubuntu server (MotoShop RMS)

Complete guide for exposing this FastAPI + Next.js app from a home Ubuntu 24.04 host over HTTPS with your own domain.

## Automated setup (Nginx by IP — no domain)

On the Ubuntu server, from the repo root:

```bash
chmod +x run_ubuntu_https.sh
sudo ./run_ubuntu_https.sh --yes
```

Useful flags:

```bash
# HTTP only (port 80) — simplest
sudo ./run_ubuntu_https.sh --yes

# HTTPS with self-signed cert (no Let's Encrypt / no domain)
# Accept the browser warning once; needed for tablet camera scanning
sudo ./run_ubuntu_https.sh --self-signed --yes

# App already built
sudo ./run_ubuntu_https.sh --skip-build --self-signed --yes
```

What the script does:

1. Creates service user `rms`, builds/migrates via `prod_deploy.py` (unless `--skip-build`)
2. Installs systemd units `rms-api` + `rms-web` (bind `127.0.0.1`)
3. Configures UFW (22 / 80, and 443 if `--self-signed`)
4. Installs Nginx as reverse proxy (access by LAN IP, no DNS)
5. Prints the URLs to open

**Day-to-day menu** (after setup):

```bash
chmod +x run_prod_menu.sh
./run_prod_menu.sh
```

| # | Action |
|---|--------|
| 1 | Status |
| 2 | Start services |
| 3 | Stop services |
| 4 | Restart all |
| 5 | Deploy / apply code changes (pull optional → migrate/build → restart) |
| 6 | Restart API only |
| 7 | Restart Web only |
| 8 | Reload Nginx |
| 9 | Logs |
| 10 | Re-run Nginx setup |

Templates: `deploy/ubuntu/`. Domain + Certbot steps remain in §2 below if you add a domain later.

---

**Stack assumptions**

| Piece | Binding |
|-------|---------|
| Next.js | `127.0.0.1:3000` (or `0.0.0.0:3000` on LAN only) |
| FastAPI (Uvicorn) | `127.0.0.1:8000` |
| Postgres | Docker Compose on the host (or local Postgres) |
| Public edge | Nginx + Let’s Encrypt **or** Cloudflare Tunnel |

**Critical app detail (do not skip)**

In this repo the browser talks to **Next.js**, not FastAPI:

- UI pages → Next.js
- Client API → `/api/proxy/...` (Next.js route → FastAPI `/api/v1/...`)
- Login cookie → `/api/auth/login` (Next.js route)

So Nginx must **not** send all of `/api` to Uvicorn. That would break login and the proxy.

Recommended public routing:

| Public path | Upstream |
|-------------|----------|
| `/` (everything by default) | Next.js `:3000` |
| Optional: `/api/v1/`, `/docs`, `/openapi.json`, `/health`, `/uploads/` | FastAPI `:8000` |

Replace every `rms.example.com` below with your real hostname.

---

## 0. Recommended directory layout on the server

```text
/opt/rms/
├── retail_management_system/     # git clone of this repo
│   ├── backend/
│   ├── frontend/
│   ├── cloudflare/
│   ├── docker-compose.yml
│   └── ...
├── backups/                      # optional DB dumps
└── secrets/                      # optional; keep out of git

/etc/nginx/sites-available/rms
/etc/nginx/sites-enabled/rms → ../sites-available/rms
/etc/systemd/system/rms-api.service
/etc/systemd/system/rms-web.service
/etc/cloudflared/config.yml       # CGNAT / Tunnel path only
```

Clone once:

```bash
sudo mkdir -p /opt/rms
sudo chown "$USER:$USER" /opt/rms
cd /opt/rms
git clone https://github.com/JRParreno/retail_management_system.git
cd retail_management_system
```

Deploy the app (build + migrate + seed) before opening the firewall to the world:

```bash
chmod +x run_prod.sh
./run_prod.sh
# or later with systemd (section 2.7 / 3.x) instead of the detached prod script
```

Change `admin` / `admin123` immediately after first login.

---

## 1. Detect CGNAT (Converge ICT often uses it)

**Why:** Port forwarding only works if your router has a **true public** WAN IPv4. Under CGNAT, many customers share one public IP; inbound 80/443 never reach your router.

### 1.1 Read the router WAN IP

Log into the router admin UI (often `192.168.1.1` or `192.168.0.1`) and note **WAN / Internet IPv4**.

Or, if the Ubuntu box can see the gateway via UPnP/SNMP you may still prefer the router UI — it is the source of truth for “what the modem thinks its WAN is.”

### 1.2 Read the public IP seen by the internet

On the Ubuntu server:

```bash
curl -4 -s https://ifconfig.me
echo
curl -4 -s https://api.ipify.org
echo
curl -4 -s https://icanhazip.com
```

### 1.3 Compare

| Result | Meaning | Path |
|--------|---------|------|
| Router WAN IP **equals** public IP from `curl` | You likely have a public IPv4 | **Section 2** (port forward + Nginx + Certbot) |
| Router WAN is private (`10.x`, `100.64.0.0/10`, `172.16–31.x`, `192.168.x`) **or** differs from public IP | **CGNAT** (or double NAT) | **Section 3** (Cloudflare Tunnel) |
| Only IPv6 works publicly | IPv4 inbound still blocked | Prefer Tunnel, or ask ISP for public IPv4 |

CGNAT shared range reminder: `100.64.0.0/10` (RFC 6598) is a strong CGNAT signal when it appears as WAN.

**Converge note:** Many residential plans are CGNAT. If WAN ≠ public IP, skip port forwarding and use Section 3. You can still run Nginx locally behind the tunnel.

---

## 2. Public IP path — Nginx + Let’s Encrypt + UFW + systemd

Use this only after Section 1 confirms a real public IPv4.

### 2.1 DNS records

At your domain registrar (or Cloudflare DNS if the domain is on Cloudflare):

| Type | Name | Value | TTL |
|------|------|-------|-----|
| `A` | `rms` (or `@`) | Your public IPv4 | 300 (while testing) |
| `AAAA` | optional | Your public IPv6 if you forward IPv6 too | 300 |

Example for hostname `rms.example.com`:

```text
rms.example.com.   300   IN   A   203.0.113.50
```

Verify propagation:

```bash
dig +short rms.example.com A
# or
getent hosts rms.example.com
```

Point DNS **before** Certbot HTTP-01 validation (needs port 80 reachable).

### 2.2 Router port forwarding

Forward **TCP** from WAN to the Ubuntu server’s **LAN IP** (example `192.168.1.50`):

| WAN port | LAN IP | LAN port | Protocol |
|----------|--------|----------|----------|
| 80 | 192.168.1.50 | 80 | TCP |
| 443 | 192.168.1.50 | 443 | TCP |

Do **not** forward 3000 or 8000 to the internet.

Give the Ubuntu host a DHCP reservation so the LAN IP does not change.

### 2.3 UFW firewall

**Why:** Only expose 22 (SSH), 80, and 443. Keep Uvicorn/Next bound to localhost when possible.

```bash
sudo apt update
sudo apt install -y ufw

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
# or: sudo ufw allow 22/tcp

sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw enable
sudo ufw status verbose
```

Confirm nothing public is listening on 3000/8000:

```bash
ss -tulpn | grep -E ':80|:443|:3000|:8000'
```

### 2.4 Install Nginx and Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable --now nginx
```

### 2.5 Bind app processes to localhost

For internet-facing production, Uvicorn and Next should listen on `127.0.0.1` so only Nginx is public.

Update the systemd units in §2.7 accordingly (`--host 127.0.0.1`).

If you still need LAN tablets without the domain, either:

- keep Next on `0.0.0.0:3000` **and** restrict with UFW to LAN only, or  
- use the public HTTPS hostname on tablets (preferred; camera needs HTTPS anyway).

### 2.6 Full Nginx site config

Create `/etc/nginx/sites-available/rms`:

```nginx
# /etc/nginx/sites-available/rms
# MotoShop RMS — reverse proxy (HTTP first; Certbot will add SSL)

upstream rms_next {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream rms_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

# Redirect bare HTTP → HTTPS after certificates exist.
# Certbot usually manages this; this block is the pre-cert HTTP vhost.
server {
    listen 80;
    listen [::]:80;
    server_name rms.example.com;

    # Certbot HTTP-01
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        allow all;
    }

    # Temporary: proxy until Certbot runs (or redirect after certs)
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name rms.example.com;

    # --- filled by Certbot (paths below are typical) ---
    ssl_certificate     /etc/letsencrypt/live/rms.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rms.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # --- logging ---
    access_log /var/log/nginx/rms.access.log;
    error_log  /var/log/nginx/rms.error.log warn;

    # --- security headers ---
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;
    # Enable HSTS only after HTTPS is confirmed working:
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # --- compression ---
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 256;
    gzip_proxied any;
    gzip_vary on;
    gzip_types
        text/plain
        text/css
        text/xml
        application/json
        application/javascript
        application/xml
        application/rss+xml
        image/svg+xml
        font/woff2;

    client_max_body_size 25m;  # GCash proof photos / uploads

    # Optional: expose FastAPI docs and versioned API directly
    location /api/v1/ {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 120s;
    }

    location /docs {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /openapi.json {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /uploads/ {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Next.js UI + /api/proxy + /api/auth (must stay on Next)
    location / {
        proxy_pass http://rms_next;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 120s;
        proxy_buffering off;  # streaming / large responses
    }
}
```

Add the WebSocket map once in `/etc/nginx/nginx.conf` inside the `http { }` block (if not already present):

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
```

Enable the site **before** certificates exist. First boot strategy:

1. Temporarily comment out the entire `listen 443` server block, and change the port-80 `location /` to proxy to Next (so Certbot can reach the host).
2. Or use Certbot’s nginx plugin with a minimal HTTP-only server first.

Minimal HTTP-only starter (use this first if Certbot has not run yet):

```nginx
# Temporary /etc/nginx/sites-available/rms (HTTP only)
upstream rms_next {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream rms_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

server {
    listen 80;
    listen [::]:80;
    server_name rms.example.com;

    client_max_body_size 25m;

    location /api/v1/ {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
    }

    location /docs { proxy_pass http://rms_api; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
    location /openapi.json { proxy_pass http://rms_api; proxy_set_header Host $host; }
    location /health { proxy_pass http://rms_api; proxy_set_header Host $host; }
    location /uploads/ { proxy_pass http://rms_api; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }

    location / {
        proxy_pass http://rms_next;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}
```

Enable and test:

```bash
sudo ln -sf /etc/nginx/sites-available/rms /etc/nginx/sites-enabled/rms
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 2.7 systemd units (FastAPI + Next.js)

Create `/etc/systemd/system/rms-api.service`:

```ini
[Unit]
Description=MotoShop RMS FastAPI (Uvicorn)
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=rms
Group=rms
WorkingDirectory=/opt/rms/retail_management_system/backend
Environment=PATH=/opt/rms/retail_management_system/backend/.venv/bin:/usr/bin
EnvironmentFile=-/opt/rms/retail_management_system/backend/.env
ExecStart=/opt/rms/retail_management_system/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/rms/retail_management_system/backend

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/rms-web.service`:

```ini
[Unit]
Description=MotoShop RMS Next.js
After=network.target rms-api.service
Requires=rms-api.service

[Service]
Type=simple
User=rms
Group=rms
WorkingDirectory=/opt/rms/retail_management_system/frontend
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1
# Server-side proxy target used by getBackendUrl()
Environment=BACKEND_URL=http://127.0.0.1:8000
ExecStart=/usr/bin/npm run start -- --hostname 127.0.0.1 --port 3000
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Create the service user and enable:

```bash
sudo useradd --system --home /opt/rms --shell /usr/sbin/nologin rms || true
sudo chown -R rms:rms /opt/rms/retail_management_system

# Ensure backend venv + frontend build exist as user rms (or build as you, then chown)
cd /opt/rms/retail_management_system
sudo -u rms bash -lc 'cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -U pip && .venv/bin/python -m pip install -r requirements.txt'
sudo -u rms bash -lc 'cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.scripts.seed_production'
sudo -u rms bash -lc 'cd frontend && npm ci && npm run build'

sudo systemctl daemon-reload
sudo systemctl enable --now rms-api rms-web
sudo systemctl status rms-api rms-web --no-pager
```

If Postgres is Docker Compose:

```bash
cd /opt/rms/retail_management_system
docker compose up -d
# ensure backend/.env DATABASE_URL points at that Postgres
```

### 2.8 Certbot (Let’s Encrypt) + auto-renewal

With DNS pointing at you and ports 80/443 forwarded:

```bash
sudo certbot --nginx -d rms.example.com
```

Follow prompts (email, agree ToS). Certbot will obtain certs and patch the Nginx SSL server block.

Test renewal (dry run):

```bash
sudo certbot renew --dry-run
```

Ubuntu’s `certbot` package installs a systemd timer:

```bash
systemctl list-timers | grep certbot
sudo systemctl status certbot.timer
```

Reload Nginx after renew (Certbot usually deploys a deploy-hook). Optional hook file `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`:

```bash
#!/bin/bash
systemctl reload nginx
```

```bash
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

### 2.9 CORS / trusted host for your domain

If browsers ever call FastAPI on `/api/v1` directly from `https://rms.example.com`, update `backend/app/main.py` CORS regex to include your hostname (or set an allowlist via env if you add that later).

When traffic stays on Next (`/api/proxy`, `/api/auth`), CORS is less critical, but `/docs` from the public domain still benefits from correct origins.

Also set a strong `SECRET_KEY` and `DEBUG=false` in `backend/.env`.

### 2.10 HTTP/2 and HTTP/3 notes

- **HTTP/2:** Enabled above with `listen 443 ssl http2;` (OpenSSL build on Ubuntu 24.04 + modern Nginx).
- **HTTP/3 (QUIC):** Optional; requires `nginx` with QUIC/HTTP3 packages or Cloudflare orange-cloud. For a home Certbot setup, HTTP/2 is enough. Prefer Cloudflare Tunnel (Section 3) if you want CDN HTTP/3 without local QUIC complexity.

### 2.11 Verify (public IP path)

```bash
# Local upstreams
curl -sS http://127.0.0.1:8000/health
curl -sI http://127.0.0.1:3000 | head

# Through Nginx
curl -sI http://rms.example.com | head
curl -sI https://rms.example.com | head
curl -sS https://rms.example.com/health
curl -sI https://rms.example.com/docs | head

# From a phone off your Wi‑Fi (mobile data) open:
# https://rms.example.com
```

Expected: HTTPS 200 on `/`, login works, barcode camera works on tablets (secure context).

---

## 3. CGNAT path — Cloudflare Tunnel + custom domain (+ optional Nginx)

Use when Section 1 shows CGNAT / no inbound ports.

### 3.1 Advantages vs limitations

| | Port forward + Certbot | Cloudflare Tunnel |
|--|------------------------|-------------------|
| Needs public IPv4 | Yes | No |
| Open router 80/443 | Yes | No |
| ISP blocks inbound | Fails | Works |
| HTTPS certs | Let’s Encrypt on box | Cloudflare edge HTTPS |
| IP exposure | Public IP visible | Origin IP hidden |
| Extra dependency | Router + DynDNS | Cloudflare account + `cloudflared` |
| Latency | Direct | Slightly higher (edge hop) |
| Free tier limits | N/A | Fair use; named tunnels are free for this use case |
| Local LAN access | Still works | Still works on LAN IPs |

### 3.2 Install `cloudflared` (Ubuntu 24.04)

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflare-main jammy main" \
  | sudo tee /etc/apt/sources.list.d/cloudflare.list

sudo apt update
sudo apt install -y cloudflared
cloudflared --version
```

(If Cloudflare’s Ubuntu release name differs, follow the current install page: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)

### 3.3 Login, create tunnel, route DNS

```bash
cloudflared tunnel login
# Opens a browser; authorize the domain zone in Cloudflare DNS

cloudflared tunnel create rms
# Note the Tunnel UUID printed

cloudflared tunnel list
```

Route hostname to the tunnel (creates a Cloudflare DNS CNAME):

```bash
cloudflared tunnel route dns rms rms.example.com
```

In Cloudflare DNS you should see something like:

```text
rms.example.com  CNAME  <TUNNEL-UUID>.cfargotunnel.com  (Proxied / orange cloud)
```

### 3.4 Two topologies

**A — Simple (recommended for this app):** Tunnel → Next.js `:3000` only  
(Next already proxies API. Matches `cloudflare/config.example.yml` in this repo.)

**B — Nginx behind tunnel:** Tunnel → Nginx `:80` → Next + optional FastAPI paths  
(Useful if you want one place for headers, uploads size, `/docs` routing, access logs.)

#### Topology A — tunnel → Next.js

`/etc/cloudflared/config.yml`:

```yaml
tunnel: REPLACE_WITH_TUNNEL_UUID
credentials-file: /home/YOUR_USER/.cloudflared/REPLACE_WITH_TUNNEL_UUID.json

ingress:
  - hostname: rms.example.com
    service: http://127.0.0.1:3000
  - service: http_status:404
```

#### Topology B — tunnel → Nginx → apps

Keep systemd units from §2.7. Install Nginx **without** opening UFW 80/443 to the world.

`/etc/nginx/sites-available/rms-tunnel`:

```nginx
# Local-only Nginx in front of apps (Cloudflare Tunnel terminates HTTPS)
upstream rms_next {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream rms_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

server {
    listen 127.0.0.1:8080;
    server_name rms.example.com;

    access_log /var/log/nginx/rms.access.log;
    error_log  /var/log/nginx/rms.error.log warn;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 256;
    gzip_proxied any;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript application/xml image/svg+xml font/woff2;

    client_max_body_size 25m;

    location /api/v1/ {
        proxy_pass http://rms_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        proxy_read_timeout 120s;
    }

    location /docs {
        proxy_pass http://rms_api;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /openapi.json {
        proxy_pass http://rms_api;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /health {
        proxy_pass http://rms_api;
        proxy_set_header Host $host;
    }

    location /uploads/ {
        proxy_pass http://rms_api;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location / {
        proxy_pass http://rms_next;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/rms-tunnel /etc/nginx/sites-enabled/rms-tunnel
sudo nginx -t && sudo systemctl reload nginx
```

`/etc/cloudflared/config.yml` for topology B:

```yaml
tunnel: REPLACE_WITH_TUNNEL_UUID
credentials-file: /home/YOUR_USER/.cloudflared/REPLACE_WITH_TUNNEL_UUID.json

ingress:
  - hostname: rms.example.com
    service: http://127.0.0.1:8080
  - service: http_status:404
```

HTTPS is terminated at Cloudflare; origin is plain HTTP on localhost. In Cloudflare dashboard → SSL/TLS for the zone, use **Full** (not Flexible) when origin speaks HTTP only on loopback via the tunnel — Cloudflare’s tunnel connector handles the secure path to Cloudflare. Prefer **Full (strict)** only when the origin presents a valid cert (unusual for loopback).

### 3.5 Run `cloudflared` as a systemd service

```bash
sudo cloudflared service install
# Uses /etc/cloudflared/config.yml on many installs

sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -f
```

If `service install` is unavailable, create `/etc/systemd/system/cloudflared.service`:

```ini
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
```

### 3.6 UFW when using Tunnel only

No need to allow 80/443 from the internet:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

### 3.7 Repo helper (optional)

From this project you can also use:

```bash
# after copying cloudflare/config.example.yml → cloudflare/config.yml
./run_prod.sh --with-tunnel named
```

For a permanent shop server, prefer the systemd `cloudflared` unit above so the tunnel survives reboot independently of the Python deploy script.

### 3.8 Verify (Tunnel path)

```bash
curl -sI https://rms.example.com | head
curl -sS https://rms.example.com/health
# Login in a browser over mobile data
```

---

## 4. Logging and troubleshooting

### 4.1 Where to look

```bash
# Apps
sudo journalctl -u rms-api -u rms-web -n 100 --no-pager
sudo journalctl -u cloudflared -n 100 --no-pager

# Nginx
sudo tail -f /var/log/nginx/rms.access.log
sudo tail -f /var/log/nginx/rms.error.log

# Repo deploy logs (if using prod_deploy.py)
tail -f /opt/rms/retail_management_system/logs/prod_*.log
```

### 4.2 Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `dig` shows wrong/old IP | DNS TTL / not updated | Lower TTL, wait, fix A record |
| Certbot: connection refused / timeout | CGNAT or no port 80 forward | Re-run Section 1; use Tunnel |
| 502 Bad Gateway | Next/API down | `systemctl status rms-web rms-api` |
| Login broken / API 404 | Nginx sent `/api` to FastAPI | Route `/` (and Next `/api/*`) to Next only |
| Camera scan blocked | Not HTTPS / insecure context | Use domain HTTPS or Tunnel |
| Works on home Wi‑Fi, not mobile data | Hairpin NAT / only LAN | Test on cellular; fix public path |
| Cloudflare 1033 / 502 | Tunnel down / wrong ingress | `journalctl -u cloudflared`, check UUID + hostname |
| Large upload fails | `client_max_body_size` too small | Raise in Nginx (25m+) |

### 4.3 Quick connectivity checklist

```bash
# 1. Apps up?
curl -sS http://127.0.0.1:8000/health
curl -sI http://127.0.0.1:3000 | head

# 2. Nginx config valid?
sudo nginx -t

# 3. Listening publicly? (port-forward path)
ss -tulpn | grep -E ':80|:443'

# 4. External view (from another network)
curl -sI https://rms.example.com
```

---

## 5. Security best practices

1. **Change default admin password** on first production login.
2. **Strong `SECRET_KEY`**, `DEBUG=false` in `backend/.env`; never commit `.env`.
3. **Do not publish** ports 3000/8000/5432 to the WAN; only 80/443 (or neither, with Tunnel).
4. **SSH:** key-only auth, optionally non-default port + `ufw`; consider `fail2ban`.
5. **Automatic updates:** `sudo apt install unattended-upgrades` and enable.
6. **Backups:** nightly `pg_dump` to `/opt/rms/backups/` and copy off-site.
7. **Least privilege:** run apps as `rms`, not root.
8. **HSTS** only after HTTPS is stable (included in Nginx sample).
9. **Cloudflare:** enable WAF managed rules if on a paid plan; always keep orange-cloud on the tunnel hostname.
10. **Uploads:** keep `client_max_body_size` bounded; store proofs outside the web root if you harden further.
11. **Postgres:** bind to Docker/private network only; strong password.
12. Prefer **Tunnel on Converge** unless you confirmed a real public IP and stable port forwards.

---

## 6. Decision flowchart

```text
Compare router WAN IP vs curl public IP
            |
            +-- equal --> Port forward 80/443
            |               DNS A record
            |               Nginx + Certbot + UFW + systemd
            |
            +-- differ / CGNAT --> Cloudflare Tunnel
                                    DNS CNAME via `tunnel route dns`
                                    systemd cloudflared
                                    (optional) local Nginx on 127.0.0.1:8080
```

---

## 7. Minimal “day-2” ops cheatsheet

```bash
# Restart apps
sudo systemctl restart rms-api rms-web

# Deploy new code
cd /opt/rms/retail_management_system
git pull
sudo -u rms bash -lc 'cd backend && .venv/bin/python -m pip install -r requirements.txt && .venv/bin/alembic upgrade head'
sudo -u rms bash -lc 'cd frontend && npm ci && npm run build'
sudo systemctl restart rms-api rms-web

# Cert renewal check
sudo certbot renew --dry-run

# Tunnel status
sudo systemctl status cloudflared
```

This guide matches this repository’s routing model. If you later split a dedicated API hostname (`api.example.com`), point that hostname at FastAPI only and keep the UI hostname on Next.js.
