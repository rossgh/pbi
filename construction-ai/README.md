# BuildMate AI — AI assistant for construction companies

A working Flask web app that gives construction teams (GCs, subs, PMs, superintendents, estimators, safety
officers) an AI assistant for the paperwork and field problems they hit every week — with full account
management: email/password, Google and Microsoft sign-in, email verification, password reset, profiles,
company workspaces and team invites.

## Features

**Accounts & security**
- Register with email + password (strength rules), or one-click **Google** / **Microsoft** sign-in
- Email verification (resend from the banner), **forgot / reset password** (1-hour, single-use links)
- Login lockout after repeated failures, "keep me signed in", safe `next` redirects, CSRF on every form
- Profile: name, job title, trade/role, phone, preferred units (imperial/metric)
- Change email (confirmed via link to the new address), change or set password
- Connect / disconnect Google & Microsoft (you can't remove your last sign-in method)
- **Sign out of all devices**; password reset also signs out everywhere
- Delete account (blocked for company owners until ownership is transferred)

**Company workspaces & teams**
- Every account belongs to a company; new sign-ups create one (OAuth users get a short onboarding step)
- Owners/admins invite teammates by email (7-day links), promote/demote admins, remove members, revoke invites
- Owners can transfer ownership; members can leave

**AI tools for common construction problems**
| Tool | What it does |
|---|---|
| Site Assistant | Chat about codes, methods, scheduling, crew and supplier issues |
| RFI Writer | Field question → formal, numbered RFI |
| Daily Site Report | Rough notes → clean daily log |
| Safety Toolbox Talk & JHA | Job hazard analysis table + 5-minute talk |
| Change Order Drafter | Scope change with cost breakdown, markup and time impact |
| Delay & Schedule Recovery | Delay classification, notice letter, recovery plan |
| Punch List Organizer | Walk-through notes → list grouped by trade & priority |
| Material Estimator | Quantity takeoff with formulas and waste |
| Contract & Spec Explainer | Plain-English clause review with risk flags |
| Client & Sub Communicator | Professional emails for tricky situations |
| Field Calculators | Concrete, block/brick, drywall, paint, studs (instant, no AI needed) |

Every tool output opens as a conversation, so you can keep refining it. Answers are tailored to the
user's company, region, trade and units.

## Quick start

```bash
cd construction-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # optional — the app runs without any keys
python wsgi.py              # http://localhost:5000
```

With no keys configured the app runs fully in **demo mode**:
- AI tools produce template-based drafts (real, usable output — not an LLM).
- Emails aren't sent; verification / reset / invite links are shown on screen and logged.
- Google / Microsoft buttons are hidden until their credentials are set.

Run the tests: `pytest`

## Configuration

All settings are environment variables (see `.env.example`).

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | **Required in production.** Long random string. |
| `DATABASE_URL` | SQLAlchemy URL; defaults to SQLite in `instance/`. Use Postgres in production. |
| `BASE_URL` | Public URL used in emailed links. |
| `SESSION_COOKIE_SECURE` | `true` when served over HTTPS. |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Use Claude (default model `claude-opus-5-5`). |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Use OpenAI. |
| `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT` | Use Azure OpenAI. |
| `AI_PROVIDER` | Force `anthropic`, `openai`, `azure` or `demo` (otherwise auto-detected). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Enable Google sign-in. |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` / `MICROSOFT_TENANT` | Enable Microsoft sign-in. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM` | SMTP for real emails. |

### Setting up Google sign-in
1. Google Cloud Console → APIs & Services → Credentials → *Create OAuth client ID* (Web application).
2. Authorized redirect URI: `http://localhost:5000/auth/oauth/google/callback` (plus your production URL).
3. Put the client ID/secret in `.env`. Open the app at `http://localhost:5000` (not `127.0.0.1`).

### Setting up Microsoft sign-in
1. Microsoft Entra admin center → App registrations → New registration.
   Supported account types: *any organizational directory and personal Microsoft accounts* (for `common`).
2. Redirect URI (Web): `http://localhost:5000/auth/oauth/microsoft/callback`.
3. Certificates & secrets → New client secret. Put the ID/secret in `.env`.

Microsoft doesn't guarantee the email claim is verified, so a Microsoft login never auto-links to an
existing password account — the user signs in with their password and connects Microsoft from
**Settings → Security**. Google logins with a verified email do link automatically.

## Production deployment

```bash
gunicorn --bind=0.0.0.0:8000 --timeout 120 wsgi:app
```

Set `SECRET_KEY`, `DATABASE_URL` (Postgres), `BASE_URL`, `SESSION_COOKIE_SECURE=true`, SMTP settings,
`DEV_SHOW_EMAIL_LINKS=false`, and an AI key. Tables are created automatically on first start; add
Alembic/Flask-Migrate before evolving the schema in production. Replace the placeholder Terms and
Privacy pages with reviewed legal text.

## Project layout

```
construction-ai/
├── wsgi.py                  # entry point (dev server + gunicorn)
├── buildmate/
│   ├── __init__.py          # app factory, dashboard, markdown sanitising
│   ├── config.py            # env-driven settings
│   ├── models.py            # Company, User, OAuthAccount, Invite, Conversation, Message
│   ├── security.py          # signed tokens, password policy, safe redirects
│   ├── mailer.py            # SMTP or dev-mode email
│   ├── forms.py
│   ├── auth/routes.py       # login, register, OAuth, verify, reset, onboarding, invites
│   ├── account/routes.py    # profile, security, company, team
│   ├── ai/                  # tools, providers (Anthropic/OpenAI/Azure), demo mode, chat API
│   ├── templates/
│   └── static/
└── tests/test_app.py
```
