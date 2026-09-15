import asyncio
import datetime
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Use a dedicated test database
os.environ["DATABASE_URL"] = "postgresql+asyncpg://library:library@localhost:5433/library_test"

from app.db import SessionLocal, engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Book, Rental, User  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # Fresh schema per test
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    transport = ASGITransport(app=app)
    c = AsyncClient(transport=transport, base_url="http://test")
    await c.__aenter__()
    yield c
    await c.aclose()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    # Each test gets a new event loop; drop pooled connections bound to the old loop
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(client):
    """Seed 2 users and 3 books, return their ids."""
    u1 = await client.post("/users", json={"name": "Hossein", "email": "h@x.com"})
    u2 = await client.post("/users", json={"name": "Sara", "email": "s@x.com"})
    b1 = await client.post("/books", json={"title": "Pragmatic Programmer", "author": "Hunt"})
    b2 = await client.post("/books", json={"title": "Clean Code", "author": "Martin"})
    b3 = await client.post("/books", json={"title": "Clean Architecture", "author": "Martin"})
    assert all(r.status_code == 201 for r in (u1, u2, b1, b2, b3))
    return {
        "users": [u1.json()["id"], u2.json()["id"]],
        "books": [b1.json()["id"], b2.json()["id"], b3.json()["id"]],
    }


def future_date(days=14) -> str:
    d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------- users ----------------

async def test_create_user(client):
    r = await client.post("/users", json={"name": "Hossein", "email": "h@x.com"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["name"] == "Hossein"


async def test_create_user_validation(client):
    r = await client.post("/users", json={"name": ""})
    assert r.status_code == 422


async def test_list_users(client, seeded):
    r = await client.get("/users")
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_get_user_404(client, seeded):
    r = await client.get("/users/999")
    assert r.status_code == 404


# ---------------- books ----------------

async def test_create_book(client):
    r = await client.post("/books", json={"title": "Clean Code", "author": "Martin"})
    assert r.status_code == 201
    assert r.json()["title"] == "Clean Code"


async def test_books_pagination(client, seeded):
    r = await client.get("/books", params={"page": 1, "size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2

    r2 = await client.get("/books", params={"page": 2, "size": 2})
    assert len(r2.json()["items"]) == 1


async def test_books_search(client, seeded):
    r = await client.get("/books", params={"search": "clean"})
    assert r.status_code == 200
    assert r.json()["total"] == 2


# ---------------- rentals ----------------

async def test_create_rental(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["name"] == "Hossein"
    assert body["book"]["title"] == "Pragmatic Programmer"
    assert body["returned_at"] is None


async def test_rental_duplicate_book_409(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 201
    r2 = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][1], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r2.status_code == 409


async def test_rental_past_due_date_400(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": "2020-01-01T00:00:00Z"},
    )
    assert r.status_code == 400


async def test_rental_unknown_user_404(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": 999, "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 404


async def test_rental_unknown_book_404(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": 999, "due_date": future_date()},
    )
    assert r.status_code == 404


async def test_user_rentals(client, seeded):
    await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.get(f"/users/{seeded['users'][0]}/rentals")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["book_id"] == seeded["books"][0]

    r2 = await client.get(f"/users/{seeded['users'][1]}/rentals")
    assert r2.json() == []


async def test_return_rental(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    rental_id = r.json()["id"]
    r2 = await client.post(f"/rentals/{rental_id}/return")
    assert r2.status_code == 200
    assert r2.json()["returned_at"] is not None
    r3 = await client.post(f"/rentals/{rental_id}/return")
    assert r3.status_code == 409


async def test_return_unknown_404(client, seeded):
    r = await client.post("/rentals/999/return")
    assert r.status_code == 404


async def test_book_rentable_after_return(client, seeded):
    r = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    rental_id = r.json()["id"]
    await client.post(f"/rentals/{rental_id}/return")
    r2 = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][1], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r2.status_code == 201


# ---------------- overdue ----------------

async def test_overdue_empty_when_not_expired(client, seeded):
    await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.get("/rentals/overdue")
    assert r.status_code == 200
    assert r.json() == []


async def test_overdue_detects_expired(client, seeded):
    # Rent directly in DB with an expired due date (API rejects past dates on create)
    async with SessionLocal() as s:
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
        s.add(Rental(user_id=seeded["users"][0], book_id=seeded["books"][0], due_date=past))
        await s.commit()

    r = await client.get("/rentals/overdue")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["user_id"] == seeded["users"][0]
    assert items[0]["book"]["title"] == "Pragmatic Programmer"

    # After return it must disappear
    await client.post(f"/rentals/{items[0]['id']}/return")
    r2 = await client.get("/rentals/overdue")
    assert r2.json() == []


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------- PATCH /users/{id} ----------------

async def test_update_user_partial(client, seeded):
    uid = seeded["users"][1]
    r = await client.patch(f"/users/{uid}", json={"name": "Sara K."})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Sara K."
    # email untouched
    assert body["email"] == "s@x.com"


async def test_update_user_clear_email(client, seeded):
    uid = seeded["users"][0]
    r = await client.patch(f"/users/{uid}", json={"email": None})
    assert r.status_code == 200
    assert r.json()["email"] is None


async def test_update_user_404(client, seeded):
    r = await client.patch("/users/999", json={"name": "Ghost"})
    assert r.status_code == 404


# ---------------- DELETE /users/{id} ----------------

async def test_delete_user(client, seeded):
    uid = seeded["users"][1]
    r = await client.delete(f"/users/{uid}")
    assert r.status_code == 204
    r2 = await client.get(f"/users/{uid}")
    assert r2.status_code == 404


async def test_delete_user_with_rentals_409(client, seeded):
    uid = seeded["users"][0]
    await client.post(
        "/rentals",
        json={"user_id": uid, "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.delete(f"/users/{uid}")
    assert r.status_code == 409
    r2 = await client.get(f"/users/{uid}")
    assert r2.status_code == 200


# ---------------- PATCH /books/{id} ----------------

async def test_update_book(client, seeded):
    bid = seeded["books"][2]
    r = await client.patch(f"/books/{bid}", json={"title": "Clean Architecture (2nd ed.)"})
    assert r.status_code == 200
    assert r.json()["title"] == "Clean Architecture (2nd ed.)"
    assert r.json()["author"] == "Martin"


async def test_update_book_404(client, seeded):
    r = await client.patch("/books/999", json={"title": "Ghost Book"})
    assert r.status_code == 404


# ---------------- DELETE /books/{id} ----------------

async def test_delete_book(client, seeded):
    bid = seeded["books"][2]
    r = await client.delete(f"/books/{bid}")
    assert r.status_code == 204
    r2 = await client.get(f"/books/{bid}")
    assert r2.status_code == 404


async def test_delete_book_with_rentals_409(client, seeded):
    bid = seeded["books"][1]
    await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": bid, "due_date": future_date()},
    )
    r = await client.delete(f"/books/{bid}")
    assert r.status_code == 409
    r2 = await client.get(f"/books/{bid}")
    assert r2.status_code == 200


# ---------------- Quantity & Concurrency Tests ----------------

async def test_book_quantity_crud(client):
    r = await client.post("/books", json={"title": "Rust Book", "author": "Steve", "quantity": 4})
    assert r.status_code == 201
    book = r.json()
    assert book["quantity"] == 4

    r = await client.patch(f"/books/{book['id']}", json={"quantity": 2})
    assert r.status_code == 200
    assert r.json()["quantity"] == 2

    r = await client.get(f"/books/{book['id']}")
    assert r.status_code == 200
    assert r.json()["quantity"] == 2


async def test_rent_and_return_updates_quantity(client, seeded):
    book_id = seeded["books"][0]
    # Initial quantity is 1
    book_res = await client.get(f"/books/{book_id}")
    assert book_res.json()["quantity"] == 1

    # Rent 1 copy -> quantity becomes 0
    r1 = await client.post(
        "/rentals",
        json={"user_id": seeded["users"][0], "book_id": book_id, "due_date": future_date()},
    )
    assert r1.status_code == 201
    rental_id = r1.json()["id"]

    book_res = await client.get(f"/books/{book_id}")
    assert book_res.json()["quantity"] == 0


# ---------------- Sorting & Pagination Composition Tests ----------------

async def test_books_sorting_by_date(client):
    b1 = (await client.post("/books", json={"title": "Book Alpha", "author": "Author A"})).json()
    await asyncio.sleep(0.01)
    b2 = (await client.post("/books", json={"title": "Book Beta", "author": "Author B"})).json()
    await asyncio.sleep(0.01)
    b3 = (await client.post("/books", json={"title": "Book Gamma", "author": "Author C"})).json()

    # Ascending by created_at
    r_asc = await client.get("/books", params={"sort_by": "created_at", "order": "asc"})
    assert r_asc.status_code == 200
    ids_asc = [b["id"] for b in r_asc.json()["items"]]
    assert ids_asc == [b1["id"], b2["id"], b3["id"]]

    # Descending by created_at
    r_desc = await client.get("/books", params={"sort_by": "created_at", "order": "desc"})
    assert r_desc.status_code == 200
    ids_desc = [b["id"] for b in r_desc.json()["items"]]
    assert ids_desc == [b3["id"], b2["id"], b1["id"]]


async def test_books_sorting_by_quantity_and_name_alias(client):
    await client.post("/books", json={"title": "C Book", "quantity": 10})
    await client.post("/books", json={"title": "A Book", "quantity": 30})
    await client.post("/books", json={"title": "B Book", "quantity": 20})

    # Sort by quantity desc with sort_dir alias
    r_qty = await client.get("/books", params={"sort_by": "quantity", "sort_dir": "desc"})
    assert r_qty.status_code == 200
    quantities = [b["quantity"] for b in r_qty.json()["items"]]
    assert quantities == [30, 20, 10]

    # Sort by 'name' alias (maps to title) asc
    r_name = await client.get("/books", params={"sort_by": "name", "order": "asc"})
    assert r_name.status_code == 200
    titles = [b["title"] for b in r_name.json()["items"]]
    assert titles == ["A Book", "B Book", "C Book"]


async def test_books_invalid_sort_rejected_400(client):
    # Invalid sort_by field
    r1 = await client.get("/books", params={"sort_by": "secret_field"})
    assert r1.status_code == 400
    assert "Invalid sort_by field" in r1.json()["detail"]

    # Invalid sort order
    r2 = await client.get("/books", params={"sort_by": "created_at", "order": "sideways"})
    assert r2.status_code == 400
    assert "Invalid sort order" in r2.json()["detail"]


async def test_books_search_pagination_and_sort_composition(client):
    # Seed 5 books, 4 of which match search "Python"
    await client.post("/books", json={"title": "Python Basics", "author": "Guido", "quantity": 5})
    await client.post("/books", json={"title": "Advanced Python", "author": "Luciano", "quantity": 15})
    await client.post("/books", json={"title": "Python Cookbook", "author": "Beazley", "quantity": 25})
    await client.post("/books", json={"title": "Expert Python", "author": "Tarek", "quantity": 10})
    await client.post("/books", json={"title": "Rust for Rustaceans", "author": "Gjengset", "quantity": 50})

    # Search "Python", sorted by quantity descending, page 1 (size 2)
    r_page1 = await client.get("/books", params={
        "search": "Python",
        "sort_by": "quantity",
        "order": "desc",
        "page": 1,
        "size": 2,
    })
    assert r_page1.status_code == 200
    p1_data = r_page1.json()
    assert p1_data["total"] == 4
    assert p1_data["pages"] == 2
    assert len(p1_data["items"]) == 2
    assert [b["quantity"] for b in p1_data["items"]] == [25, 15]
    assert p1_data["items"][0]["title"] == "Python Cookbook"
    assert p1_data["items"][1]["title"] == "Advanced Python"

    # Page 2 (size 2)
    r_page2 = await client.get("/books", params={
        "search": "Python",
        "sort_by": "quantity",
        "order": "desc",
        "page": 2,
        "size": 2,
    })
    assert r_page2.status_code == 200
    p2_data = r_page2.json()
    assert len(p2_data["items"]) == 2
    assert [b["quantity"] for b in p2_data["items"]] == [10, 5]
    assert p2_data["items"][0]["title"] == "Expert Python"
    assert p2_data["items"][1]["title"] == "Python Basics"


async def test_concurrent_return_race_condition(client, seeded):
    book_id = seeded["books"][0]
    user_id = seeded["users"][0]

    # Rent the book
    rental = (await client.post(
        "/rentals",
        json={"user_id": user_id, "book_id": book_id, "due_date": future_date()},
    )).json()
    rental_id = rental["id"]

    # Verify quantity is 0
    assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 0

    # Two concurrent return calls for the same rental
    res1, res2 = await asyncio.gather(
        client.post(f"/rentals/{rental_id}/return"),
        client.post(f"/rentals/{rental_id}/return"),
    )
    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [200, 409]

    # Quantity must be incremented exactly once (0 -> 1)
    assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 1


async def test_concurrent_rent_last_copy_race_condition(client, seeded):
    book_id = seeded["books"][0]
    # book has quantity=1
    u1, u2 = seeded["users"][0], seeded["users"][1]

    res1, res2 = await asyncio.gather(
        client.post("/rentals", json={"user_id": u1, "book_id": book_id, "due_date": future_date()}),
        client.post("/rentals", json={"user_id": u2, "book_id": book_id, "due_date": future_date()}),
    )

    status_codes = sorted([res1.status_code, res2.status_code])
    # Exactly one 201 and one 409
    assert status_codes == [201, 409], f"Unexpected status codes: {status_codes}"

    # Quantity must be exactly 0, never negative
    book_res = await client.get(f"/books/{book_id}")
    assert book_res.json()["quantity"] == 0


async def test_concurrent_rent_multi_copy_race_condition(client):
    # Create book with quantity = 3
    b = (await client.post("/books", json={"title": "High Concurrency", "quantity": 3})).json()
    book_id = b["id"]

    # Create 6 users
    users = []
    for i in range(6):
        u = (await client.post("/users", json={"name": f"User_{i}", "email": f"u{i}@race.com"})).json()
        users.append(u["id"])

    # 6 concurrent rental attempts for 3 copies
    tasks = [
        client.post("/rentals", json={"user_id": uid, "book_id": book_id, "due_date": future_date()})
        for uid in users
    ]
    responses = await asyncio.gather(*tasks)
    status_codes = [r.status_code for r in responses]

    assert status_codes.count(201) == 3
    assert status_codes.count(409) == 3

    book_res = await client.get(f"/books/{book_id}")
    assert book_res.json()["quantity"] == 0
