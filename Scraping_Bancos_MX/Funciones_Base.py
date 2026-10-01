import re

import pdfplumber
import pandas as pd
from ._normalizacion import montos_cero

# Una línea de movimiento empieza con "dd/mm/aaaa" seguido del resto de la
# fila (el concepto puede seguir envolviendo varias líneas antes y/o después
# de esta, pero la fecha y los montos siempre viven en una sola línea física).
FECHA_RE = re.compile(r'^(\d{2}/\d{2}/\d{4})\s*(.*)$')
MONTO_RE = re.compile(r'\d{1,3}(?:,\d{3})*\.\d{2}')

STOP_MARKER = "[SALDO INICIAL DE"


@montos_cero
def Scrap_Estado_Base(ruta_archivo: str) -> pd.DataFrame:
    """
    Extrae la tabla de movimientos de un estado de cuenta de Banco BASE.
    """
    with pdfplumber.open(ruta_archivo) as pdf:
        lineas = _extraer_lineas_movimientos(pdf)
    movimientos = _procesar_lineas(lineas)

    columnas = ["fecha", "descripcion", "deposito", "retiro", "saldo"]
    if not movimientos:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(movimientos, columns=columnas)


def _extraer_lineas_movimientos(pdf) -> list:
    """
    Junta, en orden, las líneas de texto de las páginas de "DETALLE DE
    OPERACIONES", ignorando encabezados repetidos y deteniéndose en el
    resumen final de la tabla (donde empieza el texto legal/fiscal).
    """
    lineas = []
    detenido = False
    for pagina in pdf.pages:
        if detenido:
            break
        texto = pagina.extract_text() or ""
        if "DETALLE DE OPERACIONES" not in texto:
            continue
        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea:
                continue
            if STOP_MARKER in linea:
                detenido = True
                break
            if linea == "DETALLE DE OPERACIONES":
                continue
            if linea.startswith("FECHA CONCEPTO/REFERENCIA"):
                continue
            if linea.startswith("Página "):
                continue
            lineas.append(linea)
    return lineas


def _parse_monto(texto: str) -> float:
    return float(texto.replace(",", ""))


def _procesar_lineas(lineas: list) -> list:
    """
    Agrupa las líneas en movimientos: cada línea sin fecha es concepto
    acumulado; al llegar una línea con fecha se cierra el movimiento con
    ese concepto acumulado + el texto restante de la propia línea de fecha.

    El signo de depósito/retiro se infiere comparando el saldo contra el
    saldo del movimiento anterior (igual que en Funciones_Banorte.py /
    Funciones_Scotiabank.py), en vez de depender de la columna (Cargos vs.
    Abonos) en la que cayó el número dentro del texto plano.
    """
    movimientos = []
    concepto_pendiente = []
    saldo_anterior = None

    for linea in lineas:
        m = FECHA_RE.match(linea)
        if not m:
            concepto_pendiente.append(linea)
            continue

        fecha, resto = m.group(1), m.group(2)
        montos = MONTO_RE.findall(resto)
        concepto_linea = MONTO_RE.sub("", resto).strip()
        if concepto_linea:
            concepto_pendiente.append(concepto_linea)
        descripcion = " ".join(concepto_pendiente).strip()
        concepto_pendiente = []

        if not montos:
            # Línea con fecha pero sin ningún monto reconocible: no hay
            # suficiente información para armar un movimiento, se ignora.
            continue

        saldo = _parse_monto(montos[-1])
        monto = _parse_monto(montos[-2]) if len(montos) > 1 else None

        if monto is None and "SALDO INICIAL" in descripcion.upper():
            # Fila de saldo inicial: no es un movimiento, solo fija el
            # punto de partida para inferir el signo del siguiente.
            saldo_anterior = saldo
            continue

        deposito = retiro = None
        if monto is not None:
            if saldo_anterior is None or saldo >= saldo_anterior:
                deposito = monto
            else:
                retiro = monto

        movimientos.append({
            "fecha": fecha,
            "descripcion": descripcion,
            "deposito": deposito,
            "retiro": retiro,
            "saldo": saldo,
        })
        saldo_anterior = saldo

    return movimientos
