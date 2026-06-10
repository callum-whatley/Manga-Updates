# Manga Updates

A personal manga tracking app with a Flask backend, Vue 3 frontend, and Android app via Capacitor.

---

## Deploying to a VPS

### 1. Domain & HTTPS

1. Register a domain and add it to Cloudflare.
2. Create an **A record** pointing your domain (e.g. `manga.yourdomain.com`) at your VPS IP.
3. Enable the Cloudflare proxy (orange cloud). Cloudflare terminates HTTPS automatically — no Certbot setup needed. Your server only needs to accept HTTP on port 80.

### 2. OAuth credentials

In **Google Cloud Console** ([console.cloud.google.com](https://console.cloud.google.com)), add these as authorised redirect URIs:
```
https://manga.yourdomain.com/auth/google/callback
https://manga.yourdomain.com/auth/google/login/callback
```

In **GitHub Developer Settings** ([github.com/settings/developers](https://github.com/settings/developers)), set the callback URL to:
```
https://manga.yourdomain.com/auth/github/callback
https://manga.yourdomain.com/auth/github/login/callback
```

### 3. Server setup

SSH into the VPS, clone the repo, then create the environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in all values. Both `FRONTEND_URL` and `BACKEND_URL` should be the same public URL:

```
FRONTEND_URL=https://manga.yourdomain.com
BACKEND_URL=https://manga.yourdomain.com
```

### 4. Start the stack

```bash
docker compose up -d --build
```

This starts three containers:
- **db** — PostgreSQL (data persisted in a named Docker volume)
- **backend** — Flask + Gunicorn (runs DB migrations automatically on startup)
- **frontend** — nginx serving the built Vue app and proxying `/api` and `/auth` to the backend

The app will be available at `https://manga.yourdomain.com`.

### 5. Make yourself an admin

```bash
docker compose exec backend flask user make-admin your@email.com
```

---

## Building the Android APK

The APK bundles the frontend assets and talks directly to the deployed backend.

### 1. Prerequisites

- [Android Studio](https://developer.android.com/studio) installed
- Java 17+
- Node.js + Yarn

### 2. Point the app at your backend

Edit `frontend/.env.capacitor`:

```
VITE_API_URL=https://manga.yourdomain.com
VITE_APP_BASE=./
```

For local development against a backend running on your machine, use:
- **Android emulator:** `http://10.0.2.2:5001` (emulator's alias for host localhost)
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
cp .env.example .env        # fill in values
flask db upgrade
python run.py               # runs on http://localhost:5001

# Frontend
cd frontend
yarn
yarn dev                    # runs on http://localhost:5173, proxies /api to :5001
```
