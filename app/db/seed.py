"""Idempotent seed: 7 folios × exactly 12 stocks each.

Because `Stock` is a master table, seeding has two phases:

1. Upsert every ticker referenced by any folio into `stocks`.
2. For each folio, create `FolioStock` links pointing at those `Stock` rows.

Runs at application startup. If the `folios` table is already populated this
is a no-op, so restarting the app never duplicates data.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.folio import FOLIO_SIZE, Folio, FolioStock, Stock

# --- Seed catalog ----------------------------------------------------------
# Each entry: (ticker, human-readable name, base_quantity).
# The same ticker may appear in multiple folios; the name is stored once.

FOLIO_SEEDS: list[dict] = [
    {
        "name": "Alpha Growth",
        "description": "Large-cap compounders with a growth tilt.",
        "stocks": [
            ("RELIANCE",   "Reliance Industries",        2),
            ("TCS",        "Tata Consultancy Services",  1),
            ("INFY",       "Infosys",                    1),
            ("HDFCBANK",   "HDFC Bank",                  2),
            ("ICICIBANK",  "ICICI Bank",                 2),
            ("SBIN",       "State Bank of India",        3),
            ("BHARTIARTL", "Bharti Airtel",              1),
            ("LT",         "Larsen & Toubro",            1),
            ("ITC",        "ITC",                        2),
            ("MARUTI",     "Maruti Suzuki",              1),
            ("AXISBANK",   "Axis Bank",                  2),
            ("SUNPHARMA",  "Sun Pharmaceutical",         1),
        ],
    },
    {
        "name": "Bluechip Core",
        "description": "Defensive index-heavy core basket.",
        "stocks": [
            ("HDFCBANK",   "HDFC Bank",                  3),
            ("RELIANCE",   "Reliance Industries",        2),
            ("TCS",        "Tata Consultancy Services",  2),
            ("ICICIBANK",  "ICICI Bank",                 2),
            ("INFY",       "Infosys",                    2),
            ("LT",         "Larsen & Toubro",            2),
            ("ITC",        "ITC",                        2),
            ("SBIN",       "State Bank of India",        2),
            ("KOTAKBANK",  "Kotak Mahindra Bank",        2),
            ("HINDUNILVR", "Hindustan Unilever",         1),
            ("BHARTIARTL", "Bharti Airtel",              1),
            ("AXISBANK",   "Axis Bank",                  1),
        ],
    },
    {
        "name": "India Momentum",
        "description": "High-beta cyclicals and domestic growth themes.",
        "stocks": [
            ("TATAMOTORS", "Tata Motors",                2),
            ("ADANIENT",   "Adani Enterprises",          1),
            ("JSWSTEEL",   "JSW Steel",                  2),
            ("TATASTEEL",  "Tata Steel",                 3),
            ("HINDALCO",   "Hindalco Industries",        2),
            ("VEDL",       "Vedanta",                    3),
            ("DLF",        "DLF",                        1),
            ("ZOMATO",     "Zomato",                     4),
            ("PAYTM",      "One 97 Communications",      5),
            ("IRCTC",      "IRCTC",                      2),
            ("PNB",        "Punjab National Bank",       6),
            ("BANKBARODA", "Bank of Baroda",             4),
        ],
    },
    {
        "name": "Dividend Leaders",
        "description": "Yield-focused PSU and utility names.",
        "stocks": [
            ("COALINDIA", "Coal India",                  4),
            ("ONGC",      "Oil & Natural Gas Corp",      5),
            ("POWERGRID", "Power Grid Corp",             4),
            ("NTPC",      "NTPC",                        3),
            ("ITC",       "ITC",                         3),
            ("HINDUNILVR","Hindustan Unilever",          1),
            ("SUNPHARMA", "Sun Pharmaceutical",          1),
            ("IOC",       "Indian Oil Corp",             5),
            ("BPCL",      "Bharat Petroleum",            3),
            ("GAIL",      "GAIL India",                  4),
            ("NHPC",      "NHPC",                        8),
            ("RECLTD",    "REC",                         2),
        ],
    },
    {
        "name": "Tech Innovators",
        "description": "IT services and digital engineering exposure.",
        "stocks": [
            ("TCS",        "Tata Consultancy Services",  2),
            ("INFY",       "Infosys",                    2),
            ("WIPRO",      "Wipro",                      4),
            ("HCLTECH",    "HCL Technologies",           2),
            ("TECHM",      "Tech Mahindra",              3),
            ("LTIM",       "LTIMindtree",                1),
            ("PERSISTENT", "Persistent Systems",         1),
            ("COFORGE",    "Coforge",                    1),
            ("MPHASIS",    "Mphasis",                    2),
            ("KPITTECH",   "KPIT Technologies",          2),
            ("TATAELXSI",  "Tata Elxsi",                 1),
            ("OFSS",       "Oracle Financial Services",  1),
        ],
    },
    {
        "name": "Consumer Power",
        "description": "Staples, discretionary and consumption proxies.",
        "stocks": [
            ("HINDUNILVR","Hindustan Unilever",          1),
            ("ITC",       "ITC",                         3),
            ("NESTLEIND", "Nestle India",                1),
            ("BRITANNIA", "Britannia Industries",        1),
            ("DABUR",     "Dabur India",                 3),
            ("MARICO",    "Marico",                      3),
            ("GODREJCP",  "Godrej Consumer Products",    2),
            ("TITAN",     "Titan Company",               1),
            ("ASIANPAINT","Asian Paints",                1),
            ("PIDILITIND","Pidilite Industries",         1),
            ("VBL",       "Varun Beverages",             4),
            ("TATACONSUM","Tata Consumer Products",      2),
        ],
    },
    {
        "name": "Value Select",
        "description": "Deep-value cyclicals trading below long-run averages.",
        "stocks": [
            ("ONGC",      "Oil & Natural Gas Corp",      6),
            ("COALINDIA", "Coal India",                  4),
            ("PNB",       "Punjab National Bank",        8),
            ("SBIN",      "State Bank of India",         3),
            ("IOC",       "Indian Oil Corp",             6),
            ("BPCL",      "Bharat Petroleum",            3),
            ("GAIL",      "GAIL India",                  5),
            ("NTPC",      "NTPC",                        3),
            ("POWERGRID", "Power Grid Corp",             3),
            ("HINDALCO",  "Hindalco Industries",         2),
            ("VEDL",      "Vedanta",                     4),
            ("CANBK",     "Canara Bank",                 8),
        ],
    },
]

# Every ticker present in the seeds, plus extras an admin may legitimately
# swap in (the assessment example uses IDEA).
TICKER_UNIVERSE: list[tuple[str, str]] = [
    ("IDEA",       "Vodafone Idea"),
    ("YESBANK",    "Yes Bank"),
    ("IDFCFIRSTB", "IDFC First Bank"),
    ("NIFTYBEES",  "Nippon India ETF Nifty 50"),
    ("SUZLON",     "Suzlon Energy"),
    ("TRIDENT",    "Trident"),
    ("BEL",        "Bharat Electronics"),
    ("HAL",        "Hindustan Aeronautics"),
    ("IRFC",       "Indian Railway Finance Corp"),
    ("RVNL",       "Rail Vikas Nigam"),
]


def _validate_seeds() -> None:
    
    seen_names: set[str] = set()
    for spec in FOLIO_SEEDS:
        stocks = spec["stocks"]
        if len(stocks) != FOLIO_SIZE:
            raise RuntimeError(
                f"Seed folio '{spec['name']}' must contain exactly "
                f"{FOLIO_SIZE} stocks (found {len(stocks)})"
            )
        if len({t for t, _, _ in stocks}) != len(stocks):
            raise RuntimeError(f"Seed folio '{spec['name']}' has duplicate tickers")
        for ticker, name, qty in stocks:
            if not ticker or not name or qty <= 0:
                raise RuntimeError(
                    f"Seed folio '{spec['name']}' has an invalid entry: {ticker}"
                )
        if spec["name"] in seen_names:
            raise RuntimeError(f"Duplicate folio name in seeds: {spec['name']}")
        seen_names.add(spec["name"])


def _all_seed_tickers() -> dict[str, str]:
    """ticker → name, from every folio plus the extended universe."""
    mapping: dict[str, str] = {}
    for spec in FOLIO_SEEDS:
        for ticker, name, _ in spec["stocks"]:
            mapping[ticker] = name
    for ticker, name in TICKER_UNIVERSE:
        mapping.setdefault(ticker, name)
    return mapping


def seed_folios(db: Session) -> int:
    """Create seed folios if the table is empty. Returns count created.

    Idempotent: if `folios` already contains rows the function exits without
    touching anything. Safe to call on every application startup.
    """
    _validate_seeds()

    existing = db.scalar(select(func.count()).select_from(Folio))
    if existing:
        return 0

    # Phase 1 — upsert every Stock referenced by any folio.
    ticker_to_stock: dict[str, Stock] = {
        s.ticker: s for s in db.scalars(select(Stock)).all()
    }
    for ticker, name in _all_seed_tickers().items():
        if ticker not in ticker_to_stock:
            stock = Stock(ticker=ticker, name=name)
            db.add(stock)
            ticker_to_stock[ticker] = stock
    db.flush()  # assign ids to new Stocks

    # Phase 2 — build folios and link them via stock_id.
    for spec in FOLIO_SEEDS:
        folio = Folio(name=spec["name"], description=spec["description"])
        folio.stocks = [
            FolioStock(
                stock_id=ticker_to_stock[ticker].id,
                base_quantity=qty,
            )
            for ticker, _, qty in spec["stocks"]
        ]
        db.add(folio)

    db.commit()
    return len(FOLIO_SEEDS)