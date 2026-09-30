import asyncio
import datetime
import pytest
from httpx import AsyncClient

from .conftest import future_date
from app.db.session import SessionLocal
from app.models.rental import Rental


async def test_create_rental(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["name"] == "Hossein"
    assert body["book"]["title"] == "Pragmatic Programmer"
    assert body["returned_at"] is None


async def test_rental_duplicate_book_409(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 201
    r2 = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][1], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r2.status_code == 409


async def test_rental_past_due_date_400(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": "2020-01-01T00:00:00Z"},
    )
    assert r.status_code == 400
    assert "due_date must be in the future" in r.json()["detail"]


async def test_rental_unknown_user_404(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": 999, "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r.status_code == 404


async def test_rental_unknown_book_404(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": 999, "due_date": future_date()},
    )
    assert r.status_code == 404


async def test_return_rental(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    rental_id = r.json()["id"]
    r2 = await client.post(f"/api/v1/rentals/{rental_id}/return")
    assert r2.status_code == 200
    assert r2.json()["returned_at"] is not None
    r3 = await client.post(f"/api/v1/rentals/{rental_id}/return")
    assert r3.status_code == 409


async def test_return_unknown_404(client: AsyncClient, seeded: dict):
    r = await client.post("/api/v1/rentals/999/return")
    assert r.status_code == 404


async def test_book_rentable_after_return(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    rental_id = r.json()["id"]
    await client.post(f"/api/v1/rentals/{rental_id}/return")
    r2 = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][1], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    assert r2.status_code == 201


async def test_rent_and_return_updates_quantity(client: AsyncClient, seeded: dict):
    book_id = seeded["books"][0]
    book_res = await client.get(f"/api/v1/books/{book_id}")
    assert book_res.json()["quantity"] == 1

    r1 = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": book_id, "due_date": future_date()},
    )
    assert r1.status_code == 201
    rental_id = r1.json()["id"]

    book_res = await client.get(f"/api/v1/books/{book_id}")
    assert book_res.json()["quantity"] == 0
    ret = await client.post(f"/api/v1/rentals/{rental_id}/return")
    assert ret.status_code == 200
    book_res = await client.get(f"/api/v1/books/{book_id}")
    assert book_res.json()["quantity"] == 1


async def test_overdue_empty_when_not_expired(client: AsyncClient, seeded: dict):
    await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.get("/api/v1/rentals/overdue")
    assert r.status_code == 200
    assert r.json() == []


async def test_overdue_detects_expired(client: AsyncClient, seeded: dict):
    # Rent directly in DB with an expired due date (API rejects past dates on create)
    async with SessionLocal() as s:
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
        s.add(Rental(user_id=seeded["users"][0], book_id=seeded["books"][0], due_date=past))
        await s.commit()

    r = await client.get("/api/v1/rentals/overdue")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["user_id"] == seeded["users"][0]
    assert items[0]["book"]["title"] == "Pragmatic Programmer"

    # After return it must disappear
    await client.post(f"/api/v1/rentals/{items[0]['id']}/return")
    r2 = await client.get("/api/v1/rentals/overdue")
    assert r2.json() == []


async def test_list_rentals(client: AsyncClient, seeded: dict):
    await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.get("/api/v1/rentals")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_rental(client: AsyncClient, seeded: dict):
    r1 = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": future_date()},
    )
    rental_id = r1.json()["id"]
    r2 = await client.get(f"/api/v1/rentals/{rental_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == rental_id


async def test_concurrent_return_race_condition(client: AsyncClient, seeded: dict):
    book_id = seeded["books"][0]
    user_id = seeded["users"][0]

    rental = (await client.post(
        "/api/v1/rentals",
        json={"user_id": user_id, "book_id": book_id, "due_date": future_date()},
    )).json()
    rental_id = rental["id"]

    assert (await client.get(f"/api/v1/books/{book_id}")).json()["quantity"] == 0

    res1, res2 = await asyncio.gather(
        client.post(f"/api/v1/rentals/{rental_id}/return"),
        client.post(f"/api/v1/rentals/{rental_id}/return"),
    )
    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [200, 409]
    assert (await client.get(f"/api/v1/books/{book_id}")).json()["quantity"] == 1


async def test_concurrent_rent_last_copy_race_condition(client: AsyncClient, seeded: dict):
    book_id = seeded["books"][0]
    u1, u2 = seeded["users"][0], seeded["users"][1]

    res1, res2 = await asyncio.gather(
        client.post("/api/v1/rentals", json={"user_id": u1, "book_id": book_id, "due_date": future_date()}),
        client.post("/api/v1/rentals", json={"user_id": u2, "book_id": book_id, "due_date": future_date()}),
    )

    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [201, 409], f"Unexpected status codes: {status_codes}"

    book_res = await client.get(f"/api/v1/books/{book_id}")
    assert book_res.json()["quantity"] == 0


async def test_concurrent_rent_multi_copy_race_condition(client: AsyncClient):
    b = (await client.post("/api/v1/books", json={"title": "High Concurrency", "quantity": 3})).json()
    book_id = b["id"]

    users = []
    for i in range(6):
        u = (await client.post("/api/v1/users", json={"name": f"User_{i}", "email": f"u{i}@race.com"})).json()
        users.append(u["id"])

    tasks = [
        client.post("/api/v1/rentals", json={"user_id": uid, "book_id": book_id, "due_date": future_date()})
        for uid in users
    ]
    responses = await asyncio.gather(*tasks)
    status_codes = [r.status_code for r in responses]

    assert status_codes.count(201) == 3
    assert status_codes.count(409) == 3

    book_res = await client.get(f"/api/v1/books/{book_id}")
    assert book_res.json()["quantity"] == 0
