# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the pure business rules and the ledger helpers."""

from __future__ import annotations

import pytest

from custom_components.kis_segito import ledger as lg
from custom_components.kis_segito.logic import (
    interest_for,
    reward_for,
    selectable_children,
)

BANDS = [
    {"min_early_min": 20, "tokens": 4},
    {"min_early_min": 10, "tokens": 3},
    {"min_early_min": 0, "tokens": 2},
]


@pytest.mark.parametrize(
    ("seconds_early", "tokens"),
    [
        (25 * 60, 4),
        (20 * 60, 4),
        (19 * 60, 3),
        (10 * 60, 3),
        (60, 2),
        (0, 2),  # exactly at the deadline still counts as on time
        (-1, 0),  # late: nothing, never negative
        (-3600, 0),
    ],
)
def test_reward_bands(seconds_early: float, tokens: int) -> None:
    assert reward_for(BANDS, seconds_early) == tokens


def test_reward_bands_do_not_stack_and_handle_empty() -> None:
    assert reward_for([], 600) == 0
    assert reward_for([{"min_early_min": 0, "tokens": 5}], 3600) == 5


@pytest.mark.parametrize(
    ("balance", "minimum", "maximum", "expected"),
    [
        (5, None, None, 0),
        (10, None, None, 1),
        (19, None, None, 1),
        (20, None, None, 2),
        (5, 1, 5, 1),
        (10, 1, 5, 1),
        (20, 1, 5, 2),
        (100, 1, 5, 5),
        (0, 1, 5, 0),
    ],
)
def test_interest(
    balance: int, minimum: int | None, maximum: int | None, expected: int
) -> None:
    assert interest_for(balance, 10, minimum, maximum) == expected


def test_compound_interest() -> None:
    balance = 100
    for _ in range(3):
        balance += interest_for(balance, 10)
    assert balance == 133  # 100 -> 110 -> 121 -> 133


def test_selectable_children() -> None:
    everyone = ["a", "b", "c"]
    assert selectable_children(everyone, []) == {"a", "b", "c"}
    assert selectable_children(everyone, ["a"]) == {"a"}
    assert selectable_children(everyone, ["a", "b"]) == {"a", "b"}
    assert selectable_children(everyone, everyone) == {"a", "b", "c"}


def _tx(amount: int, account: str = lg.WALLET) -> dict:
    return lg.make_transaction(
        "kid",
        lg.REASON_MANUAL,
        [{"account": account, "amount": amount}],
        timestamp="2026-01-01T00:00:00",
        source="test",
        creator="test",
    )


def test_ledger_balances_reversal_and_correction() -> None:
    txs = [_tx(10), _tx(-3), _tx(5, lg.PIGGY)]
    assert lg.balances(txs, "kid") == {lg.WALLET: 7, lg.PIGGY: 5}
    assert lg.balances(txs, "other") == {lg.WALLET: 0, lg.PIGGY: 0}

    reversal = lg.reversal_of(txs[1], [], timestamp="t", source="s", creator="c")
    assert reversal["reverses"] == txs[1]["id"]
    assert lg.balances([*txs, reversal], "kid")[lg.WALLET] == 10

    txs[1]["reversed_by"] = reversal["id"]
    with pytest.raises(lg.LedgerError):
        lg.reversal_of(txs[1], [], timestamp="t", source="s", creator="c")
    with pytest.raises(lg.LedgerError):
        lg.reversal_of(reversal, [], timestamp="t", source="s", creator="c")


def test_ledger_refuses_bad_lines() -> None:
    with pytest.raises(lg.LedgerError):
        _tx(0)
    with pytest.raises(lg.LedgerError):
        _tx(1.5)  # type: ignore[arg-type]
    with pytest.raises(lg.LedgerError):
        _tx(1, "savings")


def test_icon_aliases() -> None:
    from custom_components.kis_segito.icons import ICON_ALIASES, stored_icon

    assert stored_icon("task_bath") == "routine_bath"
    assert stored_icon("task_toothbrush") == "task_toothbrush"
    # Every alias points to an icon that has its own artwork.
    assert all(not target.startswith("task_bath") for target in ICON_ALIASES.values())
