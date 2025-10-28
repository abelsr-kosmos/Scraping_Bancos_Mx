import re
import time
from typing import Any, Dict, List

import pdfplumber
import pandas as pd

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    tabla2 = tabla2[['Fecha', 'Concepto', 'Origen', 'Deposito', 'Retiro','Saldo']]
    tabla2['descripcion'] = tabla2['Concepto'] + ' ' + tabla2['Origen']
    tabla2 = tabla2.drop(['Concepto', 'Origen'], axis=1)
    tabla2.columns = tabla2.columns.str.lower()
    try:
        tabla2['deposito'] = pd.to_numeric(tabla2['deposito'].str.replace(",",""), errors='coerce')
    except:
        print("Error al convertir deposito a numérico")
    try:
        tabla2['retiro'] = pd.to_numeric(tabla2['retiro'].str.replace(",",""), errors='coerce')
    except:
        print("Error al convertir retiro a numérico")
    try:
        tabla2['saldo'] = pd.to_numeric(tabla2['saldo'].str.replace(",",""), errors='coerce')
    except:
        print("Error al convertir saldo a numérico")
    tabla2 = tabla2[['fecha', 'descripcion', 'deposito', 'retiro','saldo']]
    return tabla2

def obtener_coordenadas(pagina):
    caracteres = []
    #Iterar sobre cada caracter
    for caracter in pagina.chars:
        #agregamos a la lista únicamente los datos que nos interesan
        caracteres.append(
            {
                "Texto": caracter["text"], 
                "top": caracter["top"], 
                "bottom": caracter["bottom"], 
                "left": caracter["x0"], 
                "right": caracter["x1"],
                "height": caracter["height"], 
                "width": caracter["width"]
            }
        )
    #Convertimos la lista en un dataframe
    df = pd.DataFrame(caracteres)
    #Ordenamos el dataframe por top
    df = df.sort_values(by=["top"])
    #Redondeamos los valores de top al inmediato superior
    #df["top"] = df["top"].apply(lambda x: round(x,0))
    return df

#Operar linea
def identificar_campos(coordenada):
        if(coordenada) <= 55 and coordenada >= 0:
            return "Oper"
        elif(coordenada) <= 100 and coordenada >= 55:
            return "Fecha"
        elif(coordenada) <= 314 and coordenada >= 100:
            return "Descripcion"
        elif(coordenada) <= 420 and coordenada >= 314:
            return "Cargos"
        elif(coordenada) <= 466 and coordenada >= 420:
            return "Abono"
        else:
            return "-"


def identificar_numero_de_linea(df):
    df = df.copy()  # Avoid modifying the original DataFrame
    df["tipo"] = df["right"].apply(identificar_campos)
    df['prev_top'] = df['top'].shift(1)
    condition = df['top'] > (df['prev_top'] + (df['height'] * 0.7))
    df['linea'] = condition.cumsum().fillna(0).astype(int)
    df.drop('prev_top', axis=1, inplace=True)
    return df

#Identifca que tipo de campo y concatena el texto para obtener la información correspondiente
def scrap_fila(fila):
    # Group by 'tipo' and concatenate 'Texto' for each group
    grouped = fila.groupby("tipo")["Texto"].apply(''.join)
    
    # Extract the concatenated strings, defaulting to empty string if key not present
    oper = grouped.get("Oper", "")
    fecha = grouped.get("Fecha", "")
    descripcion = grouped.get("Descripcion", "")
    cargo = grouped.get("Cargos", "")
    abono = grouped.get("Abono", "")
    
    return {"Operacion": oper, "Fecha": fecha, "Descripcion": descripcion, "Cargo": cargo, "Abono": abono}

def scrap_filas(df):
    # Ensure "linea" is integer for proper grouping
    df = df.copy()
    df["linea"] = df["linea"].astype(int)
    
    # Use pandas groupby for vectorized operation: group by "linea", sort each group by "left", apply scrap_fila
    filas = df.groupby("linea").apply(lambda group: scrap_fila(group.sort_values(by=["left"])))
    
    # Convert the resulting Series of dicts to a DataFrame
    result_df = pd.DataFrame(list(filas))
    return result_df


def limpiar_primera_pagina(df):
    df = df.copy()
    primeras_filas = True
    for index,row in df.iterrows():
        if re.search(r"\d{1,2}/\w{3}",row["Operacion"]) and primeras_filas:
            df.drop(df.index[:index], inplace=True)
            primeras_filas = False
        if re.search("La GAT ",row["Operacion"]):
        
            df.drop(index, inplace=True)        
        if re.search("BBVA M",row["Operacion"]):
        
            df.drop(index, inplace=True)
        #if re.search("([0-2][0-9]|3[0-1])(\/|-)(0[1-9]|1[0-2])\2(\d{4})"):
            
    return df


def operar_pagina(pagina):
    df = obtener_coordenadas(pagina)
    df = identificar_numero_de_linea(df)
    df = scrap_filas(df)
    return df

def limpiar_ultima_pagina(df):
    df = df.copy()
    ultimas_filas = False
    primeras_filas = True
    for index,row in df.iterrows():
        
        if re.search(r"\d{1,2}/\w{3}",row["Operacion"]) and primeras_filas:
            df.drop(df.index[:index ], inplace=True)
            primeras_filas = False
        if re.search(r"Total de ",row["Operacion"]):
            ultimas_filas = True
        if ultimas_filas:
            df.drop(index, inplace=True)

    return df

def limpiar_paginas(df):
    df = df.copy()
    eliminar_celdas_vacias = True
    for index,row in df.iterrows():
        if re.search(r"\d{1,2}\/\w{3}",row["Operacion"]):
            eliminar_celdas_vacias = False
        if (row["Operacion"] == "" and eliminar_celdas_vacias):
            df.drop(index, inplace=True)

        if not re.search(r"\d{1,2}\/\w{3}",row["Operacion"]) and row["Operacion"] != "":
            df.drop(index, inplace=True)
    return df

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def correccion_abono_cargo(df_movimientos):
    for index,fila in df_movimientos.iterrows(): #[+-]?([0-9]*[.])?[0-9]+
        abono_temp = fila["Abono"].replace(",","")
        abono_temp = abono_temp.replace(" ","")
        cargo_temp = fila["Cargo"].replace(",","")
        cargo_temp = cargo_temp.replace(" ","")
        if is_number(abono_temp) and is_number(cargo_temp):
                fila["Abono"] = str(fila["Cargo"]) + str(fila["Abono"])
                fila["Cargo"] = ""
    return df_movimientos

def unificar_tabla(df):

    df = df.copy()
    movimientos = df["Movimiento"].max()
    lista_movimientos = []
    for i in df["Movimiento"].unique():
        tabla_temporal = df[df["Movimiento"] == i]
        movimiento = unificar_movimientos(tabla_temporal)
        lista_movimientos.append(movimiento)
    return pd.DataFrame(lista_movimientos)

def inicializar_movimientos(df_movimientos):
    df_movimientos["Movimiento"] = 0
    numero_movimiento = 0
    for i in range(0,df_movimientos.shape[0]):
        operacion = df_movimientos.iloc[i,0]
        if re.search(r"\d{1,2}\/\w{3}",operacion):
            numero_movimiento += 1
        df_movimientos.iloc[i,5] = numero_movimiento
    return df_movimientos

def unificar_movimientos(df):
    df = df.copy()
    descripcion = ""
    for index,fila in df.iterrows():
        descripcion = descripcion + "|" + fila["Descripcion"]

    try:
        referencia = df.iloc[1,3]
    except:
        referencia = " - "
    moviemiento = {"Operacion":df.iloc[0,0],"Fecha":df.iloc[0,1],"Descripcion":descripcion,"Referencia":referencia, "Cargo":df.iloc[0,3],"Abono":df.iloc[0,4],"Movimiento":df.iloc[0,5]}
    return moviemiento

def extraer_fecha_primera_pagina(pagina):
    texto = pagina.extract_text().replace("\n","").replace(" ","")
    periodo = re.findall(r"PeriodoDEL\d{2}\/\d{2}\/\d{4}AL\d{2}\/\d{2}\/\d{4}",texto)[0]
    anio = re.findall(r"\d{2}\/\d{2}\/\d{4}",periodo)[0].split("/")[-1]
    return anio

def incluir_anios(df_movimientos,anio_inicio):
    campo_fecha=0
    df_movimientos = incluir_anio(df_movimientos,anio_inicio,campo_fecha)
    campo_fecha=1
    df_movimientos = incluir_anio(df_movimientos,anio_inicio,campo_fecha)
    return df_movimientos

def incluir_anio(df,anio_inicio,campo_fecha):
    meses = []
    for i in range(0,df.shape[0]):
        operacion =re.findall(r"\d{1,2}\/\w{3}",df.iloc[i,campo_fecha])
        if operacion:
            mes = re.findall(r"\w{3}",operacion[0])
            meses.append(mes)
    try:
        if meses[0][0] == "DIC":
            for i in range(0,df.shape[0]):
                operacion =re.findall(r"DIC",df.iloc[i,campo_fecha])
                if(operacion):
                    df.iloc[i,campo_fecha] += str(anio_inicio)
                else:
                    df.iloc[i,campo_fecha] += str(int(anio_inicio)+1)
        else:
            for i in range(0,df.shape[0]):
                df.iloc[i,campo_fecha] += "/" + str(int(anio_inicio))
    except:
        pass
    return df


def analizar_estados(documento):
    movimientos = False
    df_movimientos = pd.DataFrame()
    anio_inicio = ""
    for index, pagina in enumerate(documento.pages):
        # Extraer texto de la página
        texto = pagina.extract_text().replace("\n", "").replace(" ", "")
        
        # Busca coincidencias en el texto para identificar el tipo de pagina y aplicar la función correspondiente a cada uno
        if re.search("DetalledeMovimientosRealizados", texto) and re.search("OPERLIQ", texto):
            movimientos = True
            # Extraer Fecha o Periodo
            df = operar_pagina(pagina)
            df = limpiar_primera_pagina(df)
            anio_inicio = extraer_fecha_primera_pagina(pagina)
            df = incluir_anios(df, anio_inicio)
            df_movimientos = pd.concat([df_movimientos, df], ignore_index=True)
            continue
        
        elif re.search("TotaldeMovimientos", texto) and re.search("TOTALMOVIMIENTOSCARGOS", texto):
            df = operar_pagina(pagina)
            df = limpiar_ultima_pagina(df)
            df = incluir_anios(df, anio_inicio)
            df_movimientos = pd.concat([df_movimientos, df], ignore_index=True)
            movimientos = False
            continue
        
        if movimientos:
            df = operar_pagina(pagina)
            df = limpiar_paginas(df)
            df = incluir_anios(df, anio_inicio)
            df_movimientos = pd.concat([df_movimientos, df], ignore_index=True)
        
    df_movimientos = correccion_abono_cargo(df_movimientos)
    df_movimientos = inicializar_movimientos(df_movimientos)
    df_movimientos = unificar_tabla(df_movimientos)
    
    return df_movimientos


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
    df = df.drop('Fecha', axis=1)
    df["Saldo"] = ""
    df = df.rename(columns={"Operacion": "Fecha", "Descripcion": "Concepto", "Referencia": "Origen", "Cargo": "Retiro", "Abono": "Deposito"})
    df = df[['Fecha', 'Concepto', 'Origen', 'Deposito', 'Retiro','Saldo','TipoMovimiento','Contraparte','InstitucionContraparte','ConceptoMovimiento']]
    return df


def analisis_concepto(df):
    df["ConceptoMovimiento"] = ""
    for index,row in df.iterrows():
        descripciones = row["Descripcion"]
        descripcion= "-"
        tipo = row["TipoMovimiento"]
        if re.search("SPEI",tipo):
            contador_concepto = descripciones.count("|")
            if contador_concepto > 2:
                descripcion = descripciones.split("|")[2]
                if re.search(r"\d{7}",descripcion):
                    descripcion = descripcion.replace(re.search(r"\d{7}",descripcion).group(),"")
        df.loc[index,"ConceptoMovimiento"] = descripcion

    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        conceptos= row["Descripcion"].split("|")
        tipo = row["TipoMovimiento"]
        banco = "Sin Contraparte"
        concepto = conceptos[1]
        if re.search("SPEI RECIBIDO",concepto):
            banco = concepto.replace("SPEI RECIBIDO","")
        elif re.search("SPEI ENVIADO",concepto):
            banco = concepto.replace("SPEI ENVIADO","")
        elif re.search("SPEI DEVUELTO",concepto):
            banco = concepto.replace("SPEI DEVUELTO","")
        df.loc[index,"InstitucionContraparte"] = banco
    return df
            
            
            



def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        concepto = row["Descripcion"]
        tipo = row["TipoMovimiento"]
        contraparte="-"

        if re.search("SPEI",tipo) :
            contador_concepto = concepto.count("|")
            if contador_concepto > 2:
                contraparte = concepto.split("|")[-1]
            else:
                contraparte = "SPEI CON ERROR"
        elif re.search("COMPRA",tipo):
            contraparte = concepto.split("|")[1]
        elif re.search("PAGO",concepto) and re.search("TERCERO",concepto):
            if re.search(r"\w{4} \d{10}",concepto):
                contraparte = re.search(r"\w{4} \d{10}",concepto).group()

        df.loc[index,"Contraparte"] = contraparte
    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
         
        concepto = row["Descripcion"].split("|")[1]
        if re.search("SPEI",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("DEPOSITO",concepto):
            df.loc[index,"TipoMovimiento"] = "DEPOSITO"
        elif re.search("PAGO",concepto):
            df.loc[index,"TipoMovimiento"] = "PAGO"
        elif re.search("RFC",row["Descripcion"]):
            df.loc[index,"TipoMovimiento"] = "COMPRA"
        elif re.search("COM",row["Descripcion"]) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",row["Descripcion"]):
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"
    return df


class BBVAExtractor:
    # 1️⃣ Constantes de clase
    months: List[str] = [
        'ENE','FEB','MAR','ABR','MAY','JUN',
        'JUL','AGO','SEP','OCT','NOV','DIC'
    ]
    months_pattern: str = '|'.join(months)
    double_date_pattern: str = rf"\b\d{{2}}[/I]?({months_pattern})\b\s+\d{{2}}[/I]?({months_pattern})\b"
    money_regex: str = r'\b\d{1,3}(?:,\d{3})*\.\d{2}\b'

    def __init__(self, text: str, ocr: dict):
        self.text = text
        self.ocr  = ocr
        self.flattened_ocr: pd.DataFrame = pd.DataFrame()

    def _flatten_ocr(self) -> None:
        """Aplana el OCR en un DataFrame ['word','geometry']"""
        words: List[tuple] = []
        for page_index, page in enumerate(self.ocr, 1):
            for item in page['items']:
                for block in item['blocks']:
                    for line in block['lines']:
                        for word in line['words']:
                            words.append((word['value'], word['geometry'], page_index))
        self.flattened_ocr = pd.DataFrame(words, columns=['word','geometry','page'])
        self.flattened_ocr['x0'] = self.flattened_ocr['geometry'].apply(lambda g: g[0])
        self.flattened_ocr['y0'] = self.flattened_ocr['geometry'].apply(lambda g: g[1])
        self.flattened_ocr['x1'] = self.flattened_ocr['geometry'].apply(lambda g: g[2])
        self.flattened_ocr['y1'] = self.flattened_ocr['geometry'].apply(lambda g: g[3])
        self.flattened_ocr.sort_values(by=['page','y0','x0'], inplace=True)
        self.flattened_ocr = self.flattened_ocr[~((self.flattened_ocr['page']==1) & (self.flattened_ocr['y0']<0.65))]
        self.flattened_ocr.reset_index(drop=True, inplace=True)

    def _split_text(self) -> List[str]:
        """Divide el texto en fragmentos que empiezan con un par de fechas"""
        matches = list(re.finditer(self.double_date_pattern, self.text))
        if not matches:
            return [self.text.strip()]

        parts: List[str] = []
        for i, m in enumerate(matches):
            start = m.start()
            end   = matches[i+1].start() if i+1 < len(matches) else len(self.text)
            parts.append(self.text[start:end].strip())
        return parts

    def _build_dataframe(self, parts: List[str]) -> pd.DataFrame:
        """Extrae fecha, montos, saldo y geometrías, y genera el DataFrame final"""
        movimientos: List[Dict[str, Any]] = []

        for fragment in parts:
            # 📅 Fecha
            fecha = re.search(self.double_date_pattern, fragment).group().split()[0]
            # 💰 Montos con dos decimales
            montos = re.findall(self.money_regex, fragment)
            # 📐 Geometrías
            geoms = self.flattened_ocr.loc[
                self.flattened_ocr['word'].str.contains(montos[0], flags=re.IGNORECASE, regex=True)
            ]['geometry'].tolist()
            # limpiamos para no volver a reutilizar
            if len(geoms) != 0:
                geoms = geoms[0]
                index = self.flattened_ocr.index[self.flattened_ocr['word'] == montos[0]][0]
                self.flattened_ocr = self.flattened_ocr.drop(index)

            bbva_index = fragment.find('BBVA MEXICO')
            if bbva_index != -1:
                fragment = fragment[:bbva_index].strip()
                
            # Remove first occurrence of duplicated amount and saldo from the fragment text
            for i in range(len(montos)):
                fragment = re.sub(rf'\b{re.escape(montos[i])}\b', '', fragment, count=1)
            fragment = re.sub(r'\n{2,}', '\n', fragment).strip()  
                          
            movimientos.append({
                "fecha":      fecha,
                "descripcion": fragment[14:200],
                "monto":      montos[0],
                "saldo":      montos[2] if len(montos)>2 else None,
                "geometry":   geoms
            })

        df = pd.DataFrame(movimientos)
        # 🔄 Postprocesado
        df['monto'] = df['monto'].str.replace(',','').astype(float)
        if df['saldo'].notnull().any():
            df['saldo'] = df['saldo'].str.replace(',','').astype(float)
        df['x0_pos'] = df['geometry'].apply(lambda g: g[0] if g else None)
        df['x1_pos'] = df['geometry'].apply(lambda g: g[2] if g else None)
        df['x_pos']  = (df['x0_pos'] + df['x1_pos'])/2

        # Determinar signo según posición
        df['monto'] = df.apply(
            lambda r: r['monto'] if pd.isnull(r['x_pos'])
                      else ( r['monto'] if r['x_pos']>0.68 else -r['monto'] ),
            axis=1
        )
        df['retiro']      = df['monto'].apply(lambda v: abs(v) if v<0 else 0)
        df['deposito']      = df['monto'].apply(lambda v: v if v>0 else 0)
        df['confidence'] = df['x_pos'].notnull()

        return df[['fecha','descripcion','retiro','deposito','saldo']]

    def extract(self) -> pd.DataFrame:
        """Método interno que corre todo el pipeline"""
        self._flatten_ocr()
        partes = self._split_text()
        return self._build_dataframe(partes)

    @classmethod
    def parse(cls, text: str, ocr: dict) -> pd.DataFrame:
        """
        INTERFAZ PRINCIPAL ► Pasa solo text y ocr, devuelve el DataFrame listo.
        """
        extractor = cls(text, ocr)
        return extractor.extract()