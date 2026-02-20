import re
from typing import Tuple, Optional

import pdfplumber
import pandas as pd


# Límites de columnas del PDF de Banjercito (x0, x1) obtenidos de los
# rectángulos del encabezado de la tabla "DETALLE DE MOVIMIENTOS".
COL_BOUNDS = {
    "dia_oper":   (28, 56),
    "dia_regis":  (56, 83),
    "concepto":   (83, 253),
    "usuario":    (253, 304),
    "referencia": (304, 367),
    "cargos":     (367, 441),
    "abonos":     (441, 516),
    "saldo":      (516, 590),
}

HAS_NUMERIC_RE = re.compile(r"^[\d,.]+$")


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _split_line_cols(line_chars: list) -> dict:
    """Divide una línea en columnas con una sola pasada por los caracteres."""
    values = {key: [] for key in COL_BOUNDS}

    for c in line_chars:
        x0 = c["x0"]
        if x0 < COL_BOUNDS["dia_oper"][0] or x0 >= COL_BOUNDS["saldo"][1]:
            continue

        if x0 < COL_BOUNDS["dia_oper"][1]:
            values["dia_oper"].append(c["text"])
        elif x0 < COL_BOUNDS["dia_regis"][1]:
            values["dia_regis"].append(c["text"])
        elif x0 < COL_BOUNDS["concepto"][1]:
            values["concepto"].append(c["text"])
        elif x0 < COL_BOUNDS["usuario"][1]:
            values["usuario"].append(c["text"])
        elif x0 < COL_BOUNDS["referencia"][1]:
            values["referencia"].append(c["text"])
        elif x0 < COL_BOUNDS["cargos"][1]:
            values["cargos"].append(c["text"])
        elif x0 < COL_BOUNDS["abonos"][1]:
            values["abonos"].append(c["text"])
        else:
            values["saldo"].append(c["text"])

    return {k: "".join(v).strip() for k, v in values.items()}


def _line_text(line_chars: list) -> str:
    return "".join(c["text"] for c in line_chars).strip()


def _group_lines(chars: list, tol: float = 1.5) -> list:
    """Agrupa caracteres por su coordenada 'top' con tolerancia."""
    if not chars:
        return []
    sorted_chars = sorted(chars, key=lambda c: (c["top"], c["x0"]))
    lines: list = []
    current_top = sorted_chars[0]["top"]
    current_chars = [sorted_chars[0]]

    for c in sorted_chars[1:]:
        if abs(c["top"] - current_top) <= tol:
            current_chars.append(c)
        else:
            lines.append((current_top, current_chars))
            current_top = c["top"]
            current_chars = [c]
    lines.append((current_top, current_chars))
    return lines


def _find_data_start_index(lines: list) -> int:
    """Encuentra el índice donde inicia la data de movimientos."""
    header_idx = -1

    for idx, (_top, line_chars) in enumerate(lines):
        text = _line_text(line_chars).upper()
        if "DETALLE DE MOVIMIENTOS" in text:
            header_idx = idx
            continue

        if "CONCEPTO" in text and ("DÍA" in text or "DIA" in text):
            if header_idx == -1 or idx >= header_idx:
                return idx + 1

    return -1


def _parse_monto(val: str) -> Optional[float]:
    """Convierte un string de monto a float, o None si está vacío."""
    if not val or not val.strip():
        return None
    val = val.replace(",", "").strip()
    try:
        return float(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

MESES = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
}


def _extraer_anio_mes(pdf) -> Tuple[str, str]:
    """Extrae año y mes numérico del texto 'Fecha de Corte' en cualquier página."""
    for page in pdf.pages:
        text = page.extract_text() or ""
        match = re.search(r"Fecha de Corte\.?:?\s*\d{1,2}\s+(\w+)\s+(\d{4})", text)
        if match:
            mes_nombre = match.group(1).upper()
            anio = match.group(2)
            mes = MESES.get(mes_nombre, "01")
            return anio, mes
    return "", ""


def Scrap_Estado(ruta_archivo: str) -> pd.DataFrame:
    """
    Extrae la tabla de movimientos de un estado de cuenta de Banjercito.

    Parameters
    ----------
    ruta_archivo : str
        Ruta al archivo PDF del estado de cuenta de Banjercito.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: fecha, descripcion, retiros, depositos, saldo
    """
    all_movements: list = []

    with pdfplumber.open(ruta_archivo) as pdf:
        anio, _mes_corte = _extraer_anio_mes(pdf)

        for page in pdf.pages:
            chars = page.chars
            if not chars:
                continue

            lines = _group_lines(chars)
            data_start = _find_data_start_index(lines)
            if data_start == -1:
                continue

            current_movement = None

            for _top, line_chars in lines[data_start:]:
                cols = _split_line_cols(line_chars)
                dia_oper = cols["dia_oper"]
                dia_regis = cols["dia_regis"]
                concepto = cols["concepto"]
                usuario = cols["usuario"]
                referencia = cols["referencia"]
                cargos = cols["cargos"]
                abonos = cols["abonos"]
                saldo = cols["saldo"]

                # Saltar encabezado de columnas
                if "Concepto" in concepto or "Día" in dia_oper:
                    continue

                # Saltar fila de saldo inicial (SALDO...)
                if "SALDO" in abonos:
                    continue

                # Ignorar texto fuera de la tabla
                has_table_data = bool(dia_oper or saldo or cargos or abonos)
                if not has_table_data and not current_movement:
                    continue

                # Detectar nueva fila de movimiento:
                # 1) Tiene saldo numérico, O
                # 2) Tiene dia_oper + (cargos o abonos) → movimiento en borde de página sin saldo
                has_saldo = bool(saldo and HAS_NUMERIC_RE.match(saldo))
                has_monto = bool(cargos or abonos)
                is_new_movement = has_saldo or (bool(dia_oper) and has_monto and not has_saldo)

                if is_new_movement:
                    if current_movement:
                        all_movements.append(current_movement)

                    current_movement = {
                        "dia_oper": dia_oper,
                        "dia_regis": dia_regis,
                        "concepto": concepto,
                        "usuario": usuario,
                        "referencia": referencia,
                        "cargos": cargos,
                        "abonos": abonos,
                        "saldo": saldo,
                    }
                elif current_movement and concepto:
                    # Línea de continuación del concepto
                    current_movement["concepto"] += " " + concepto
                    if referencia and not current_movement["referencia"]:
                        current_movement["referencia"] = referencia
                    if usuario and not current_movement["usuario"]:
                        current_movement["usuario"] = usuario

            if current_movement:
                all_movements.append(current_movement)

    if not all_movements:
        return pd.DataFrame(columns=["fecha", "descripcion", "retiros", "depositos", "saldo"])

    df = pd.DataFrame(all_movements)

    # Construir fecha dd/mm/yyyy a partir de "DD M" y el año de la fecha de corte
    def _format_fecha(row):
        raw = row["dia_regis"].strip() if row["dia_regis"].strip() else row["dia_oper"].strip()
        parts = raw.split()
        if len(parts) == 2:
            dia = parts[0].zfill(2)
            mes = parts[1].zfill(2)
            return f"{dia}/{mes}/{anio}"
        return raw

    df["fecha"] = df.apply(_format_fecha, axis=1)

    # Construir descripción limpia
    df["descripcion"] = (
        df["concepto"]
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Parsear montos numéricos
    df["retiros"]   = df["cargos"].apply(_parse_monto)
    df["depositos"] = df["abonos"].apply(_parse_monto)
    df["saldo"]     = df["saldo"].apply(_parse_monto)
    
    # Quita filas donde no haya retiro ni depósito (ej. filas de continuación sin monto)
    df = df[~((df["retiros"].isna() | (df["retiros"] == 0)) & (df["depositos"].isna() | (df["depositos"] == 0)))]

    return df[["fecha", "descripcion", "retiros", "depositos", "saldo"]].copy()
