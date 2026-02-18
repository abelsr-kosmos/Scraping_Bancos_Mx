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
        if re.search("SPEI",row["Concepto"]) and (re.search("TRA",row["Concepto"]) or re.search("INT",row["Concepto"]) ) and not re.search("IVA",row["Concepto"]) and not re.search("COMISION",row["Concepto"],re.IGNORECASE):
            concepto = row["Concepto"].split(",")[-1]

        try:
            concepto = concepto.replace("|","")
        except:
            pass
        df.loc[index,"ConceptoMovimiento"] = concepto
    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        banco = "Sin Contraparte"
        if re.search("SPEI",row["Concepto"]) and (re.search("TRA",row["Concepto"]) or re.search("INT",row["Concepto"]) ) and not re.search("IVA",row["Concepto"]) and not re.search("COMISION",row["Concepto"],re.IGNORECASE):
            concepto = row["Concepto"].split("SPEI,")[1]
            banco = concepto.split(",")[0]
        elif re.search("TRASPASO",row["Concepto"]):
            banco = "BANREGIO"
        try:
            banco = banco.replace("|","")
        except:
            pass
        df.loc[index,"InstitucionContraparte"] = banco

    return df


def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        concepto= "-"
        if re.search("SPEI",row["Concepto"]) and (re.search("TRA",row["Concepto"]) or re.search("INT",row["Concepto"]) )and not re.search("IVA",row["Concepto"]) and not re.search("COMISION",row["Concepto"],re.IGNORECASE):
            concepto = row["Concepto"].split(",")[3]
        elif re.search("TRASPASO",row["Concepto"]) and re.search("RFC",row["Concepto"]):
            concepto = row["Concepto"].split(",")[1]

        try:
            concepto = concepto.replace("|","")
        except:
            pass
        df.loc[index,"Contraparte"] = concepto

    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        conceptos = row["Concepto"].split("|")
        concepto = conceptos[1]
        if re.search("SPEI",concepto) and not re.search("IVA",concepto) and not re.search("COM.",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("TRA",concepto) and  re.search("PAGO",concepto,re.IGNORECASE) and not re.search("COM.",concepto):
            df.loc[index,"TipoMovimiento"] = "PAGO"
        elif re.search("omision",concepto) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",concepto):
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
        if re.search("DIACONCEPTOCARGOSABONOSSALDO", texto) and not re.search("GráficoTransaccional", texto) and not re.search("REGIOCUENTA", texto):
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
        if row["Fecha"] != "" and row["Concepto"] == "":
            df.loc[index+1, "Fecha"] = df.loc[index, "Fecha"]
            df.loc[index+1, "Deposito"] = df.loc[index, "Deposito"]
            df.loc[index+1, "Retiro"] = df.loc[index, "Retiro"]
            df.loc[index+1, "Saldo"] = df.loc[index, "Saldo"]
            df.drop(index, inplace=True)

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

def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match(r"\d{2}", fila["Fecha"]):
            contador_movimiento += 1 
        df.loc[index,"Movimiento"] = contador_movimiento
    return df


def extraer_movimientos_pagina(pagina,texto):
    caracteres = pagina.chars
    columnas = agrupar_columnas(caracteres)
    filas = unificar_columnas(columnas)
    filas = eliminar_movimientos_no_deseados(filas)
    incluir_anio_mes(filas,texto)
    return filas

def incluir_anio_mes(filas,texto):
    anios = {"ENERO":1,"FEBRERO":2,"MARZO":3,"ABRIL":4,"MAYO":5,"JUNIO":6,"JULIO":7,"AGOSTO":8,"SEPTIEMBRE":9,"OCTUBRE":10,"NOVIEMBRE":11,"DICIEMBRE":12}
    periodo = re.search(r"del\d{2}al\d{2}de\w+\d{4}",texto)
    periodo = periodo.group(0).replace("del","")
    periodo = periodo.split("de")[1]
    anio = periodo[-4:]
    mes = periodo[:-4]
    mes = anios[mes.upper()]
    for index, fila in filas.iterrows():
        if  re.match(r"\d{2}", fila["Fecha"]):
            filas.loc[index,"Fecha"] = fila["Fecha"] + "/" + str(mes) + "/" + str(anio)




def agrupar_columnas(caracteres):
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 50 and coordenada >= 34:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],4),"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 341  and coordenada > 50:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],4),"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 420  and coordenada > 341:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],4),"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 500  and coordenada > 420:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],4),"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 577  and coordenada > 500:
            columnas.append({"Caracter": caracter["text"], "Top": round(caracter["top"],4),"X":caracter["x1"],"Columna": 4})
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
    for index,row in filas.iterrows():
        if index > 0:
            if row["Fecha"] == "DIA":
                filas = filas[filas["Top"] > row["Top"]]
            elif  re.search("Page" ,row["Saldo"]):
                filas = filas[filas["Top"] < row["Top"]]


    return filas