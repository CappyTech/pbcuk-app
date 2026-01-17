# AI Coding Agent Guide for pbcuk-app

## Big Picture
- Django 5 project with apps: `core`, `quotes`, `accounts`.
- Active settings: [pbcuk/settings.py](pbcuk/settings.py). [config/settings.py](config/settings.py) is a shim importing `pbcuk.settings`.
- URL entrypoints: [pbcuk/urls.py](pbcuk/urls.py) includes `core`, `quotes` (namespace `quotes`) and `accounts` (namespace `accounts`).
- Payments: Stripe checkout + webhook; optional bank transfer details via env or `CompanyDetails` model.
- Static files: Served via WhiteNoise when `DEBUG=0`; Tailwind CSS pipeline outputs to `static/dist/tailwind.css`.
- Admin: Jazzmin configured in settings for an improved admin UI.

## Workflows
- Local dev (PowerShell): create venv, install, migrate, run:
  ```powershell
  py -3 -m venv .venv; . .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt
  python manage.py migrate
  python manage.py runserver
  ```
- Frontend (Tailwind): build or watch from [package.json](package.json).
  ```bash
  npm run tailwind:build
  npm run tailwind:watch
  ```
  Input: [static/src/tailwind.css](static/src/tailwind.css) → Output: `static/dist/tailwind.css`; content paths in [tailwind.config.js](tailwind.config.js).
- Docker (compose): [docker-compose.yml](docker-compose.yml) runs `web` (gunicorn) + `db` (Postgres). Common maintenance:
  ```bash
  docker compose up --build
  docker compose exec web python manage.py migrate
  docker compose exec web python manage.py collectstatic --noinput
  ```
- Tests: use Django test runner.
  ```bash
  python manage.py test
  ```

## Configuration & Env
- DB selection: `DATABASE_URL` (postgres) or `POSTGRES_HOST` → Postgres; otherwise SQLite [db.sqlite3](db.sqlite3).
- Reverse proxy/SSL: `USE_X_FORWARDED_HOST` and `SECURE_PROXY_SSL_HEADER` set; set `CSRF_TRUSTED_ORIGINS` for HTTPS domains.
- Email: console backend in dev; `DEFAULT_FROM_EMAIL` set in [pbcuk/settings.py](pbcuk/settings.py).
- Stripe keys in env: `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- Card fee logic controls: `STRIPE_FEE_PERCENT`, `STRIPE_FEE_FIXED`, `STRIPE_FEE_GROSS_UP`.
- Bank transfer env defaults; overridden by [core/models.py](core/models.py) `CompanyDetails` if present.

## Domain Logic Highlights
- Quotes: `Quote` auto-generates `reference` and supports 15‑minute acceptance reservations (`reservation_*` fields) [quotes/models.py](quotes/models.py).
- Invoices: `Invoice.create_from_quote()` and `InvoiceEvent.record()` drive build/shipping progress and customer notifications [quotes/models.py](quotes/models.py).
- Payments: `InvoicePayment` auto-marks `Invoice` paid when completed payments ≥ invoice total [quotes/models.py](quotes/models.py).
- Accounts flow: email verification gating; invoices list/detail and card payments via Stripe [accounts/urls.py](accounts/urls.py), [accounts/views.py](accounts/views.py).

## Key Endpoints
- Public quotes: `/q/<token>/`, `/q/<token>/accept/`, `/q/<token>/thanks/` [quotes/urls.py](quotes/urls.py).
- Invoice ops: `/q/invoice/<number>/pdf/`, `mark-paid`, `add-payment`, `webhook` [quotes/urls.py](quotes/urls.py).
- Customer pages: `/accounts/login`, `/accounts/register`, `/accounts/invoices/<number>` and payment routes [accounts/urls.py](accounts/urls.py).
- Stripe webhook: `/accounts/stripe/webhook/` (configure in Stripe dashboard to post events like `checkout.session.completed`).

## Static & Deployment
- For production, run `collectstatic` and serve via WhiteNoise; Caddyfile present for reverse proxy/TLS; ensure `CSRF_TRUSTED_ORIGINS` includes your HTTPS domains.

## Tips for Contributions
- Favor `pbcuk.settings` for any configuration; keep env‑driven behavior consistent with existing patterns.
- When adding invoice/quote features, use `InvoiceEvent.record()` for customer notifications and progress tracking.
- For new templates, include utility classes aligned with Tailwind and rebuild `static/dist/tailwind.css`.
