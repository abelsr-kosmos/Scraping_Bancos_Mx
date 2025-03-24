import pandas as pd
import re
import pdfplumber


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