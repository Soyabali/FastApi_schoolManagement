# Neon Auth Demo (FastAPI + Neon PostgreSQL)

A simple authentication API with **registration, login, logout, change password and forgot/reset password**, using the tables already in your Neon database.

---

## 1. Setup (first time only)

```bash
cd /Users/synergy/Desktop/neondb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project folder:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>/neondb?sslmode=require&channel_binding=require
DEV_MODE=true
```

> `.env` holds your database password. It is listed in `.gitignore`, so never commit it.

## 2. Run the server

```bash
source .venv/bin/activate
fastapi dev main.py --port 8001
```

- API: http://127.0.0.1:8001
- **Interactive docs (easiest way to test):** http://127.0.0.1:8001/docs

---

## 3. How it works

### Project files

| File | What it does |
|---|---|
| `main.py` | Creates the FastAPI app and adds the auth routes |
| `auth.py` | All `/auth/...` endpoints and the "who is logged in" check |
| `models.py` | Maps Python classes to the existing Neon tables |
| `schemas.py` | Request/response shapes and validation (email format, password length) |
| `security.py` | Password hashing (bcrypt) and random token generation |
| `database.py` | Connects to Neon using `DATABASE_URL` |

### Database tables used

| Table | Used for |
|---|---|
| `registration` | User accounts. Passwords are stored as **bcrypt hashes**, never plain text |
| `login` | One row per login attempt (`success` / `failed` / `blocked`). Successful logins store the **session token** |
| `change_password` | History of every password change (`manual` or `reset`) |
| `forgot_password` | Password reset requests. The token is stored as a **SHA-256 hash** |

### Flow

1. **Register**: creates a row in `registration`.
2. **Login**: checks the password. On success it returns an `access_token` that is valid for 24 hours.
3. Send that token on protected requests as a header:
   `Authorization: Bearer <access_token>`
4. **5 wrong passwords in a row** lock the account for 15 minutes (HTTP `423`).
5. **Change password**: needs the old password. Logs out your other devices.
6. **Forgot password**: creates a reset token valid for 15 minutes. **Reset password**: uses it once, then logs out every device.

---

## 4. Endpoints

| Method | URL | Login needed? | Body |
|---|---|---|---|
| POST | `/auth/register` | No | `full_name`, `email`, `password`, optional `phone_number`, `date_of_birth` |
| POST | `/auth/login` | No | `email`, `password` |
| GET | `/auth/me` | **Yes** | – |
| POST | `/auth/logout` | **Yes** | – |
| POST | `/auth/change-password` | **Yes** | `old_password`, `new_password` |
| POST | `/auth/forgot-password` | No | `email` |
| POST | `/auth/reset-password` | No | `token`, `new_password` |

Passwords must be at least 8 characters.

---

## 5. Try it with curl

**Register**
```bash
curl -X POST http://127.0.0.1:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Doe","email":"john@example.com","password":"secret123"}'
```

**Login** (copy the `access_token` from the response)
```bash
curl -X POST http://127.0.0.1:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"secret123"}'
```

**Get my profile**
```bash
curl http://127.0.0.1:8001/auth/me \
  -H "Authorization: Bearer <access_token>"
```

**Change password**
```bash
curl -X POST http://127.0.0.1:8001/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"old_password":"secret123","new_password":"newpass123"}'
```

**Forgot password**
```bash
curl -X POST http://127.0.0.1:8001/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com"}'
```
This app does not send email. The reset token is printed in the server terminal, and with `DEV_MODE=true` it is also returned in the response as `reset_token`.

**Reset password**
```bash
curl -X POST http://127.0.0.1:8001/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token":"<reset_token>","new_password":"brandnew123"}'
```

**Logout**
```bash
curl -X POST http://127.0.0.1:8001/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

### Using the /docs page instead
1. Open http://127.0.0.1:8001/docs
2. Run `POST /auth/register`, then `POST /auth/login`, and copy the `access_token`.
3. Click **Authorize** (top right), paste the token and click Authorize.
4. Now the protected endpoints (`/auth/me`, `/auth/change-password`, `/auth/logout`) work.

---

## 6. Common responses

| Code | Meaning |
|---|---|
| 200 / 201 | Success |
| 400 | Wrong old password, or reset token invalid/expired/already used |
| 401 | Wrong email/password, or missing/expired token |
| 409 | Email already registered |
| 422 | Invalid input (bad email, password too short) |
| 423 | Account locked after too many failed logins |

## 7. Settings (optional, in `.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_HOURS` | 24 | How long a login token lasts |
| `RESET_TOKEN_MINUTES` | 15 | How long a reset token lasts |
| `MAX_FAILED_ATTEMPTS` | 5 | Wrong passwords before lock |
| `LOCK_MINUTES` | 15 | How long the lock lasts |
| `DEV_MODE` | false | Return reset token in the API response (testing only) |

## 8. Notes

- The 5 sample users already in `registration` (alice, bob, …) have placeholder password hashes, so **they cannot log in**. Register new users to test.
- Before real use: turn off `DEV_MODE`, send reset tokens by email, and serve the API over HTTPS.
