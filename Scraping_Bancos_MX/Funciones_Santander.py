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
        if re.search("CONCEPTOADM",row["Concepto"]):
            concepto = row["Concepto"].split("CONCEPTOADM")[1]
            
        df.loc[index,"ConceptoMovimiento"] = concepto

    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        banco = "-"
        if re.search("SPEI",row["Concepto"]):
            try:
                banco = row["Concepto"].split("ENVIADOA")[1]
            except:
                banco = row["Concepto"].split("RECIBIDODE")[1]
            banco = banco.split("|")[0]
        df.loc[index,"InstitucionContraparte"] = banco
    return df

def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        destinatario = "-"
        if re.search("SPEI",row["Concepto"]):
            destinatario = row["Concepto"].split("LCLIENTE")[1]
            
            try:
                destinatario = destinatario.split("(")[0]
            except:
                destinatario = destinatario.split("|")[0]
        df.loc[index,"Contraparte"] = destinatario


    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        conceptos = row["Concepto"].split("|")
        concepto = conceptos[1]
        if re.search("SPEI",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("COM",concepto) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        elif re.search("RFC",concepto):
            df.loc[index,"TipoMovimiento"] = "PAGO"
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
        if re.search("FECHAFOLIODESCRIPCIONDEPOSITOSRETIROSSALDO", texto) :
                movimientos = extraer_movimientos_pagina(pagina,texto)
                df = pd.concat([df, pd.DataFrame(movimientos)])    
                contador += 1
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
        if coordenada <= 61 and coordenada >= 16:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 96  and coordenada > 68:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 326  and coordenada > 96:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 415  and coordenada > 326:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 495  and coordenada > 415:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 577  and coordenada > 495:
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
            elif row["Fecha"] == "BANCOSANT" or row["Concepto"] == "OMUNIQUESUSOBJECIONESENUNPLAZODE90DIASDELOCONTR":
                filas = filas[filas["Top"] < row["Top"]]
            elif row["Concepto"] == "TOTAL":
                filas = filas[filas["Top"] < row["Top"]]
                
    for index,row in filas.iterrows():
        if index > 0:
            if row["Concepto"] == "SALDOFINALDELPERIODOANTERIOR":
                filas = filas.drop(index)
    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match("\d{2}-\w{3}-\d{4}", fila["Fecha"]):
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