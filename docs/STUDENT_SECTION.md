# Student Section — Implementation Summary

**Project:** Jigyaasaa — Smart Hybrid LMS
**Date:** 2026-07-22
**Scope:** Student-facing API modules. All routes are prefixed with `/api/v1`
and (except signup/login/OTP/password-reset) require `Authorization: Bearer <access_token>`.
Interactive docs: `/api/docs/` (Swagger) · Schema: `/api/schema/`.

---

## 1. Summary

Before today only 3 apps had a working API: **accounts (partial)**, **courses**,
**certificates**. Today the remaining student-facing modules were built, wired
into the URLconf, and covered with tests. The full student journey now works
end to end: sign up → browse → enroll or buy → learn → get assessed → earn a
certificate, with notifications and gamification firing along the way.

- **Total tests: 74 passing** (32 pre-existing + 42 new).
- **No new gateway/hardware dependencies** except `boto3` (for S3/R2 uploads).
- **New migration:** `assessments/0003_answer_file_key` (assignment file uploads).

---

## 2. Modules implemented today

### 2.1 Free Library (PRD §3.10) — `/api/v1/`
- `GET  /library-resources/` — search/filter (`q`, `format`, `category`,
  `access_level`, `ordering=-popularity_score`).
- `GET  /library-resources/{slug}/` — detail; increments `views_count`.
- `POST /library-resources/{slug}/bookmark/` — toggle bookmark.
- `GET  /library-bookmarks/` — the student's "Saved" tab; `DELETE` to remove.
- Authoring (create/update/delete) restricted to trainers/admins (owner-checked).

### 2.2 Live Classes & 1:1 (PRD §3.5, §3.6) — `/api/v1/`
- `GET  /live-sessions/` — filter `upcoming=true`, `course=`, `status=`.
- `POST /live-sessions/{id}/register/` — register; **auto-waitlists** past the limit.
- `POST /live-sessions/{id}/join/` — mark attendance + return join URL.
- `POST /live-sessions/{id}/raise-doubt/` — raise a doubt during class.
- `GET  /live-sessions/{id}/doubts/` — student sees own; trainer sees all.
- `GET  /session-registrations/` + `POST /{id}/cancel/` — cancel frees the seat
  and **promotes the next waitlisted student**.
- `GET  /trainer-availability/?trainer=&available=true` — open 1:1 slots.
- `POST /individual-bookings/` — book a 1:1 slot (marks the slot booked).

### 2.3 Assessments & Assignments (PRD §3.12) — `/api/v1/`
- `GET  /assessments/?course=` and `GET /assessments/{id}/` — questions & choices
  with **answer keys hidden** from students.
- `POST /assessments/{id}/submit/` — one-call attempt:
  - MCQ / multi-select are **auto-graded instantly** (pass/fail vs `pass_percent`).
  - Descriptive / coding / **file uploads** are held as `submitted` for trainer review.
  - Enforces attempt limits and availability window.
- `GET  /submissions/` + `GET /submissions/{id}/` — the student's attempts & scores.
- Trainer grading: `POST /submissions/{id}/grade/`.
- **Assignment files**: submit an object key via `file_key` (see Uploads, §2.7).

### 2.4 Discussions & Community (PRD §3.12) — `/api/v1/`
- `GET/POST /discussion-threads/` (filter `course=`, `scope=`, `status=`, `q=`);
  `GET /discussion-threads/{id}/` returns nested replies.
- `POST /discussion-replies/` — reply (bumps thread activity + reply count);
  `POST /discussion-replies/{id}/accept/` — author/trainer marks the accepted
  answer → thread resolved.
- `GET/POST /community-posts/` + `POST /{id}/like/` — community feed.
- `GET  /badges/` — all earnable badges.
- `GET  /community-profile/me/` and `/my_badges/` — points, level, earned badges.

### 2.5 Notifications (PRD §3.12) — `/api/v1/`
- `GET  /notifications/` (`?is_read=`, `?category=`), `GET /unread_count/`,
  `POST /mark_all_read/`, `POST /{id}/read/`.
- `GET  /notification-preferences/` — category × channel matrix, **auto-seeded**;
  `PATCH` to change a row.
- `GET/POST/DELETE /device-tokens/` — push token registration.
- **Notifications now actually fire** (previously the bell was always empty):
  signal handlers create in-app notifications on **enrollment, certificate
  issued, assessment passed/graded, live-session registration**, honoring the
  user's per-channel preferences.

### 2.6 Payments & Purchase (PRD §3.3, §3.4, §3.13) — `/api/v1/`
- `GET  /pricing-plans/` — platform-access plans (monthly/quarterly/annual).
- `GET  /course-prices/?course=` — a course's price options.
- `POST /coupons/validate/` — preview a discount for a cart.
- `GET/POST /payment-methods/` — saved instruments.
- `POST /orders/` — create a checkout order; **priced server-side** (line items →
  coupon → 18% GST → total).
- `POST /orders/{id}/pay/` — confirm payment → **issues GST invoice** and
  **grants access** (paid course enrollment / subscription activation). Idempotent.
- `GET  /orders/`, `GET /invoices/`, `GET /subscriptions/` + `POST /{id}/cancel/`.

> ⚠️ **MOCK GATEWAY.** `pay/` confirms payment synchronously with a stub. There is
> **no real Razorpay/Stripe/PayPal/UPI integration and no money moves yet.** The
> money math, invoicing, coupons and access-granting are fully functional; only
> the actual gateway + webhook verification is pending. (This caveat is also shown
> on Swagger `/api/docs/`.)

### 2.7 File Uploads — direct-to-storage (S3 / Cloudflare R2) — `/api/v1/uploads/`
- `POST /uploads/presign/` — returns a short-lived **private presigned PUT URL**
  (`{filename, content_type, purpose}` → `{method, url, headers, key, expires_in}`).
- `PUT <url>` — browser uploads the file **straight to storage** (bytes never
  touch Django).
- `GET  /uploads/download/?key=...` — short-lived presigned GET to read a private
  file back.
- Configured for **Cloudflare R2** (S3-compatible); verified with a live upload
  round-trip. Purposes: `avatar`, `assignment`, `library_video`, `library_file`,
  `course_thumbnail`, `lesson_video`, `message_attachment`, etc.

### 2.8 Auth additions (PRD §3.1) — `/api/v1/auth/`
- `POST /otp/request/` + `/otp/verify/` — **mobile OTP login** (6-digit code via the
  pluggable SMS provider; verify issues JWTs; rate-limited, 5-min TTL).
- `POST /password-reset/` + `/confirm/` — **password reset** using Django's token
  generator (generic response, anti-enumeration).
- Social / SSO login remains a `501` stub (needs an OAuth provider + credentials).

### 2.9 Gamification (PRD §3.12)
- Points awarded on activity (enroll 10, assessment pass 25, certificate 50…),
  level computed (500 pts/level), and badges auto-granted — all via the same
  event signals as notifications. `community-profile/me/` reflects real activity.

---

## 3. Parked / not in scope today

- **Recordings (§3.11)** — fully built (serializers/views/urls) but **unmounted**
  from the URLconf per request; enable by uncommenting one line in `Jigaysa/urls.py`.
- **Smart Classroom / Physical rooms (§3.7, §3.8)** — skipped per request.

---

## 4. Still pending in Payments (for later)

Real gateway integration (Razorpay/UPI recommended first) + webhook verification,
refunds endpoint, EMI/installments, pay-per-session & 1:1 booking checkout,
corporate/group pricing, referral credits, and trainer revenue-share payouts.

---

## 5. Supporting fixes made today

- **`pytest.ini`** pointed at `Jigayasa.settings` (typo) → fixed to `Jigaysa.settings`;
  the test suite had never actually run before.
- Removed duplicate default `tests.py` stubs that shadowed `tests/` packages and
  broke test discovery (courses, certificates, and the new apps).
- **CORS**: added `localhost:3000` default and a `*.jigyaasaa.com` regex.
- **S3/R2**: added `boto3`, env-driven storage settings, and `core/storage.py`.

---

## 6. How to run & verify

```bash
# Migrate + seed demo data (shared demo password: Passw0rd!123)
python manage.py migrate
python manage.py seed_demo

# Run the app
python manage.py runserver
#   Swagger:  http://127.0.0.1:8000/api/docs/

# Tests (needs a DB; against SQLite:)
DB_ENGINE=django.db.backends.sqlite3 DB_NAME=:memory: python -m pytest -q
#   → 74 passed
```

---

## 7. Student journey status (PRD §2.3)

| Capability            | Status                        |
|-----------------------|-------------------------------|
| Register / login      | ✅ (email + mobile OTP)        |
| Password reset        | ✅                             |
| Browse courses        | ✅                             |
| Purchase course       | ✅ (mock gateway)              |
| Access free library   | ✅                             |
| Attend live classes   | ✅                             |
| Raise doubts          | ✅ (live + forum)              |
| Assessments/assignments | ✅ (auto-grade + file upload) |
| Track progress        | ✅                             |
| Notifications         | ✅ (auto-fired)                |
| Gamification          | ✅                             |
| Download certificates | ✅                             |
| Join physical classes | ❌ (smart classroom, skipped)  |
| Watch recordings      | ⏸️ (built, parked)            |
