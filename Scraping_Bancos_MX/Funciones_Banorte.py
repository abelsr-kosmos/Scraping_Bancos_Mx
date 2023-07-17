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
        if re.search("SPEI RECIBIDO",row["Concepto"]):
            conceptos = row["Concepto"].split("CONCEPTO:")[1]
            concepto = conceptos.split("REFERENCIA")[0]
        elif re.search("PAGO SPEI",row["Concepto"]) and not re.search("COMISION",row["Concepto"]) and not re.search("I.V.A",row["Concepto"]):
            conceptos = row["Concepto"].split("INST),")[1]
            concepto = conceptos.split("CVE")[0]
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
            if re.search("BCO:\d{4}",row["Concepto"]):
                conceptos = row["Concepto"].split("BCO:")[1]
                conceptos = conceptos[4:]
                concepto = conceptos.split("HR")[0]
                df.loc[index,"InstitucionContraparte"] = concepto
        elif re.search("PAGO SPEI",row["Concepto"]) and not re.search("COMISION",row["Concepto"]) and not re.search("I.V.A",row["Concepto"]):
                conceptos = row["Concepto"].split("IVA:")[1]
                concepto = conceptos.split("HORA")[0]
                concepto = ''.join([i for i in concepto if not i.isdigit()])
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
            conceptos = row["Concepto"].split("BENEF:")[1]
            concepto = conceptos.split("(DA")[0]
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
    anios = []
    contador = 0
    for pagina in estado.pages:
        texto = pagina.extract_text()
        texto = texto.replace("\n", "")
        texto = texto.replace(" ", "")
        if re.search("FECHADESCRIPCIÓN/ESTABLECIMIENTO", texto) :
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

def unificar_columna(top):
    top = top.sort_values(by=["X"])
    fecha = ""
    concepto = ""
    deposito = ""
    retiro = ""
    saldo = ""
    for index, row in top.iterrows():
        if row["Columna"] == 0:
            fecha = fecha + row["Caracter"]
        elif row["Columna"] == 1:
            concepto = concepto + row["Caracter"]
        elif row["Columna"] == 2:
            deposito = deposito + row["Caracter"]
        elif row["Columna"] == 3:
            retiro = retiro + row["Caracter"]
        elif row["Columna"] == 4:
            saldo = saldo + row["Caracter"]
    fila = {"Fecha": fecha, "Concepto": concepto, "Origen": "", "Deposito": deposito, "Retiro": retiro, "Saldo": saldo, "Top": top["Top"].max()}
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
            elif  re.search("Directa" ,row["Fecha"]):
                filas = filas[filas["Top"] < row["Top"]]
    for index, row in filas.iterrows():
        if index >0:
            if re.search("SALDO ANTERIOR",row["Concepto"] ):
                    filas = filas.drop(index)
            #elif  not re.match("\d{2}-\w{3}-\d{2}", row["Fecha"]):
            #    filas = filas.drop(index)

    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match("\d{2}-\w{3}-\d{2}", fila["Fecha"]):
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