# Jigayasa — Smart Hybrid LMS Platform

Django 6 + DRF backend for a hybrid LMS (self-paced, live, paid market training,
IoT smart classrooms, recordings, payments, analytics, AI). API-first, JWT auth,
multi-tenant ready.

## Status

**Phase 1 — Authentication & Access Control** is implemented. Remaining PRD
modules are scaffolded as the blueprint below.

## Quick start

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env            # then edit DB creds / SECRET_KEY

# Ensure the MySQL database in .env exists, then:
python manage.py migrate
python manage.py createsuperuser     # prompts for EMAIL (custom user model)
python manage.py runserver
```

- Interactive API docs: http://127.0.0.1:8000/api/docs/
- Admin: http://127.0.0.1:8000/admin/

## Auth API (Phase 1) — base `/api/v1/auth/`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `register/` | Email/password signup (role: student/trainer) |
| POST | `login/` | JWT obtain (access + refresh); logs login activity |
| POST | `token/refresh/` | Refresh access token |
| POST | `logout/` | Blacklist refresh token |
| GET/PATCH | `me/` | Current user profile |
| POST | `otp/request/`, `otp/verify/` | **Scaffolded (501)** |
| POST | `social/` | **Scaffolded (501)** |
| POST | `password-reset/`, `password-reset/confirm/` | **Scaffolded (501)** |

## Architecture

- **Custom user model** (`accounts.User`) — email login, no username, with
  `role`, `phone`, and `organization` fields already present for future flows.
- **RBAC** — `Role` choices (admin/trainer/student/institution) + reusable DRF
  permissions in `core/permissions.py` (`IsAdmin`, `IsTrainer`, `IsStudent`,
  `IsInstitution`, `HasRole(*roles)`).
- **JWT** via `djangorestframework-simplejwt` with rotation + blacklist
  (multi-device logout, session timeout).
- **Multi-tenant seam** — `core.Organization` (nullable FK on user) for
  institutions/corporate clients.
- **Shared base** — `core.TimeStampedModel` for `created_at`/`updated_at`.
- **Versioned API** (`/api/v1/`) + OpenAPI docs (`drf-spectacular`).
- **Pluggable providers** — `accounts/providers.py` defines `SMSProvider` /
  `SocialProvider` interfaces (mock `ConsoleSMSProvider` in dev), selected via
  `SMS_PROVIDER` setting.

## Module roadmap (PRD → apps)

| App | PRD | Phase |
|-----|-----|-------|
| `core` | shared base, multi-tenant Organization | **1 ✅** |
| `accounts` | §2 roles, §3.1 auth & access | **1 ✅** |
| `courses` | §3.2 course mgmt, §3.3 paid market | later |
| `payments` | §3.3/§3.4 pricing, §3.13 payments | later |
| `live` | §3.5 live training, §3.6 individual/group | later |
| `classrooms` | §3.7 smart/IoT, §3.8 seating, §3.9 container (Phase 2) | later |
| `library` | §3.10 free library | later |
| `recordings` | §3.11 recording & storage | later |
| `assessments` | §3.12 quizzes, assignments, certificates | later |
| `forum` | §3.12 discussion forum | later |
| `notifications` | §3.12 notifications | later |
| `analytics` | §3.14 reports | later |
| `ai` | §3.15 AI features | later |

## Tests

```bash
pytest
```

## Configuration

All secrets live in `.env` (see `.env.example`) — `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, database credentials, CORS origins, JWT lifetimes, and the SMS
provider path. Nothing sensitive is committed.
