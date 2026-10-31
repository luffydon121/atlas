"""Position accounting. All records stay in the local database."""

import csv
import io
from collections import defaultdict
from datetime import datetime

SIDES = {"buy", "sell", "dividend", "deposit", "withdraw"}
CSV_FIELDS = {"date", "symbol", "side", "quantity", "price"}


class LedgerError(ValueError):
    pass


def compute_positions(transactions: list) -> dict:
    """Average-cost ledger. Rows need ts, symbol, side, quantity, price, fee and currency."""
    book: dict[str, dict] = defaultdict(lambda: {"quantity": 0.0, "cost": 0.0, "realised": 0.0, "income": 0.0, "fees": 0.0, "currency": "USD"})
    for t in sorted(transactions, key=lambda x: x.ts):
        if t.side in {"deposit", "withdraw"}:
            continue
        pos = book[t.symbol]
        pos["currency"] = t.currency
        pos["fees"] += t.fee or 0
        if t.side == "buy":
            pos["quantity"] += t.quantity
            pos["cost"] += t.quantity * t.price + (t.fee or 0)
        elif t.side == "sell":
            if t.quantity > pos["quantity"] + 1e-9:
                raise LedgerError(f"{t.symbol}: sold {t.quantity} but only {pos['quantity']:.4f} held on {t.ts:%Y-%m-%d}")
            avg = pos["cost"] / pos["quantity"] if pos["quantity"] else 0
            pos["realised"] += (t.price - avg) * t.quantity - (t.fee or 0)
            pos["cost"] -= avg * t.quantity
            pos["quantity"] -= t.quantity
        elif t.side == "dividend":
            pos["income"] += t.quantity * t.price - (t.fee or 0)
    return {k: {**v, "avg_cost": v["cost"] / v["quantity"] if v["quantity"] > 1e-9 else None} for k, v in book.items()}


def cash_balance(starting: float, transactions: list) -> float:
    cash = starting
    for t in transactions:
        gross = t.quantity * t.price
        cash += {"buy": -gross - (t.fee or 0), "sell": gross - (t.fee or 0), "dividend": gross - (t.fee or 0), "deposit": gross, "withdraw": -gross}[t.side]
    return cash


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    fields = {(f or "").strip().lower() for f in reader.fieldnames or []}
    if missing := CSV_FIELDS - fields:
        raise LedgerError(f"CSV is missing columns: {', '.join(sorted(missing))}")
    rows = []
    for line, raw in enumerate(reader, 2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        try:
            side = row["side"].lower()
            if side not in SIDES:
                raise ValueError(f"unknown side {side!r}")
            qty, price = float(row["quantity"]), float(row["price"])
            if qty <= 0 or price < 0:
                raise ValueError("quantity must be positive and price non-negative")
            rows.append({"ts": datetime.fromisoformat(row["date"]), "symbol": row["symbol"].upper()[:32], "side": side, "quantity": qty, "price": price,
                         "fee": float(row.get("fee") or 0), "currency": (row.get("currency") or "USD").upper()[:3], "note": row.get("note") or None})
        except ValueError as exc:
            raise LedgerError(f"Line {line}: {exc}") from exc
    return rows
