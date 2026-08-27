# Library Management API

API مدیریت کتابخونه — یوزرها، کتاب‌ها و اجاره (rental). بدون احراز هویت، با CORS.

## استک
- FastAPI + SQLModel + SQLAlchemy (async) + asyncpg
- PostgreSQL 16 (docker-compose)
- تست: pytest + httpx (ASGI)

## راهاندازی
```bash
# 1) دیتابیس
docker compose up -d

# 2) API
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
```
- Swagger: `http://localhost:8010/docs`
- دیتابیس روی پورت `5433` میزبانی میشه (کاربر/پسورد/DB: `library`)

## تست
```bash
.venv/bin/pip install -r requirements-dev.txt
# دیتابیس تست جداگانه:
docker exec -i library_db psql -U library -c 'CREATE DATABASE library_test;'
.venv/bin/pytest -v
```

## Endpoints

| Method | Path | توضیح |
|--------|------|-------|
| POST | `/users` | اضافه کردن یوزر |
| GET | `/users` | لیست یوزرها |
| GET | `/users/{id}` | یوزر |
| GET | `/users/{id}/rentals` | رنت‌های یوزر |
| POST | `/books` | اضافه کردن کتاب |
| GET | `/books` | لیست کتابها با پجینشن (`page`, `size`, `search`) |
| GET | `/books/{id}` | کتاب |
| POST | `/rentals` | ثبت رنت — `user_id`, `book_id`, `due_date` (تاریخ پسدهی را caller میفرستد) |
| GET | `/rentals` | لیست رنت‌ها |
| GET | `/rentals/overdue` | رنت‌هایی که از `due_date` گذشته‌اند و هنوز پسداده نشده‌اند |
| GET | `/rentals/{id}` | رنت |
| POST | `/rentals/{id}/return` | ثبت پسدهی |

### قوانین
- `due_date` باید در آینده باشد (وگرنه `400`)
- کتابی که هنوز رفته دست کسی، دوباره قابل رنت نیست (`409`)
- پسدهی دوباره‌ی یک رنت: `409`
- یوزر/کتاب/رنت پیدا نشد: `404`

## ساختار
```
app/
  main.py        # FastAPI app + CORS + create_all
  db.py          # engine + session (env: DATABASE_URL)
  models.py      # User, Book, Rental
  schemas.py     # request/response models
  routers/       # users, books, rentals
tests/test_api.py
```