"""Rebalance fan-out.

Celery runs in eager mode (`CELERY_TASK_ALWAYS_EAGER=true`), so the cascade
executes **inline** when `POST /api/admin/rebalance` returns. Every assertion
below can therefore be made immediately after the request — no polling, no
worker, no Redis.
"""
from __future__ import annotations


# -------------------------------------------------------------- happy path

def test_rebalance_updates_folio_and_cascades_to_all_active_subscribers(
    client, subscribe, folio_payload
):
    folio_before = folio_payload(1)
    base_qty = next(
        s["base_quantity"]
        for s in folio_before["stocks"]
        if s["ticker"] == "RELIANCE"
    )

    subscribe("user-a", folio_id=1, multiplier=1)
    subscribe("user-b", folio_id=1, multiplier=3)
    subscribe("user-c", folio_id=1, multiplier=5)

    r = client.post(
        "/api/admin/rebalance",
        json={
            "folio_id": 1,
            "outgoing_ticker": "RELIANCE",
            "incoming_ticker": "IDEA",
        },
    )
    assert r.status_code == 202
    accepted = r.json()
    assert accepted["active_subscribers_queued"] == 3
    assert accepted["incoming_base_quantity"] == base_qty

    # Folio composition changed
    folio_after = folio_payload(1)
    tickers = {s["ticker"] for s in folio_after["stocks"]}
    assert "IDEA" in tickers
    assert "RELIANCE" not in tickers
    assert len(folio_after["stocks"]) == 12

    # Each subscriber received exactly 2 rebalance orders, scaled per multiplier
    for user, mult in (("user-a", 1), ("user-b", 3), ("user-c", 5)):
        orders = client.get(
            f"/api/orders?user_id={user}&source=REBALANCE"
        ).json()["items"]
        assert len(orders) == 2, f"{user} should have exactly 2 rebalance orders"

        by_action = {o["action"]: o for o in orders}
        assert by_action["SELL"]["ticker"] == "RELIANCE"
        assert by_action["SELL"]["quantity"] == base_qty * mult
        assert by_action["BUY"]["ticker"] == "IDEA"
        assert by_action["BUY"]["quantity"] == base_qty * mult


def test_rebalance_with_custom_incoming_base_quantity(client, subscribe):
    subscribe("user-1", folio_id=1, multiplier=3)

    r = client.post(
        "/api/admin/rebalance",
        json={
            "folio_id": 1,
            "outgoing_ticker": "ITC",
            "incoming_ticker": "IDEA",
            "incoming_base_quantity": 7,
        },
    )
    assert r.status_code == 202
    assert r.json()["incoming_base_quantity"] == 7

    buys = [
        o
        for o in client.get(
            "/api/orders?user_id=user-1&source=REBALANCE"
        ).json()["items"]
        if o["action"] == "BUY"
    ]
    assert len(buys) == 1
    assert buys[0]["ticker"] == "IDEA"
    assert buys[0]["quantity"] == 7 * 3


def test_rebalance_updates_positions_of_active_subscribers(client, subscribe):
    payload = subscribe("user-1", folio_id=1, multiplier=2)
    sub_id = payload["subscription"]["id"]

    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "RELIANCE", "incoming_ticker": "IDEA"},
    )
    assert r.status_code == 202

    # Re-fetch the subscription and check its positions
    sub_after = client.get(f"/api/subscriptions/{sub_id}").json()
    tickers = {p["ticker"] for p in sub_after["positions"]}
    assert "IDEA" in tickers
    assert "RELIANCE" not in tickers
    assert len(sub_after["positions"]) == 12


# -------------------------------------------------------------- exclusions

def test_inactive_subscribers_are_excluded_from_rebalance(client, subscribe):
    subscribe("active-user", folio_id=1, multiplier=2)
    exited = subscribe("exited-user", folio_id=1, multiplier=4)
    client.post(f"/api/subscriptions/{exited['subscription']['id']}/exit")

    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "TCS", "incoming_ticker": "IDEA"},
    )
    assert r.status_code == 202
    assert r.json()["active_subscribers_queued"] == 1

    # Exited user got no rebalance orders
    exited_orders = client.get(
        "/api/orders?user_id=exited-user&source=REBALANCE"
    ).json()["total"]
    assert exited_orders == 0

    # Active user got the SELL + BUY
    active_orders = client.get(
        "/api/orders?user_id=active-user&source=REBALANCE"
    ).json()["items"]
    assert {o["ticker"] for o in active_orders} == {"TCS", "IDEA"}


def test_late_subscriber_is_not_rebalanced(client, subscribe, folio_payload):
    """A user subscribing *after* the trigger only sees the new basket."""
    subscribe("user-before", folio_id=1, multiplier=2)

    r = client.post(
        "/api/admin/rebalance",
        json={
            "folio_id": 1,
            "outgoing_ticker": "SBIN",
            "incoming_ticker": "YESBANK",
            "incoming_base_quantity": 4,
        },
    )
    assert r.status_code == 202

    subscribe("user-after", folio_id=1, multiplier=2)

    rebalance_orders = client.get(
        "/api/orders?user_id=user-after&source=REBALANCE"
    ).json()["total"]
    assert rebalance_orders == 0

    # The late subscriber got YESBANK (not SBIN) in their initial BUY orders
    buys = [
        o
        for o in client.get(
            "/api/orders?user_id=user-after&source=SUBSCRIPTION"
        ).json()["items"]
    ]
    tickers = {o["ticker"] for o in buys}
    assert "YESBANK" in tickers
    assert "SBIN" not in tickers


# -------------------------------------------------------------- validation

def test_rebalance_rejects_unknown_folio(client):
    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 9999, "outgoing_ticker": "TCS", "incoming_ticker": "IDEA"},
    )
    assert r.status_code == 404


def test_rebalance_rejects_unknown_outgoing_ticker(client):
    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "NOTREAL", "incoming_ticker": "IDEA"},
    )
    assert r.status_code == 400
    assert "not part of folio" in r.json()["message"]


def test_rebalance_rejects_duplicate_incoming_ticker(client):
    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "TCS", "incoming_ticker": "INFY"},
    )
    assert r.status_code == 400
    assert "already part of folio" in r.json()["message"]


def test_rebalance_rejects_invalid_ticker_format(client):
    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "TCS", "incoming_ticker": "1234"},
    )
    assert r.status_code == 400
    assert "not a valid ticker" in r.json()["message"]


def test_rebalance_rejects_non_positive_incoming_quantity(client):
    r = client.post(
        "/api/admin/rebalance",
        json={
            "folio_id": 1,
            "outgoing_ticker": "TCS",
            "incoming_ticker": "IDEA",
            "incoming_base_quantity": 0,
        },
    )
    # Pydantic gt=0 catches it before the service sees it.
    assert r.status_code == 422


def test_rebalance_rejects_unknown_incoming_ticker(client):
    """A ticker that exists in the folio but is not in the Stock universe."""
    r = client.post(
        "/api/admin/rebalance",
        json={
            "folio_id": 1,
            "outgoing_ticker": "TCS",
            "incoming_ticker": "ZZZZZZ",  # valid format, not in universe
        },
    )
    assert r.status_code == 404
    assert "not in the ticker universe" in r.json()["message"]


# ---------------------------------------------------------------- job row

def test_rebalance_job_is_persisted_with_summary(client, subscribe):
    subscribe("user-1", folio_id=1, multiplier=2)

    r = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "RELIANCE", "incoming_ticker": "IDEA"},
    )
    job_id = r.json()["job_id"]

    # Eager mode: job ran inline, so status is COMPLETED by now
    job = client.get(f"/api/admin/rebalances/{job_id}").json()
    assert job["id"] == job_id
    assert job["status"] == "COMPLETED"
    assert job["subscribers_total"] == 1
    assert job["subscribers_processed"] == 1
    assert job["orders_created"] == 2
    assert job["outgoing_ticker"] == "RELIANCE"
    assert job["incoming_ticker"] == "IDEA"
    assert job["error"] is None


def test_list_rebalances_returns_jobs_newest_first(client, subscribe):
    subscribe("user-1", folio_id=1, multiplier=2)

    client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "RELIANCE", "incoming_ticker": "IDEA"},
    )
    client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "TCS", "incoming_ticker": "YESBANK"},
    )

    jobs = client.get("/api/admin/rebalances").json()
    assert len(jobs) == 2
    assert jobs[0]["created_at"] >= jobs[1]["created_at"]


# -------------------------------------------------------- multiple rebalances

def test_two_consecutive_rebalances_chain_correctly(client, subscribe):
    """Swap A → B, then swap B → C. End state should reflect C."""
    subscribe("user-chain", folio_id=1, multiplier=2)

    r1 = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "RELIANCE", "incoming_ticker": "IDEA"},
    )
    assert r1.status_code == 202

    r2 = client.post(
        "/api/admin/rebalance",
        json={"folio_id": 1, "outgoing_ticker": "IDEA", "incoming_ticker": "YESBANK"},
    )
    assert r2.status_code == 202

    # Folio now has YESBANK, not IDEA or RELIANCE
    folio = client.get("/api/folios/1").json()
    tickers = {s["ticker"] for s in folio["stocks"]}
    assert "YESBANK" in tickers
    assert "IDEA" not in tickers
    assert "RELIANCE" not in tickers

    # User's final position reflects the chain
    sub = client.get(
        "/api/users/user-chain/subscriptions?active_only=true"
    ).json()[0]
    positions = {p["ticker"] for p in sub["positions"]}
    assert "YESBANK" in positions
    assert "IDEA" not in positions
    assert "RELIANCE" not in positions

    # 4 rebalance orders total (2 per swap)
    rebalance_orders = client.get(
        "/api/orders?user_id=user-chain&source=REBALANCE"
    ).json()["total"]
    assert rebalance_orders == 4