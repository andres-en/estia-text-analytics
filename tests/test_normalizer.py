from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from clasificador.normalizer import (
    is_dash,
    is_valid_phone,
    normalize_date,
    normalize_phone,
    normalize_text,
)


@pytest.mark.parametrize("value", ["-", " - ", None, float("nan")])
def test_is_dash_true(value):
    assert is_dash(value) is True


@pytest.mark.parametrize("value", ["Quiero usar mi cupo", "0", 0])
def test_is_dash_false(value):
    assert is_dash(value) is False


def test_normalize_text_strips_dash_to_none():
    assert normalize_text("-") is None
    assert normalize_text("  Hola  ") == "Hola"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (573001000001, "573001000001"),
        (573001000001.0, "573001000001"),
        ("5.73001000001E+11", "573001000001"),
        ("+57 300 100 0001", "573001000001"),
        ("57-300-100-0001", "573001000001"),
        ("573001000001", "573001000001"),
        ("(57) 300 100 0001", "573001000001"),
        ("-", None),
        (None, None),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_is_valid_phone():
    assert is_valid_phone("573001000001") is True
    assert is_valid_phone("123") is False
    assert is_valid_phone(None) is False
    assert is_valid_phone("") is False


def test_normalize_date_from_timestamp():
    ts = pd.Timestamp("2026-08-01 09:15:52")
    result = normalize_date(ts)
    assert result == dt.datetime(2026, 8, 1, 9, 15, 52)


def test_normalize_date_from_string():
    result = normalize_date("2026-08-01 09:15:52")
    assert result == dt.datetime(2026, 8, 1, 9, 15, 52)


def test_normalize_date_dash_is_none():
    assert normalize_date("-") is None
