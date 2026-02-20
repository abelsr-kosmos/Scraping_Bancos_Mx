import re
from typing import List, Tuple, Optional

import pdfplumber
import pandas as pd
from rich.console import Console
from rich.table import Table


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


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _get_col_text(line_chars: list, x_min: float, x_max: float) -> str:
    """Extrae texto de los caracteres cuyo x0 cae en [x_min, x_max)."""
    chars = [c for c in line_chars if c["x0"] >= x_min and c["x0"] < x_max]
    chars.sort(key=lambda c: c["x0"])
    return "".join(c["text"] for c in chars).strip()


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


def _find_header_bottom(page) -> Optional[float]:
    """Encuentra el bottom del header de la tabla usando los rectángulos."""
    rects = page.rects
    if not rects:
        return None
    header_rects = [r for r in rects if r["x0"] < 60 and r["x1"] > 80]
    if header_rects:
        return max(r["bottom"] for r in header_rects)
    return None


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
        anio, mes_corte = _extraer_anio_mes(pdf)

        for page in pdf.pages:
            header_bottom = _find_header_bottom(page)
            if header_bottom is None:
                continue

            chars = [c for c in page.chars if c["top"] >= header_bottom - 2]
            if not chars:
                continue

            lines = _group_lines(chars)
            current_movement = None

            for _top, line_chars in lines:
                dia_oper   = _get_col_text(line_chars, *COL_BOUNDS["dia_oper"])
                dia_regis  = _get_col_text(line_chars, *COL_BOUNDS["dia_regis"])
                concepto   = _get_col_text(line_chars, *COL_BOUNDS["concepto"])
                usuario    = _get_col_text(line_chars, *COL_BOUNDS["usuario"])
                referencia = _get_col_text(line_chars, *COL_BOUNDS["referencia"])
                cargos     = _get_col_text(line_chars, *COL_BOUNDS["cargos"])
                abonos     = _get_col_text(line_chars, *COL_BOUNDS["abonos"])
                saldo      = _get_col_text(line_chars, *COL_BOUNDS["saldo"])

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
                has_saldo = bool(saldo and re.match(r"[\d,.]+$", saldo))
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


if __name__ == "__main__":
    
    # Ejemplo de uso
    pdf_path = "/home/abelsr/Proyects/OCR-General/Scraping_Bancos_Mx/notebooks/19991988_15122025_151027.pdf"
    df_movimientos = Scrap_Estado(pdf_path)
    
    console = Console()
    table = Table(title="Movimientos Banjercito")
    
    for column in df_movimientos.columns:
        table.add_column(column, style="cyan")
    
    for _, row in df_movimientos.iterrows():
        table.add_row(*[str(v) for v in row.values])
    
    console.print(table)