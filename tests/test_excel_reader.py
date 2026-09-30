from __future__ import annotations

import pytest

from clasificador.excel_reader import ExcelValidationError, read_excel_rows


def test_reads_sample_and_finds_header_row_dynamically(sample_xlsx_path):
    result = read_excel_rows(sample_xlsx_path)
    assert result.header_row == 8
    assert len(result.rows) == 1163
    assert result.rows[0].source_row == 9
    assert result.rows[-1].source_row == 1171


def test_first_row_matches_known_values(sample_xlsx_path):
    result = read_excel_rows(sample_xlsx_path)
    first = result.rows[0]
    assert first.session_id == "573001000001.botco-4402-acme_venta.1001"
    assert first.channel == "whatsapp"
    assert first.customer_query == "Quiero usar mi cupo"
    assert first.conn_id == 900000001


def test_missing_file_raises(tmp_path):
    with pytest.raises(ExcelValidationError):
        read_excel_rows(tmp_path / "no_existe.xlsx")


def test_wrong_extension_raises(tmp_path):
    bad_file = tmp_path / "archivo.csv"
    bad_file.write_text("a,b,c")
    with pytest.raises(ExcelValidationError):
        read_excel_rows(bad_file)
