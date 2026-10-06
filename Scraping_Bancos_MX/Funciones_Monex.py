"""
Parser para estados de cuenta de Monex.

LIMITACIÓN CONOCIDA (multi-divisa): una cuenta Monex puede tener varias
"libretas" de saldo independientes por divisa (peso mexicano, dólar
americano, euro, ...), cada una impresa en su propia sección
"Movimientos de <mes>[ en <divisa>]" con su propia continuidad de saldo.
Esta función NO combina esas secciones en una sola tabla (rompería la
continuidad del saldo, que es distinta por divisa). En vez de eso:
  - Si existe una sección "Movimientos de <mes>" sin sufijo de divisa
    (que es la que se imprime en pesos mexicanos), se usa esa.
  - Si no existe, se usa la primera sección de movimientos que aparezca
    en el documento (normalmente la única, cuando la cuenta no maneja
    más de una divisa).
Las demás divisas simplemente no se incluyen en el resultado.
"""

import re

import pdfplumber
import pandas as pd
from ._normalizacion import montos_cero

MONEY_RE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
DATE_RE = re.compile(r"\b(\d{1,2})\s*/\s*([A-Za-zÁÉÍÓÚáéíóú]{3})\b")

# Líneas de encabezado/pie que se repiten en cada página y no son parte de
# la descripción de ningún movimiento.
LINEAS_A_IGNORAR = [
    re.compile(r"^Estado de Cuenta \| Banco$"),
    re.compile(r"^CONTRATO: \d+$"),
    re.compile(r"^Movimientos de"),
    re.compile(r"^Fechas Descripci"),
    re.compile(r"^Liquidaci.n \(Pactada\)$"),
    re.compile(r"^Hoja \d+ de \d+$"),
    re.compile(r"^Saldo inicial:"),
    re.compile(r"^Saldo final:"),
]


def _extraer_anio_periodo(pdf) -> str:
    """Extrae el año del periodo declarado en la carátula. Algunos estados
    traen la portada como imagen (sin texto), así que se busca en las primeras
    páginas en vez de solo en la primera."""
    for page in pdf.pages[:5]:
        texto = page.extract_text() or ""
        match = re.search(r"PERIODO:.*", texto)
        if match:
            anios = re.findall(r"\d{4}", match.group())
            if anios:
                return anios[0]
    return ""


def _encabezado_movimientos(texto: str):
    """Regresa la línea "Movimientos de ..." de una página, o None si no tiene."""
    for line in texto.split("\n"):
        s = line.strip()
        if s.startswith("Movimientos de"):
            return s
    return None


def _elegir_divisa_objetivo(pdf) -> str:
    """
    Decide qué encabezado de sección de movimientos se va a extraer:
    el que no trae sufijo " en <divisa>" (peso mexicano) si existe,
    o si no, el primero que aparezca en el documento.
    """
    primer_encabezado = None
    for page in pdf.pages:
        encabezado = _encabezado_movimientos(page.extract_text() or "")
        if encabezado is None:
            continue
        if primer_encabezado is None:
            primer_encabezado = encabezado
        if " en " not in encabezado:
            return encabezado
    return primer_encabezado


def _extraer_lineas_seccion(pdf, encabezado_objetivo: str) -> list[str]:
    """Concatena las líneas útiles de todas las páginas que pertenecen a la
    sección de movimientos con encabezado `encabezado_objetivo`."""
    lineas = []
    for page in pdf.pages:
        texto = page.extract_text() or ""
        if _encabezado_movimientos(texto) != encabezado_objetivo:
            continue
        for line in texto.split("\n"):
            s = line.strip()
            if not s or any(patron.match(s) for patron in LINEAS_A_IGNORAR):
                continue
            lineas.append(s)
    return lineas


def _es_linea_de_montos(line: str) -> list[str]:
    """Si `line` es la fila con los montos de un movimiento (Abonos, Cargos,
    Movimiento garantía, Saldo en garantía, Saldo disponible, Saldo total),
    regresa esos montos; si no, regresa una lista vacía.

    Exige las 6 columnas completas: con menos, no hay forma de saber cuál de
    las 6 quedó vacía sin desalinear abono/cargo/saldo (montos6[0]/[1]/[-1]
    dejarían de corresponder a Abonos/Cargos/Saldo total)."""
    montos = MONEY_RE.findall(line)
    return montos if len(montos) >= 6 else []


# Línea que abre un movimiento nuevo (tipo de operación). Se usa para separar
# el texto que va DESPUÉS de la fila de montos (cola del movimiento anterior)
# del que va ANTES de la siguiente fila (encabezado del siguiente). "Comisión $"
# e "Intereses $" son líneas de detalle (cola), no inicios.
INICIO_MOVIMIENTO_RE = re.compile(
    r"^(?:Retiro|Dep[oó]sito|Abono|Cargo|Traspaso|Comisi[oó]n|Comision|Pago|Intereses?)\b(?!\s*\$)",
    re.IGNORECASE,
)
FIN_DETALLE_RE = re.compile(r"^Dato no verificado", re.IGNORECASE)


def _largo_cola(gap: list[str]) -> int:
    """Cuántas líneas de `gap` (las que hay entre dos filas de montos)
    pertenecen al movimiento anterior. El resto es el encabezado del
    siguiente. Si no hay una señal clara, ninguna (comportamiento previo)."""
    for i, line in enumerate(gap):
        if FIN_DETALLE_RE.match(line):
            return i + 1
        if INICIO_MOVIMIENTO_RE.match(line):
            return i
    return 0


@montos_cero
def Scrap_Estado_Monex(ruta_archivo: str) -> pd.DataFrame:
    """
    Extrae la tabla de movimientos de un estado de cuenta de Monex.

    Cada movimiento en el PDF se imprime como un bloque de varias líneas de
    texto (descripción libre + una línea con la fecha y los 6 montos de la
    tabla + más líneas de detalle). Esa línea de montos es la única señal
    estructural confiable, así que se usa como ancla: cada bloque termina
    justo en la línea que trae la fecha y >=5 montos con formato de dinero,
    y todo el texto acumulado desde el bloque anterior se usa como
    descripción. Ver el docstring del módulo sobre la limitación con
    cuentas multi-divisa.

    Parameters
    ----------
    ruta_archivo : str
        Ruta al archivo PDF del estado de cuenta.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: fecha, descripcion, deposito, retiro, saldo.
    """
    with pdfplumber.open(ruta_archivo) as pdf:
        anio = _extraer_anio_periodo(pdf)
        encabezado_objetivo = _elegir_divisa_objetivo(pdf)
        if encabezado_objetivo is None:
            return pd.DataFrame(columns=["fecha", "descripcion", "deposito", "retiro", "saldo"])
        lineas = _extraer_lineas_seccion(pdf, encabezado_objetivo)

    movimientos = []
    idx_montos = [i for i, line in enumerate(lineas) if _es_linea_de_montos(line)]

    # Fronteras cabeza/cola: el texto entre dos filas de montos se reparte
    # entre la cola del movimiento anterior y la cabeza del siguiente.
    inicio_cabeza = []  # índice donde empieza el texto previo de cada fila
    fin_cola = []       # índice (excl.) donde termina el texto posterior
    previo = -1
    for k, i in enumerate(idx_montos):
        sig = idx_montos[k + 1] if k + 1 < len(idx_montos) else len(lineas)
        cola = _largo_cola(lineas[i + 1:sig]) if k + 1 < len(idx_montos) else sig - i - 1
        fin_cola.append(i + 1 + cola)
        inicio_cabeza.append(previo + 1 if k == 0 else fin_cola[k - 1])
        previo = i

    for k, i in enumerate(idx_montos):
        line = lineas[i]
        cabeza = lineas[inicio_cabeza[k]:i]
        cola = lineas[i + 1:fin_cola[k]]
        montos6 = _es_linea_de_montos(line)[-6:]
        abono = float(montos6[0].replace(",", ""))
        cargo = float(montos6[1].replace(",", ""))
        saldo = float(montos6[-1].replace(",", ""))

        fecha_match = DATE_RE.search(line) or DATE_RE.search("\n".join(cabeza + [line]))
        if not fecha_match:
            # Sin fecha reconocible: no se puede formar un movimiento válido.
            continue

        dia, mes_abbr = fecha_match.group(1), fecha_match.group(2).upper()
        # Mismo formato que BBVA: dd/MMM/aaaa (p. ej. 01/JUN/2026)
        fecha = f"{dia.zfill(2)}/{mes_abbr}" + (f"/{anio}" if anio else "")

        # Limpia la línea de montos (deja solo el texto que no es fecha/monto,
        # quitando solo la primera fecha) y une cabeza + fila + cola.
        linea_limpia = MONEY_RE.sub("", DATE_RE.sub("", line, count=1))
        descripcion = re.sub(r"[\s|]+", " ", " ".join(cabeza + [linea_limpia] + cola)).strip()

        movimientos.append({
            "fecha": fecha,
            "descripcion": descripcion,
            "deposito": abono if abono > 0 else None,
            "retiro": cargo if cargo > 0 else None,
            "saldo": saldo,
        })

    return pd.DataFrame(movimientos, columns=["fecha", "descripcion", "deposito", "retiro", "saldo"])
