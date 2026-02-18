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
        if re.search("CONCEPTO:",row["Concepto"]):
            concepto = row["Concepto"].split("CONCEPTO:")[1]
            concepto = concepto.split("|")[0]
            if re.search("|HORA",row["Concepto"]):
                concepto = concepto.split("|HORA:")[0]
            try:
                concepto = concepto.replace("|","")
            except:
                pass
            df.loc[index,"ConceptoMovimiento"] = concepto
        elif re.search(" CON|CEPTO:",row["Concepto"]):
            concepto = row["Concepto"].split(" CON|CEPTO:")[1]
            df.loc[index,"ConceptoMovimiento"] = concepto
        else:
            concepto = row["Concepto"].replace("|","")
            df.loc[index,"ConceptoMovimiento"] = concepto
    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        if re.search("SPEI",row["Concepto"]):
            texto = row["Concepto"].split("|")[1]
            texto = texto.split("-")[1]
            df.loc[index,"InstitucionContraparte"] = texto
        elif re.search("OTRO BANCO",row["Concepto"]):
            texto = "OTRO BANCO"
            df.loc[index,"InstitucionContraparte"] = texto
        else:
            texto = "-"
            df.loc[index,"InstitucionContraparte"] = texto

    return df

def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        if re.search("DESTINATARIO",row["Concepto"]):
            destinatario =row["Concepto"].split("DESTINATARIO:")[1]
            destinatario = destinatario.split("(DA")[0]
            destinatario = destinatario.replace("|","")
            df.loc[index,"Contraparte"] = destinatario
        elif re.search("EMISOR:",row["Concepto"]):
            emisor = row["Concepto"].split("EMISOR:")[1]
            emisor = emisor.split("|")[0]
            df.loc[index,"Contraparte"] = emisor
        else:
            cheque = "-"
            banco = ""
            df.loc[index,"Contraparte"] = f"{cheque} {banco}"
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
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"
        #Se busco el saber cuando identificar un pago y compra pero solo se tiene un estado de cuenta afirme por lo que solo se vieron
        #estos casos
    return df

def analizar_estados(estado):
    df = pd.DataFrame()
    anios = []
    contador = 0
    for pagina in estado.pages:
        texto = pagina.extract_text()
        texto = texto.replace("\n", "")
        texto = texto.replace(" ", "")
        if re.search("DíaDescripciónReferenciaDepósitosRetirosSaldo", texto) :
                movimientos = extraer_movimientos_pagina(pagina,texto)
                df = pd.concat([df, pd.DataFrame(movimientos)])    
                contador += 1
    df = corregir_concepto(df)
    df = incluir_movimientos(df)
    df = unificar_tabla(df)

    return df

def corregir_concepto(df):
    df = df.reset_index(drop=True)
    for index,row in df.iterrows():
        if row["Fecha"] != "" and row["Concepto"] == "":
            df.loc[index,"Concepto"] = df.loc[index-1,"Concepto"]
            df = df.drop(index=index-1) 
    return df
    
def extraer_movimientos_pagina(pagina,texto):
    caracteres = pagina.chars
    columnas = agrupar_columnas(caracteres)
    filas = unificar_columnas(columnas)
    filas = eliminar_movimientos_no_deseados(filas)
    filas = incluir_anio_mes(filas,texto)
    return filas

def incluir_anio_mes(filas,texto):
    anios = {"ENE":1,"FEB":2,"MAR":3,"ABR":4,"MAY":5,"JUN":6,"JUL":7,"AGO":8,"SEP":9,"OCT":10,"NOV":11,"DIC":12}
    periodo = re.search(r"\d{2}[A-Z]{3}\d{4}",texto)
    anio = periodo.group(0)[5:]
    mes =  periodo.group(0)[2:5]
    for index, fila in filas.iterrows():
        if  re.match("\d{2}", fila["Fecha"]):
            filas.loc[index,"Fecha"] = fila["Fecha"] + "/" + str(mes) + "/" + str(anio)
    return filas

def agrupar_columnas(caracteres):
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 60 and coordenada >= 35:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 287  and coordenada > 60:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 340  and coordenada > 287:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 420  and coordenada > 340:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 497  and coordenada > 420:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 578  and coordenada > 497:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],2),"X":caracter["x1"],"Columna": 5})
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
            if row["Fecha"] == "Día" and contador_repeticion == 0:
                filas = filas[filas["Top"] > row["Top"]]
                contador_repeticion += 1
            if  re.search("Sus ahorros" ,row["Concepto"]) or re.search("Método" ,row["Fecha"]):
                filas = filas[filas["Top"] < row["Top"]]
            #if  row["Fecha"] == "" and row["Concepto"] == "":
            #    filas = filas.drop(index)
    #for index,row in filas.iterrows():
        #if index > 0:
            #if row["Fecha"] == "" and row["Concepto"] == "":
                #filas = filas.drop(index)



    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match(r"\d{2}", fila["Fecha"]):
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