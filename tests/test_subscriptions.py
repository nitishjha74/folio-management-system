"""Subscription flow + validation."""
from __future__ import annotations


# ------------------------------------------------------------------ seeding

def test_seven_folios_are_seeded(client):
    r = client.get("/api/folios")
    assert r.status_code == 200
    folios = r.json()

    assert len(folios) == 7
    for folio in folios:
        assert len(folio["stocks"]) == 12, f"{folio['name']} has wrong stock count"
        assert all(s["base_quantity"] > 0 for s in folio["stocks"])
        assert all(s["ticker"] for s in folio["stocks"])


# ---------------------------------------------------------------- subscribe

def test_subscription_creates_twelve_buy_orders_with_multiplied_quantities(
    client, subscribe, folio_payload
):
    folio = folio_payload(1)
    payload = subscribe("user-101", folio_id=1, multiplier=3)

    sub = payload["subscription"]
    orders = payload["orders"]

    assert sub["active"] is True
    assert sub["multiplier"] == 3
    assert len(orders) == 12
    assert all(o["action"] == "BUY" for o in orders)
    assert all(o["status"] == "EXECUTED" for o in orders)
    assert all(o["source"] == "SUBSCRIPTION" for o in orders)

    base_qty = {s["ticker"]: s["base_quantity"] for s in folio["stocks"]}
    for order in orders:
        assert order["quantity"] == base_qty[order["ticker"]] * 3

    positions = {p["ticker"]: p["quantity"] for p in sub["positions"]}
    for ticker, qty in base_qty.items():
        assert positions[ticker] == qty * 3


def test_multiplier_is_persisted_and_visible_to_user(client, subscribe):
    subscribe("user-202", folio_id=2, multiplier=5)

    r = client.get("/api/users/user-202/subscriptions?active_only=true")
    assert r.status_code == 200
    subs = r.json()
    assert len(subs) == 1
    assert subs[0]["multiplier"] == 5
    assert subs[0]["folio_name"] == "Bluechip Core"


def test_subscription_is_queryable_by_id(client, subscribe):
    payload = subscribe("user-303", folio_id=1, multiplier=2)
    sub_id = payload["subscription"]["id"]

    r = client.get(f"/api/subscriptions/{sub_id}")
    assert r.status_code == 200
    assert r.json()["id"] == sub_id
    assert len(r.json()["positions"]) == 12


def test_orders_are_queryable_by_user_and_source(client, subscribe):
    subscribe("user-404", folio_id=1, multiplier=2)

    r = client.get("/api/orders?user_id=user-404&source=SUBSCRIPTION")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 12
    assert len(body["items"]) == 12
    assert all(o["user_id"] == "user-404" for o in body["items"])
    assert all(o["source"] == "SUBSCRIPTION" for o in body["items"])


def test_different_multipliers_produce_proportional_quantities(
    client, subscribe, folio_payload
):
    folio = folio_payload(1)
    base_qty = {s["ticker"]: s["base_quantity"] for s in folio["stocks"]}

    for user, mult in (("user-a", 1), ("user-b", 3), ("user-c", 5)):
        payload = subscribe(user, folio_id=1, multiplier=mult)
        for order in payload["orders"]:
            assert order["quantity"] == base_qty[order["ticker"]] * mult


# ---------------------------------------------------------------- validation

def test_duplicate_active_subscription_is_rejected(client, subscribe):
    subscribe("user-dup", folio_id=1, multiplier=2)

    r = client.post(
        "/api/subscriptions",
        json={"user_id": "user-dup", "folio_id": 1, "multiplier": 2},
    )
    assert r.status_code == 409
    body = r.json()
    assert body["success"] is False
    assert "already has an active subscription" in body["message"]


def test_unknown_folio_returns_404(client):
    r = client.post(
        "/api/subscriptions",
        json={"user_id": "u", "folio_id": 9999, "multiplier": 1},
    )
    assert r.status_code == 404
    assert r.json()["success"] is False


def test_zero_and_negative_multiplier_are_rejected(client):
    for bad in (0, -3):
        r = client.post(
            "/api/subscriptions",
            json={"user_id": "u", "folio_id": 1, "multiplier": bad},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["message"] == "Field Validation Error"
        assert "multiplier" in body["errors"]


def test_multiplier_above_ceiling_is_rejected(client):
    r = client.post(
        "/api/subscriptions",
        json={"user_id": "u", "folio_id": 1, "multiplier": 1001},
    )
    assert r.status_code == 422


def test_whitespace_only_user_id_is_rejected(client):
    r = client.post(
        "/api/subscriptions",
        json={"user_id": "   ", "folio_id": 1, "multiplier": 1},
    )
    assert r.status_code == 400
    assert r.json()["success"] is False


def test_missing_user_id_returns_422(client):
    r = client.post(
        "/api/subscriptions",
        json={"folio_id": 1, "multiplier": 1},
    )
    assert r.status_code == 422
    assert "user_id" in r.json()["errors"]