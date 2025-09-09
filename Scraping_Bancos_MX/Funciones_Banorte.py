import re
from typing import List, Tuple, Optional

import pdfplumber
import pandas as pd
import time

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    tabla2.columns = [col.lower() for col in tabla2.columns]
    tabla2['descripcion'] = tabla2['concepto'] + " | " + tabla2['origen'] + " | " + tabla2['conceptomovimiento']
    tabla2['descripcion'] = (
        tabla2['descripcion']
        .astype(str)
        .str.replace(r'[\t\r\n]+', ' ', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip(' |')      # quita espacios y pipes extremos
        .str.slice(0, 256)    # limita a 256 caracteres
    )
    tabla2 = tabla2[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
    try:
        tabla2['deposito'] = pd.to_numeric(tabla2['deposito'].str.replace(',', '').str.replace('$', ''), errors='coerce')
    except Exception as e:
        print(f"Error al convertir depósito: {e}")
    try:
        tabla2['retiro'] = pd.to_numeric(tabla2['retiro'].str.replace(',', '').str.replace('$', ''), errors='coerce')
    except Exception as e:
        print(f"Error al convertir retiro: {e}")
    try:
        tabla2['saldo'] = pd.to_numeric(tabla2['saldo'].str.replace(',', '').str.replace('$', ''), errors='coerce')
    except Exception as e:
        print(f"Error al convertir saldo: {e}")
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
    if 'Movimiento' in df.columns:
        df = df.drop('Movimiento', axis=1)
    return df


def analisis_concepto(df):
    df["ConceptoMovimiento"] = ""
    for index,row in df.iterrows():
        concepto = "-"
        if re.search("SPEI RECIBIDO",row["Concepto"]):
            conceptos = row["Concepto"].split("CONCEPTO:")[1]
            concepto = conceptos.split("REFERENCIA")[0]
        elif re.search("PAGO SPEI",row["Concepto"]) and not re.search("COMISION",row["Concepto"]) and not re.search("I.V.A",row["Concepto"]):
            concepto = ''.join([i for i in row["Concepto"] if not i.isdigit()])
        try:
            concepto = concepto.replace("|","")
        except:
            pass
        df.loc[index,"ConceptoMovimiento"] = concepto   
    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        if re.search("SPEI RECIBIDO",row["Concepto"]):
            if re.search(r"BCO:\d{4}",row["Concepto"]):
                conceptos = row["Concepto"].split("BCO:")[1]
                conceptos = conceptos[4:]
                concepto = conceptos.split("HR")[0]
                df.loc[index,"InstitucionContraparte"] = concepto
        elif re.search("PAGO SPEI",row["Concepto"]) and not re.search("COMISION",row["Concepto"]) and not re.search("I.V.A",row["Concepto"]):
                concepto = ''.join([i for i in row["Concepto"] if not i.isdigit()])
                try:
                    concepto = concepto.replace("|","")
                    concepto = concepto.replace(".","")
                except:
                    pass
                df.loc[index,"InstitucionContraparte"] = concepto
        else:
            texto = "Sin contraparte"
            df.loc[index,"InstitucionContraparte"] = texto

    return df


def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        if re.search("RFC",row["Concepto"]) and not re.search("SPEI RECIBIDO",row["Concepto"]) and not re.search("PAGO SPEI",row["Concepto"]):
            conceptos = row["Concepto"].split("RFC")[0]
            concepto = conceptos.split("|")[1]
            df.loc[index,"Contraparte"] = concepto
        elif re.search("SPEI RECIBIDO",row["Concepto"]):
            conceptos = row["Concepto"].split("CLIENTE")[1]
            concepto = conceptos.split("DE LA CLABE")[0]
            try:
                concepto = concepto.replace("|","")
            except:
                pass
            df.loc[index,"Contraparte"] = concepto
        elif re.search("PAGO SPEI",row["Concepto"]) and not re.search("COMISION",row["Concepto"]) and not re.search("I.V.A",row["Concepto"]):
            concepto = row["Concepto"]
            df.loc[index,"Contraparte"] = concepto
        else:
            df.loc[index,"Contraparte"] = "-"
 
    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        conceptos = row["Concepto"].split("|")
        concepto = conceptos[1]
        if re.search("SPEI",concepto) and not re.search("I.V.A",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("COMISION",concepto) and not re.search("I.V.A",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("I.V.A",concepto):
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        elif re.search("RFC",concepto):
            df.loc[index,"TipoMovimiento"] = "COMPRA"
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"

    return df

def analizar_estados(estado):
    df = pd.DataFrame()
    texto_paginas = [pagina.extract_text().replace("\n", "").replace(" ", "")  for pagina in estado.pages]
    for i, pagina in enumerate(estado.pages, 1):
        texto = texto_paginas[i-1]
        if re.search("FECHADESCRIPCIÓN/ESTABLECIMIENTO", texto):
            movimientos = extraer_movimientos_pagina(pagina,texto)
            df = pd.concat([df, pd.DataFrame(movimientos)])
    df = df.reset_index(drop=True)
    df = incluir_movimientos(df)
    df = unificar_tabla(df)

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
        if coordenada <= 85 and coordenada >= 50:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],5),"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 351  and coordenada > 85:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],5),"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 420  and coordenada > 351:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],5),"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 490  and coordenada > 420:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],5),"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 560  and coordenada > 490:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],5),"X":caracter["x1"],"Columna": 4})
    columnas = pd.DataFrame(columnas)
    return columnas

def unificar_columnas(columnas):
    if columnas.empty:
        return pd.DataFrame(columns=["Fecha","Concepto","Origen","Deposito","Retiro","Saldo","Top"])

    columnas = columnas.sort_values(["Top", "Columna", "X"], kind="mergesort")

    wide = (columnas
            .groupby(["Top", "Columna"], sort=False)["Caracter"]
            .agg(''.join)
            .unstack("Columna", fill_value=''))

    for c in range(5):
        if c not in wide.columns:
            wide[c] = ""

    wide = wide.rename(columns={
        0: "Fecha",
        1: "Concepto",
        2: "Deposito",
        3: "Retiro",
        4: "Saldo"
    })

    wide["Origen"] = ""  # Columna vacía (placeholder)

    # Orden y salida final
    result = (wide
              .reset_index()
              .loc[:, ["Fecha","Concepto","Origen","Deposito","Retiro","Saldo","Top"]]
              .sort_values("Top")
              .reset_index(drop=True))
    return result

def eliminar_movimientos_no_deseados(filas):
    filas = filas.reset_index(drop=True)
    filas = filas.copy()
    contador_repeticion = 0
    for index,row in filas.iterrows():
        if index > 0:
            if row["Fecha"] == "FECHA" and contador_repeticion == 0:
                filas = filas[filas["Top"] > row["Top"]]
                contador_repeticion += 1
            elif  re.search("Directa" ,row["Fecha"]):
                filas = filas[filas["Top"] < row["Top"]]
    for index, row in filas.iterrows():
        if index >0:
            if re.search("SALDO ANTERIOR",row["Concepto"] ):
                    filas = filas.drop(index)
    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match(r"\d{2}-\w{3}-\d{2}", fila["Fecha"]):
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

class BanorteStatementParser:
    """
    Parser de estados Banorte (o similares) que separa transacciones por bloques
    delimitados por líneas con fecha (p.ej. '09-JUN-25'), detecta montos y saldo,
    normaliza importes y construye un DataFrame con:
      - fecha
      - descripcion
      - monto (interno)
      - deposito
      - retiro
      - saldo
    """
    # Por defecto: 2 dígitos día, 3 letras mes en mayúsculas, 2 dígitos año
    DATE_PATTERN = r'\d{2}-[A-Z]{3}-\d{2}'
    # Cantidades como '1,234.56' o '1.234,56' o '1234.56' o '1234,56'
    AMOUNT_PATTERN = r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})'

    def __init__(self, text: str, date_pattern: Optional[str] = None):
        self.text = text.replace("0CT", "OCT")  # Fix for OCT without dot
        self.date_pattern = date_pattern or self.DATE_PATTERN
        self._df: Optional[pd.DataFrame] = None

    # ------------ API pública ------------ #
    def parse(self) -> pd.DataFrame:
        """Ejecuta el pipeline completo y devuelve el DataFrame final."""
        dates_positions = self._find_dates_positions()
        transactions = self._extract_transactions(dates_positions)
        df = pd.DataFrame(transactions)

        if df.empty:
            self._df = df
            return df

        # Normaliza saldo/monto y asigna signo del monto según cambio en saldo
        df['saldo'] = df['saldo'].apply(self._to_float_safe)
        df = self._apply_sign_by_balance_delta(df)

        # Deriva columnas deposito / retiro
        df['retiro'] = df['monto'].apply(
            lambda x: -x if isinstance(x, (int, float)) and x < 0 else None
        )
        df['deposito'] = df['monto'].apply(
            lambda x: x if isinstance(x, (int, float)) and x > 0 else None
        )

        # Orden de columnas de salida
        self._df = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
        
        # Columnas en Title format
        self._df.columns = [col.capitalize() for col in self._df.columns]
        return self._df

    @property
    def dataframe(self) -> Optional[pd.DataFrame]:
        """Devuelve el último DataFrame parseado (si ya corriste parse())."""
        return self._df

    # ------------ Implementación interna ------------ #
    def _find_dates_positions(self) -> List[Tuple[int, str, str]]:
        """
        Devuelve lista de tuplas: (índice_de_línea, línea_completa, fecha_encontrada)
        """
        positions: List[Tuple[int, str, str]] = []
        lines = self.text.split('\n')
        for i, line in enumerate(lines):
            matches = re.findall(self.date_pattern, line)
            if matches:
                # Si hay varias fechas en la misma línea, tomamos la primera
                positions.append((i, line, matches[0]))
        return positions

    def _extract_transactions(self, dates_positions: List[Tuple[int, str, str]]) -> List[dict]:
        """
        Construye una lista de transacciones a partir de los bloques entre fechas.
        Cada bloque va desde una línea con fecha hasta la línea anterior a la siguiente fecha.
        """
        if not dates_positions:
            return []

        lines = self.text.split('\n')
        transactions = []

        for i in range(len(dates_positions)):
            current_pos, current_line, current_date = dates_positions[i]
            next_pos = dates_positions[i + 1][0] if i < len(dates_positions) - 1 else len(lines)

            block_lines = lines[current_pos:next_pos]
            block_text = '\n'.join(block_lines)

            # La descripción: tomamos la primera línea del bloque sin la fecha
            descripcion = block_lines[0].replace(current_date, '').strip()

            # Tomamos cantidades del inicio del bloque (recorte evita agarrar de más)
            amounts = re.findall(self.AMOUNT_PATTERN, block_text[:250])

            saldo = amounts[-1] if amounts else None
            monto = amounts[-2] if len(amounts) > 1 else None

            transactions.append({
                'fecha': current_date,
                'descripcion': descripcion,
                'monto': self._to_float_safe(monto),
                'saldo': self._to_float_safe(saldo),
            })

        return transactions

    @staticmethod
    def _to_float_safe(value: Optional[str]):
        """
        Convierte strings de cantidad a float, robusto a formatos:
          - '1,234.56'  -> 1234.56
          - '1.234,56'  -> 1234.56
          - '1234.56'   -> 1234.56
          - '1234,56'   -> 1234.56
        Ignora símbolos $, espacios y saltos de línea.
        """
        if value is None or not isinstance(value, str) or value.strip() == '':
            return value
        v = value.strip().replace(' ', '').replace('\n', '')
        v = v.replace('$', '').replace('MXN', '').replace('-', '')
        # Localiza el último separador como separador decimal
        last_dot = v.rfind('.')
        last_com = v.rfind(',')
        dec_idx = max(last_dot, last_com)
        if dec_idx == -1:
            # No hay parte decimal clara; intenta float directo
            try:
                return float(v)
            except ValueError:
                return value
        integer_part = v[:dec_idx]
        decimal_part = v[dec_idx+1:]
        # Elimina todos los separadores de miles de la parte entera
        integer_part = integer_part.replace('.', '').replace(',', '')
        normalized = f"{integer_part}.{decimal_part}"
        try:
            return float(normalized)
        except ValueError:
            return value

    def _apply_sign_by_balance_delta(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Asigna signo a 'monto' comparando el delta de 'saldo' entre filas consecutivas.
        Si saldo sube -> monto positivo; si baja -> monto negativo.
        Mantiene el saldo de la primera fila como referencia.
        """
        saldo_prev = None
        rows = []
        for i, row in df.iterrows():
            monto = row['monto']
            saldo = row['saldo']
            if i == 0:
                # Sin delta; asumir 'monto' ya normalizado si existe
                rows.append({'fecha': row['fecha'],
                             'descripcion': row['descripcion'],
                             'monto': monto,
                             'saldo': saldo})
                saldo_prev = saldo if isinstance(saldo, (int, float)) else saldo_prev
                continue

            if isinstance(saldo, (int, float)) and isinstance(saldo_prev, (int, float)) and isinstance(monto, (int, float)):
                delta = saldo - saldo_prev
                if delta < 0 and monto > 0:
                    monto = -monto
                elif delta > 0 and monto < 0:
                    monto = -monto
            rows.append({'fecha': row['fecha'],
                         'descripcion': row['descripcion'],
                         'monto': monto,
                         'saldo': saldo})
            saldo_prev = saldo if isinstance(saldo, (int, float)) else saldo_prev
        
        return pd.DataFrame(rows)
