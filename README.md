# autoroster

Upload a screenshot of your shift roster and have it automatically added to your Google or iCloud Calendar.

Shift codes supported: **A** (Day 07:00–19:00), **N** (Night 19:00–07:00), **P** (Afternoon 15:00–23:00). Day Off (DO) entries are ignored.

---

## Setup & deployment

### 1. Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a new project (or select an existing one).
2. Enable the following APIs — search for each in **APIs & Services → Library**:
   - **Google Calendar API**
   - **Cloud Run API**
   - **Cloud Build API**
   - **Artifact Registry API**

### 2. Google OAuth credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Set Application type to **Web application**.
3. Under **Authorised redirect URIs** add a placeholder for now — you'll update it with the real URL after deploying:
   ```
   https://YOUR_SERVICE_URL/auth/google/callback
   ```
4. Download the credentials or note the **Client ID** and **Client Secret**.
5. Go to **APIs & Services → OAuth consent screen** and publish the app (or add your email as a test user while in development).

### 3. Apple Sign In (optional — skip if using Google only)

1. Sign in to [developer.apple.com](https://developer.apple.com/account).
2. Go to **Identifiers → +** and register a **Services ID** (e.g. `com.yourname.autoroster`). This is your `APPLE_CLIENT_ID`.
3. Enable **Sign In with Apple**, click **Configure**, and add your domain and return URL:
   ```
   https://YOUR_SERVICE_URL/auth/apple/callback
   ```
4. Go to **Keys → +**, enable **Sign In with Apple**, and download the `.p8` private key file. Note the **Key ID** and your **Team ID** (shown top-right on the developer portal).

### 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

```dotenv
SECRET_KEY=<random string — run: openssl rand -hex 32>

GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxx
GOOGLE_REDIRECT_URI=https://YOUR_SERVICE_URL/auth/google/callback

# Apple (leave blank if not using Apple Sign In)
APPLE_CLIENT_ID=com.yourname.autoroster
APPLE_TEAM_ID=XXXXXXXXXX
APPLE_KEY_ID=XXXXXXXXXX
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
APPLE_REDIRECT_URI=https://YOUR_SERVICE_URL/auth/apple/callback
```

### 5. Deploy to Google Cloud Run

Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and authenticate:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Build and deploy in one command:

```bash
gcloud run deploy autoroster \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 60 \
  --set-env-vars "SECRET_KEY=$(openssl rand -hex 32)" \
  --set-env-vars "GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com" \
  --set-env-vars "GOOGLE_CLIENT_SECRET=xxxx" \
  --set-env-vars "GOOGLE_REDIRECT_URI=https://YOUR_SERVICE_URL/auth/google/callback" \
  --set-env-vars "APPLE_CLIENT_ID=com.yourname.autoroster" \
  --set-env-vars "APPLE_TEAM_ID=XXXXXXXXXX" \
  --set-env-vars "APPLE_KEY_ID=XXXXXXXXXX" \
  --set-env-vars "APPLE_PRIVATE_KEY=$(cat AuthKey_XXXX.p8 | awk 'NF {printf "%s\\n", $0}')" \
  --set-env-vars "APPLE_REDIRECT_URI=https://YOUR_SERVICE_URL/auth/apple/callback"
```

`--source .` tells Cloud Run to build the Docker image automatically using Cloud Build — no separate build step needed.

After the first deploy, Cloud Run gives you a permanent URL like `https://autoroster-xxxx-uc.a.run.app`. Substitute this for `YOUR_SERVICE_URL` above and redeploy with the correct redirect URIs set.

### 6. Update OAuth redirect URIs

Once you have your permanent service URL:

- **Google**: Go back to **APIs & Services → Credentials → your OAuth client** and replace the placeholder with the real callback URL.
- **Apple**: Go to **Identifiers → your Services ID → Sign In with Apple → Configure** and update the Return URL.

### 7. Subsequent deploys

```bash
gcloud run deploy autoroster --source . --region us-central1
```

---

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr
cp .env.example .env  # fill in credentials with localhost redirect URIs
python app.py
```

The app will be available at `http://localhost:5000`. Use `http://localhost:5000/auth/google/callback` as the redirect URI in your Google OAuth client for local development.
