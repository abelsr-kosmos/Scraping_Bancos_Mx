import re

import pdfplumber
import pandas as pd
from ._normalizacion import montos_cero

MESES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

# Encabezado de la tabla de movimientos. Hay dos variantes según el estado de
# cuenta: "Día ..." (solo día del mes) o "Fecha ..." (fecha completa dd/mm/aaaa).
HEADER_RE = re.compile(r"(?:D[ií]a|Fecha)\s+Referencia\s+Descripci[oó]n\s+Retiros\s+Dep[oó]sitos\s+Saldo", re.IGNORECASE)
PERIODO_RE = re.compile(r"Periodo\s+Del:?\s*(\d{1,2})-(\w{3})-(\d{4})\s*Al\s*(\d{1,2})-(\w{3})-(\d{4})", re.IGNORECASE)
FOOTER_RE = re.compile(r"Banco Multiva", re.IGNORECASE)
FIN_TABLA_RE = re.compile(r"CARGOS OBJETADOS POR EL CLIENTE", re.IGNORECASE)

# Una línea de movimiento termina siempre en tres montos: retiro, depósito y
# saldo. El retiro, cuando aplica, viene con un "-" (a veces con un espacio
# después, a veces pegado); cuando no aplica es literalmente "0.00". El
# depósito nunca trae signo. El primer campo es el día (1-2 dígitos) o, en la
# otra variante, la fecha completa dd/mm/aaaa.
MOVIMIENTO_RE = re.compile(
    r"^(?P<fecha>\d{1,2}/\d{1,2}/\d{4}|\d{1,2})\s+"
    r"(?P<referencia>\S+)\s+"
    r"(?P<descripcion>.*?)\s+"
    r"(?P<retiro>-\s*[\d,]+\.\d{2}|0\.00)\s+"
    r"(?P<deposito>[\d,]+\.\d{2}|0\.00)\s+"
    r"(?P<saldo>-?\s*[\d,]+\.\d{2})\s*$"
)


def _extraer_periodo_inicio(textos_paginas):
    """Regresa (anio, mes) de inicio del periodo, o (None, None) si no se encontró."""
    for texto in textos_paginas:
        match = PERIODO_RE.search(texto)
        if match:
            _dia_i, mes_i, anio_i, _dia_f, _mes_f, _anio_f = match.groups()
            mes_num = MESES.get(mes_i[:3].upper())
            if mes_num:
                return int(anio_i), mes_num
    return None, None


def _limpiar_numero(texto: str) -> float:
    """Magnitud (sin signo) de un monto de retiro/depósito: ambas columnas
    solo indican si aplican o no, el signo de 'retiro' en el texto fuente es
    puramente tipográfico."""
    texto = texto.replace(",", "").replace(" ", "").lstrip("-")
    return float(texto)


def _limpiar_saldo(texto: str) -> float:
    """A diferencia de _limpiar_numero, el saldo sí puede ser legítimamente
    negativo (cuenta sobregirada) y ese signo debe conservarse."""
    return float(texto.replace(",", "").replace(" ", ""))


def _parse_monto_movimiento(texto: str):
    """Convierte el texto de retiro/depósito a float, o None si no aplica ('0.00')."""
    valor = _limpiar_numero(texto)
    return valor if valor != 0 else None


def _procesar_pagina(lineas, anio_actual, mes_actual, dia_anterior):
    """Extrae los movimientos de una página ya delimitada (sin encabezado/pie).

    Regresa (movimientos, anio_actual, mes_actual, dia_anterior) para poder
    seguir el conteo de mes/año a través de varias páginas.
    """
    movimientos = []
    movimiento_actual = None

    for linea in lineas:
        match = MOVIMIENTO_RE.match(linea.strip())
        if match:
            if movimiento_actual is not None:
                movimientos.append(movimiento_actual)

            fecha_cruda = match.group("fecha")
            if "/" in fecha_cruda:
                fecha = fecha_cruda
            elif mes_actual is not None:
                dia = int(fecha_cruda)
                if dia_anterior is not None and dia < dia_anterior:
                    mes_actual += 1
                    if mes_actual > 12:
                        mes_actual = 1
                        anio_actual += 1
                dia_anterior = dia
                fecha = f"{dia:02d}/{mes_actual:02d}/{anio_actual}"
            else:
                fecha = fecha_cruda

            movimiento_actual = {
                "fecha": fecha,
                "descripcion": match.group("descripcion").strip(),
                "deposito": _parse_monto_movimiento(match.group("deposito")),
                "retiro": _parse_monto_movimiento(match.group("retiro")),
                "saldo": _limpiar_saldo(match.group("saldo")),
            }
        else:
            linea_limpia = linea.strip()
            if linea_limpia and movimiento_actual is not None:
                movimiento_actual["descripcion"] += " " + linea_limpia

    if movimiento_actual is not None:
        movimientos.append(movimiento_actual)

    return movimientos, anio_actual, mes_actual, dia_anterior


@montos_cero
def Scrap_Estado_Multiva(ruta_archivo: str) -> pd.DataFrame:
    """
    Extrae la tabla de movimientos de un estado de cuenta de Banco Multiva.

    Soporta las dos variantes de encabezado observadas: estados con columna
    "Día" (solo día del mes, hay que reconstruir la fecha con el periodo de
    la carátula) y estados con columna "Fecha" (ya viene completa dd/mm/aaaa).

    Parameters
    ----------
    ruta_archivo : str
        Ruta al archivo PDF del estado de cuenta de Multiva.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: fecha, descripcion, deposito, retiro, saldo
    """
    todos_los_movimientos = []

    with pdfplumber.open(ruta_archivo) as pdf:
        textos_paginas = [pagina.extract_text() or "" for pagina in pdf.pages]
        anio_actual, mes_actual = _extraer_periodo_inicio(textos_paginas)
        dia_anterior = None

        for texto in textos_paginas:
            lineas = texto.split("\n")

            header_idx = -1
            fin_idx = len(lineas)
            for idx, linea in enumerate(lineas):
                if header_idx == -1 and HEADER_RE.search(linea):
                    header_idx = idx
                    continue
                if header_idx != -1 and (FIN_TABLA_RE.search(linea) or FOOTER_RE.search(linea)):
                    fin_idx = idx
                    break

            if header_idx == -1:
                continue

            movimientos, anio_actual, mes_actual, dia_anterior = _procesar_pagina(
                lineas[header_idx + 1:fin_idx], anio_actual, mes_actual, dia_anterior
            )
            todos_los_movimientos.extend(movimientos)

    if not todos_los_movimientos:
        return pd.DataFrame(columns=["fecha", "descripcion", "deposito", "retiro", "saldo"])

    df = pd.DataFrame(todos_los_movimientos)
    return df[["fecha", "descripcion", "deposito", "retiro", "saldo"]]
