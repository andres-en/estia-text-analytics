from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

REQUIRED_COLUMNS = [
    "SESSION_ID",
    "CHANNEL",
    "RP_ID",
    "DATE",
    "CUSTOMER_NAME",
    "CUSTOMER_EMAIL",
    "CUSTOMER_PHONE",
    "CUSTOMER_QUERY",
    "ROUTING_ANSWER",
    "CUSTOMER_ID",
    "CONN_ID",
    "BSUID",
]

MAX_HEADER_SCAN_ROWS = 30


class ExcelValidationError(Exception):
    pass


@dataclass(frozen=True)
class RawRow:
    source_row: int  # número de fila real en el Excel (1-indexed), para auditoría
    session_id: Any
    channel: Any
    rp_id: Any
    date: Any
    customer_name: Any
    customer_email: Any
    customer_phone: Any
    customer_query: Any
    routing_answer: Any
    customer_id: Any
    conn_id: Any
    bsuid: Any


def _find_header_row(path: str | Path) -> int:
    """Devuelve el número de fila (1-indexed) donde están los encabezados reales.

    El reporte trae filas de metadata antes del encabezado real (ver sección 2 del
    documento de especificación), así que no se asume una posición fija: se busca la
    primera fila cuyas celdas coincidan exactamente con REQUIRED_COLUMNS.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        required = set(REQUIRED_COLUMNS)
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=MAX_HEADER_SCAN_ROWS, values_only=True), start=1):
            values = {str(v).strip() for v in row if v is not None}
            if required.issubset(values):
                return i
    finally:
        wb.close()
    raise ExcelValidationError(
        f"Header row not found (expected the columns {REQUIRED_COLUMNS}) "
        f"in the first {MAX_HEADER_SCAN_ROWS} rows of the file."
    )


@dataclass(frozen=True)
class ExcelReadResult:
    rows: list[RawRow]
    header_row: int
    sheet_name: str


def read_excel_rows(path: str | Path) -> ExcelReadResult:
    path = Path(path)
    if not path.exists():
        raise ExcelValidationError(f"File does not exist: {path}")
    if path.suffix.lower() != ".xlsx":
        raise ExcelValidationError(f"Expected an .xlsx file, got: {path.suffix}")

    header_row = _find_header_row(path)

    df = pd.read_excel(path, sheet_name=0, header=header_row - 1)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ExcelValidationError(f"Missing required columns in the Excel file: {missing}")

    wb = openpyxl.load_workbook(path, read_only=True)
    sheet_name = wb.sheetnames[0]
    wb.close()

    rows: list[RawRow] = []
    for i, record in enumerate(df.to_dict(orient="records")):
        source_row = header_row + 1 + i  # primera fila de datos = header_row + 1
        rows.append(
            RawRow(
                source_row=source_row,
                session_id=record["SESSION_ID"],
                channel=record["CHANNEL"],
                rp_id=record["RP_ID"],
                date=record["DATE"],
                customer_name=record["CUSTOMER_NAME"],
                customer_email=record["CUSTOMER_EMAIL"],
                customer_phone=record["CUSTOMER_PHONE"],
                customer_query=record["CUSTOMER_QUERY"],
                routing_answer=record["ROUTING_ANSWER"],
                customer_id=record["CUSTOMER_ID"],
                conn_id=record["CONN_ID"],
                bsuid=record["BSUID"],
            )
        )

    return ExcelReadResult(rows=rows, header_row=header_row, sheet_name=sheet_name)
