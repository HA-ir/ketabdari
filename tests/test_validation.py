import pytest
from httpx import AsyncClient

from .conftest import future_date, past_date


# ---------------- Pagination Validation ----------------

async def test_pagination_page_zero_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books?page=0")
    assert r.status_code == 422


async def test_pagination_page_negative_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books?page=-1")
    assert r.status_code == 422


async def test_pagination_size_zero_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books?size=0")
    assert r.status_code == 422


async def test_pagination_size_exceeding_max_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books?size=101")
    assert r.status_code == 422


async def test_pagination_non_numeric_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books?page=abc")
    assert r.status_code == 422


# ---------------- ID Validation ----------------

async def test_path_id_zero_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/users/0")
    assert r.status_code == 422


async def test_path_id_negative_rejected_422(client: AsyncClient):
    r = await client.get("/api/v1/books/-5")
    assert r.status_code == 422


async def test_body_id_zero_rejected_422(client: AsyncClient):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": 0, "book_id": 1, "due_date": future_date()},
    )
    assert r.status_code == 422

    r2 = await client.post(
        "/api/v1/rentals",
        json={"user_id": 1, "book_id": 0, "due_date": future_date()},
    )
    assert r2.status_code == 422


async def test_body_id_negative_rejected_422(client: AsyncClient):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": -1, "book_id": 1, "due_date": future_date()},
    )
    assert r.status_code == 422


# ---------------- String Validation ----------------

async def test_user_name_empty_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": ""})
    assert r.status_code == 422


async def test_user_name_whitespace_only_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": "    "})
    assert r.status_code == 422


async def test_user_name_too_long_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": "A" * 201})
    assert r.status_code == 422


async def test_book_title_empty_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": ""})
    assert r.status_code == 422


async def test_book_title_whitespace_only_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "   "})
    assert r.status_code == 422


async def test_book_title_too_long_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "T" * 301})
    assert r.status_code == 422


# ---------------- Email Validation ----------------

async def test_invalid_email_format_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/users", json={"name": "Alice", "email": "not-an-email"})
    assert r.status_code == 422

    r2 = await client.post("/api/v1/users", json={"name": "Alice", "email": "alice@"})
    assert r2.status_code == 422


# ---------------- Quantity Validation ----------------

async def test_negative_quantity_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "Bad Qty", "quantity": -1})
    assert r.status_code == 422


async def test_excessive_quantity_rejected_422(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "Huge Qty", "quantity": 100001})
    assert r.status_code == 422


# ---------------- PATCH Validation ----------------

async def test_patch_user_empty_body_rejected_422(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    r = await client.patch(f"/api/v1/users/{uid}", json={})
    assert r.status_code == 422


async def test_patch_user_unknown_field_rejected_422(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    r = await client.patch(f"/api/v1/users/{uid}", json={"name": "Valid", "unknown_field": 123})
    assert r.status_code == 422


async def test_patch_book_empty_body_rejected_422(client: AsyncClient, seeded: dict):
    bid = seeded["books"][0]
    r = await client.patch(f"/api/v1/books/{bid}", json={})
    assert r.status_code == 422


async def test_patch_book_unknown_field_rejected_422(client: AsyncClient, seeded: dict):
    bid = seeded["books"][0]
    r = await client.patch(f"/api/v1/books/{bid}", json={"title": "Valid", "extra": "invalid"})
    assert r.status_code == 422


# ---------------- due_date Validation (400) ----------------

async def test_past_due_date_rejected_400(client: AsyncClient, seeded: dict):
    r = await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": seeded["books"][0], "due_date": past_date(1)},
    )
    assert r.status_code == 400
    assert "due_date must be in the future" in r.json()["detail"]


# ---------------- Sort & Filter Whitelisting ----------------

async def test_invalid_sort_by_rejected_400(client: AsyncClient):
    r = await client.get("/api/v1/books?sort_by=unknown_col")
    assert r.status_code == 400
    assert "Invalid sort_by field" in r.json()["detail"]


async def test_invalid_order_direction_rejected_400(client: AsyncClient):
    r = await client.get("/api/v1/books?sort_by=title&order=random")
    assert r.status_code == 400
    assert "Invalid sort order" in r.json()["detail"]


async def test_invalid_status_filter_rejected_400(client: AsyncClient, seeded: dict):
    uid = seeded["users"][0]
    r = await client.get(f"/api/v1/users/{uid}/rentals?status=invalid_status")
    assert r.status_code == 400
    assert "Invalid status filter" in r.json()["detail"]
