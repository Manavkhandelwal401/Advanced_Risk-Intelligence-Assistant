# ARIA - Advanced Risk Intelligence Assistant

ARIA is a Streamlit financial risk dashboard for startups and small businesses. It includes authenticated accounts, CSV upload, SQLite storage, risk scoring, interactive charts, AI recommendations, saved report history, exports, and optional email delivery.

## Features

- Streamlit web app with register/login, forgot password, Google reCAPTCHA, and email OTP verification
- Per-user SQLite financial data
- Flexible CSV upload with required `date`, `revenue`, `expenses`
- Safe extra columns; `orders` is preserved, unrelated columns are stored as metadata
- Multi-file upload with duplicate-date handling
- Interactive Plotly charts with hover, zoom, pan, and responsive sizing
- Dark/light compatible UI styling
- Saved report history with TXT/JSON/CSV downloads
- Optional Groq AI recommendations with rule-based fallback
- Optional SMTP email delivery to the registered user email
- Pure downloads; report email is sent only from the explicit save/send action

## Project Structure

```text
ARIA_final/
├── app.py
├── auth.py
├── config.py
├── setup_db.py
├── daily_runner.py
├── requirements.txt
├── .env.example
├── sample_data.csv
├── database/
├── llm/
├── models/
├── notifications/
└── workflows/
```

## Local Run Steps

```powershell
cd ARIA_final
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python setup_db.py
streamlit run app.py
```

Open the Streamlit URL, usually `http://localhost:8501`.

## Environment Variables

Copy `.env.example` to `.env` and configure only the values you need.

```env
APP_ENV=development
APP_SECRET=
ARIA_DB_PATH=aria.db
GROQ_API_KEY=
CLOUD_MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct
EMAIL_DEV_MODE=true
EMAIL_SENDER=
EMAIL_PASSWORD=
EMAIL_RECEIVER=
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
RECAPTCHA_USE_TEST_KEYS=true
RECAPTCHA_SITE_KEY=
RECAPTCHA_SECRET_KEY=
```

Notes:
- Leave `GROQ_API_KEY` empty if you only need dashboard/risk features.
- Keep `EMAIL_DEV_MODE=true` for localhost testing without SMTP; the OTP appears in the UI but is still hashed, expires, and must be verified.
- Set `EMAIL_DEV_MODE=false` and `EMAIL_SENDER` to the Gmail account or SMTP mailbox that will send OTP/report emails when testing real delivery.
- Use a Gmail App Password for `EMAIL_PASSWORD`; never use or commit a real account password.
- Set `APP_SECRET` to a random value of at least 32 characters. OTP hashes depend on it.
- Set Google reCAPTCHA v2 checkbox site/secret keys before allowing public registration or password reset.
- For localhost demos, keep `RECAPTCHA_USE_TEST_KEYS=true`; ARIA uses a clean local verification gate instead of Google's public test widget.
- For staging/production, set `RECAPTCHA_USE_TEST_KEYS=false`, create a Google reCAPTCHA v2 checkbox key pair, add your deployed host, for example `your-app.streamlit.app`, and set both `RECAPTCHA_SITE_KEY` and `RECAPTCHA_SECRET_KEY`.
- If reCAPTCHA shows `ERROR for site owner: Invalid site key`, the site key does not belong to the current domain or is not a v2 checkbox key. Create a new v2 checkbox key pair and update both frontend site key and backend secret key together.
- Saved report emails are sent to the signed-in user's registered email.
- `EMAIL_RECEIVER` is only for `daily_runner.py` fixed high-risk alerts.

## Database Setup

Run:

```powershell
python setup_db.py
```

The app also verifies tables at startup. A fresh clone starts with an empty database. Register a user, upload data, then save reports to populate history.

`ARIA_DB_PATH` controls where SQLite is stored. Relative paths are resolved from the project root. Runtime database files are ignored by Git.

## CSV Upload Guide

Required columns:

```csv
date,revenue,expenses
2024-01-01,120000,85000
```

Allowed optional columns:

```csv
date,revenue,expenses,orders,channel
2024-01-01,120000,85000,42,Direct
```

Rules:
- Dates must be `YYYY-MM-DD`.
- Revenue, expenses, and orders must be non-negative numbers.
- Extra columns are accepted and stored as metadata.
- Multiple files are combined into one upload batch.
- Duplicate dates inside the batch are summed.
- Existing saved dates are skipped by default unless you choose replace.
- Files above 25 MB should be split before upload.

## Fresh-System Setup

```powershell
git clone <your-repo-url>
cd ARIA_final
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python setup_db.py
streamlit run app.py
```

Then register a business account and upload `sample_data.csv`.

## Deployment Steps

For Streamlit Community Cloud:

1. Push this folder to GitHub without `.env`, `.venv`, databases, caches, or `__pycache__`.
2. Create a new Streamlit app from the GitHub repo.
3. Set the app entrypoint to `app.py`.
4. Add secrets/environment values in Streamlit Cloud settings:

```toml
APP_ENV = "production"
ARIA_DB_PATH = "aria.db"
GROQ_API_KEY = ""
CLOUD_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
EMAIL_SENDER = ""
EMAIL_PASSWORD = ""
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = "587"
APP_SECRET = ""
RECAPTCHA_SITE_KEY = ""
RECAPTCHA_SECRET_KEY = ""
RECAPTCHA_USE_TEST_KEYS = "false"
```

5. Deploy and register the first business account in the running app.

SQLite on Streamlit Cloud is suitable for demos and portfolio use. For multi-user production, move to a managed database.

Required external services:
- Google reCAPTCHA v2 checkbox: `RECAPTCHA_SITE_KEY` is used by the Streamlit component; `RECAPTCHA_SECRET_KEY` is used only by the server verifier in `verification.py`.
- SMTP mailbox: `EMAIL_SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER`, and `SMTP_PORT` are required for registration OTP, password reset OTP, and report email delivery.
- Groq: `GROQ_API_KEY` is optional. When missing or unavailable, ARIA uses the built-in rule-based recommendation fallback.

## GitHub Upload Steps

```powershell
git init
git add .
git status
git commit -m "Prepare ARIA Streamlit app"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

Before pushing, confirm these are not tracked:

```powershell
git status --ignored
```

Do not commit `.env`, `.venv`, `*.db`, `*.db-wal`, `*.db-shm`, `.matplotlib_cache`, or `__pycache__`.

## Report and Email Workflow

- `Save Report and Send Email` stores the report in SQLite and attempts email delivery.
- `Download Complete Report TXT` only downloads the file and does not send email.
- History shows saved reports, email status, report text, JSON, and downloads.
- If SMTP is missing or invalid, the report still saves and email status is recorded as `not_sent`.

## Troubleshooting

- If AI fails, set `GROQ_API_KEY` or use the built-in fallback.
- If email fails, check `EMAIL_SENDER`, `EMAIL_PASSWORD`, SMTP host/port, and Gmail App Password setup.
- If the app starts empty, register a user and upload `sample_data.csv`.
- If database errors appear, delete local runtime `.db` files and rerun `python setup_db.py`.
