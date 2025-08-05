import re
from typing import List, Optional, Tuple


import pdfplumber
import pandas as pd

## Función del repo original ##

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    return tabla2

def agrupar_columnas(caracteres):
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 91 and coordenada >= 47:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 252  and coordenada > 91:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 378  and coordenada > 252:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 440  and coordenada > 378:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 513  and coordenada > 440:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 587  and coordenada > 513:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 5})
    columnas = pd.DataFrame(columnas)
    return columnas

def unificar_columna(top):
    top = top.sort_values(by=["X"])
    fecha = ""
    concepto = ""
    origen = ""
    deposito = ""
    retiro = ""
    saldo = ""
    for index, row in top.iterrows():
        if row["Columna"] == 0:
            fecha = fecha + row["Caracter"]
        elif row["Columna"] == 1:
            concepto = concepto + row["Caracter"]
        elif row["Columna"] == 2:
            origen = origen + row["Caracter"]
        elif row["Columna"] == 3:
            deposito = deposito + row["Caracter"]
        elif row["Columna"] == 4:
            retiro = retiro + row["Caracter"]
        elif row["Columna"] == 5:
            saldo = saldo + row["Caracter"]
    fila = {"Fecha": fecha, "Concepto": concepto, "Origen": origen, "Deposito": deposito, "Retiro": retiro, "Saldo": saldo, "Top": top["Top"].max()}
    return fila

#Aqui se podria implementar el agregar la columna movimiento para saber diferencias y agrupar conocimientos

def unificar_columnas(columnas):
    tops = columnas["Top"].unique()
    filas = []
    for top in tops:
        top = columnas[columnas["Top"] == top]
        fila = unificar_columna(top)
        filas.append(fila)
    filas = pd.DataFrame(filas)
    
    filas = filas.sort_values(by=["Top"])
    return filas


def analizar_estados(estado):
    df = pd.DataFrame()
    anios = []
    for pagina in estado.pages:
        texto = pagina.extract_text()
        texto = texto.replace("\n", "")
        texto = texto.replace(" ", "")
        if re.search("FechaConceptoOrigen", texto):
            movimientos = extraer_movimientos_pagina(pagina)
            df = pd.concat([df, pd.DataFrame(movimientos)])
        elif re.search("Periodo", texto):
            periodo = texto.split("Periodo")[1]
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
    df = df.drop('Top', axis=1)
    for index, row in  df.iterrows():
        if row["Deposito"] is not None:
            df.loc[index,"Deposito"] = df.loc[index,"Deposito"].replace("$", "")
            df.loc[index,"Deposito"] = df.loc[index,"Deposito"].replace(",", "")
        if row["Retiro"] is not None:
            df.loc[index,"Retiro"] = df.loc[index,"Retiro"].replace("$", "")
            df.loc[index,"Retiro"] = df.loc[index,"Retiro"].replace(",", "")
        if row["Saldo"] is not None:
            df.loc[index,"Saldo"] = df.loc[index,"Saldo"].replace("$", "")
            df.loc[index,"Saldo"] = df.loc[index,"Saldo"].replace(",", "")

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


def incluir_movimientos(filas):
    filas = filas.reset_index(drop=True)
    filas["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in filas.iterrows():
        if  re.match("\d{2} \w{3}", fila["Fecha"]):
            contador_movimiento += 1 
        filas.loc[index,"Movimiento"] = contador_movimiento
        
    return filas

def eliminar_movimientos_no_deseados(filas):
    filas = filas.reset_index(drop=True)
    for index,row in filas.iterrows():
        if index > 0:
            if row["Fecha"] == "Fecha":
                filas = filas[filas["Top"] > row["Top"]]
            elif  re.search("LAS\s*TAS" ,row["Fecha"]):
                filas = filas[filas["Top"] < row["Top"]]
            elif row["Deposito"] != "" and row["Retiro"] != "":
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
