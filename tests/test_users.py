import datetime
import pytest
from httpx import AsyncClient

from .conftest import future_date, past_date
from app.db.session import SessionLocal
from app.models.rental import Rental


async def test_create_user(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": "Hossein", "email": "h@x.com"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["name"] == "Hossein"
    assert body["email"] == "h@x.com"


async def test_create_user_validation(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": ""})
    assert r.status_code == 422


async def test_list_users(client: AsyncClient, seeded: dict):
    r = await client.get("/api/v1/users")
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_get_user_404(client: AsyncClient, seeded: dict):
    r = await client.get("/api/v1/users/999")
    assert r.status_code == 404


async def test_update_user_partial(client: AsyncClient, seeded: dict):
    uid = seeded["users"][1]
    r = await client.patch(f"/api/v1/users/{uid}", json={"name": "Sara K."})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Sara K."
    assert body["email"] == "s@x.com"


async def test_update_user_clear_email(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    r = await client.patch(f"/api/v1/users/{uid}", json={"email": None})
    assert r.status_code == 200
    assert r.json()["email"] is None


async def test_update_user_404(client: AsyncClient, seeded: dict):
    r = await client.patch("/api/v1/users/999", json={"name": "Ghost"})
    assert r.status_code == 404


async def test_delete_user(client: AsyncClient, seeded: dict):
    uid = seeded["users"][1]
    r = await client.delete(f"/api/v1/users/{uid}")
    assert r.status_code == 204
    r2 = await client.get(f"/api/v1/users/{uid}")
    assert r2.status_code == 404


async def test_delete_user_with_rentals_409(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": seeded["books"][0], "due_date": future_date()},
    )
    r = await client.delete(f"/api/v1/users/{uid}")
    assert r.status_code == 409
    r2 = await client.get(f"/api/v1/users/{uid}")
    assert r2.status_code == 200


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    r_v1 = await client.get("/api/v1/health")
    assert r_v1.status_code == 200
    assert r_v1.json() == {"status": "ok"}


# ---------------- Combined Endpoint Tests: GET /api/v1/users/{id}/rentals ----------------

async def test_user_rentals_empty(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    r = await client.get(f"/api/v1/users/{uid}/rentals")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["pages"] == 1


async def test_user_rentals_nonexistent_user_404(client: AsyncClient):
    r = await client.get("/api/v1/users/9999/rentals")
    assert r.status_code == 404


async def test_user_rentals_enriched(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    bid = seeded["books"][0]
    rental_res = await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": bid, "due_date": future_date(7)},
    )
    assert rental_res.status_code == 201

    r = await client.get(f"/api/v1/users/{uid}/rentals")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["rental_id"] == rental_res.json()["id"]
    assert item["status"] == "active"
    assert item["user_id"] == uid
    assert item["book_id"] == bid
    assert item["returned_at"] is None
    assert "created_at" in item
    assert "due_date" in item

    # Verify nested book object contains all details
    book = item["book"]
    assert book["id"] == bid
    assert book["title"] == "Pragmatic Programmer"
    assert book["author"] == "Hunt"
    assert "quantity" in book
    assert "created_at" in book

    # Verify user details included
    assert item["user"]["id"] == uid
    assert item["user"]["name"] == "Hossein"


async def test_user_rentals_status_filter_and_pagination(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    b1 = seeded["books"][0]
    b2 = seeded["books"][1]
    b3 = seeded["books"][2]

    # Rental 1: Active
    r1 = await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": b1, "due_date": future_date(10)},
    )
    assert r1.status_code == 201

    # Rental 2: Returned
    r2 = await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": b2, "due_date": future_date(5)},
    )
    assert r2.status_code == 201
    await client.post(f"/api/v1/rentals/{r2.json()['id']}/return")

    # Rental 3: Overdue (inserted directly to simulate expired due date)
    async with SessionLocal() as s:
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        s.add(Rental(user_id=uid, book_id=b3, due_date=past))
        await s.commit()

    # Total check
    r_all = await client.get(f"/api/v1/users/{uid}/rentals?page=1&size=2")
    assert r_all.status_code == 200
    all_data = r_all.json()
    assert all_data["total"] == 3
    assert all_data["pages"] == 2
    assert len(all_data["items"]) == 2

    # Filter active
    r_active = await client.get(f"/api/v1/users/{uid}/rentals?status=active")
    assert r_active.status_code == 200
    active_items = r_active.json()["items"]
    assert len(active_items) == 1
    assert active_items[0]["status"] == "active"
    assert active_items[0]["book_id"] == b1

    # Filter returned
    r_returned = await client.get(f"/api/v1/users/{uid}/rentals?status=returned")
    assert r_returned.status_code == 200
    ret_items = r_returned.json()["items"]
    assert len(ret_items) == 1
    assert ret_items[0]["status"] == "returned"
    assert ret_items[0]["book_id"] == b2

    # Filter overdue
    r_overdue = await client.get(f"/api/v1/users/{uid}/rentals?status=overdue")
    assert r_overdue.status_code == 200
    od_items = r_overdue.json()["items"]
    assert len(od_items) == 1
    assert od_items[0]["status"] == "overdue"
    assert od_items[0]["book_id"] == b3


async def test_user_rentals_sorting(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    b1 = seeded["books"][0]
    b2 = seeded["books"][1]

    # Create two rentals with different due dates
    await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": b1, "due_date": future_date(10)},
    )
    await client.post(
        "/api/v1/rentals",
        json={"user_id": uid, "book_id": b2, "due_date": future_date(20)},
    )

    r_asc = await client.get(f"/api/v1/users/{uid}/rentals?sort_by=due_date&order=asc")
    assert r_asc.status_code == 200
    items_asc = r_asc.json()["items"]
    assert items_asc[0]["book_id"] == b1
    assert items_asc[1]["book_id"] == b2

    r_desc = await client.get(f"/api/v1/users/{uid}/rentals?sort_by=due_date&order=desc")
    assert r_desc.status_code == 200
    items_desc = r_desc.json()["items"]
    assert items_desc[0]["book_id"] == b2
    assert items_desc[1]["book_id"] == b1
