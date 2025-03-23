import pdfplumber
import pandas as pd
import math
import re

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    return tabla2

def obtener_coordenadas(pagina):
    caracteres = []
    #Iterar sobre cada caracter
    for caracter in pagina.chars:
        #agregamos a la lista únicamente los datos que nos interesan
        caracteres.append({"Texto": caracter["text"], "top": caracter["top"], "bottom": caracter["bottom"], "left": caracter["x0"], "right": caracter["x1"],"height": caracter["height"], "width": caracter["width"]})
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
        elif(coordenada) <= 463 and coordenada >= 420:
            return "Abono"
        else:
            return "-"


def identificar_numero_de_linea(df):
    #Iterar los caracteres
    df["linea"]  = 0
    df["tipo"] = df["right"].apply(identificar_campos)
    linea = 0
    for i in range(df.shape[0]):

        posicion = df.iloc[i]["top"]
        altura = df.iloc[i]["height"]
        if i == 0:
            altura_linea = posicion
        
        if posicion > altura_linea + altura:
            altura_linea = posicion
            linea = linea + 1
        df.iloc[i,7] = linea
    return df

    #Si la poisicion del siguiente caracter es mayor que la posición actual + la altura del caracter, es una nueva linea

#Identifca que tipo de campo y concatena el texto para obtener la información correspondiente
def scrap_fila(fila):
    #meses = {"ENE":1,"FEB":2,"MAR":3,"ABR":4,"MAY":5,"JUN":6,"JUL":7,"AGO":8,"SEP":9,"OCT":10,"NOV":11,"DIC":12}
    oper = ""
    fecha = ""
    descripcion = ""
    cargo = ""
    abono = ""
    for i in range(fila.shape[0]):
        if fila.iloc[i]["tipo"] == "Oper":
            oper = oper + fila.iloc[i]["Texto"]
        elif fila.iloc[i]["tipo"] == "Fecha":
            fecha = fecha + fila.iloc[i]["Texto"]
        elif fila.iloc[i]["tipo"] == "Descripcion":
            descripcion = descripcion  + fila.iloc[i]["Texto"]
        elif fila.iloc[i]["tipo"] == "Cargos":
            cargo = cargo + fila.iloc[i]["Texto"]
        elif fila.iloc[i]["tipo"] == "Abono":
            abono = abono + fila.iloc[i]["Texto"]

    
    return {"Operacion": oper, "Fecha": fecha, "Descripcion": descripcion, "Cargo": cargo, "Abono": abono}

def scrap_filas(df):
    filas = []
    for i in range(df["linea"].max()):
        filas.append(scrap_fila(df[df["linea"] == i].sort_values(by=["left"])))
    df = pd.DataFrame(filas)
    return df


def limpiar_primera_pagina(df):
    df = df.copy()
    primeras_filas = True
    for index,row in df.iterrows():
        if re.search("\d{1,2}/\w{3}",row["Operacion"]) and primeras_filas:
            df.drop(df.index[:index], inplace=True)
            primeras_filas = False
        if re.search("La GAT ",row["Operacion"]):
        
            df.drop(index, inplace=True)        
        if re.search("BBVA M",row["Operacion"]):
        
            df.drop(index, inplace=True)
        #if re.search("([0-2][0-9]|3[0-1])(\/|-)(0[1-9]|1[0-2])\2(\d{4})"):
            
    return df

def limpiar_paginas(df):
    df = df.copy()

    eliminar_celdas_vacias = True
    for index,row in df.iterrows():
        if re.search("\d{1,2}\/\w{3}",row["Operacion"]):
            eliminar_celdas_vacias = False
        if (row["Operacion"] == "" and eliminar_celdas_vacias):
            df.drop(index, inplace=True)

        if not re.search("\d{1,2}\/\w{3}",row["Operacion"]) and row["Operacion"] != "":
            df.drop(index, inplace=True)
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
        
        if re.search("\d{1,2}/\w{3}",row["Operacion"]) and primeras_filas:
            df.drop(df.index[:index ], inplace=True)
            primeras_filas = False
        if re.search("Total de ",row["Operacion"]):
            
            ultimas_filas = True  
        if ultimas_filas:
            df.drop(index, inplace=True)

    return df

def limpiar_paginas(df):
    df = df.copy()

    eliminar_celdas_vacias = True
    for index,row in df.iterrows():
        if re.search("\d{1,2}\/\w{3}",row["Operacion"]):
            eliminar_celdas_vacias = False
        if (row["Operacion"] == "" and eliminar_celdas_vacias):
            df.drop(index, inplace=True)

        if not re.search("\d{1,2}\/\w{3}",row["Operacion"]) and row["Operacion"] != "":
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
        #a_num = is_number(abono_temp)
        #c_num = is_number(cargo_temp)
        #print(f"{abono_temp}= {a_num}|{cargo_temp} = {c_num}")
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
        if re.search("\d{1,2}\/\w{3}",operacion):
            numero_movimiento += 1
        df_movimientos.iloc[i,5] = numero_movimiento
    return df_movimientos

def unificar_movimientos(df):
    df = df.copy()
    descripcion = ""
    for index,fila in df.iterrows():
        descripcion = descripcion + "|" + fila["Descripcion"]

    referencia = df.iloc[1,3]
    moviemiento = {"Operacion":df.iloc[0,0],"Fecha":df.iloc[0,1],"Descripcion":descripcion,"Referencia":referencia, "Cargo":df.iloc[0,3],"Abono":df.iloc[0,4],"Movimiento":df.iloc[0,5]}
    return moviemiento

def extraer_fecha_primera_pagina(pagina):
    texto = pagina.extract_text().replace("\n","").replace(" ","")
    periodo = re.findall("PeriodoDEL\d{2}\/\d{2}\/\d{4}AL\d{2}\/\d{2}\/\d{4}",texto)[0]
    anio = re.findall("\d{2}\/\d{2}\/\d{4}",periodo)[0].split("/")[-1]
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
        operacion =re.findall("\d{1,2}\/\w{3}",df.iloc[i,campo_fecha])
        if operacion:
            mes = re.findall("\w{3}",operacion[0])
            meses.append(mes)
    try:
        if meses[0][0] == "DIC":
            for i in range(0,df.shape[0]):
                operacion =re.findall("DIC",df.iloc[i,campo_fecha])
                if(operacion):
                    df.iloc[i,campo_fecha] += str(anio_inicio)
                else:
                    df.iloc[i,campo_fecha] += str(int(anio_inicio)+1)
        else:
            for i in range(0,df.shape[0]):
                df.iloc[i,campo_fecha] += str(int(anio_inicio))
    except:
        pass
    return df


def analizar_estados(documento):
    movimientos = False
    df_movimientos = pd.DataFrame()
    fecha_estado_de_cuenta = ""
    anio_inicio = ""
    for index,pagina in enumerate(documento.pages):
        #Extraer texto de la página
        texto = pagina.extract_text().replace("\n","").replace(" ","")
        #Busca coincidencias en el texto para identificar el tipo de pagina y aplicar la función correspondiente a cada uno
        if re.search("DetalledeMovimientosRealizados",texto) and re.search("OPERLIQ",texto):
            movimientos = True
            #Extraer Fecha o Periodo
            df = operar_pagina(pagina)
            df = limpiar_primera_pagina(df)
            anio_inicio = extraer_fecha_primera_pagina(pagina)
            df = incluir_anios(df,anio_inicio)
            df_movimientos = pd.concat([df_movimientos,df], ignore_index=True)
            
            continue
        elif re.search("TotaldeMovimientos",texto) and re.search("TOTALMOVIMIENTOSCARGOS",texto):
            df = operar_pagina(pagina)
            df = limpiar_ultima_pagina(df)
            df = incluir_anios(df,anio_inicio)
            df_movimientos = pd.concat([df_movimientos,df], ignore_index=True)
            movimientos = False
            continue
        if(movimientos):
            df = operar_pagina(pagina)
            df = limpiar_paginas(df)
            df = incluir_anios(df,anio_inicio)
            df_movimientos = pd.concat([df_movimientos,df], ignore_index=True)
        print(f"{index+1} de {len(documento.pages)}", end="\r")


    df_movimientos =correccion_abono_cargo(df_movimientos)
    df_movimientos = inicializar_movimientos(df_movimientos)
    df_movimientos =unificar_tabla(df_movimientos)

    

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
                if re.search("\d{7}",descripcion):
                    descripcion = descripcion.replace(re.search("\d{7}",descripcion).group(),"")
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
            if re.search("\w{4} \d{10}",concepto):
                contraparte = re.search("\w{4} \d{10}",concepto).group()
            
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

