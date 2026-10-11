"""Exit flow."""
from __future__ import annotations


def test_exit_creates_twelve_sell_orders_with_multiplied_quantities(
    client, subscribe, folio_payload
):
    folio = folio_payload(1)
    payload = subscribe("user-101", folio_id=1, multiplier=3)
    sub_id = payload["subscription"]["id"]

    r = client.post(f"/api/subscriptions/{sub_id}/exit")
    assert r.status_code == 200
    body = r.json()

    assert body["subscription"]["active"] is False
    assert body["subscription"]["exited_at"] is not None
    assert body["subscription"]["positions"] == []

    orders = body["orders"]
    assert len(orders) == 12
    assert all(o["action"] == "SELL" for o in orders)
    assert all(o["source"] == "EXIT" for o in orders)
    assert all(o["status"] == "EXECUTED" for o in orders)

    base_qty = {s["ticker"]: s["base_quantity"] for s in folio["stocks"]}
    for order in orders:
        assert order["quantity"] == base_qty[order["ticker"]] * 3


def test_exit_twice_returns_400(client, subscribe):
    payload = subscribe("user-101", folio_id=1, multiplier=1)
    sub_id = payload["subscription"]["id"]

    first = client.post(f"/api/subscriptions/{sub_id}/exit")
    assert first.status_code == 200

    second = client.post(f"/api/subscriptions/{sub_id}/exit")
    assert second.status_code == 400
    assert "already inactive" in second.json()["message"]


def test_exit_unknown_subscription_returns_404(client):
    r = client.post("/api/subscriptions/sub-nope/exit")
    assert r.status_code == 404


def test_exited_subscription_not_returned_by_active_only_filter(client, subscribe):
    payload = subscribe("user-101", folio_id=1, multiplier=2)
    sub_id = payload["subscription"]["id"]
    client.post(f"/api/subscriptions/{sub_id}/exit")

    active = client.get("/api/users/user-101/subscriptions?active_only=true").json()
    assert active == []

    all_subs = client.get("/api/users/user-101/subscriptions").json()
    assert len(all_subs) == 1
    assert all_subs[0]["active"] is False


def test_exit_orders_are_queryable_by_source(client, subscribe):
    payload = subscribe("user-101", folio_id=1, multiplier=2)
    sub_id = payload["subscription"]["id"]
    client.post(f"/api/subscriptions/{sub_id}/exit")

    r = client.get(f"/api/orders?subscription_id={sub_id}&source=EXIT")
    assert r.status_code == 200
    assert r.json()["total"] == 12


def test_exit_with_multiplier_1_produces_base_quantities(
    client, subscribe, folio_payload
):
    folio = folio_payload(1)
    payload = subscribe("user-one", folio_id=1, multiplier=1)
    sub_id = payload["subscription"]["id"]

    r = client.post(f"/api/subscriptions/{sub_id}/exit")
    body = r.json()

    base_qty = {s["ticker"]: s["base_quantity"] for s in folio["stocks"]}
    for order in body["orders"]:
        assert order["quantity"] == base_qty[order["ticker"]]


def test_exit_user_1_does_not_affect_user_2(client, subscribe):
    payload_a = subscribe("user-a", folio_id=1, multiplier=2)
    payload_b = subscribe("user-b", folio_id=1, multiplier=5)

    client.post(f"/api/subscriptions/{payload_a['subscription']['id']}/exit")

    # user-b remains active
    b_subs = client.get("/api/users/user-b/subscriptions?active_only=true").json()
    assert len(b_subs) == 1
    assert b_subs[0]["active"] is True
    assert b_subs[0]["id"] == payload_b["subscription"]["id"]
    assert len(b_subs[0]["positions"]) == 12