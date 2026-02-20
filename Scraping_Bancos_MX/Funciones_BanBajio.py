import pandas as pd
import re
import pdfplumber

def Scrap_Estado(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estado(estado)
    tabla = analisis_movimientos(tabla)
    tabla = formatear_tabla(tabla)
    return tabla

def formatear_tabla(df):
    df = df.copy()
    df['descripcion'] = df['Origen'] + " " + df['Concepto'].str.replace("|"," ")
    df['fecha'] = df['Fecha']
    df['deposito'] = df['Deposito']
    df['retiro'] = df['Retiro']
    df['saldo'] = df['Saldo']
    df = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
    return df

def extraer_movimientos_primera_pagina(pagina):
    periodo = pagina.extract_text().split("\n")
    periodo = periodo[1].split(" ")
    periodo = periodo[-1]
    texto = pagina.extract_text().split("FECHA DESCRIPCION DE LA OPERACION")

    ultima_pagina = False
    if len(texto) == 1:
        return False
    else:
        texto = pagina.extract_text().split("FECHA DESCRIPCION DE LA OPERACION")[1]
        texto = texto.split("CONTINUA EN LA SIGUIENTE PAGINA")[0]
        if re.search("TOTAL DE MOVIMIENTOS EN EL PERIODO",texto):
            ultima_pagina = True
        texto = texto.split("\n")
        texto = texto[2:]
        if ultima_pagina:
            texto = texto[:-3]
        if re.search(r"^\d{4}$",periodo):
            texto += f" °{periodo}°"
        return texto

def scrap_movimientos(movimientos):
    numero_movimiento = 0
    movimientos_identificados = []
    for movimiento in movimientos:
        if re.match(r"\d{1,2} \w{3}",movimiento):
            numero_movimiento += 1
        movimientos_identificados.append({"movimiento":movimiento,"numero_movimiento":numero_movimiento})
        
    return pd.DataFrame(movimientos_identificados)
        
def obtener_montos_movimiento(movimiento):
    movimiento = movimiento.replace(" ","")
    movimiento = movimiento.split("$")
    if len(movimiento) == 2:
        monto = 0
        saldo = movimiento[-1]
    elif len(movimiento) >2:
        monto = movimiento[-2]
        saldo = movimiento[-1]
    else:
        monto = -1
        saldo = -1
    if str(monto)[-1] == "-":
        monto = monto[:-1]
        saldo = "-" + saldo
    return monto,saldo

def extraer_montos_saldos(movimientos):
    movimientos["Monto"] = ""
    movimientos["Saldo"] = ""
    for index,fila in movimientos.iterrows():
        movimiento =fila["movimiento"]
        monto,saldo = obtener_montos_movimiento(movimiento)
        movimientos.loc[index,"Monto"] = str(monto)
        movimientos.loc[index,"Saldo"] = str(saldo)
    return movimientos

def unificar_movimiento(df):
    df = df.copy()
    descripcion = ""
    for index,fila in df.iterrows():
        descripcion = descripcion + "|" + fila["movimiento"]
    moviemiento = {"Descripcion":descripcion,"Movimiento":df.iloc[0,1],"Monto":df.iloc[0,2],"Saldo":df.iloc[0,3]}
    return moviemiento

def unificar_tabla(movimmientos):
    total_movimientos = movimmientos["numero_movimiento"].max()
    movimientos_unificados = []
    for i in range(0,total_movimientos+1):
        movimientos_unificados.append(unificar_movimiento(movimmientos[movimmientos["numero_movimiento"]==i]))
    return pd.DataFrame(movimientos_unificados)

def extraer_movimientos_estado_de_cuenta(estado):
    movimientos = []
    for pag in estado.pages:
        movs = extraer_movimientos_primera_pagina(pag)
        if  movs:
            movimientos = movimientos + (extraer_movimientos_primera_pagina(pag))
    return movimientos
    

def identificar_cargo_abono(df):
    df["Cargos"] = ""
    df["Abonos"] = ""
    for i in range(1,df.shape[0]):
        saldo_anterior = df.iloc[i-1,3].replace(",","")
        saldo_actual = float(df.iloc[i,3].replace(",",""))
        monto = df.iloc[i,2].replace(",","")
        saldo_ideal = float(saldo_anterior) + float(monto)
        saldo_ideal = round(saldo_ideal,2)
        monto = str(monto)
        if saldo_actual != saldo_ideal:
            df.loc[i,"Cargos"] = monto
        else:
            df.loc[i,"Abonos"] = monto  
    return df

def separar_fecha(df):
    df["Fecha"] = None  # Crear la columna "Fecha" inicialmente con valores nulos
    for index, row in df.iterrows():
        texto = row["Descripcion"]
        matches = re.findall(r"\d{1,2}\ \w{3}", texto)
        if len(matches) > 0:
            fecha = matches[0]
            df.at[index, "Fecha"] = fecha
            df.at[index, "Descripcion"] = re.sub(r"\d{1,2}\ \w{3}", "", texto, count=1)
    return df

def separar_referencia(df):
    df["Referencia"] = None  
    for index, row in df.iterrows():
        texto = row["Descripcion"]
        matches = re.findall(r"\d{7}", texto)
        if len(matches) > 0:
            referencia = matches[0]
            df.at[index, "Referencia"] = referencia
            df.at[index, "Descripcion"] = re.sub(r"\d{7}", "", texto, count=1)
    return df

def incluir_anio(df):
    df["Anio"] = None
    estado_diciembre = False
    for index, row in df.iterrows():
        if re.search("°",row["Descripcion"]):
            anio_sin_modificar = row["Descripcion"].split("°")[1]
            anio = anio_sin_modificar.replace("|","")
            #df.at[index, "Descripcion"] = re.sub(f"\|\|\s\|°\|[0-9\|]+\|°", "", row["Descripcion"], count=1)
    for index, row in df.iterrows():
        if row["Fecha"] is not None:

            if re.search("DIC",row["Fecha"]):
                df.at[index, "Fecha"] += f"/{anio}"
                estado_diciembre = True
            else:
                if estado_diciembre:
                    df.at[index, "Fecha"] += f"/{int(anio)+1}"
                else:
                    df.at[index, "Fecha"] += f"/{anio}"
    return df

def eliminar_saldo_inicial(df):
    for index, row in df.iterrows():
        if re.search("SALDO INICIAL",row["Descripcion"]):
            df.drop(index, inplace=True)
    return df

def analizar_estado(estado):
    movimientos = extraer_movimientos_estado_de_cuenta(estado)
    movimientos = scrap_movimientos(movimientos)
    movimientos = extraer_montos_saldos(movimientos)
    movimientos = unificar_tabla(movimientos)
    movimientos = identificar_cargo_abono(movimientos)
    movimientos = separar_fecha(movimientos)
    movimientos = separar_referencia(movimientos)
    movimientos = incluir_anio(movimientos)
    movimientos = eliminar_saldo_inicial(movimientos)
    return movimientos

def normalizar_tabla(df):
    df = df.drop('Movimiento', axis=1)
    df = df.drop('Anio', axis=1)
    df = df.drop('Monto', axis=1)
    df = df.rename(columns={"Descripcion": "Concepto", "Referencia": "Origen", "Cargos": "Retiro", "Abonos": "Deposito"})
    df = df[['Fecha', 'Concepto', 'Origen', 'Deposito', 'Retiro','Saldo','TipoMovimiento','Contraparte','InstitucionContraparte','ConceptoMovimiento']]
    return df

def analisis_movimientos(df):
    df = df.copy()
    df = analisis_tipo_movimiento(df)
    df = analisis_contraparte(df)
    df = analisis_institucion_contraparte(df)
    df = analisis_concepto(df)
    df = normalizar_tabla(df)
    return df

def analisis_concepto(df):
    df["ConceptoMovimiento"] = ""
    for index,row in df.iterrows():
        if re.search("SPEI:",row["Descripcion"]):
            concepto = row["Descripcion"].split("SPEI:")[1]
            concepto = concepto.split("$")[0]
        else:
            concepto = "-"
        df.loc[index,"ConceptoMovimiento"] = concepto

    return df


def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    
    for index,row in df.iterrows():
        if re.search("ENVÍO SPEI",row["Descripcion"]):
            texto = row["Descripcion"].split("RECEPTORA:")[1]
            texto = texto.split("|")[0]
        elif re.search("DEPÓSITO SPEI:",row["Descripcion"]):
            texto = row["Descripcion"].split("EMISORA:")[1]
            texto = texto.split("|")[0]
        else:
            texto= "Sin contraparte"
        df.loc[index,"InstitucionContraparte"] = texto

    return df


def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        if re.search("BENEFICIARIO:",row["Descripcion"]):
            beneficiario = row["Descripcion"].split("BENEFICIARIO:")[1]
            beneficiario = beneficiario.split("|")[0]
            df.loc[index,"Contraparte"] = beneficiario
        elif re.search("ORDENANTE:",row["Descripcion"]):
            beneficiario = row["Descripcion"].split("ORDENANTE:")[1]
            beneficiario = beneficiario.split("|")[0]
            df.loc[index,"Contraparte"] = beneficiario
        elif re.search("COMPRA-DISPOSICION",row["Descripcion"]):
            separador = re.search(r"\d{2}\w{3}\d{4}",row["Descripcion"])
            beneficiario = row["Descripcion"].split(separador.group())[1]
            beneficiario = beneficiario.split("$")[0]
            df.loc[index,"Contraparte"] = beneficiario
        else:
            df.loc[index,"Contraparte"] = "-"
    return df

def analisis_tipo_movimiento(df):
    df["TipoMovimiento"] = ""
    for index,row in df.iterrows():
        conceptos = row["Descripcion"].split("|")
        concepto = conceptos[1]
        if re.search("SPEI",concepto) and not re.search("COMISION",concepto) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "SPEI"
        elif re.search("COMISION",concepto) and not re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "COMISION"
        elif re.search("IVA",concepto):
            df.loc[index,"TipoMovimiento"] = "IVACOMISION"
        elif re.search("COMPRA-DISPOSICION",concepto):
            df.loc[index,"TipoMovimiento"] = "COMPRA"
        elif re.search("PAGO",concepto):
            df.loc[index,"TipoMovimiento"] = "PAGO"
        else:
            df.loc[index,"TipoMovimiento"] = "OTRO"
    return df

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    ruta_archivo = "/home/abelsr/Proyects/OCR-General/Scraping_Bancos_Mx/notebooks/2033_033620303_1_20260105114600.pdf"
    tabla = Scrap_Estado(ruta_archivo)
    tabla['descripcion'] = tabla['descripcion'][:10] + "..."
    
    # Convert DataFrame to Rich Table
    rich_table = Table(title="Estado de Cuenta")
    for column in tabla.columns:
        rich_table.add_column(column)
    
    for _, row in tabla.iterrows():
        rich_table.add_row(*[str(val) for val in row])
    
    console.print(rich_table)