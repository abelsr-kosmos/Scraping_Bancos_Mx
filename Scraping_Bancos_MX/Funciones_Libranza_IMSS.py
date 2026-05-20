import re
from pathlib import Path
from typing import Union

import pandas as pd
import pdfplumber


COLUMNS = [
    "Núm. Desc.",
    "Saldo capital",
    "Abono a capital",
    "Intereses",
    "IVA",
    "Descuento mensual",
]

_MONEY_COLS = COLUMNS[1:]
_MONEY_RE = re.compile(r"[^\d.\-]")


def _parse_money(value):
    if value is None:
        return None
    cleaned = _MONEY_RE.sub("", str(value))
    if cleaned in ("", "-", "."):
        return None
    return float(cleaned)


def _is_amort_header(row) -> bool:
    if not row or len(row) < 6:
        return False
    return [(c or "").strip() for c in row[:6]] == COLUMNS


def _is_data_row(row) -> bool:
    if not row or not row[0]:
        return False
    return str(row[0]).strip().isdigit()


def Scrap_Libranza_IMSS(pdf_path: Union[str, Path]) -> pd.DataFrame:
    """Extrae la *Tabla de Amortización* de una Carta de Libranza del IMSS.

    Parameters
    ----------
    pdf_path : str | Path
        Ruta al PDF de la Carta de Libranza.

    Returns
    -------
    pandas.DataFrame
        Columnas: ``Núm. Desc.``, ``Saldo capital``, ``Abono a capital``,
        ``Intereses``, ``IVA``, ``Descuento mensual``. ``Núm. Desc.`` es
        ``int`` y los montos son ``float``. Filas ordenadas por número de
        descuento.
    """
    filas = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tabla in page.extract_tables():
                header_idx = next(
                    (i for i, r in enumerate(tabla) if _is_amort_header(r)),
                    None,
                )
                if header_idx is None:
                    continue
                for row in tabla[header_idx + 1:]:
                    if _is_data_row(row):
                        filas.append(row[:6])

    df = pd.DataFrame(filas, columns=COLUMNS)
    df["Núm. Desc."] = df["Núm. Desc."].astype(int)
    for col in _MONEY_COLS:
        df[col] = df[col].map(_parse_money)
    return df.sort_values("Núm. Desc.").reset_index(drop=True)
