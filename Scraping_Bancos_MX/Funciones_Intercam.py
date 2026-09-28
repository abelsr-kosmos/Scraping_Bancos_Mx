import re
from typing import Dict, List, Optional, Tuple

import pdfplumber
import pandas as pd


# Intercam Banco emite (al menos) dos plantillas de estado de cuenta para el
# mismo cliente, cada una con su propio layout de columnas:
#   - "cash_management": encabezado "CASH MANAGEMENT M.N. S INT", columnas
#     OPER/LIQ/COD./DESCRIPCIÓN/REFERENCIA/CARGOS/ABONOS/SALDO OPERACIÓN-LIQ.
#   - "unico": encabezado "ESTADO DE CUENTA ÚNICO", columnas
#     DÍA/FOLIO/CONCEPTO/DEPÓSITOS/RETIROS/SALDO.
# Esta función detecta cuál es y usa el extractor correspondiente.

MESES_INTERCAM = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

RE_MONTO = re.compile(r"^[\d,]+\.\d{2}$")

# "Periodo DEL 01/10/2024 AL 31/10/2024" (plantilla cash_management)
RE_PERIODO_SLASH = re.compile(
    r"Periodo\s+DEL\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+AL\s+(\d{1,2})/(\d{1,2})/(\d{4})"
)
# "Período DEL 2024-12-01 AL 2024-12-31" (plantilla unico)
RE_PERIODO_ISO = re.compile(
    r"Per[íi]odo\s+DEL\s+(\d{4})-(\d{2})-(\d{2})\s+AL\s+(\d{4})-(\d{2})-(\d{2})"
)

RE_FECHA_CORTA = re.compile(r"^\d{1,2}/[A-ZÁÉÍÓÚ]{3}$")
RE_DIA_SOLO = re.compile(r"^\d{1,2}$")

# (dia, mes, anio) de inicio y fin del periodo del estado de cuenta.
Periodo = Tuple[Tuple[int, int, int], Tuple[int, int, int]]


# ---------------------------------------------------------------------------
# Funciones comunes
# ---------------------------------------------------------------------------

def _extraer_periodo(texto: str) -> Optional[Periodo]:
    """Extrae ((dia,mes,anio)_inicio, (dia,mes,anio)_fin) del periodo del
    estado de cuenta, sin importar cuál de las dos plantillas sea."""
    match = RE_PERIODO_SLASH.search(texto)
    if match:
        d1, m1, y1, d2, m2, y2 = match.groups()
        return (int(d1), int(m1), int(y1)), (int(d2), int(m2), int(y2))

    match = RE_PERIODO_ISO.search(texto)
    if match:
        y1, m1, d1, y2, m2, d2 = match.groups()
        return (int(d1), int(m1), int(y1)), (int(d2), int(m2), int(y2))

    return None


def _parse_monto(texto: Optional[str]) -> Optional[float]:
    if not texto:
        return None
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def _agrupar_lineas(words: List[dict]) -> List[List[dict]]:
    """Agrupa palabras de una página en renglones según su coordenada 'top'."""
    palabras_ordenadas = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lineas: List[List[dict]] = []
    actual: List[dict] = []
    top_actual = None

    for w in palabras_ordenadas:
        if top_actual is None or abs(w["top"] - top_actual) > 2:
            if actual:
                lineas.append(actual)
            actual = [w]
            top_actual = w["top"]
        else:
            actual.append(w)

    if actual:
        lineas.append(actual)
    return lineas


def _es_inicio_pie_pagina(linea: List[dict]) -> bool:
    """Detecta el aviso legal recurrente ('Estimado Cliente, ... La GAT Real
    ... BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE ...'), que no
    pertenece a ningún movimiento y puede aparecer intercalado entre
    movimientos reales (no solo al pie de página)."""
    if len(linea) < 2:
        return False
    primeras = (linea[0]["text"], linea[1]["text"])
    if primeras[0] == "Estimado" and primeras[1].startswith("Cliente"):
        return True
    if primeras[0] == "BBVA" and primeras[1].startswith("MEXICO"):
        return True
    return False


def _es_linea_de_totales(linea: List[dict]) -> bool:
    """Detecta la fila de subtotal/total ('Total 5,669,042.38 5,688,988.30
    7,425.17') que el estado de cuenta imprime al final de cada hoja o
    segmento de la tabla. No empieza con fecha/día, así que sin este filtro
    se pega como continuación de texto del último movimiento real y sus
    montos terminan rellenando campos vacíos de esa fila (cargo/abono que no
    le pertenecen)."""
    return bool(linea) and linea[0]["text"].strip().lower() == "total"


def _nuevo_movimiento(fecha: str) -> Dict:
    return {
        "fecha": fecha,
        "descripcion_partes": [],
        "deposito": None,
        "retiro": None,
        "saldo": None,
    }


def _cerrar_movimiento(mov: Dict) -> Optional[Dict]:
    """Convierte el acumulador interno en la fila final, o None si el
    renglón no tenía ningún monto (basura de layout, no es un movimiento)."""
    deposito = _parse_monto(mov["deposito"])
    retiro = _parse_monto(mov["retiro"])
    if deposito is None and retiro is None:
        return None

    descripcion = " ".join(mov["descripcion_partes"])
    descripcion = re.sub(r"\s+", " ", descripcion).strip()

    return {
        "fecha": mov["fecha"],
        "descripcion": descripcion,
        "deposito": deposito,
        "retiro": retiro,
        "saldo": _parse_monto(mov["saldo"]),
    }


# ---------------------------------------------------------------------------
# Plantilla "cash_management" (CASH MANAGEMENT M.N. S INT)
# ---------------------------------------------------------------------------
# Límites de columnas (x0) obtenidos de las posiciones del encabezado "OPER
# LIQ COD. DESCRIPCIÓN REFERENCIA CARGOS ABONOS OPERACIÓN LIQUIDACIÓN". El
# estado de cuenta no imprime la referencia alineada a su columna de
# encabezado: en la práctica viene en el renglón de continuación, mezclada
# con la descripción, por eso todo lo que cae a la izquierda de CARGOS se
# trata como descripción.
CM_COL_OPER_MAX = 45
CM_COL_LIQ_MAX = 85
CM_COL_DESCRIPCION_MAX = 360
CM_COL_CARGO_MAX = 410
CM_COL_ABONO_MAX = 465
CM_COL_SALDO_OPERACION_MAX = 530


def _cm_es_inicio_movimiento(linea: List[dict]) -> bool:
    """Un renglón inicia un movimiento nuevo si sus dos primeras palabras
    son fechas cortas 'dd/MES' (columnas OPER y LIQ)."""
    return (
        len(linea) >= 2
        and bool(RE_FECHA_CORTA.match(linea[0]["text"]))
        and bool(RE_FECHA_CORTA.match(linea[1]["text"]))
    )


def _cm_clasificar_columna(x0: float) -> str:
    if x0 < CM_COL_OPER_MAX:
        return "oper"
    if x0 < CM_COL_LIQ_MAX:
        return "liq"
    if x0 < CM_COL_DESCRIPCION_MAX:
        return "descripcion"
    if x0 < CM_COL_CARGO_MAX:
        return "retiro"
    if x0 < CM_COL_ABONO_MAX:
        return "deposito"
    if x0 < CM_COL_SALDO_OPERACION_MAX:
        return "saldo_operacion"
    return "saldo_liquidacion"


def _cm_asignar_palabra(movimiento: Dict, tipo: str, texto: str) -> None:
    if tipo in ("oper", "liq"):
        return
    if tipo == "descripcion":
        movimiento["descripcion_partes"].append(texto)
        return
    if tipo == "saldo_liquidacion":
        # La liquidación es el saldo definitivo del movimiento y se prefiere
        # sobre el de operación, pero solo la primera vez: si no, una palabra
        # de un renglón de continuación que cayera por coincidencia en este
        # rango de columna podría pisar el saldo ya correcto del renglón
        # inicial del movimiento.
        if not movimiento.get("_saldo_liquidacion_fijado") and RE_MONTO.match(texto):
            movimiento["saldo"] = texto
            movimiento["_saldo_liquidacion_fijado"] = True
        return
    if tipo == "saldo_operacion":
        tipo = "saldo"
    if tipo in ("retiro", "deposito", "saldo") and RE_MONTO.match(texto):
        if movimiento[tipo] is None:
            movimiento[tipo] = texto


def _cm_fecha_con_anio(fecha_corta: str, periodo: Optional[Periodo]) -> str:
    dia, mes_abr = fecha_corta.split("/")
    mes_num = MESES_INTERCAM.get(mes_abr)
    if mes_num is None or periodo is None:
        return fecha_corta
    (_, mes_inicio, anio_inicio), (_, mes_fin, anio_fin) = periodo
    anio = anio_inicio if mes_num == mes_inicio else anio_fin
    return f"{int(dia):02d}/{mes_num:02d}/{anio}"


def _cm_procesar_pagina(pagina, periodo: Optional[Periodo]) -> List[Dict]:
    words = pagina.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return []

    movimientos: List[Dict] = []
    actual: Optional[Dict] = None
    en_pie_pagina = False

    for linea in _agrupar_lineas(words):
        if _cm_es_inicio_movimiento(linea):
            en_pie_pagina = False
            if actual is not None:
                movimientos.append(actual)
            actual = _nuevo_movimiento(_cm_fecha_con_anio(linea[0]["text"], periodo))
            resto = linea[2:]
        elif _es_inicio_pie_pagina(linea):
            en_pie_pagina = True
            continue
        elif en_pie_pagina:
            continue
        elif _es_linea_de_totales(linea):
            continue
        elif actual is not None:
            resto = linea
        else:
            continue

        for w in resto:
            # Se clasifica por el centro de la palabra, no por x0: un monto
            # ancho ("560,000.00") alineado a la derecha de su columna puede
            # tener el borde izquierdo (x0) cayendo en la columna anterior
            # (el mismo tipo de bug de límite de columna que se corrigió en
            # Funciones_BBVA.py / correccion_abono_cargo).
            _cm_asignar_palabra(actual, _cm_clasificar_columna((w["x0"] + w["x1"]) / 2), w["text"])

    if actual is not None:
        movimientos.append(actual)

    return movimientos


# ---------------------------------------------------------------------------
# Plantilla "unico" (ESTADO DE CUENTA ÚNICO)
# ---------------------------------------------------------------------------
# Límites de columnas (x0) obtenidos del encabezado "DÍA FOLIO CONCEPTO
# DEPÓSITOS RETIROS SALDO".
UN_COL_DIA_MAX = 70
UN_COL_FOLIO_MAX = 140
UN_COL_CONCEPTO_MAX = 400
UN_COL_DEPOSITO_MAX = 465
UN_COL_RETIRO_MAX = 528


def _un_es_inicio_movimiento(linea: List[dict]) -> bool:
    """Un renglón inicia un movimiento nuevo si empieza con un número de
    día (1-31) en la columna DÍA."""
    if not linea:
        return False
    primera = linea[0]
    return bool(RE_DIA_SOLO.match(primera["text"])) and primera["x0"] < UN_COL_DIA_MAX


def _un_clasificar_columna(x0: float) -> str:
    if x0 < UN_COL_DIA_MAX:
        return "dia"
    if x0 < UN_COL_FOLIO_MAX:
        return "folio"
    if x0 < UN_COL_CONCEPTO_MAX:
        return "concepto"
    if x0 < UN_COL_DEPOSITO_MAX:
        return "deposito"
    if x0 < UN_COL_RETIRO_MAX:
        return "retiro"
    return "saldo"


def _un_asignar_palabra(movimiento: Dict, tipo: str, texto: str) -> None:
    if tipo == "dia":
        return
    if tipo in ("folio", "concepto"):
        movimiento["descripcion_partes"].append(texto)
        return
    if tipo in ("deposito", "retiro", "saldo") and RE_MONTO.match(texto):
        if movimiento[tipo] is None:
            movimiento[tipo] = texto


def _un_fecha(dia_texto: str, periodo: Optional[Periodo]) -> str:
    if periodo is None:
        return dia_texto
    (dia_inicio, mes_inicio, anio_inicio), (dia_fin, mes_fin, anio_fin) = periodo
    dia = int(dia_texto)
    if (mes_inicio, anio_inicio) == (mes_fin, anio_fin):
        mes, anio = mes_inicio, anio_inicio
    elif dia >= dia_inicio:
        mes, anio = mes_inicio, anio_inicio
    else:
        mes, anio = mes_fin, anio_fin
    return f"{dia:02d}/{mes:02d}/{anio}"


def _un_procesar_pagina(pagina, periodo: Optional[Periodo]) -> List[Dict]:
    words = pagina.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return []

    movimientos: List[Dict] = []
    actual: Optional[Dict] = None
    en_pie_pagina = False

    for linea in _agrupar_lineas(words):
        if _un_es_inicio_movimiento(linea):
            en_pie_pagina = False
            if actual is not None:
                movimientos.append(actual)
            actual = _nuevo_movimiento(_un_fecha(linea[0]["text"], periodo))
            resto = linea[1:]
        elif _es_inicio_pie_pagina(linea):
            en_pie_pagina = True
            continue
        elif en_pie_pagina:
            continue
        elif _es_linea_de_totales(linea):
            continue
        elif actual is not None:
            resto = linea
        else:
            continue

        for w in resto:
            # Ver comentario equivalente en _cm_procesar_pagina: se clasifica
            # por el centro de la palabra, no por x0, para no cortar montos
            # anchos alineados a la derecha de su columna.
            _un_asignar_palabra(actual, _un_clasificar_columna((w["x0"] + w["x1"]) / 2), w["text"])

    if actual is not None:
        movimientos.append(actual)

    return movimientos


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def _detectar_plantilla(texto: str) -> str:
    if "CUENTA ÚNICO" in texto or "CUENTA UNICO" in texto:
        return "unico"
    return "cash_management"


def Scrap_Estado_Intercam(ruta_archivo: str) -> pd.DataFrame:
    """
    Extrae la tabla de movimientos de un estado de cuenta de Intercam Banco.
    Soporta las dos plantillas observadas: "CASH MANAGEMENT M.N. S INT" y
    "ESTADO DE CUENTA ÚNICO".

    Parameters
    ----------
    ruta_archivo : str
        Ruta al archivo PDF del estado de cuenta.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: fecha, descripcion, deposito, retiro, saldo.
        En la plantilla "cash_management", `saldo` solo viene poblado en los
        renglones donde el propio estado de cuenta lo imprime (no en cada
        movimiento); en "unico" viene poblado en todos los movimientos.

    LIMITACIÓN CONOCIDA: un mismo PDF "unico" puede imprimir varias cuentas
    ligadas (cuenta multiempresarial) una tras otra, cada una con su propia
    numeración de día y continuidad de saldo independiente. Esta función
    concatena todas las filas en un solo DataFrame en el orden en que
    aparecen en el PDF sin marcar ese límite entre cuentas, así que la fila
    justo después de un cambio de cuenta puede verse como una discontinuidad
    de saldo si se reconcilia como si fuera una sola cuenta continua.
    """
    filas: List[Dict] = []

    with pdfplumber.open(ruta_archivo) as pdf:
        texto_primeras_paginas = "\n".join((p.extract_text() or "") for p in pdf.pages[:3])
        periodo = _extraer_periodo(texto_primeras_paginas)
        plantilla = _detectar_plantilla(texto_primeras_paginas)
        procesar_pagina = _un_procesar_pagina if plantilla == "unico" else _cm_procesar_pagina

        for pagina in pdf.pages:
            for mov in procesar_pagina(pagina, periodo):
                fila = _cerrar_movimiento(mov)
                if fila is not None:
                    filas.append(fila)

    return pd.DataFrame(filas, columns=["fecha", "descripcion", "deposito", "retiro", "saldo"])
