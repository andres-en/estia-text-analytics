from __future__ import annotations

from clasificador.row_classifier import classify_row, classify_session_id


def test_real_pattern():
    pattern, matched = classify_session_id("573001000001.botco-4402-acme_venta.1001")
    assert pattern == "REAL"
    assert matched is True


def test_broadcast_long_numeric_pattern():
    pattern, matched = classify_session_id("100000000000000000000000000000002")
    assert pattern == "BROADCAST_LONG_NUMERIC"
    assert matched is True


def test_broadcast_dotted_pattern():
    pattern, matched = classify_session_id("6852.573009990003.20260801125109.10")
    assert pattern == "BROADCAST_DOTTED"
    assert matched is True


def test_unknown_pattern_falls_back_to_real_with_warning_flag():
    pattern, matched = classify_session_id("algo-totalmente-nuevo-123")
    assert pattern == "REAL"
    assert matched is False


def test_classify_row_real_with_conn_id_matches_no_warning():
    result = classify_row("573001000001.botco-4402-acme_venta.1001", 186111266)
    assert result.session_pattern == "REAL"
    assert result.is_broadcast is False
    assert result.warning is None


def test_classify_row_broadcast_with_dash_conn_id_no_warning():
    result = classify_row("100000000000000000000000000000002", "-")
    assert result.session_pattern == "BROADCAST_LONG_NUMERIC"
    assert result.is_broadcast is True
    assert result.warning is None


def test_classify_row_real_with_dash_conn_id_warns():
    result = classify_row("573001000001.botco-4402-acme_venta.1001", "-")
    assert result.warning is not None
    assert "CONN_ID" in result.warning


def test_classify_row_broadcast_with_real_conn_id_warns():
    result = classify_row("100000000000000000000000000000002", 186111266)
    assert result.warning is not None
