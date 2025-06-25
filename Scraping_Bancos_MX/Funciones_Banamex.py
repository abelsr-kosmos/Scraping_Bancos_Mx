import re
import pdfplumber
import pandas as pd

def Scrap_Estado(ruta_archivo):
    df = procesar_pdf(ruta_archivo)
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

        todos_los_movimientos = []
        movimiento_actual = None

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

            for top_val, words_in_line in lineas_ordenadas:
                if stop_reading:
                    break

                line_text = " ".join(w['text'] for w in words_in_line)
                line_text_upper = line_text.upper()

                # Detectar periodo, p. ej. "RESUMEN DEL: 01/DIC/2023 AL 31/DIC/2023"
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

                # ¿Es un nuevo movimiento? => tokens[0] = dd, tokens[1] = mmm
                if es_linea_movimiento(line_text_upper):
                    # Guardar el anterior
                    if movimiento_actual:
                        todos_los_movimientos.append(movimiento_actual)

                    tokens_line = line_text_upper.split()
                    movimiento_actual = {
                        "Fecha": f"{tokens_line[0]} {tokens_line[1]}",
                        "Descripcion": "",
                        "Retiro": None,
                        "Deposito": None,
                        "Saldo": None
                    }
                else:
                    # Continuación
                    if not movimiento_actual:
                        movimiento_actual = {
                            "Fecha": None,
                            "Descripcion": "",
                            "Retiro": None,
                            "Deposito": None,
                            "Saldo": None
                        }

                # Asignar montos por coordenadas
                for w in words_in_line:
                    txt = w['text'].strip()
                    center_w = (w['x0'] + w['x1']) / 2

                    if es_numero_monetario(txt):
                        val = parse_monetario(txt)
                        if center_w > 345 and center_w < 395:
                            movimiento_actual["Retiro"] = val
                        elif center_w > 395 and center_w < 475:
                            movimiento_actual["Deposito"] = val
                        elif center_w > 480:
                            movimiento_actual["Saldo"] = val
                    else:
                        # Texto al concepto (omitir dd y mmm)
                        if re.match(r'^\d{1,2}$', txt) or txt in MESES_CORTOS:
                            continue
                        movimiento_actual["Descripcion"] += " " + txt

        # Al terminar
        if movimiento_actual:
            todos_los_movimientos.append(movimiento_actual)
            

    # =======================
    # 5) GUARDAR EN EXCEL
    # =======================
    df = pd.DataFrame(todos_los_movimientos, columns=[
        "Fecha",
        "Descripcion",
        "Retiro",
        "Deposito",
        "Saldo"
    ])
    df = df[df["Retiro"].notna() | df["Deposito"].notna() | df["Saldo"].notna()]

    return df