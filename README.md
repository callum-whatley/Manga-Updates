# Manga Updates

A personal manga tracking app with a Flask backend, Vue 3 frontend, and Android app via Capacitor.

---

## Deploying (self-hosted)

The app runs on a home server behind Cloudflare. Cloudflare terminates HTTPS and proxies HTTP to port 80 on your machine — your server only needs to serve plain HTTP.

### 1. DNS

In the Cloudflare dashboard for `mangatrack.uk`:
1. Add an **A record**: name `@`, value = your home IP address
2. Enable the **orange cloud** (proxy) on that record

Your home IP is hidden from the public and Cloudflare handles HTTPS automatically.

### 2. Keep the IP updated (ddclient)

Home IPs change occasionally. Install `ddclient` on the server to auto-update the Cloudflare record:

```bash
sudo apt install ddclient
```

Create a Cloudflare API token with **Zone:DNS:Edit** permission for `mangatrack.uk` (Cloudflare dashboard → My Profile → API Tokens), then configure `/etc/ddclient.conf`:

```
protocol=cloudflare
use=web
zone=mangatrack.uk
login=your@cloudflare-email.com
password=your-cloudflare-api-token
mangatrack.uk
```

```bash
sudo systemctl enable --now ddclient
```

### 3. Port forwarding

On your router, forward **port 80** to your server's local IP. Port 443 is not needed — Cloudflare handles that.

### 4. OAuth credentials

In **Google Cloud Console** ([console.cloud.google.com](https://console.cloud.google.com)), add these as authorised redirect URIs:
```
https://mangatrack.uk/auth/google/callback
https://mangatrack.uk/auth/google/login/callback
```

In **GitHub Developer Settings** ([github.com/settings/developers](https://github.com/settings/developers)), set the callback URL to:
```
https://mangatrack.uk/auth/github/callback
https://mangatrack.uk/auth/github/login/callback
```

### 5. Server setup

Clone the repo on the server, then create the environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in all values. The URLs are already set to `mangatrack.uk`.

### 6. Start the stack

```bash
docker compose up -d --build
```

This starts three containers:
- **db** — PostgreSQL (data persisted in a named Docker volume)
- **backend** — Flask + Gunicorn (runs DB migrations automatically on startup)
- **frontend** — Caddy serving the built Vue app and proxying `/api` and `/auth` to the backend

The app will be available at `https://mangatrack.uk`.

### 7. Make yourself an admin

```bash
docker compose exec backend flask user make-admin your@email.com
```

---

## Building the Android APK

The APK bundles the frontend assets and talks to the deployed backend.

### 1. Prerequisites

- [Android Studio](https://developer.android.com/studio) installed
- Java 17+
- Node.js + Yarn

### 2. Point the app at the backend

Edit `frontend/.env.capacitor`:

```
VITE_API_URL=https://mangatrack.uk
VITE_APP_BASE=./
```

For local development against a backend running on your machine, use:
- **Android emulator:** `http://10.0.2.2:5001`
- **Physical device on same network:** `http://<your-machine-ip>:5001`

### 3. Build and sync

```bash
cd frontend
yarn cap:sync        # builds the frontend and syncs assets into android/
npx cap open android # opens Android Studio
```

### 4. Generate the APK

In Android Studio:
1. **Build → Generate Signed App Bundle / APK**
2. Choose **APK**
3. Create or select a keystore
4. Select **release** build variant
5. Click **Finish**

The signed APK will be in `android/app/release/`.

---

## Local development

```bash
# Backend
cd backend
source .venv/bin/activate   # or create one: python -m venv .venv
pip install -r requirements.txt
flask db upgrade
python run.py               # runs on http://localhost:5001

# Frontend
cd frontend
yarn
yarn dev                    # runs on http://localhost:5173, proxies /api to :5001
```
