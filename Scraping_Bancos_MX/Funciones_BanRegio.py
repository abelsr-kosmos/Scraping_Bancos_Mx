import re

import pdfplumber
import pandas as pd
import numpy as np

RE_SPEI = re.compile(r"SPEI")
RE_TRA_INT = re.compile(r"TRA|INT")
RE_IVA = re.compile(r"IVA")
RE_COMISION = re.compile(r"COMISION", re.IGNORECASE)
RE_COM = re.compile(r"COM\.")
RE_TRASPASO = re.compile(r"TRASPASO")
RE_RFC = re.compile(r"RFC")
RE_PAGE = re.compile(r"Page")
RE_FECHA = re.compile(r"\d{2}")

def Scrap_Estado(ruta_archivo):
    with pdfplumber.open(ruta_archivo) as estado:
        tabla = analizar_estados(estado)
    tabla = analisis_movimientos(tabla)
    tabla = formatear_tabla(tabla)
    return tabla
    

def formatear_tabla(df):
    # Normalizamos solo para tener: ['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']
    # Concepto -> descripcion
    df = df.rename(columns={"Concepto": "descripcion"})
    # Fecha -> fecha
    df = df.rename(columns={"Fecha": "fecha"})
    # Deposito -> deposito
    df = df.rename(columns={"Deposito": "deposito"})
    # Retiro -> retiro
    df = df.rename(columns={"Retiro": "retiro"})
    # Saldo -> saldo
    df = df.rename(columns={"Saldo": "saldo"})
    # Quita | a la descripcion
    df["descripcion"] = df["descripcion"].str.replace("|", " ", regex=False)
    # Convert deposito, retiro y saldo a float, manejando comas y signos
    df["deposito"] = df["deposito"].apply(lambda x: float(str(x).replace(",", "").replace("$", "").strip()) if pd.notna(x) and str(x).strip() != "" else None)
    df["retiro"] = df["retiro"].apply(lambda x: float(str(x).replace(",", "").replace("$", "").strip()) if pd.notna(x) and str(x).strip() != "" else None)
    df["saldo"] = df["saldo"].apply(lambda x: float(str(x).replace(",", "").replace("$", "").strip()) if pd.notna(x) and str(x).strip() != "" else None)
    return df[["fecha", "descripcion", "deposito", "retiro", "saldo"]]

def analisis_movimientos(df):
    df = df.copy()
    df = analisis_tipo_movimiento(df)
    df = analisis_contraparte(df)
    df = analisis_institucion_contraparte(df)
    df = analisis_concepto(df)
    df = normalizar_tabla(df)
    return df

def normalizar_tabla(df):
    df = df.drop('Movimiento', axis=1, errors="ignore")
    return df


def analisis_concepto(df):
    concepto = df["Concepto"].fillna("")
    mask_spei = (
        concepto.str.contains(RE_SPEI)
        & concepto.str.contains(RE_TRA_INT)
        & ~concepto.str.contains(RE_IVA)
        & ~concepto.str.contains(RE_COMISION)
    )
    df["ConceptoMovimiento"] = "-"
    df.loc[mask_spei, "ConceptoMovimiento"] = concepto[mask_spei].str.rsplit(",", n=1).str[-1]
    df["ConceptoMovimiento"] = df["ConceptoMovimiento"].str.replace("|", "", regex=False)
    return df

def analisis_institucion_contraparte(df):
    concepto = df["Concepto"].fillna("")
    mask_spei = (
        concepto.str.contains(RE_SPEI)
        & concepto.str.contains(RE_TRA_INT)
        & ~concepto.str.contains(RE_IVA)
        & ~concepto.str.contains(RE_COMISION)
    )
    mask_traspaso = concepto.str.contains(RE_TRASPASO)

    df["InstitucionContraparte"] = "Sin Contraparte"
    df.loc[mask_spei, "InstitucionContraparte"] = concepto[mask_spei].str.extract(r"SPEI,([^,]+)")[0].fillna("Sin Contraparte")
    df.loc[mask_traspaso, "InstitucionContraparte"] = "BANREGIO"
    df["InstitucionContraparte"] = df["InstitucionContraparte"].str.replace("|", "", regex=False)

    return df


def analisis_contraparte(df):
    concepto = df["Concepto"].fillna("")
    mask_spei = (
        concepto.str.contains(RE_SPEI)
        & concepto.str.contains(RE_TRA_INT)
        & ~concepto.str.contains(RE_IVA)
        & ~concepto.str.contains(RE_COMISION)
    )
    mask_traspaso_rfc = concepto.str.contains(RE_TRASPASO) & concepto.str.contains(RE_RFC)

    df["Contraparte"] = "-"
    df.loc[mask_spei, "Contraparte"] = concepto[mask_spei].str.split(",").str[3].fillna("-")
    df.loc[mask_traspaso_rfc, "Contraparte"] = concepto[mask_traspaso_rfc].str.split(",").str[1].fillna("-")
    df["Contraparte"] = df["Contraparte"].str.replace("|", "", regex=False)

    return df

def analisis_tipo_movimiento(df):
    concepto = df["Concepto"].fillna("").str.split("|", n=2).str[1].fillna(df["Concepto"].fillna(""))

    mask_spei = concepto.str.contains(RE_SPEI) & ~concepto.str.contains(RE_IVA) & ~concepto.str.contains(RE_COM)
    mask_pago = concepto.str.contains("TRA") & concepto.str.contains("PAGO", case=False) & ~concepto.str.contains(RE_COM)
    mask_comision = concepto.str.contains("omision", case=False) & ~concepto.str.contains(RE_IVA)
    mask_iva = concepto.str.contains(RE_IVA)
    mask_compra = concepto.str.contains(RE_RFC)

    df["TipoMovimiento"] = "OTRO"
    df.loc[mask_spei, "TipoMovimiento"] = "SPEI"
    df.loc[mask_pago, "TipoMovimiento"] = "PAGO"
    df.loc[mask_comision, "TipoMovimiento"] = "COMISION"
    df.loc[mask_iva, "TipoMovimiento"] = "IVACOMISION"
    df.loc[mask_compra, "TipoMovimiento"] = "COMPRA"
    return df

def analizar_estados(estado):
    movimientos_paginas = []
    for pagina in estado.pages:
        texto = pagina.extract_text() or ""
        texto = texto.replace("\n", "").replace(" ", "")
        if re.search("DIACONCEPTOCARGOSABONOSSALDO", texto) and not re.search("GráficoTransaccional", texto) and not re.search("REGIOCUENTA", texto):
                movimientos = extraer_movimientos_pagina(pagina,texto)
                movimientos_paginas.append(movimientos)
    if movimientos_paginas:
        df = pd.concat(movimientos_paginas, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Top"])
    df = df.reset_index(drop=True)
    df = unificar_variaciones_altura(df)
    df = incluir_movimientos(df)
    df = unificar_tabla(df)
    return df



    

def unificar_variaciones_altura(df):
    if df.empty:
        return df

    mask = (df["Fecha"] != "") & (df["Concepto"] == "")
    idx = df.index[mask]
    if len(idx) == 0:
        return df

    idx_validos = idx[idx + 1 < len(df)]
    for col in ["Fecha", "Deposito", "Retiro", "Saldo"]:
        df.loc[idx_validos + 1, col] = df.loc[idx_validos, col].to_numpy()
    df = df.drop(idx)

    return df


def unificar_movimiento(df):
    df = df.copy()
    concepto = ""
    for index,fila in df.iterrows():
        concepto = concepto + "|" + fila["Concepto"]
    moviemiento = {"Fecha": df.iloc[0,0], "Concepto": concepto, "Origen": df.iloc[0,2], "Deposito": df.iloc[0,3], "Retiro": df.iloc[0,4], "Saldo": df.iloc[0,5],"Movimiento": df.iloc[0,6]}
    return moviemiento

def unificar_tabla(df):
    if df.empty:
        return pd.DataFrame(columns=["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Movimiento"])

    tabla = (
        df.groupby("Movimiento", sort=False)
        .agg(
            Fecha=("Fecha", "first"),
            Concepto=("Concepto", lambda s: "|" + "|".join(s.astype(str))),
            Origen=("Origen", "first"),
            Deposito=("Deposito", "first"),
            Retiro=("Retiro", "first"),
            Saldo=("Saldo", "first"),
        )
        .reset_index()
    )
    return tabla

def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = df["Fecha"].astype(str).str.match(RE_FECHA).cumsum().astype(int)
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
    if not periodo:
        return
    periodo = periodo.group(0).replace("del","")
    periodo = periodo.split("de")[1]
    anio = periodo[-4:]
    mes = periodo[:-4]
    mes = anios[mes.upper()]
    mask_fechas = filas["Fecha"].astype(str).str.match(RE_FECHA)
    filas.loc[mask_fechas, "Fecha"] = filas.loc[mask_fechas, "Fecha"] + "/" + str(mes) + "/" + str(anio)




def agrupar_columnas(caracteres):
    if not caracteres:
        return pd.DataFrame(columns=["Caracter", "Top", "X", "Columna"])

    columnas = pd.DataFrame(caracteres)[["text", "top", "x1"]].rename(columns={"text": "Caracter", "top": "Top", "x1": "X"})
    columnas["Top"] = columnas["Top"].round(4)

    x = columnas["X"]
    columnas["Columna"] = np.select(
        [
            (x >= 34) & (x <= 50),
            (x > 50) & (x <= 341),
            (x > 341) & (x <= 420),
            (x > 420) & (x <= 500),
            (x > 500) & (x <= 577),
        ],
        [0, 1, 2, 3, 4],
        default=-1,
    )
    return columnas[columnas["Columna"] >= 0]

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
    if columnas.empty:
        return pd.DataFrame(columns=["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Top"])

    col_ordenadas = columnas.sort_values(["Top", "X"])
    pivot = col_ordenadas.groupby(["Top", "Columna"], sort=False)["Caracter"].agg("".join).unstack(fill_value="")

    filas = pd.DataFrame(
        {
            "Fecha": pivot.get(0, ""),
            "Concepto": pivot.get(1, ""),
            "Origen": "",
            "Deposito": pivot.get(2, ""),
            "Retiro": pivot.get(3, ""),
            "Saldo": pivot.get(4, ""),
            "Top": pivot.index,
        }
    ).reset_index(drop=True)
    return filas.sort_values(by=["Top"])

def eliminar_movimientos_no_deseados(filas):
    filas = filas.reset_index(drop=True)
    if filas.empty:
        return filas

    mask_dia = (filas.index > 0) & (filas["Fecha"] == "DIA")
    if mask_dia.any():
        top_inicio = filas.loc[mask_dia, "Top"].iloc[0]
        filas = filas[filas["Top"] > top_inicio]

    mask_page = filas["Saldo"].astype(str).str.contains(RE_PAGE)
    if mask_page.any():
        top_fin = filas.loc[mask_page, "Top"].iloc[0]
        filas = filas[filas["Top"] < top_fin]


    return filas


if __name__ == "__main__":
    import cProfile
    import pstats
    from io import StringIO
    
    pr = cProfile.Profile()
    pr.enable()
    
    ruta_archivo = "/home/abelsr/Proyects/OCR-General/Scraping_Bancos_Mx/notebooks/gettablefileurl (59).pdf"
    df = Scrap_Estado(ruta_archivo)
    df["descripcion"] = df["descripcion"].str[:20]
    
    pr.disable()
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    print(s.getvalue())
    
    # To ensure results
    print(df.head())
    print(f"Total depositos: {df['deposito'].notna().sum()}, Total retiros: {df['retiro'].notna().sum()}")
    print(f"Suma depositos: {df['deposito'].sum()}, Suma retiros: {df['retiro'].sum()}")