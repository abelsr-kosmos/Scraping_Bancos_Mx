import re
from datetime import date
from typing import Optional

import pdfplumber
import pandas as pd
from ._normalizacion import montos_cero


_MESES_NUM = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
_RE_PERIODO = re.compile(
    r"(\d{1,2})/([A-Z]{3})/(\d{4})\s+AL\s+(\d{1,2})/([A-Z]{3})/(\d{4})", re.IGNORECASE)


_MESES_LARGOS = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
                 "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
_RE_PERIODO_DEL_AL = re.compile(
    r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})", re.IGNORECASE)
_RE_CORTE = re.compile(r"ESTADO\s+DE\s+CUENTA\s+AL\s+(\d{1,2})\s+DE\s+([A-Za-z]+)\s+DE\s+(\d{4})", re.IGNORECASE)


def _periodo_alterno(texto):
    """'Periodo del 01 al 30 de noviembre de 2024', o la fecha de corte
    ('ESTADO DE CUENTA AL 20 DE DICIEMBRE DE 2024') como fin y un mes antes
    como inicio."""
    try:
        m = _RE_PERIODO_DEL_AL.search(texto)
        if m and m.group(3).upper() in _MESES_LARGOS:
            mes, anio = _MESES_LARGOS[m.group(3).upper()], int(m.group(4))
            return date(anio, mes, int(m.group(1))), date(anio, mes, int(m.group(2)))
        m = _RE_CORTE.search(texto)
        if m and m.group(2).upper() in _MESES_LARGOS:
            fin = date(int(m.group(3)), _MESES_LARGOS[m.group(2).upper()], int(m.group(1)))
            ini = date(fin.year - (fin.month == 1), 12 if fin.month == 1 else fin.month - 1, 1)
            return ini, fin
    except ValueError:
        pass
    return None


def extraer_periodo(texto):
    """Busca 'DD/MMM/AAAA AL DD/MMM/AAAA' (RESUMEN DEL ...) y regresa
    (date_inicio, date_fin), o None si no aparece / no es válido."""
    texto = re.sub(r"\s*/\s*", "/", re.sub(r"(?<=\d)[ \t]+(?=\d)", "", texto or ""))
    m = _RE_PERIODO.search(texto)
    if not m:
        return _periodo_alterno(texto)
    try:
        ini = date(int(m.group(3)), _MESES_NUM[m.group(2).upper()], int(m.group(1)))
        fin = date(int(m.group(6)), _MESES_NUM[m.group(5).upper()], int(m.group(4)))
    except (KeyError, ValueError):
        return None
    return (ini, fin) if ini <= fin else None


def fecha_con_anio(fecha, periodo):
    """'20 MAR' + periodo -> '20/03/2024' (dd/mm/aaaa). Si no hay periodo o la
    fecha no se entiende, regresa la fecha tal cual."""
    if not periodo or not isinstance(fecha, str):
        return fecha
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]{3})\s*$", fecha)
    if not m or m.group(2).upper() not in _MESES_NUM:
        return fecha
    dia, mes = int(m.group(1)), _MESES_NUM[m.group(2).upper()]
    ini, fin = periodo
    candidatos = []
    for anio in range(ini.year, fin.year + 1):
        try:
            candidatos.append(date(anio, mes, dia))
        except ValueError:
            pass
    if not candidatos:
        return fecha
    dentro = [d for d in candidatos if ini <= d <= fin]
    elegido = (dentro or candidatos)[-1]
    return elegido.strftime("%d/%m/%Y")

MONTO_EN_BLOQUE = True

@montos_cero
def Scrap_Estado_Banamex(ruta_archivo):
    """
    Extrae la tabla de movimientos de un estado de cuenta de Banamex.

    LIMITACIÓN CONOCIDA: en estados de cuenta con muchas transacciones de
    terminal/caja por día (formato "CAJA ... AUT ... / HORA ... <monto>"
    antes de cada línea "dd MES ..."), el signo de cada movimiento se decide
    por palabras clave en la descripción (RECIBIDO/DEPOSITO = depósito;
    PAGO/COMISION/IVA/COBRO/CARGO/INTERBANCARIO = retiro) porque ni la
    posición x del monto ni el saldo (que solo se imprime de vez en cuando)
    son señales confiables en ese layout. Validado contra 2 estados reales:
    la cobertura de movimientos es casi completa, pero la reconciliación de
    saldo por tramos no cuadra al 100% (probablemente algunas transacciones
    con conceptos no cubiertos por las palabras clave, o con más de un monto
    en su bloque de continuación). Tratar con más cautela que otros bancos
    si la precisión exacta de depósito/retiro es crítica.
    """
    df = procesar_pdf(ruta_archivo)
    df.columns = [col.lower() for col in df.columns]
    # Una fila es un movimiento real si tiene retiro o depósito; NO exigir
    # también 'saldo' aquí, porque varios estados de cuenta reales solo lo
    # imprimen de vez en cuando (no en cada movimiento) - exigirlo descartaba
    # la enorme mayoría de movimientos válidos.
    df = df.dropna(subset=['retiro', 'deposito'], how='all')
    return df

def es_linea_movimiento(linea):
    """
    Determina si la línea inicia un 'movimiento' nuevo
    en formato 'dd mmm' en dos tokens separados:
    - tokens[0] = día (1-2 dígitos)
    - tokens[1] = mes (3 letras mayúsculas, p. ej. DIC, ENE)
    """
    tokens = linea.split()
    if len(tokens) < 2:
        return False

    # Verificar si tokens[0] es dd y tokens[1] es mmm
    if not re.match(r'^\d{1,2}$', tokens[0]):
        return False
    if not re.match(r'^[A-Z]{3}$', tokens[1]):
        return False

    return True

def es_numero_monetario(texto):
    """
    Determina si un texto es un número tipo '100,923.30'.
    Ajusta si tu PDF usa otro formato (p.ej. 100.923,30).
    """
    return bool(re.match(r'^[\d,]+\.\d{2}$', texto.strip()))

def parse_monetario(txt):
    """Convertir texto '100,923.30' a número 100923.30."""
    txt = txt.strip()
    sign = 1

    if txt.startswith("(") and txt.endswith(")"):
        sign = -1
        txt = txt[1:-1].strip()
    elif txt.startswith("-"):
        sign = -1
        txt = txt[1:].strip()
    txt = txt.replace(",", "")
    return sign * float(txt)

# x1 (borde derecho) de los montos de cada columna en los estados Banamex:
# RETIROS ~315-320, DEPOSITOS ~395, SALDO ~470-475.
_X1_MAX_RETIRO = 355
_X1_MAX_DEPOSITO = 435


def _lado_por_columna(x1):
    """'retiro' / 'deposito' segun la columna donde termina el monto, o None."""
    if x1 <= _X1_MAX_RETIRO:
        return "retiro"
    if x1 <= _X1_MAX_DEPOSITO:
        return "deposito"
    return None


def dist(a, b):
    """Distancia absoluta entre dos valores."""
    return abs(a - b)

def procesar_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:

        if len(pdf.pages) == 0:
            raise Exception("El PDF está vacío.")

        # =======================
        # 1) DETECTAR ENCABEZADOS EN LA 1RA PÁGINA
        # =======================
        page0 = pdf.pages[0]
        words_page0 = page0.extract_words()
        periodo_texto = "\n".join((pg.extract_text() or "") for pg in pdf.pages[:2])

        encabezados_buscar = ["RETIROS", "DEPOSITOS", "SALDO"]
        MESES_CORTOS = {"ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
            "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"}

        col_positions = {}

        regionEmpresa = (75, 165.25599999999997, 282, 173.25599999999997)

        croppedEmpresa = pdf.pages[0].within_bbox(regionEmpresa)
        empresa_str = croppedEmpresa.extract_text() or ""

        # Agrupamos las palabras de la primera página por 'top' para formar líneas
        lineas_dict_page0 = {}
        for w in words_page0:
            top_approx = int(w['top'])
            if top_approx not in lineas_dict_page0:
                lineas_dict_page0[top_approx] = []
            lineas_dict_page0[top_approx].append(w)

        lineas_ordenadas_page0 = sorted(lineas_dict_page0.items(), key=lambda x: x[0])

        # Buscamos la línea que contenga los 3 encabezados
        for top_val, words_in_line in lineas_ordenadas_page0:
            line_text_upper = " ".join(w['text'].strip().upper() for w in words_in_line)
            # Si en esta línea aparecen los 3 encabezados, es la línea real de columnas
            if all(h in line_text_upper for h in encabezados_buscar):
                # Extraemos la coordenada de cada encabezado
                for w in words_in_line:
                    w_text_upper = w['text'].strip().upper()
                    if w_text_upper in encabezados_buscar:
                        center_x = (w['x0'] + w['x1']) / 2
                        col_positions[w_text_upper] = center_x
                break

        # Ordenamos por la coordenada X
        columnas_ordenadas = sorted(col_positions.items(), key=lambda x: x[1])

        # =======================
        # 2) VARIABLES PARA ENCABEZADOS DEL EXCEL
        # =======================
        no_cliente_str = ""
        rfc_str = ""

        # =======================
        # 3) FRASES A OMITIR (skip) Y A DETENER (stop)
        # =======================
        skip_phrases = [
            "ESTADO DE CUENTA AL",
            "Página",
        ]
        skip_phrases = [s.upper() for s in skip_phrases]

        stop_phrases = [
            "SALDO MINIMO REQUERIDO",
            # "COMISIONES EFECTIVAMENTE COBRADAS"
        ]

        start_reading = False
        stop_reading = False
        RE_ENCABEZADO = re.compile(
            r"^(CLIENTE:\s*\d+|DETALLE DE OPERACIONES|FECHA CONCEPTO RETIROS|\d{6}\.\w+\.OD\.\d{4}\.\d{2})")
        periodo = extraer_periodo(periodo_texto)

        todos_los_movimientos = []
        movimiento_actual = None
        # En algunos estados de cuenta, el bloque "CAJA/AUT/HORA/SUC <monto>"
        # de una transacción se imprime ANTES de su propia línea "dd MES ..."
        # (pertenece a la transacción que sigue, no a la que está abierta en
        # ese momento). Estos montos se guardan aquí hasta que arranca el
        # siguiente movimiento, momento en el que se le asignan a ese
        # movimiento nuevo en vez de al que se acaba de cerrar.
        #
        # "Monto" guarda la magnitud sin signo (el layout real no separa de
        # forma confiable la columna de Cargos de la de Abonos por posición
        # x: en al menos un estado real, un pago claramente saliente cae del
        # lado de "Depositos"). El signo se decide después comparando contra
        # el Saldo de la fila anterior, igual que en Funciones_Base.py.
        monto_pendiente = {"Monto": None, "Saldo": None}

        # =======================
        # 4) RECORRER TODAS LAS PÁGINAS PARA DETECTAR MOVIMIENTOS
        # =======================
        for page_index, page in enumerate(pdf.pages):
            if stop_reading:
                break

            words = page.extract_words()
            # Agrupamos por 'top'
            lineas_dict = {}
            for w in words:
                top_approx = int(w['top'])
                if top_approx not in lineas_dict:
                    lineas_dict[top_approx] = []
                lineas_dict[top_approx].append(w)

            lineas_ordenadas = sorted(lineas_dict.items(), key=lambda x: x[0])

            # Encabezado repetido en cada hoja (CLIENTE, Página, razón social, "DETALLE DE
            # OPERACIONES", "FECHA CONCEPTO RETIROS...") y clave de pie ("000180.B06CHDA...");
            # si no se omiten, se pegan a la descripción del movimiento que cruza la hoja.
            top_encabezado = next((t for t, ws in lineas_ordenadas
                                   if "FECHA CONCEPTO RETIROS" in " ".join(w['text'] for w in ws).upper()), None)

            for top_val, words_in_line in lineas_ordenadas:
                if stop_reading:
                    break

                line_text = " ".join(w['text'] for w in words_in_line)
                line_text_upper = line_text.upper()

                # Detectar periodo, p. ej. "RESUMEN DEL: 01/DIC/2023 AL 31/DIC/2023"
                if "RESUMEN" in line_text_upper and "DEL" in line_text_upper and periodo is None:
                    periodo = extraer_periodo(line_text)
                if "RESUMEN" in line_text_upper and "DEL:" in line_text_upper:
                    tokens_line = line_text.split()
                    fechas = [t for t in tokens_line if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', t)]
                    if len(fechas) == 2:
                        periodo_str = f"{fechas[0]} al {fechas[1]}"
                    else:
                        periodo_str = line_text
                    continue

                # Revisar stop_phrases
                if any(sp in line_text_upper for sp in stop_phrases):
                    stop_reading = True
                    break

                # Empezar a leer movimientos cuando detectemos la primera fecha "dd mmm"
                if not start_reading:
                    tokens_line = line_text.split()
                    found_day = any(re.match(r'^\d{1,2}$', t) for t in tokens_line)
                    found_month = any(re.match(r'^[A-Z]{3}$', t) for t in tokens_line)
                    if found_day and found_month:
                        start_reading = True
                    else:
                        # Aún no es movimiento, saltar
                        continue

                # Omitir líneas con skip_phrases
                if any(sp in line_text_upper for sp in skip_phrases):
                    continue
                # Encabezado/pie que se repite en cada hoja y se cuela en medio de
                # la descripción del movimiento que cruza de página
                # (solo se omite su texto: un monto puede caer en la misma línea)
                es_encabezado = (bool(RE_ENCABEZADO.search(line_text_upper))
                                 or (top_encabezado is not None and top_val <= top_encabezado))

                # ¿Es un nuevo movimiento? => tokens[0] = dd, tokens[1] = mmm
                if es_linea_movimiento(line_text_upper):
                    # Guardar el anterior
                    if movimiento_actual:
                        todos_los_movimientos.append(movimiento_actual)

                    tokens_line = line_text_upper.split()
                    movimiento_actual = {
                        "Fecha": f"{tokens_line[0]} {tokens_line[1]}",
                        "Descripcion": "",
                        "DescSigno": "",
                        "Monto": monto_pendiente["Monto"],
                        "Saldo": monto_pendiente["Saldo"],
                        "Lado": monto_pendiente.get("Lado"),
                    }
                    monto_pendiente = {"Monto": None, "Saldo": None, "Lado": None}
                    es_linea_nueva = True
                else:
                    # Continuación
                    if not movimiento_actual:
                        movimiento_actual = {
                            "Fecha": None,
                            "Descripcion": "",
                            "DescSigno": "",
                            "Monto": None,
                            "Saldo": None,
                            "Lado": None,
                        }
                    es_linea_nueva = False

                # Asignar montos por coordenadas. Si la línea es continuación
                # (no la que abrió el movimiento), el monto se guarda en el
                # buffer por si en realidad pertenece al siguiente movimiento
                # (ver comentario de monto_pendiente arriba); si para cuando
                # cierre este movimiento nadie reclamó el buffer, se pierde,
                # que es preferible a asignárselo al movimiento equivocado.
                destino = movimiento_actual if MONTO_EN_BLOQUE else (movimiento_actual if es_linea_nueva else monto_pendiente)
                for i_w, w in enumerate(words_in_line):
                    txt = w['text'].strip()
                    center_w = (w['x0'] + w['x1']) / 2

                    if es_numero_monetario(txt) and center_w > 260 and center_w != 415:
                        val = parse_monetario(txt)
                        # Límite (centro x) calibrado contra estados reales:
                        # SALDO ~452, con margen amplio por debajo para el
                        # monto (Cargos/Abonos ~283-380, según el estado).
                        if center_w < 415:
                            destino["Monto"] = val
                            destino["Lado"] = _lado_por_columna(w['x1'])
                        else:
                            destino["Saldo"] = val
                    elif es_encabezado:
                        # fuera de la descripción, pero sí cuenta para deducir el signo
                        movimiento_actual["DescSigno"] += " " + txt
                        continue
                    else:
                        # Texto al concepto: solo se omite la fecha (dd mmm) con la
                        # que abre el movimiento; "CAJA 3", "SUC 12" y demás números
                        # sueltos del concepto se conservan, igual que los montos
                        # fuera de las columnas de monto/saldo.
                        if es_linea_nueva and i_w < 2:
                            continue
                        movimiento_actual["Descripcion"] += " " + txt
                        movimiento_actual["DescSigno"] += " " + txt

        # Al terminar
        if movimiento_actual:
            todos_los_movimientos.append(movimiento_actual)
            

    # =======================
    # 5) GUARDAR EN EXCEL
    # =======================
    for mov in todos_los_movimientos:
        mov["Descripcion"] = re.sub(r"\s+", " ", mov["Descripcion"].replace("|", " ")).strip()
    df = pd.DataFrame(todos_los_movimientos, columns=[
        "Fecha",
        "Descripcion",
        "DescSigno",
        "Monto",
        "Saldo",
        "Lado",
    ])
    df = df[df["Monto"].notna() | df["Saldo"].notna()]
    df = df.reset_index(drop=True)
    df["Fecha"] = df["Fecha"].apply(lambda f: fecha_con_anio(f, periodo))

    # Signo de "Monto": el saldo solo se imprime de vez en cuando (no en cada
    # movimiento) y la posición x del monto NO distingue Cargos de Abonos en
    # los estados de cuenta reales usados para validar esto (una misma
    # posición x aparece tanto en pagos hechos como en pagos recibidos, muy
    # probablemente porque depende de la sucursal/caja que procesó el
    # movimiento, no de si es cargo o abono). La descripción sí es confiable:
    # "PAGO RECIBIDO"/"DEPOSITO" son abonos, el resto de movimientos con
    # "PAGO"/"COMISION"/"IVA"/"COBRO"/"CARGO" son cargos. El delta de saldo
    # se usa como respaldo solo cuando la descripción no da ninguna pista Y
    # sí hay saldo de referencia (p.ej. un concepto no reconocido).
    RE_CLAVE_ABONO = re.compile(r"RECIBID|DEPOSITO|DEP[ÓO]SITO|ABONO", re.IGNORECASE)
    RE_CLAVE_CARGO = re.compile(r"PAGO|COMISION|COMISIÓN|IVA|COBRO|CARGO|INTERBANCARIO|RETIRO", re.IGNORECASE)

    retiro = []
    deposito = []
    saldo_anterior = None
    for _, fila in df.iterrows():
        monto = fila["Monto"]
        saldo_actual = fila["Saldo"]
        # El signo se deduce con el mismo texto que antes (incluye el encabezado de hoja
        # que cruza el movimiento) para no cambiar retiro/deposito al limpiar la descripción.
        descripcion = fila["DescSigno"] or ""
        if pd.isna(monto):
            monto = None
        if pd.isna(saldo_actual):
            saldo_actual = None

        if monto is None:
            es_abono = None
        elif fila["Lado"] in ("deposito", "retiro"):
            # La columna donde se imprime el monto es la señal más confiable
            es_abono = fila["Lado"] == "deposito"
        elif (saldo_anterior is not None and saldo_actual is not None
              and abs(saldo_anterior + monto - saldo_actual) < 0.005):
            es_abono = True
        elif (saldo_anterior is not None and saldo_actual is not None
              and abs(saldo_anterior - monto - saldo_actual) < 0.005):
            es_abono = False
        elif RE_CLAVE_ABONO.search(descripcion):
            es_abono = True
        elif RE_CLAVE_CARGO.search(descripcion):
            es_abono = False
        elif saldo_anterior is not None and saldo_actual is not None:
            es_abono = saldo_actual >= saldo_anterior
        else:
            es_abono = None

        if es_abono is True:
            deposito.append(monto)
            retiro.append(None)
        elif es_abono is False:
            retiro.append(monto)
            deposito.append(None)
        else:
            retiro.append(None)
            deposito.append(None)

        if saldo_actual is not None:
            saldo_anterior = saldo_actual

    df["Retiro"] = retiro
    df["Deposito"] = deposito
    df = df.drop(columns=["Monto", "DescSigno", "Lado"])
    df = df[df["Retiro"].notna() | df["Deposito"].notna() | df["Saldo"].notna()]

    return df

class TransactionsParser:
    """
    Parser para renders de estados de cuenta en texto plano.

    Ejemplo de uso:
    >>> parser = TransactionsParser()
    >>> df = parser.parse(render_text)
    """
    MONTHS = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
              'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

    def __init__(self) -> None:
        # Compilamos patrones una sola vez para eficiencia
        months_pattern = '|'.join(self.MONTHS)
        self.date_pattern = re.compile(rf'\b\d{{2}}\s(?:{months_pattern})\b')
        self.money_pattern = re.compile(r'\$?\d{1,3}(?:,\d{3})*\.\d{2}')

    # ---------- Paso 2 ----------
    def _split_transactions(self, render: str) -> list[str]:
        """
        Divide el texto completo en bloques que inician con una fecha.
        """
        matches = list(self.date_pattern.finditer(render))
        splits = []

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(render)
            block = render[start:end].strip()
            if block:
                splits.append(block)
        return splits

    # ---------- Paso 3 ----------
    def _extract_transaction(self, block: str) -> Optional[dict]:
        """
        Extrae la información de un bloque y la devuelve como dict,
        o None si el bloque no contiene ningún monto reconocible.
        """
        fecha_match = re.search(r'\d{2} \w{3}', block)
        if not fecha_match:
            raise ValueError(f"Fecha no encontrada en bloque:\n{block}")

        fecha = fecha_match.group()
        montos = self.money_pattern.findall(block)
        if not montos:
            return None

        # Limpiar descripción
        # Solo se quita la fecha inicial y las dos cifras que son monto y saldo
        # (su última aparición); otras cifras o repeticiones del texto se conservan.
        description = block.replace(fecha, "", 1)
        for monto in montos[-2:]:
            pos = description.rfind(monto)
            if pos != -1:
                description = description[:pos] + description[pos + len(monto):]
        description = re.sub(r"\s+", " ", description.replace("|", " ")).strip()

        return {
            "fecha": fecha,
            "descripcion": description,
            "monto": montos[-2] if len(montos) > 1 else None,
            "saldo": montos[-1]
        }

    # ---------- Paso 4 ----------
    @staticmethod
    def _build_dataframe(transactions: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(transactions)

        # Limpiar símbolo $ y comas, convertir a float
        to_float = lambda x: float(x.replace('$', '').replace(',', '')) if pd.notnull(x) else x
        df['monto'] = df['monto'].apply(to_float)
        df['saldo'] = df['saldo'].apply(to_float)

        # Asignar signo a 'monto'
        saldo_val = 0.0
        for idx, row in df.iterrows():
            if row['monto'] is not None:
                if row['saldo'] >= saldo_val:
                    df.at[idx, 'monto'] = row['monto']    # Depósito
                else:
                    df.at[idx, 'monto'] = -row['monto']   # Retiro
            saldo_val = row['saldo']

        # Separar retiros y depósitos
        df['retiro'] = df['monto'].apply(lambda x: abs(x) if pd.notnull(x) and x < 0 else None)
        df['deposito'] = df['monto'].apply(lambda x: abs(x) if pd.notnull(x) and x > 0 else None)
        df = df.drop(columns=['monto'])

        # Orden final de columnas
        df = df[['fecha', 'descripcion', 'retiro', 'deposito', 'saldo']]
        return df

    # ---------- Paso 5 ----------
    def parse(self, render: str) -> pd.DataFrame:
        """
        Orquesta todo el flujo: recibe texto, devuelve DataFrame listo.
        """
        blocks = self._split_transactions(render)
        transactions = [t for t in (self._extract_transaction(b) for b in blocks) if t is not None]
        df = self._build_dataframe(transactions)
        periodo = extraer_periodo(render)
        df['fecha'] = df['fecha'].apply(lambda f: fecha_con_anio(f, periodo))
        return df
