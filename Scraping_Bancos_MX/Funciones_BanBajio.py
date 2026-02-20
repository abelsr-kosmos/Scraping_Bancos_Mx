import pandas as pd
import re
import pdfplumber

MARCADORES_CORTE_TEXTO = ["SALDO TOTAL*", "TOTAL DE MOVIMIENTOS EN EL PERIODO", "RESUMEN DEL PERIODO"]
MARCADORES_FIN_MOVIMIENTOS = [
    "TOTAL DE MOVIMIENTOS EN EL PERIODO",
    "RESUMEN DEL PERIODO",
    "CODIGO",
    "CÓDIGO",
    "SELLO DIGITAL",
    "CADENA ORIGINAL",
    "CERTIFICACION DIGITAL",
    "NOMBRE O RAZON SOCIAL DEL RECEPTOR",
    "NOMBRE O RAZÓN SOCIAL DEL RECEPTOR",
]

RE_FECHA_CORTA = re.compile(r"\d{1,2}\ \w{3}")
RE_REFERENCIA = re.compile(r"\b\d{7,}\b")

def Scrap_Estado(ruta_archivo):
    with pdfplumber.open(ruta_archivo) as estado:
        tabla = analizar_estado(estado)
    tabla = analisis_movimientos(tabla)
    tabla = formatear_tabla(tabla)
    return tabla

def formatear_tabla(df):
    df = df.copy()
    origen = (
        df['Origen']
        .fillna("-")
        .astype(str)
        .replace({"nan": "-", "None": "-"})
        .str.strip()
    )
    concepto = (
        df['Concepto']
        .fillna("-")
        .astype(str)
        .replace({"nan": "-", "None": "-"})
        .str.replace(r"\$\s*-?[\d,]+(?:\.\d{2})?", " ", regex=True)
        .str.replace("|", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    df['descripcion'] = (origen + " " + concepto).str.replace(r"\s+", " ", regex=True).str.strip()
    df['descripcion'] = df['descripcion'].str.replace(r"^-\s-$", "-", regex=True)
    df['fecha'] = df['Fecha'].apply(lambda x: x.strip().replace(" ", "/") if isinstance(x, str) else x)
    df['deposito'] = pd.to_numeric(df['Deposito'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    df['retiro'] = pd.to_numeric(df['Retiro'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    df['saldo'] = pd.to_numeric(df['Saldo'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    df = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
    return df

def extraer_movimientos_primera_pagina(pagina):
    texto_pagina = pagina.extract_text_simple() or pagina.extract_text() or ""

    return _extraer_movimientos_desde_texto(texto_pagina)

def _extraer_movimientos_desde_texto(texto_pagina):
    if "FECHA DESCRIPCION DE LA OPERACION" not in texto_pagina:
        return False

    periodo = texto_pagina.split("\n")
    if len(periodo) < 2:
        return False
    periodo = periodo[1].split(" ")[-1]
    texto = texto_pagina.split("FECHA DESCRIPCION DE LA OPERACION", 1)

    ultima_pagina = False
    if len(texto) == 1:
        return False
    else:
        texto = texto[1]
        texto = texto.split("CONTINUA EN LA SIGUIENTE PAGINA", 1)[0]
        if "TOTAL DE MOVIMIENTOS EN EL PERIODO" in texto:
            ultima_pagina = True
        for marcador in MARCADORES_CORTE_TEXTO:
            texto = texto.split(marcador, 1)[0]
        texto = texto.split("\n")
        texto = texto[2:]
        if ultima_pagina:
            texto = texto[:-3]
        if periodo.isdigit() and len(periodo) == 4:
            texto.append(f"°{periodo}°")
        return texto

def scrap_movimientos(movimientos):
    numero_movimiento = 0
    movimientos_identificados = []

    for movimiento in movimientos:
        if not str(movimiento).strip():
            continue

        movimiento_mayus = str(movimiento).upper()
        if any(marcador in movimiento_mayus for marcador in MARCADORES_FIN_MOVIMIENTOS):
            break

        if re.match(r"\d{1,2} \w{3}",movimiento):
            numero_movimiento += 1

        if numero_movimiento == 0:
            continue

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
    movimientos = movimientos.copy()
    montos_saldos = movimientos["movimiento"].astype(str).map(obtener_montos_movimiento)
    movimientos["Monto"] = montos_saldos.str[0].astype(str)
    movimientos["Saldo"] = montos_saldos.str[1].astype(str)
    return movimientos

def unificar_movimiento(df):
    df = df.copy()
    descripcion = ""
    for index,fila in df.iterrows():
        descripcion = descripcion + "|" + fila["movimiento"]
    moviemiento = {"Descripcion":descripcion,"Movimiento":df.iloc[0,1],"Monto":df.iloc[0,2],"Saldo":df.iloc[0,3]}
    return moviemiento

def unificar_tabla(movimmientos):
    if movimmientos.empty:
        return pd.DataFrame(columns=["Descripcion", "Movimiento", "Monto", "Saldo"])

    tabla = (
        movimmientos.groupby("numero_movimiento", sort=False)
        .agg(
            Descripcion=("movimiento", lambda serie: "|" + "|".join(serie.astype(str))),
            Monto=("Monto", "first"),
            Saldo=("Saldo", "first"),
        )
        .reset_index()
        .rename(columns={"numero_movimiento": "Movimiento"})
    )
    return tabla[["Descripcion", "Movimiento", "Monto", "Saldo"]]

def extraer_movimientos_estado_de_cuenta(estado):
    movimientos = []
    en_tabla = False

    for pag in estado.pages:
        texto_pagina = pag.extract_text_simple() or pag.extract_text() or ""
        movs = _extraer_movimientos_desde_texto(texto_pagina)
        if movs:
            en_tabla = True
            movimientos.extend(movs)
            continue

        if en_tabla:
            break

    return movimientos
    

def identificar_cargo_abono(df):
    df = df.copy()
    df["Cargos"] = ""
    df["Abonos"] = ""

    saldo = pd.to_numeric(df["Saldo"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    monto = pd.to_numeric(df["Monto"].astype(str).str.replace(",", "", regex=False), errors="coerce")

    saldo_anterior = saldo.shift(1)
    saldo_ideal = (saldo_anterior + monto).round(2)

    mask_base = saldo.notna() & saldo_anterior.notna() & monto.notna()
    mask_abono = mask_base & (saldo == saldo_ideal)
    mask_cargo = mask_base & ~mask_abono

    monto_txt = monto.abs().map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    df.loc[mask_abono, "Abonos"] = monto_txt[mask_abono]
    df.loc[mask_cargo, "Cargos"] = monto_txt[mask_cargo]

    mask_pendiente = (
        (df["Cargos"].astype(str).str.strip() == "")
        & (df["Abonos"].astype(str).str.strip() == "")
        & monto.notna()
    )

    descripcion_mayus = df["Descripcion"].fillna("").astype(str).str.upper()
    mask_claves_abono = descripcion_mayus.str.contains(r"DEPÓSITO|DEPOSITO|ABONO|RECIBIDO|ORDENANTE:", regex=True)
    mask_claves_cargo = descripcion_mayus.str.contains(r"ENVÍO|ENVIO|COMPRA|DISPOSICION|PAGO|COMISION|IVA|BENEFICIARIO:", regex=True)

    mask_fallback_cargo = mask_pendiente & ((monto < 0) | mask_claves_cargo | ~mask_claves_abono)
    mask_fallback_abono = mask_pendiente & ~mask_fallback_cargo

    df.loc[mask_fallback_abono, "Abonos"] = monto_txt[mask_fallback_abono]
    df.loc[mask_fallback_cargo, "Cargos"] = monto_txt[mask_fallback_cargo]

    return df

def separar_fecha(df):
    df = df.copy()
    descripcion = df["Descripcion"].fillna("").astype(str)
    fecha = descripcion.str.extract(r"(\d{1,2}\ \w{3})", expand=False)
    df["Fecha"] = fecha
    df["Descripcion"] = descripcion.str.replace(RE_FECHA_CORTA, "", n=1, regex=True)
    return df

def separar_referencia(df):
    df = df.copy()
    descripcion = df["Descripcion"].fillna("").astype(str)
    referencia = descripcion.str.extract(r"(\b\d{7,}\b)", expand=False)
    df["Referencia"] = referencia.fillna("-")
    df["Descripcion"] = descripcion.str.replace(RE_REFERENCIA, "", n=1, regex=True)
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
    import time
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    ruta_archivo = "/home/abelsr/Proyects/OCR-General/Scraping_Bancos_Mx/notebooks/2033_033620303_1_20260105114600.pdf"
    t0 = time.perf_counter_ns()
    tabla = Scrap_Estado(ruta_archivo)
    t1 = time.perf_counter_ns()
    console.print(f"Tiempo de procesamiento: {(t1 - t0) / 1e9:.2f} segundos")
    # Resumen de depositos y retiros (totales)
    depositos = tabla['deposito'].sum()
    retiros = tabla['retiro'].sum()
    console.print(f"Total de depósitos: ${depositos}")
    console.print(f"Total de retiros: ${retiros}")
    saldo_inicial = tabla['saldo'].iloc[0]
    saldo_final = tabla['saldo'].iloc[-1]
    console.print(f"Saldo inicial: ${saldo_inicial}")
    console.print(f"Saldo final: ${saldo_final}")
    tabla['descripcion'] = tabla['descripcion'].astype(str).str.slice(0, 120) + "..."
    
    # Convert DataFrame to Rich Table
    rich_table = Table(title="Estado de Cuenta")
    for column in tabla.columns:
        rich_table.add_column(column)
    
    for _, row in tabla.iterrows():
        rich_table.add_row(*[str(val) for val in row])
    
    console.print(rich_table)
    
    