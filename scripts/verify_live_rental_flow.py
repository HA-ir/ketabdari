#!/usr/bin/env python3
"""Integration check for rental flow, row-level locking, and quantity updates."""
import asyncio
from datetime import datetime, timedelta, timezone
import httpx

BASE_URL = "http://127.0.0.1:8888"

def future_date(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Create users
        users = []
        for name, email in [("Alice", "alice@example.com"), ("Bob", "bob@example.com"), ("Charlie", "charlie@example.com")]:
            resp = await client.post("/users", json={"name": name, "email": email})
            users.append(resp.json())
        print(f"Created users: {[u['id'] for u in users]}")

        # Create book with quantity = 2
        book = (await client.post("/books", json={
            "title": "Designing Data-Intensive Applications",
            "author": "Martin Kleppmann",
            "quantity": 2,
        })).json()
        book_id = book["id"]
        print(f"Created book {book_id} (quantity={book['quantity']})")

        # Rent copy 1
        r1 = await client.post("/rentals", json={"user_id": users[0]["id"], "book_id": book_id, "due_date": future_date()})
        assert r1.status_code == 201
        assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 1

        # Rent copy 2
        r2 = await client.post("/rentals", json={"user_id": users[1]["id"], "book_id": book_id, "due_date": future_date()})
        assert r2.status_code == 201
        assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 0

        # Out of stock check
        r3 = await client.post("/rentals", json={"user_id": users[2]["id"], "book_id": book_id, "due_date": future_date()})
        assert r3.status_code == 409
        print(f"Out of stock 409 confirmed: {r3.json().get('detail')}")

        # Concurrent race test on 1 copy
        race_book = (await client.post("/books", json={"title": "Concurrency in Practice", "quantity": 1})).json()
        res_a, res_b = await asyncio.gather(
            client.post("/rentals", json={"user_id": users[0]["id"], "book_id": race_book["id"], "due_date": future_date()}),
            client.post("/rentals", json={"user_id": users[1]["id"], "book_id": race_book["id"], "due_date": future_date()}),
        )
        codes = sorted([res_a.status_code, res_b.status_code])
        assert codes == [201, 409]
        assert (await client.get(f"/books/{race_book['id']}")).json()["quantity"] == 0
        print(f"Concurrent race for last copy: {codes} (quantity=0)")

        # Return and re-rent
        ret = await client.post(f"/rentals/{r1.json()['id']}/return")
        assert ret.status_code == 200
        assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 1

        r4 = await client.post("/rentals", json={"user_id": users[2]["id"], "book_id": book_id, "due_date": future_date()})
        assert r4.status_code == 201
        assert (await client.get(f"/books/{book_id}")).json()["quantity"] == 0
        print("Return and inventory restore verified successfully.")

if __name__ == "__main__":
    asyncio.run(main())
