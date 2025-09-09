import re
from typing import List, Optional, Tuple


import pdfplumber
import pandas as pd

## Función del repo original ##

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    tabla2.columns = tabla2.columns.str.lower()
    tabla2['concepto'] = tabla2['concepto'] + tabla2['origen']
    tabla2 = tabla2[["fecha", "concepto", "deposito", "retiro", "saldo"]]
    tabla2 = tabla2.rename(columns={"concepto": "descripcion"})
    try:
        tabla2['deposito'] = pd.to_numeric(tabla2['deposito'], errors='coerce')
    except:
        print("Error al convertir deposito a numérico")
    try:
        tabla2['retiro'] = pd.to_numeric(tabla2['retiro'], errors='coerce')
    except:
        print("Error al convertir retiro a numérico")
    try:
        tabla2['saldo'] = pd.to_numeric(tabla2['saldo'], errors='coerce')
    except:
        print("Error al convertir saldo a numérico")
    return tabla2

def agrupar_columnas(caracteres) -> pd.DataFrame:
    """
    Asigna cada caracter a una columna según rangos de x1.
    Optimizada: evita cadena de if/elif y valida rangos una sola vez.
    Rangos (inclusive/exclusive replicando lógica original):
      Col 0: 47 <= x <= 91
      Col 1: 91 < x <= 252
      Col 2: 252 < x <= 378
      Col 3: 378 < x <= 440
      Col 4: 440 < x <= 513
      Col 5: 513 < x <= 587
    """
    if not caracteres:
        return pd.DataFrame(columns=["Caracter", "Top", "X", "Columna"])

    # Límites de corte
    edges = [47, 91, 252, 378, 440, 513, 587]  # 6 intervalos => 7 edges
    rows = []
    for ch in caracteres:
        x = ch.get("x1")
        if x is None or x < edges[0] or x > edges[-1]:
            continue
        # Buscar intervalo (son pocos, loop es suficiente)
        for col in range(len(edges) - 1):
            lo, hi = edges[col], edges[col + 1]
            if (col == 0 and lo <= x <= hi) or (col > 0 and lo < x <= hi):
                rows.append({
                    "Caracter": ch.get("text", ""),
                    "Top": ch.get("top"),
                    "X": x,
                    "Columna": col
                })
                break

    return pd.DataFrame(rows, columns=["Caracter", "Top", "X", "Columna"])

def unificar_columna(top: pd.DataFrame) -> dict:
    """
    Versión optimizada: evita múltiples if/elif por fila.
    top: subconjunto de 'columnas' con un solo valor de Top.
    """
    if top.empty:
        return {"Fecha": "", "Concepto": "", "Origen": "", "Deposito": "", "Retiro": "", "Saldo": "", "Top": None}

    # Orden correcto de caracteres dentro de la línea
    top_sorted = top.sort_values("X")

    # Agrupa por índice de columna y concatena caracteres
    agregados = top_sorted.groupby("Columna")["Caracter"].agg("".join).to_dict()

    # Mapea índice -> nombre
    col_map = {
        0: "Fecha",
        1: "Concepto",
        2: "Origen",
        3: "Deposito",
        4: "Retiro",
        5: "Saldo",
    }

    fila = {nombre: agregados.get(idx, "") for idx, nombre in col_map.items()}
    fila["Top"] = top_sorted["Top"].iat[0]
    return fila


def unificar_columnas(columnas: pd.DataFrame) -> pd.DataFrame:
    """
    Vectoriza la transformación:
    - Ordena una sola vez
    - Agrupa por (Top, Columna) y concatena
    - Desenrolla a formato ancho
    Mucho más eficiente que iterar Top por Top.
    """
    if columnas.empty:
        return pd.DataFrame(columns=["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Top"])

    # Asegura orden interno correcto
    columnas = columnas.sort_values(["Top", "X"])

    # Concatena caracteres por Top/Columna
    agrupado = (
        columnas
        .groupby(["Top", "Columna"])["Caracter"]
        .agg("".join)
        .unstack(fill_value="")
    )
    # Mapea columnas numéricas a nombres
    col_map = {
        0: "Fecha",
        1: "Concepto",
        2: "Origen",
        3: "Deposito",
        4: "Retiro",
        5: "Saldo",
    }
    agrupado = agrupado.rename(columns=col_map)

    # Asegura todas las columnas (si faltó alguna)
    for nombre in col_map.values():
        if nombre not in agrupado.columns:
            agrupado[nombre] = ""

    # Restaura Top como columna
    agrupado = agrupado.reset_index()

    # Orden de columnas final consistente con versiones previas
    columnas_orden = ["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Top"]
    agrupado = agrupado[columnas_orden]
    # Ordena por Top (ya debería estar ordenado)
    return agrupado.sort_values("Top").reset_index(drop=True)


def analizar_estados(estado):
    df = pd.DataFrame()
    anios = []
    texto = [pagina.extract_text().replace("\n", "").replace(" ", "") for pagina in estado.pages]
    for i, pagina in enumerate(estado.pages):
        if re.search("FechaConceptoOrigen", texto[i]):
            movimientos = extraer_movimientos_pagina(pagina)
            df = pd.concat([df, pd.DataFrame(movimientos)])
        elif re.search("Periodo", texto[i]):
            periodo = texto[i].split("Periodo")[1]
            periodo = periodo.split("C.P")[0]
            anio = periodo.split("/")[0]
            anios.append(f"20{anio.split('-')[-1]}")

    df = incluir_movimientos(df)
    df = unificar_tabla(df)
    df = arreglar_tabla(df)
    return df
    

def analisis_movimientos(df):
    df = df.copy()
    df = analisis_tipo_movimiento(df)
    df = analisis_contraparte(df)
    df = analisis_institucion_contraparte(df)
    df = analisis_concepto(df)
    df = normalizar_tabla(df)
    return df

def normalizar_tabla(df):
    df = df.drop('Movimiento', axis=1)
    return df

def analisis_concepto(df):
    df["ConceptoMovimiento"] = ""
    for index,row in df.iterrows():
        concepto = "-"
        if re.search("SPEI",row["Concepto"]):
            concepto = row["Concepto"].split("|")[3]
        try:
            concepto = concepto.replace("/","")
        except:
            pass
        df.loc[index,"ConceptoMovimiento"] = concepto
    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        banco = "Sin contraparte"
        if re.search("SPEI",row["Concepto"]):
            banco = row["Concepto"].split("|")[2]

        df.loc[index,"InstitucionContraparte"] = banco

    return df


def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        contraparte = "-"
        if re.search("SPEI",row["Concepto"]):
            contraparte = row["Concepto"].split("|")[-2]
        if re.search("RFC",row["Concepto"]):
            contraparte = row["Concepto"].split("|")[1]
        df.loc[index,"Contraparte"] = contraparte


    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        if re.search("SPEI",row["Concepto"]):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("COMISION",row["Concepto"]) and not re.search("IVA",row["Concepto"]):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",row["Concepto"]):
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        elif re.search("RFC",row["Concepto"]):
            df.loc[index,"TipoMovimiento"] = "COMPRA"
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"

    return df

def econtrar_coordenadas_movimientos(caracteres):
    coordenadas = []
    for caracter in caracteres:
        coordenada_derecha = caracter['x1']
        if coordenada_derecha < 91:
            coordenadas.append(caracter['top'])
    coordenadas = list(set(coordenadas))
    return coordenadas

def extraer_movimientos_pagina(pagina):
    caracteres = pagina.chars
    columnas = agrupar_columnas(caracteres)
    filas = unificar_columnas(columnas)
    filas = eliminar_movimientos_no_deseados(filas)
    return filas

def arreglar_tabla(df):
    """
    Limpia columnas monetarias eliminando '$' y ',' de forma vectorizada.
    - Elimina columna 'Top' si existe.
    - Convierte Deposito, Retiro y Saldo a float (NaN si vacío/no convertible).
    """
    df = df.drop(columns=['Top'], errors='ignore').copy()
    monetarias = [c for c in ['Deposito', 'Retiro', 'Saldo'] if c in df.columns]
    if not monetarias:
        return df

    # Elimina símbolos y convierte a numérico
    df[monetarias] = (
        df[monetarias]
        .replace(r'[\$,]', '', regex=True)
        .replace({'': None, 'None': None})
    )
    for c in monetarias:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    return df

def unificar_movimiento(df):
    df = df.copy()
    concepto = ""
    for index,fila in df.iterrows():
        concepto = concepto + "|" + fila["Concepto"]
    moviemiento = {"Fecha": df.iloc[0,0], "Concepto": concepto, "Origen": df.iloc[0,2], "Deposito": df.iloc[0,3], "Retiro": df.iloc[0,4], "Saldo": df.iloc[0,5], "Top": df.iloc[0,6], "Movimiento": df.iloc[0,7]}
    return moviemiento

def unificar_tabla(df):
    movimientos_unificados = []
    for movimiento in df["Movimiento"].unique():
        movimientos_unificados.append(unificar_movimiento(df[df["Movimiento"]==movimiento]))
    return pd.DataFrame(movimientos_unificados)


def incluir_movimientos(filas: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna un ID de Movimiento agrupando líneas que pertenecen a la misma transacción.
    Reglas:
      - Una nueva transacción inicia cuando aparece una fecha (regex dd MMM).
      - Las líneas siguientes sin fecha se consideran continuación (concepto/origen extendido).
      - Si la línea con fecha no trae (Deposito/Retiro/Saldo) se buscan en la(s) siguiente(s)
        línea(s) del mismo movimiento y se copian al renglón con fecha.
    No elimina los valores de las líneas fusionadas; solo asegura que la primera (con fecha)
    tenga los importes para que unificar_movimiento funcione correctamente.
    """
    if filas is None or filas.empty:
        return filas

    filas = filas.reset_index(drop=True).copy()
    for col in ["Deposito", "Retiro", "Saldo"]:
        if col not in filas.columns:
            filas[col] = ""

    date_re = re.compile(r"^\d{2}\s*[A-ZÁÉÍÓÚÑ]{3}$", re.IGNORECASE)

    def _str(x):
        return "" if pd.isna(x) else str(x)

    def has_amount(row) -> bool:
        return any(_str(row[c]).strip() != "" for c in ["Deposito", "Retiro", "Saldo"])

    # 1) Asignar IDs de movimiento
    movimiento_id = 0
    mov_ids = []
    for _, row in filas.iterrows():
        fecha_txt = _str(row.get("Fecha", "")).strip()
        if date_re.match(fecha_txt):
            movimiento_id += 1
        mov_ids.append(movimiento_id)
    filas["Movimiento"] = mov_ids

    if movimiento_id == 0:
        return filas  # No se detectaron fechas

    # 2) Completar importes faltantes en la fila con fecha
    for mov in sorted(filas["Movimiento"].unique()):
        if mov == 0:
            continue
        grupo_idx = filas.index[filas["Movimiento"] == mov]
        if len(grupo_idx) == 0:
            continue

        # Buscar la primera fila con fecha dentro del grupo
        first_date_idx = None
        for idx in grupo_idx:
            if date_re.match(_str(filas.at[idx, "Fecha"]).strip()):
                first_date_idx = idx
                break
        if first_date_idx is None:
            continue

        # Si ya tiene importes no hacemos nada
        if has_amount(filas.loc[first_date_idx]):
            continue

        # Buscar hacia adelante dentro del grupo alguna fila con importes
        for idx in grupo_idx:
            if idx == first_date_idx:
                continue
            if has_amount(filas.loc[idx]):
                # Copiar importes faltantes
                for col in ["Deposito", "Retiro", "Saldo"]:
                    if _str(filas.at[first_date_idx, col]).strip() == "" and _str(filas.at[idx, col]).strip() != "":
                        filas.at[first_date_idx, col] = filas.at[idx, col]
                break  # Solo primera coincidencia

    return filas

def eliminar_movimientos_no_deseados(filas):
    filas = filas.reset_index(drop=True)
    for index,row in filas.iterrows():
        if index > 0:
            if row["Fecha"].strip() == "Fecha":
                filas = filas[filas["Top"] > row["Top"]]
            elif re.search(r"LAS\s*TAS" ,row["Fecha"]):
                filas = filas[filas["Top"] < row["Top"]]
    return filas

## Implementación usando docTR como OCR backend ##

class ScotiabankMovementExtractor:
    """
    Extrae movimientos (fecha, depósito/retiro, saldo) de un estado de cuenta
    a partir del render (texto) y el OCR estructurado de DocTR.
    """
    DEFAULT_MONTHS = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
                      'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

    def __init__(
        self,
        render_text: str,
        doctr_ocr: dict | list,
        valid_months: Optional[List[str]] = None,
        x_threshold: float = 0.7,
    ) -> None:
        self.render_text = render_text or ""
        self.doctr_ocr = doctr_ocr or []
        self.valid_months = valid_months or self.DEFAULT_MONTHS
        self.x_threshold = x_threshold

        # Compila regex de fecha y monto
        months_alt = "|".join(self.valid_months)
        self._date_re = re.compile(rf"(\d{{1,2}} (?:{months_alt}))")
        # Permite espacios después del $ y miles con coma/punto; decimales opcionales
        self._amount_re = re.compile(r"\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?")

        # Prepara OCR aplanado
        self.ocr_df = self._flatten_doctr_ocr(self.doctr_ocr)

    # ---------- API pública ----------
    def parse(self) -> pd.DataFrame:
        """Devuelve un DataFrame con columnas: date, text, deposito, retiro, saldo."""
        date_matches = list(self._date_re.finditer(self.render_text))
        rows = []

        for i, m in enumerate(date_matches):
            start = m.end()
            if i < len(date_matches) - 1:
                end = date_matches[i + 1].start()
            else:
                end = len(self.render_text)

            text_block = self.render_text[start:end].strip()
            amounts = self._amount_re.findall(text_block)

            # Necesitamos exactamente 2: [monto, saldo]
            if len(amounts) != 2:
                continue

            monto_raw, saldo_raw = amounts[0], amounts[1]
            monto = self._to_float_money(monto_raw)
            saldo = self._to_float_money(saldo_raw)

            # Intentar ubicar geometría del monto en el OCR para decidir depósito/retiro
            geom = self._find_word_geometry(monto_raw)
            deposito, retiro = None, None
            if geom is not None:
                x_mean = (geom[0] + geom[2]) / 2.0  # (xmin + xmax)/2
                # Clasificación por posición horizontal
                if x_mean < self.x_threshold:
                    deposito = monto
                else:
                    retiro = monto
            # Si no hubo geometría, dejamos ambos en None (o podrías agregar una heurística alternativa)

            rows.append({
                "date": m.group(1),
                "text": text_block,
                "deposito": deposito,
                "retiro": retiro,
                "saldo": saldo,
            })

        return pd.DataFrame(rows)

    # ---------- Utilidades internas ----------
    @staticmethod
    def _flatten_doctr_ocr(doctr_ocr: dict | list) -> pd.DataFrame:
        """
        Convierte la estructura de DocTR en un DataFrame con columnas:
        - word: str
        - geometry: Tuple[float, float, float, float] = (xmin, ymin, xmax, ymax), normalizados [0,1]
        """
        words = []
        # Se acepta lista de páginas (como en tu ejemplo)
        for page in doctr_ocr:
            items = page.get("items", [])
            for item in items:
                for block in item.get("blocks", []):
                    for line in block.get("lines", []):
                        for word in line.get("words", []):
                            val = word.get("value")
                            geom = word.get("geometry")
                            if val is not None and geom is not None and len(geom) == 4:
                                words.append((val, tuple(geom)))

        return pd.DataFrame(words, columns=["word", "geometry"]) if words else pd.DataFrame(columns=["word", "geometry"])

    @staticmethod
    def _normalize_amount_text(s: str) -> str:
        """Normaliza texto monetario para comparaciones: quita $, espacios y saltos de línea."""
        return s.replace("$", "").replace(" ", "").replace("\n", "")

    def _find_word_geometry(self, amount_str: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Busca la geometría del monto en el OCR aplanado probando:
          1) Coincidencia exacta
          2) Sin símbolo '$'
          3) Comparación normalizada (quita separadores y compara dígitos)
        Devuelve (xmin, ymin, xmax, ymax) o None si no lo encuentra.
        """
        if self.ocr_df is None or self.ocr_df.empty:
            return None

        # 1) Exacta
        exact = self.ocr_df.loc[self.ocr_df["word"] == amount_str, "geometry"]
        if not exact.empty:
            return exact.iloc[0]

        # 2) Sin '$' y sin espacios
        amount_no_dollar = self._normalize_amount_text(amount_str)
        no_dollar = self.ocr_df.loc[self.ocr_df["word"].apply(
            lambda w: self._normalize_amount_text(str(w)) == amount_no_dollar), "geometry"]
        if not no_dollar.empty:
            return no_dollar.iloc[0]

        # 3) Normalizada sin separadores (compara solo dígitos)
        def digits_only(x: str) -> str:
            return re.sub(r"\D", "", x)

        target_digits = digits_only(amount_no_dollar)
        normalized = self.ocr_df.loc[self.ocr_df["word"].apply(
            lambda w: digits_only(self._normalize_amount_text(str(w))) == target_digits), "geometry"]
        if not normalized.empty:
            return normalized.iloc[0]

        return None

    @staticmethod
    def _to_float_money(s: str) -> Optional[float]:
        """
        Convierte una cadena monetaria a float, preservando el separador decimal real.
        Estrategia:
          - El separador decimal es el ÚLTIMO '.' o ',' que aparezca.
          - Todos los demás '.' y ',' se eliminan (se asumen de miles).
        """
        if s is None:
            return None
        raw = s.strip().replace(" ", "").replace("\n", "").replace("$", "")
        if raw == "":
            return None

        # Encuentra el último separador que actúa como decimal (.,)
        last_sep = max(raw.rfind("."), raw.rfind(","))
        if last_sep == -1:
            # Sin decimales explícitos: interpreta como entero
            digits = re.sub(r"\D", "", raw)
            return float(digits) if digits else None

        integer_part = re.sub(r"[.,]", "", raw[:last_sep])
        decimal_part = re.sub(r"\D", "", raw[last_sep + 1:])

        # Asegura 2 decimales si hay parte decimal
        if decimal_part == "":
            value_str = integer_part
        else:
            # Si tiene más de 2, toma los dos primeros (o ajusta si tu fuente garantiza 2)
            value_str = f"{integer_part}.{decimal_part[:2]}"

        try:
            return float(value_str)
        except ValueError:
            return None
