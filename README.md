# pbcuk-app (Django)

A minimal Django 5 project scaffold with a `core` app and a simple homepage.

## Quickstart (Windows PowerShell)

```powershell
# From the repo root
# 1) Create venv (once)
if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }

# 2) Activate venv for this session (option A)
#    If activation is blocked by execution policy, use option B below
. .\.venv\Scripts\Activate.ps1

# 2B) If activation fails due to execution policy, temporarily allow scripts:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1

# 3) Install dependencies
python -m pip install -r requirements.txt

# 4) Run migrations and start server
python manage.py migrate
python manage.py runserver
```

If you prefer not to activate the venv, you can call the venv’s Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

## Project Structure
- `manage.py`: Project runner
- `config/`: Project settings and URLs
- `core/`: Example app with a simple homepage

## Notes
- Default DB is SQLite (`db.sqlite3`).
- Timezone is set to `Europe/London` and language to `en-gb`.
 - Static URL now uses leading slash (`/static/`). In production or when `DEBUG=0`, static files are served via WhiteNoise (added middleware). Run `python manage.py collectstatic` before deploying or building production images.

## Docker

```bash
docker compose up --build
```

This starts:
- `web`: Django app (auto-migrates then runs dev server on 8000)
- `postgres`: Primary relational DB (PostgreSQL 16)

Environment variables come from `.env` (see `.env.example`). If `POSTGRES_HOST` or `DATABASE_URL` is present the app uses Postgres; otherwise it falls back to SQLite.

Static files are collected into `static_root` during the image build (multi-stage Dockerfile builds Tailwind first if scripts exist).

## Production (Caddy + Gunicorn)

Files:
- `docker-compose.prod.yml`: runs `web` with gunicorn, `postgres`, and `caddy` as reverse proxy/static server.
- `Caddyfile`: domain placeholders `{$CADDY_DOMAIN}` and `{$CADDY_EMAIL}`; serves `/static/*` and proxies to `web:8000`.

Quick start (after setting `.env` with real secrets and domain):

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

Notes:
- `web` runs `migrate` and `collectstatic` at startup and serves via gunicorn.
- `caddy` terminates TLS automatically (Let’s Encrypt) and serves static files from the shared `static_data` volume.
- Set `CSRF_TRUSTED_ORIGINS` to include your HTTPS domain(s) to avoid CSRF errors.

## Payments (Stripe + Bank Transfer)

Add your Stripe test keys to `.env`:

```
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Optional Stripe fee configuration (defaults shown):

```
# If STRIPE_FEE_GROSS_UP=true, the card charge is increased so that the net after fees ≈ the invoice amount.
STRIPE_FEE_PERCENT=2.9
STRIPE_FEE_FIXED=0.20
STRIPE_FEE_GROSS_UP=true
```

Bank transfer details (shown on Payment Methods page). These can be provided via settings or, if present, the `CompanyDetails` model fields with matching names will be preferred.

```
COMPANY_BANK_NAME=Your Bank plc
COMPANY_BANK_ACCOUNT_NAME=Prebuilt Computers UK
COMPANY_BANK_ACCOUNT_NUMBER=12345678
COMPANY_BANK_SORT_CODE=12-34-56
COMPANY_BANK_IBAN=GB00BARC00000012345678
COMPANY_BANK_BIC=BARCGB22
```

Flow:
1. Visit an unpaid invoice detail page while authenticated.
2. Click "Payment Methods" to see options.
3. Pay by card (Stripe): a card processing fee line is added; total charge = invoice outstanding + fee.
4. Or pay by bank transfer using the displayed account details and invoice number as the reference.
5. After successful card payment, Stripe redirects to `/accounts/invoices/<number>/pay/success/`.
6. Webhook (`/accounts/stripe/webhook/`) finalizes the payment status server-side.

Create a Stripe webhook endpoint pointing to: `https://yourdomain/accounts/stripe/webhook/` with events: `checkout.session.completed`.

Local Test Commands (PowerShell):

```powershell
# Install deps
python -m pip install -r requirements.txt

# Run server
python manage.py runserver

# In separate terminal start Stripe CLI forwarding webhook
stripe listen --forward-to localhost:8000/accounts/stripe/webhook/
```

Use test card: `4242 4242 4242 4242` with any future expiry, CVC, and UK postcode.

 