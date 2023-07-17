import pandas as pd
import re
import pdfplumber

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
        if  re.match("\w{3} \d{2}", fila["Fecha"]):
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