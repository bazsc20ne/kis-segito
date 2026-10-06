# SPDX-License-Identifier: AGPL-3.0-only
"""Append-only token ledger.

Balances are never stored on their own: they are the sum of all transaction
lines. Nothing is deleted or changed in place, except the link fields that
point to a later reversal or correction:

- a reversal is a new transaction with the opposite lines (``reverses``);
- an amount edit is a new correction transaction with the difference
  (``corrects``), so the effective amount is original + corrections.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import uuid4

WALLET = "wallet"
PIGGY = "piggy"
ACCOUNTS = (WALLET, PIGGY)

# Transaction reasons.
REASON_CHECKPOINT = "checkpoint_reward"
REASON_REDEMPTION = "reward_redemption"
REASON_PIGGY_TRANSFER = "piggy_transfer"
REASON_INTEREST = "piggy_interest"
REASON_STREAK = "streak_reward"
REASON_MANUAL = "manual_adjustment"
REASON_REVERSAL = "reversal"
REASON_CORRECTION = "correction"


class LedgerError(Exception):
    """A transaction was refused; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def new_id() -> str:
    """A new random id (32 hex characters)."""
    return uuid4().hex


def balances(
    transactions: Iterable[Mapping[str, Any]], child_id: str
) -> dict[str, int]:
    """Wallet and piggy balance of a child, derived from the ledger."""
    result = dict.fromkeys(ACCOUNTS, 0)
    for tx in transactions:
        if tx["child_id"] != child_id:
            continue
        for line in tx["lines"]:
            result[line["account"]] += int(line["amount"])
    return result


def make_transaction(
    child_id: str,
    reason: str,
    lines: list[dict[str, Any]],
    *,
    timestamp: str,
    source: str,
    creator: str,
    refs: Mapping[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Build a transaction record (whole-token lines, at least one non-zero)."""
    clean = []
    for line in lines:
        if line["account"] not in ACCOUNTS:
            raise LedgerError("invalid_account")
        amount = int(line["amount"])
        if amount != line["amount"]:
            raise LedgerError("not_whole_tokens")
        if amount:
            clean.append({"account": line["account"], "amount": amount})
    if not clean:
        raise LedgerError("zero_amount")
    return {
        "id": new_id(),
        "timestamp": timestamp,
        "child_id": child_id,
        "reason": reason,
        "lines": clean,
        "source": source,
        "creator": creator,
        "refs": dict(refs or {}),
        "note": note,
        "reverses": None,
        "reversed_by": None,
        "corrects": None,
        "corrections": [],
    }


def reversal_of(
    original: Mapping[str, Any],
    corrections: Iterable[Mapping[str, Any]],
    *,
    timestamp: str,
    source: str,
    creator: str,
) -> dict[str, Any]:
    """A compensating transaction that cancels ``original`` and its corrections."""
    if original.get("reversed_by"):
        raise LedgerError("already_reversed")
    if original.get("reverses"):
        raise LedgerError("cannot_reverse_reversal")
    lines = [
        {"account": line["account"], "amount": -line["amount"]}
        for line in effective_lines(original, corrections)
    ]
    tx = make_transaction(
        original["child_id"],
        REASON_REVERSAL,
        lines,
        timestamp=timestamp,
        source=source,
        creator=creator,
        refs=original.get("refs"),
    )
    tx["reverses"] = original["id"]
    return tx


def effective_lines(
    tx: Mapping[str, Any], corrections: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Lines of a transaction with its corrections applied (per account)."""
    totals: dict[str, int] = {}
    for line in tx["lines"]:
        totals[line["account"]] = totals.get(line["account"], 0) + line["amount"]
    for correction in corrections:
        for line in correction["lines"]:
            totals[line["account"]] = totals.get(line["account"], 0) + line["amount"]
    return [{"account": acc, "amount": amt} for acc, amt in totals.items()]
