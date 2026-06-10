# Manga Updates

A personal manga tracking app with a Flask backend, Vue 3 frontend, and Android app via Capacitor.

---

## Deploying to Fly.io

### 1. Install flyctl

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Choose app names

Fly app names are globally unique. Pick names for your backend and frontend (e.g. `manga-backend-callum` and `manga-frontend-callum`), then update both fly.toml files and the frontend's internal URL reference:

**`backend/fly.toml`** — set `app`:
```toml
app = "your-backend-name"
```

**`frontend/fly.toml`** — set `app` and `BACKEND_INTERNAL_URL`:
```toml
app = "your-frontend-name"

[env]
  BACKEND_INTERNAL_URL = "http://your-backend-name.internal:5001"
```

### 3. Deploy the backend

```bash
cd backend
fly deploy
```

Set secrets (Fly encrypts and injects these as environment variables at runtime):

```bash
fly secrets set \
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  GOOGLE_CLIENT_ID=your_id \
  GOOGLE_CLIENT_SECRET=your_secret \
  GITHUB_CLIENT_ID=your_id \
  GITHUB_CLIENT_SECRET=your_secret \
  FRONTEND_URL=https://your-frontend-name.fly.dev \
  BACKEND_URL=https://your-backend-name.fly.dev
```

### 4. Provision Postgres

```bash
fly postgres create --name manga-db --region lhr
fly postgres attach manga-db --app your-backend-name
```

This automatically sets `DATABASE_URL` on the backend. Then run migrations:

```bash
fly ssh console --app your-backend-name -C "flask db upgrade"
```

### 5. Deploy the frontend

```bash
cd ../frontend
fly deploy
```

### 6. Set OAuth redirect URIs

In **Google Cloud Console**, add as authorised redirect URIs:
```
https://your-backend-name.fly.dev/auth/google/callback
https://your-backend-name.fly.dev/auth/google/login/callback
```

In **GitHub Developer Settings**, set the callback URL to:
```
https://your-backend-name.fly.dev/auth/github/callback
https://your-backend-name.fly.dev/auth/github/login/callback
```

### 7. Make yourself an admin

```bash
fly ssh console --app your-backend-name -C "flask user make-admin your@email.com"
```

---

## Building the Android APK

The APK bundles the frontend assets and talks to the deployed backend via the frontend proxy.

### 1. Prerequisites

- [Android Studio](https://developer.android.com/studio) installed
- Java 17+
- Node.js + Yarn

### 2. Point the app at your deployment

Edit `frontend/.env.capacitor`:

```
VITE_API_URL=https://your-frontend-name.fly.dev
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
