#!/usr/bin/env python3
"""
Live end-to-end verification of users, rental flow, row locking (SELECT ... FOR UPDATE),
and quantity management against http://127.0.0.1:8888.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import httpx

BASE_URL = "http://127.0.0.1:8888"

def future_date(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        print("=" * 70)
        print("1. Creating Test Users")
        print("=" * 70)
        users = []
        user_data = [
            {"name": "Alice Developer", "email": "alice@test.local"},
            {"name": "Bob Architect", "email": "bob@test.local"},
            {"name": "Charlie DevOps", "email": "charlie@test.local"},
        ]
        for u in user_data:
            resp = await client.post("/users", json=u)
            data = resp.json()
            users.append(data)
            print(f"  [+] Created User #{data['id']}: {data['name']} ({data['email']})")

        print("\n" + "=" * 70)
        print("2. Creating Test Book with Limited Quantity (quantity = 2)")
        print("=" * 70)
        book_resp = await client.post("/books", json={
            "title": "Designing Data-Intensive Applications",
            "author": "Martin Kleppmann",
            "quantity": 2,
        })
        book = book_resp.json()
        book_id = book["id"]
        print(f"  [+] Created Book #{book_id}: '{book['title']}' | Initial Quantity: {book['quantity']}")

        print("\n" + "=" * 70)
        print("3. Sequential Rental Flow & Inventory Decrement")
        print("=" * 70)
        # Alice rents copy 1
        r1 = await client.post("/rentals", json={
            "user_id": users[0]["id"],
            "book_id": book_id,
            "due_date": future_date(14),
        })
        print(f"  [Alice] Rent request -> Status: {r1.status_code}, Rental #{r1.json()['id']}")
        b_state = (await client.get(f"/books/{book_id}")).json()
        print(f"  --> Book #{book_id} Quantity is now: {b_state['quantity']} (Expected: 1)")
        assert b_state["quantity"] == 1

        # Bob rents copy 2 (the last copy)
        r2 = await client.post("/rentals", json={
            "user_id": users[1]["id"],
            "book_id": book_id,
            "due_date": future_date(14),
        })
        print(f"  [Bob] Rent request -> Status: {r2.status_code}, Rental #{r2.json()['id']}")
        b_state = (await client.get(f"/books/{book_id}")).json()
        print(f"  --> Book #{book_id} Quantity is now: {b_state['quantity']} (Expected: 0)")
        assert b_state["quantity"] == 0

        # Charlie attempts to rent when quantity == 0
        r3 = await client.post("/rentals", json={
            "user_id": users[2]["id"],
            "book_id": book_id,
            "due_date": future_date(14),
        })
        print(f"  [Charlie] Rent request when quantity=0 -> Status: {r3.status_code}")
        print(f"  --> Error Detail: {r3.json().get('detail')}")
        assert r3.status_code == 409

        print("\n" + "=" * 70)
        print("4. Testing Concurrent Race Condition & SELECT ... FOR UPDATE Locking")
        print("=" * 70)
        # Create a new book with exactly 1 copy available
        race_book = (await client.post("/books", json={
            "title": "Database Internals: Row Locks & ACID",
            "author": "Alex Petrov",
            "quantity": 1,
        })).json()
        race_book_id = race_book["id"]
        print(f"  [+] Created Race-Test Book #{race_book_id} with Quantity = 1")
        print("  [*] Launching 2 simultaneous concurrent rent requests (Alice vs Bob)...")

        # Two concurrent requests racing for the same 1 copy
        res_alice, res_bob = await asyncio.gather(
            client.post("/rentals", json={"user_id": users[0]["id"], "book_id": race_book_id, "due_date": future_date()}),
            client.post("/rentals", json={"user_id": users[1]["id"], "book_id": race_book_id, "due_date": future_date()}),
        )
        print(f"  [Alice response]: Status {res_alice.status_code}")
        print(f"  [Bob response]  : Status {res_bob.status_code}")

        codes = sorted([res_alice.status_code, res_bob.status_code])
        print(f"  --> Results: One succeeded ({codes[0]}), One rejected with 409 ({codes[1]})")
        assert codes == [201, 409]

        final_race_book = (await client.get(f"/books/{race_book_id}")).json()
        print(f"  --> Final Book Quantity: {final_race_book['quantity']} (Must be exactly 0, never negative)")
        assert final_race_book["quantity"] == 0

        print("\n" + "=" * 70)
        print("5. Return Flow & Inventory Restoration")
        print("=" * 70)
        alice_rental_id = r1.json()["id"]
        print(f"  [*] Alice returns Rental #{alice_rental_id}...")
        ret_resp = await client.post(f"/rentals/{alice_rental_id}/return")
        print(f"  --> Return Status: {ret_resp.status_code}, Returned At: {ret_resp.json()['returned_at']}")
        assert ret_resp.status_code == 200

        b_state = (await client.get(f"/books/{book_id}")).json()
        print(f"  --> Book #{book_id} Quantity after return: {b_state['quantity']} (Expected: 1)")
        assert b_state["quantity"] == 1

        # Now Charlie can successfully rent the returned copy!
        print(f"  [*] Charlie re-attempts to rent Book #{book_id} now that 1 copy is back...")
        r4 = await client.post("/rentals", json={
            "user_id": users[2]["id"],
            "book_id": book_id,
            "due_date": future_date(14),
        })
        print(f"  [Charlie] Rent request -> Status: {r4.status_code}, Rental #{r4.json()['id']}")
        assert r4.status_code == 201

        b_state = (await client.get(f"/books/{book_id}")).json()
        print(f"  --> Final Book #{book_id} Quantity: {b_state['quantity']} (Expected: 0)")
        assert b_state["quantity"] == 0

        print("\n" + "=" * 70)
        print("ALL CHECKS PASSED: Row locking, transactions, and quantities verified!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
