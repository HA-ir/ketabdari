import asyncio
import pytest
from httpx import AsyncClient

from .conftest import future_date


async def test_create_book(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "Clean Code", "author": "Martin"})
    assert r.status_code == 201
    assert r.json()["title"] == "Clean Code"


async def test_books_pagination(client: AsyncClient, seeded: dict):
    r = await client.get("/api/v1/books", params={"page": 1, "size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2

    r2 = await client.get("/api/v1/books", params={"page": 2, "size": 2})
    assert len(r2.json()["items"]) == 1


async def test_books_search(client: AsyncClient, seeded: dict):
    r = await client.get("/api/v1/books", params={"search": "clean"})
    assert r.status_code == 200
    assert r.json()["total"] == 2


async def test_update_book(client: AsyncClient, seeded: dict):
    bid = seeded["books"][2]
    r = await client.patch(f"/api/v1/books/{bid}", json={"title": "Clean Architecture (2nd ed.)"})
    assert r.status_code == 200
    assert r.json()["title"] == "Clean Architecture (2nd ed.)"
    assert r.json()["author"] == "Martin"


async def test_update_book_404(client: AsyncClient, seeded: dict):
    r = await client.patch("/api/v1/books/999", json={"title": "Ghost Book"})
    assert r.status_code == 404


async def test_delete_book(client: AsyncClient, seeded: dict):
    bid = seeded["books"][2]
    r = await client.delete(f"/api/v1/books/{bid}")
    assert r.status_code == 204
    r2 = await client.get(f"/api/v1/books/{bid}")
    assert r2.status_code == 404


async def test_delete_book_with_rentals_409(client: AsyncClient, seeded: dict):
    bid = seeded["books"][1]
    await client.post(
        "/api/v1/rentals",
        json={"user_id": seeded["users"][0], "book_id": bid, "due_date": future_date()},
    )
    r = await client.delete(f"/api/v1/books/{bid}")
    assert r.status_code == 409
    r2 = await client.get(f"/api/v1/books/{bid}")
    assert r2.status_code == 200


async def test_book_quantity_crud(client: AsyncClient):
    r = await client.post("/api/v1/books", json={"title": "Rust Book", "author": "Steve", "quantity": 4})
    assert r.status_code == 201
    book = r.json()
    assert book["quantity"] == 4

    r = await client.patch(f"/api/v1/books/{book['id']}", json={"quantity": 2})
    assert r.status_code == 200
    assert r.json()["quantity"] == 2

    r = await client.get(f"/api/v1/books/{book['id']}")
    assert r.status_code == 200
    assert r.json()["quantity"] == 2


async def test_books_sorting_by_date(client: AsyncClient):
    b1 = (await client.post("/api/v1/books", json={"title": "Book Alpha", "author": "Author A"})).json()
    await asyncio.sleep(0.01)
    b2 = (await client.post("/api/v1/books", json={"title": "Book Beta", "author": "Author B"})).json()
    await asyncio.sleep(0.01)
    b3 = (await client.post("/api/v1/books", json={"title": "Book Gamma", "author": "Author C"})).json()

    r_asc = await client.get("/api/v1/books", params={"sort_by": "created_at", "order": "asc"})
    assert r_asc.status_code == 200
    ids_asc = [b["id"] for b in r_asc.json()["items"]]
    assert ids_asc == [b1["id"], b2["id"], b3["id"]]

    r_desc = await client.get("/api/v1/books", params={"sort_by": "created_at", "order": "desc"})
    assert r_desc.status_code == 200
    ids_desc = [b["id"] for b in r_desc.json()["items"]]
    assert ids_desc == [b3["id"], b2["id"], b1["id"]]


async def test_books_sorting_by_quantity_and_name_alias(client: AsyncClient):
    await client.post("/api/v1/books", json={"title": "C Book", "quantity": 10})
    await client.post("/api/v1/books", json={"title": "A Book", "quantity": 30})
    await client.post("/api/v1/books", json={"title": "B Book", "quantity": 20})

    r_qty = await client.get("/api/v1/books", params={"sort_by": "quantity", "sort_dir": "desc"})
    assert r_qty.status_code == 200
    quantities = [b["quantity"] for b in r_qty.json()["items"]]
    assert quantities == [30, 20, 10]

    r_name = await client.get("/api/v1/books", params={"sort_by": "name", "order": "asc"})
    assert r_name.status_code == 200
    titles = [b["title"] for b in r_name.json()["items"]]
    assert titles == ["A Book", "B Book", "C Book"]


async def test_books_invalid_sort_rejected_400(client: AsyncClient):
    r1 = await client.get("/api/v1/books", params={"sort_by": "secret_field"})
    assert r1.status_code == 400
    assert "Invalid sort_by field" in r1.json()["detail"]

    r2 = await client.get("/api/v1/books", params={"sort_by": "created_at", "order": "sideways"})
    assert r2.status_code == 400
    assert "Invalid sort order" in r2.json()["detail"]


async def test_books_search_pagination_and_sort_composition(client: AsyncClient):
    await client.post("/api/v1/books", json={"title": "Python Basics", "author": "Guido", "quantity": 5})
    await client.post("/api/v1/books", json={"title": "Advanced Python", "author": "Luciano", "quantity": 15})
    await client.post("/api/v1/books", json={"title": "Python Cookbook", "author": "Beazley", "quantity": 25})
    await client.post("/api/v1/books", json={"title": "Expert Python", "author": "Tarek", "quantity": 10})
    await client.post("/api/v1/books", json={"title": "Rust for Rustaceans", "author": "Gjengset", "quantity": 50})

    r_page1 = await client.get("/api/v1/books", params={
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

    r_page2 = await client.get("/api/v1/books", params={
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
