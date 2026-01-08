import re
from typing import List, Dict
from dataclasses import dataclass

import pdfplumber
import pandas as pd

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    return tabla2

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
        if re.search("TRANSFERENCIA SPEI",row["Concepto"]) or re.search("DEPOSITO SPEI",row["Concepto"]) :
            conceptos = row["Concepto"].split("|")
            concepto = conceptos[4]
        df.loc[index,"ConceptoMovimiento"] = concepto    

    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        banco = "-"
        if re.search("TRANSFERENCIA SPEI",row["Concepto"]) or re.search("DEPOSITO SPEI",row["Concepto"]) :
            bancos = row["Concepto"].split("|")
            banco = bancos[3]
            banco = ''.join([i for i in banco if not i.isdigit()])

        df.loc[index,"InstitucionContraparte"] = banco

    return df


def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        concepto = "Sin Contraparte"
        if re.search("TRANSFERENCIA SPEI",row["Concepto"]) or re.search("DEPOSITO SPEI",row["Concepto"]) :
            conceptos = row["Concepto"].split("|")
            concepto = conceptos[2]
            concepto = ''.join([i for i in concepto if not i.isdigit()])

        df.loc[index,"Contraparte"] = concepto

    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        conceptos = row["Concepto"].split("|")
        concepto = conceptos[1]
        contador_pip =concepto.count("|")
        if re.search("SPEI",concepto) and not re.search("IVA",concepto) and not re.search("COMISION",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("COMISION SPEI",concepto) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",concepto) :
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        elif re.search("MX",concepto):
            df.loc[index,"TipoMovimiento"] = "COMPRA"
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"
    return df

def analizar_estados(estado):
    df = pd.DataFrame()
    anios = []
    contador = 0
    for pagina in estado.pages:
        texto = pagina.extract_text()
        texto = texto.replace("\n", "")
        texto = texto.replace(" ", "")
        if re.search("FECHAREFERENCIACONCEPTOCARGOSABONOSSALDO", texto) :
                movimientos = extraer_movimientos_pagina(pagina,texto)
                df = pd.concat([df, pd.DataFrame(movimientos)])    
                contador += 1
    df = df.reset_index(drop=True)
    df = unificar_variaciones_altura(df)
    df = incluir_movimientos(df)
    df = unificar_tabla(df)
    
    return df

def unificar_variaciones_altura(df):
    for index, row in df.iterrows():
        if row["Fecha"] == "" and row["Concepto"] == "":
            df.loc[index+1, "Deposito"] = df.loc[index, "Deposito"]
            df.loc[index+1, "Retiro"] = df.loc[index, "Retiro"]
            df.loc[index+1, "Saldo"] = df.loc[index, "Saldo"]
            df.drop(index, inplace=True)
    for index, row in df.iterrows():
         if row["Fecha"] != "" and row["Concepto"] == "" and row["Origen"] != "":
            df.loc[index, "Concepto"] = df.loc[index-1, "Concepto"]
            df.drop(index-1, inplace=True)

    return df

def extraer_movimientos_pagina(pagina,texto):
    caracteres = pagina.chars
    columnas = agrupar_columnas(caracteres)
    filas = unificar_columnas(columnas)
    filas = eliminar_movimientos_no_deseados(filas)
    return filas

def agrupar_columnas(caracteres):
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 47 and coordenada >= 13:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 106  and coordenada > 47:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 366  and coordenada > 106:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 430  and coordenada > 366:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 496  and coordenada > 430:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 566  and coordenada > 496:
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
            origen = origen + row["Caracter"]
        elif row["Columna"] == 2:
            concepto = concepto + row["Caracter"]
        elif row["Columna"] == 3:
            deposito = deposito + row["Caracter"]
        elif row["Columna"] == 4:
            retiro = retiro + row["Caracter"]
        elif row["Columna"] == 5:
            saldo = saldo + row["Caracter"]
    fila = {"Fecha": fecha, "Concepto": concepto, "Origen": origen, "Deposito": deposito, "Retiro": retiro, "Saldo": saldo, "Top": top["Top"].max()}
    return fila

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

def eliminar_movimientos_no_deseados(filas):
    filas = filas.reset_index(drop=True)
    filas = filas.copy()
    contador_repeticion = 0
    for index,row in filas.iterrows():
        if index > 0:
            if row["Fecha"] == "FECHA" and contador_repeticion == 0:
                filas = filas[filas["Top"] > row["Top"]]
                contador_repeticion += 1
            elif row["Fecha"] == "Estima" or row["Concepto"] == "BANCO INBURSA, S.A. INSTITUCION DE BANCA MULTIPLE, GR":
                filas = filas[filas["Top"] < row["Top"]]
            elif re.search("BALANCE INICIAL",row["Concepto"]):
                filas = filas.drop(index)
    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match(r"\w{3} \d{2}", fila["Fecha"]):
            contador_movimiento += 1 
        
        df.loc[index,"Movimiento"] = contador_movimiento
    return df

def unificar_movimiento(df):
    df = df.copy()
    concepto = ""
    for index,fila in df.iterrows():
        concepto = concepto + "|" + fila["Concepto"]
    moviemiento = {"Fecha": df.iloc[0,0], "Concepto": concepto, "Origen": df.iloc[0,2], "Deposito": df.iloc[0,3], "Retiro": df.iloc[0,4], "Saldo": df.iloc[0,5],"Movimiento": df.iloc[0,6]}
    return moviemiento

def unificar_tabla(df):
    movimientos_unificados = []
    for movimiento in df["Movimiento"].unique():
        movimientos_unificados.append(unificar_movimiento(df[df["Movimiento"]==movimiento]))
    return pd.DataFrame(movimientos_unificados)

@dataclass
class InbursaExtractor:
    """
    Extrae movimientos de estados de cuenta (formato tipo tabla) desde PDFs.
    
    Flujo:
    - Lee todas las páginas con pdfplumber
    - Identifica páginas de movimientos por encabezado
    - Parseo con regex (date/ref/concept/amount/balance)
    - Construye DataFrame
    - Convierte monto/saldo a numérico
    - Infere signo del monto comparando saldo actual vs saldo previo
    - Genera columnas retiros/depositos
    """

    header_regex: str = r"\bFECHA REFERENCIA CONCEPTO CARGOS ABONOS SALDO\b"
    movement_pattern: str = (
        r"(?P<date>[A-Z]{3} \d{1,2})\s+"
        r"(?:(?P<ref>\d+)\s+)?"
        r"(?P<concept>.+?)\s+"
        r"(?:(?P<amount>[\d,]+\.\d{2})\s+)?"
        r"(?P<balance>[\d,]+\.\d{2})"
    )

    def extract(self, pdf_path: str) -> pd.DataFrame:
        """
        Método principal: devuelve el DataFrame final:
        ['fecha', 'descripcion', 'retiros', 'depositos', 'saldo']
        """
        pages_text = self._read_pdf_text(pdf_path)
        movements_pages = self._filter_movement_pages(pages_text)
        movements = self._parse_movements_pages(movements_pages)

        df = self._to_dataframe(movements)
        df = self._normalize_numeric(df)
        df = self._infer_amount_sign_from_balance(df)
        df = self._add_withdrawals_deposits(df)

        return df[["fecha", "descripcion", "retiros", "depositos", "saldo"]]

    # -------------------------
    # Step 1: Read PDF
    # -------------------------
    def _read_pdf_text(self, pdf_path: str) -> List[str]:
        all_text: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                all_text.append(page.extract_text() or "")
        return all_text

    # -------------------------
    # Step 2: Filter pages
    # -------------------------
    def _filter_movement_pages(self, pages_text: List[str]) -> List[str]:
        movements_pages: List[str] = []
        for idx, page_text in enumerate(pages_text, start=1):
            if re.search(self.header_regex, page_text):
                movements_pages.append(page_text)
        return movements_pages

    # -------------------------
    # Step 3: Parse movements
    # -------------------------
    def _parse_movements_pages(self, movements_pages: List[str]) -> List[Dict[str, str]]:
        movements: List[Dict[str, str]] = []
        pattern = re.compile(self.movement_pattern)

        for page in movements_pages:
            matches = list(pattern.finditer(page))
            last_end = 0

            for i, match in enumerate(matches):
                start = match.start()
                between_text = page[last_end:start].strip() if i > 0 else ""
                last_end = match.end()

                date = match.group("date") or ""
                ref = match.group("ref") or ""
                concept = match.group("concept") or ""
                amount = match.group("amount") or ""
                balance = match.group("balance") or ""

                descripcion = self._build_description(ref, concept, between_text)

                movements.append(
                    {
                        "fecha": date,
                        "descripcion": descripcion,
                        "monto": amount,
                        "saldo": balance,
                    }
                )

        return movements

    def _build_description(self, ref: str, concept: str, between_text: str) -> str:
        # Respeta tu lógica: ref + espacio + concept + espacio + between_text
        parts = []
        if ref:
            parts.append(ref)
        if concept:
            parts.append(concept)
        if between_text:
            parts.append(between_text)
        return " ".join(parts).strip()

    # -------------------------
    # Step 4: Build DataFrame
    # -------------------------
    def _to_dataframe(self, movements: List[Dict[str, str]]) -> pd.DataFrame:
        return pd.DataFrame(movements)

    # -------------------------
    # Step 5: Normalize numeric
    # -------------------------
    def _normalize_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        # Nota: amount puede venir vacío -> NaN
        df = df.copy()

        df["monto"] = pd.to_numeric(
            df["monto"].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )
        df["saldo"] = pd.to_numeric(
            df["saldo"].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )
        return df

    # -------------------------
    # Step 6: Infer sign
    # -------------------------
    def _infer_amount_sign_from_balance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Replica tu lógica:
        - saldo_inicial = saldo de la primera fila
        - para cada fila siguiente:
            si saldo_actual - saldo_inicial > 0 => monto queda igual (depósito)
            si no => monto = -monto (retiro)
          luego saldo_inicial = saldo_actual
        
        ⚠️ Nota nerd: este método asume que cada fila cambia el saldo
        y que el monto corresponde al delta entre saldos. Si hay filas
        sin monto (NaN) o movimientos raros, se conserva NaN.
        """
        df = df.copy()

        if df.empty:
            return df

        saldo_prev = df["saldo"].iloc[0]

        for i in range(1, len(df)):
            saldo_actual = df.at[i, "saldo"]
            monto = df.at[i, "monto"]

            # Si alguno es NaN, no tocamos
            if pd.isna(saldo_prev) or pd.isna(saldo_actual) or pd.isna(monto):
                saldo_prev = saldo_actual
                continue

            # Si el saldo sube -> depósito (monto positivo)
            # Si el saldo baja o no sube -> retiro (monto negativo)
            if (saldo_actual - saldo_prev) <= 0:
                df.at[i, "monto"] = -abs(monto)
            else:
                df.at[i, "monto"] = abs(monto)

            saldo_prev = saldo_actual

        return df

    # -------------------------
    # Step 7: Add retiros/depositos
    # -------------------------
    def _add_withdrawals_deposits(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["retiros"] = df["monto"].apply(lambda x: -x if pd.notna(x) and x < 0 else None)
        df["depositos"] = df["monto"].apply(lambda x: x if pd.notna(x) and x > 0 else None)
        return df


if __name__ == "__main__":
    extractor = InbursaExtractor()
    pdf_path = "/mnt/d/Documentos/Trabajo/Kosmos/OCR-General/Scraping_Bancos_Mx/proto/data/2mS8nfw-EdoCuenta_Inbursaabril2022 (1).pdf"
    movimientos_df = extractor.extract(pdf_path)
    movimientos_df.to_csv("inbursa_movimientos.csv", index=False)
    print(movimientos_df)