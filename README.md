# Ketabdari (کتابداری) — Library Management API

سرویس مدیریت کتابخانه بر پایه FastAPI، SQLModel و PostgreSQL 16 با معماری چندلایه (Layered Architecture)، تفکیک کامل لایه‌ها، اعتبارسنجی ورودی‌ها، کنترل موجودی فیزیکی و امانت با تراکنش‌های همزمان امن.

## ویژگی‌ ها
- **معماری لایه‌بندی‌شده و تمیز:** تفکیک دقیق لایه‌های انتقال (API Routes)، منطق تجاری (Services)، دسترسی به داده (Repositories)، جداول دیتابیس (Models) و مدل‌های تبادل داده (Schemas).
- **اعتبارسنجی دقیق داده‌ها:** اعتبارسنجی ورودی‌ها با Pydantic و Query constraints (محدودیت طول رشته‌ها، حذف فاصله‌های اضافی، اعتبارسنجی فرمت ایمیل، اعتبارسنجی فیلدهای مرتب‌سازی بر اساس لیست مجاز و رد فیلدهای اضافه در PATCH).
- **کنترل همزمانی موجودی:** ثبت امانت و بازگشت کتاب با قفل سطح ردیف (`SELECT ... FOR UPDATE`) داخل تراکنش اتمیک برای جلوگیری از Race Condition در لایه سرویس/مخزن.
- **اندپوینت ترکیبی امانت‌های کاربر:** دریافت لیست امانت‌های هر کاربر با صفحه‌بندی (`Page[T]`)، فیلتر وضعیت (`active` / `returned` / `overdue`)، مرتب‌سازی بر اساس تاریخ و نمایش کامل جزئیات کتاب در یک کوئری سریع بدون N+1.
- **جستجو و صفحه‌بندی:** جستجوی فازی روی عنوان و نویسنده با ایندکس Trigram GIN، صفحه‌بندی و مرتب‌سازی قطعی روی فیلدهای مجاز.
- **بهینه‌سازی کارایی:** حذف سربار ORM روی کوئری‌های جوین سنگین و سنجش عملکرد روی ۴,۰۰۰,۰۰۰ رکورد. گزارش کامل در [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md).

## ساختار لایه‌بندی پروژه

```text
app/
├── main.py               # کارخانه ساخت اپلیکیشن (create_app) + چرخه حیات (lifespan)
├── core/
│   ├── config.py         # تنظیمات با Pydantic (خواندن DATABASE_URL و تنظیمات Pool)
│   └── exceptions.py     # استثناهای دامنه (Domain Exceptions) و تبدیل به پاسخ HTTP
├── db/
│   └── session.py        # ساخت Engine، SessionLocal و وابستگی get_session
├── models/               # جداول دیتابیس SQLModel (table=True)
│   ├── __init__.py       # رجیستر کردن مدل‌ها برای ایجاد متادیتا
│   ├── user.py
│   ├── book.py
│   └── rental.py
├── schemas/              # مدل‌های اعتبارسنجی و سریالایز Pydantic
│   ├── common.py         # مدل صفحه‌بندی جنریک Page[T]
│   ├── user.py           # UserCreate, UserUpdate, UserRead
│   ├── book.py           # BookCreate, BookUpdate, BookRead
│   └── rental.py         # RentalCreate, RentalRead, UserRentalRead
├── repositories/         # لایه دسترسی به داده (تنها محل اجرای دستورات SQL)
│   ├── base.py           # مخزن جنریک BaseRepository
│   ├── user_repo.py
│   ├── book_repo.py
│   └── rental_repo.py
├── services/             # لایه منطق تجاری، تراکنش‌ها و قفل‌ها (بدون وابستگی به HTTP)
│   ├── user_service.py
│   ├── book_service.py
│   └── rental_service.py
└── api/
    ├── router.py         # مانت کردن api_router تحت پیشوند /v1
    ├── deps.py           # تزریق وابستگی‌های سرویس‌ها
    └── v1/
        ├── router.py
        ├── users.py
        ├── books.py
        └── rentals.py
```

### وظایف و قوانین لایه‌ها
1. **`app/api/` (لایه Presentation):** تنها مسئول پارس کردن درخواست‌ها، صدا زدن لایه سرویس و بازگرداندن پاسخ است. هیچ کوئری مستقیم یا لاجیک بیزنسی در این لایه وجود ندارد.
2. **`app/services/` (لایه Business Logic):** کنترل تمامی قواعد بیزنس، اعتبارسنجی‌های دامنه، ایجاد بلاک‌های تراکنشی و همزمانی. این لایه هیچ وابستگی به `fastapi` ندارد و خطاهای دامنه‌ای مانند `NotFoundError`, `ConflictError`, `BusinessRuleError`, `ValidationError` پرتاب می‌کند.
3. **`app/core/exceptions.py`:** مدیریت مرکزی خطاها و تبدیل استثناهای دامنه به کدهای وضعیت استاندارد HTTP (۴۰۴، ۴۰۹، ۴۰۰، ۴۲۲) با ساختار یکپارچه `{"detail": ...}`.
4. **`app/repositories/` (لایه Data Access):** تنها نقطه‌ای که دستورات `select`, `update`, `delete`, `with_for_update` و جوین‌ها در آن اجرا می‌شوند.

## پیش‌ نیازها و راه‌ اندازی

```bash
# اجرای دیتابیس با داکر
docker compose up -d

# محیط مجازی و نصب وابستگی‌ها
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8888
```

- مستندات تستی Swagger UI: `http://localhost:8888/docs`
- دیتابیس PostgreSQL: پورت `5433` (`library` / `library`)

## اجرای تست‌ ها

```bash
pip install -r requirements-dev.txt

# ساخت دیتابیس تست (یک‌بار)
docker exec -i library_db psql -U library -d library -c "CREATE DATABASE library_test;"

# اجرای مجموعه تست‌های جامع و لایه‌بندی‌شده
pytest
```

## مشخصات اندپوینت‌ های API (نسخه v1)

تمامی اندپوینت‌های عملیاتی تحت پیشوند `/api/v1` در دسترس هستند:

| متد | مسیر | شرح |
|---|---|---|
| GET | `/health` | وضعیت سلامت کلی سرویس |
| POST | `/api/v1/users` | ایجاد کاربر جدید (اعتبارسنجی نام غیرخالی و فرمت ایمیل) |
| GET | `/api/v1/users` | لیست کاربران (`page >= 1`, `1 <= size <= 100`) |
| GET | `/api/v1/users/{user_id}` | دریافت اطلاعات کاربر (رد آیدی نامعتبر: ۴۲۲، کاربر ناموجود: ۴۰۴) |
| PATCH | `/api/v1/users/{user_id}` | ویرایش جزئی کاربر (الزام ارسال حداقل یک فیلد، رد فیلدهای اضافه: ۴۲۲) |
| DELETE | `/api/v1/users/{user_id}` | حذف کاربر (در صورت وجود سابقه امانت فعال یا گذشته: ۴۰۹) |
| GET | `/api/v1/users/{user_id}/rentals` | **اندپوینت ترکیبی:** لیست امانت‌های کاربر با صفحه‌بندی (`page`, `size`)، فیلتر وضعیت (`status=active\|returned\|overdue`)، مرتب‌سازی (`sort_by`, `order`) و شامل اطلاعات کامل کتاب و کاربر در یک کوئری سریع بدون N+1 |
| POST | `/api/v1/books` | ایجاد کتاب (`title`, `author`, `quantity >= 0`) |
| GET | `/api/v1/books` | جستجو، صفحه‌بندی و مرتب‌سازی (`search`, `sort_by`, `order`, `page`, `size`) |
| GET | `/api/v1/books/{book_id}` | دریافت جزئیات کتاب |
| PATCH | `/api/v1/books/{book_id}` | ویرایش کتاب و تنظیم موجودی (رد فیلدهای ناشناخته و بدنه خالی: ۴۲۲) |
| DELETE | `/api/v1/books/{book_id}` | حذف کتاب (رد حذف در صورت وجود سابقه امانت: ۴۰۹) |
| POST | `/api/v1/rentals` | ثبت امانت با کنترل موجودی و قفل ردیف (`due_date` در آینده، موجودی > ۰) |
| GET | `/api/v1/rentals` | لیست تمام امانت‌ها (کوئری جوین بهینه‌شده) |
| GET | `/api/v1/rentals/overdue` | لیست امانت‌های معوق با ایندکس پارشیال (`returned_at IS NULL` و `due_date < now`) |
| GET | `/api/v1/rentals/{rental_id}` | دریافت جزئیات امانت |
| POST | `/api/v1/rentals/{rental_id}/return` | ثبت بازگشت کتاب، افزایش موجودی و به‌روزرسانی تاریخ برگشت با قفل همزمانی |

## بنچمارک و سنجش عملکرد

برای اجرای بنچمارک نرخ تأخیر روی مسیرهای جدید:
```bash
python3 bench.py http://127.0.0.1:8888
```

تحلیل عملکرد روی ۴ میلیون رکورد و جزئیات مدل همزمانی در مستند زیر در دسترس است:
- [گزارش عملکرد و معماری همزمانی (`docs/PERFORMANCE.md`)](docs/PERFORMANCE.md)
