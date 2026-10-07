import re

import pdfplumber
import numpy as np
import pandas as pd
from ._normalizacion import montos_cero

RE_SPEI = re.compile(r"SPEI")
RE_TRA_INT = re.compile(r"TRA|INT")
RE_IVA = re.compile(r"IVA")
RE_COMISION = re.compile(r"COMISION", re.IGNORECASE)
RE_COM = re.compile(r"COM\.")
RE_TRASPASO = re.compile(r"TRASPASO")
RE_RFC = re.compile(r"RFC")
RE_PAGE = re.compile(r"^\s*Page")
RE_FECHA = re.compile(r"\d{2}")
RE_NOSPACE = re.compile(r"\s+")
TABLE_SENTINEL = "DIACONCEPTOCARGOSABONOSSALDO"

@montos_cero
def Scrap_Estado_BanRegio(ruta_archivo, incluir_creditos=False):
    """Movimientos de las cuentas del estado de cuenta Banregio.

    incluir_creditos=True agrega ademas el detalle de movimientos de los
    creditos (ver Scrap_Creditos_BanRegio y docs/banregio_creditos.md). Por
    defecto esta apagado: son abonos al credito, no flujo de la cuenta."""
    with pdfplumber.open(ruta_archivo) as estado:
        tabla = analizar_estados(estado)
        creditos = extraer_creditos(estado) if incluir_creditos else None
    tabla = analisis_movimientos(tabla)
    tabla = formatear_tabla(tabla)
    if creditos is not None and not creditos.empty:
        tabla = pd.concat([tabla, creditos], ignore_index=True)
    return tabla


@montos_cero
def Scrap_Creditos_BanRegio(ruta_archivo):
    """Detalle de movimientos de los creditos (MiCredito Fijo, AutoRegio,
    Hipotecario...) de un estado de cuenta Banregio, con el esquema estandar
    (fecha, descripcion, deposito, retiro, saldo). 'deposito' = ABONO al
    credito, 'retiro' = CARGO. OJO: no es flujo de la cuenta; ver
    docs/banregio_creditos.md antes de sumarlo con los movimientos de cuenta."""
    with pdfplumber.open(ruta_archivo) as estado:
        return extraer_creditos(estado)


RE_MONTO = re.compile(r"^\(?-?[\d,]+\.\d{2}\)?$")
RE_PERIODO = re.compile(r"del\s+\d{1,2}\s+al\s+\d{1,2}\s+de\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)
RE_FECHA_AMORTI = re.compile(r"^(\d{1,2})-([a-z]{3})-(\d{2,4})$", re.IGNORECASE)
_MESES = {"ENERO": "ENE", "FEBRERO": "FEB", "MARZO": "MAR", "ABRIL": "ABR", "MAYO": "MAY", "JUNIO": "JUN",
          "JULIO": "JUL", "AGOSTO": "AGO", "SEPTIEMBRE": "SEP", "OCTUBRE": "OCT", "NOVIEMBRE": "NOV", "DICIEMBRE": "DIC"}
_MES_CORTO = {"ENE": "ENE", "FEB": "FEB", "MAR": "MAR", "ABR": "ABR", "MAY": "MAY", "JUN": "JUN",
              "JUL": "JUL", "AGO": "AGO", "SEP": "SEP", "OCT": "OCT", "NOV": "NOV", "DIC": "DIC"}


def extraer_creditos(estado):
    """Filas de las tablas de credito. Soporta los dos formatos del estado:
    'Detalle de Movimientos' (DIA CONCEPTO CARGOS ABONOS, p. ej. MiCredito
    Fijo) y 'DETALLE DE LOS ULTIMOS MOVIMIENTOS' (FECHA AMORTI. REFERENCIA
    CONCEPTO CARGO ABONO, p. ej. AutoRegio/Hipotecario). La tabla
    'REGIOCUENTA REGIOCREDITO' repite los movimientos de la cuenta y no se lee."""
    filas = []
    for pagina in estado.pages:
        lineas = {}
        palabras_pagina = pagina.extract_words()
        if not palabras_pagina:
            continue
        tops = _agrupar_tops(pd.Series([w["top"] for w in palabras_pagina]))
        for w, top in zip(palabras_pagina, tops):
            lineas.setdefault(top, []).append(w)
        tops = sorted(lineas)
        textos = {t: " ".join(w["text"] for w in sorted(lineas[t], key=lambda w: w["x0"])) for t in tops}
        periodo = RE_PERIODO.search(" ".join(textos.values()))
        mes_anio = (_MESES.get(periodo.group(1).upper()), periodo.group(2)) if periodo else (None, None)

        formato = None
        x_cargo = x_abono = None
        for t in tops:
            texto = textos[t]
            ws = sorted(lineas[t], key=lambda w: w["x0"])
            if re.match(r"^DIA CONCEPTO CARGOS ABONOS$", texto):
                formato, x_cargo, x_abono = "dia", *_x_cargo_abono(ws)
                continue
            if re.match(r"^FECHA AMORTI\. REFERENCIA CONCEPTO CARGO ABONO$", texto):
                formato, x_cargo, x_abono = "amorti", *_x_cargo_abono(ws)
                continue
            if formato is None:
                continue
            if texto.startswith("Total") or texto.startswith("*"):
                formato = None
                continue
            montos = [w for w in ws if RE_MONTO.match(w["text"])]
            if len(montos) != 1:
                continue
            monto = montos[0]
            palabras = [w["text"] for w in ws if w is not monto]
            if formato == "dia":
                if not (len(palabras) > 1 and re.match(r"^\d{1,2}$", palabras[0])) or mes_anio[0] is None:
                    continue
                fecha = f"{int(palabras[0]):02d}/{mes_anio[0]}/{mes_anio[1]}"
                descripcion = " ".join(palabras[1:])
            else:
                m = RE_FECHA_AMORTI.match(palabras[0]) if palabras else None
                if not m or m.group(2).upper() not in _MES_CORTO:
                    continue
                anio = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
                fecha = f"{int(m.group(1)):02d}/{m.group(2).upper()}/{anio}"
                descripcion = " ".join(palabras[1:])
            valor = float(monto["text"].strip("()").replace(",", ""))
            centro = (monto["x0"] + monto["x1"]) / 2
            es_abono = abs(centro - x_abono) < abs(centro - x_cargo)
            filas.append({"fecha": fecha, "descripcion": descripcion,
                          "deposito": valor if es_abono else None,
                          "retiro": None if es_abono else valor,
                          "saldo": None})
    return pd.DataFrame(filas, columns=["fecha", "descripcion", "deposito", "retiro", "saldo"])


def _x_cargo_abono(palabras):
    """Centros x de los encabezados CARGO(S) y ABONO(S) de la tabla."""
    centros = {}
    for w in palabras:
        if w["text"].upper().startswith("CARGO"):
            centros["cargo"] = (w["x0"] + w["x1"]) / 2
        elif w["text"].upper().startswith("ABONO"):
            centros["abono"] = (w["x0"] + w["x1"]) / 2
    return centros["cargo"], centros["abono"]
    

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
    # y colapsa espacios repetidos / recorta extremos
    df["descripcion"] = (
        df["descripcion"].astype(str)
        .str.replace("|", " ", regex=False)
        .str.replace(RE_NOSPACE, " ", regex=True)
        .str.strip()
    )

    for col in ["deposito", "retiro", "saldo"]:
        serie = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(serie.where(serie != ""), errors="coerce")

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
    en_tabla = False

    for pagina in estado.pages:
        caracteres = pagina.chars
        if not caracteres:
            if en_tabla:
                break
            continue

        texto = normalizar_texto_chars(caracteres)
        texto_fallback = None

        if TABLE_SENTINEL in texto:
            tiene_encabezado = True
        else:
            texto_fallback = RE_NOSPACE.sub("", pagina.extract_text_simple() or "")
            tiene_encabezado = TABLE_SENTINEL in texto_fallback
            if tiene_encabezado:
                texto = texto_fallback

        # Ultima hoja de cada producto: trae el encabezado de la tabla pero solo
        # el grafico/resumen, sin movimientos. No cierra la tabla: pueden seguir
        # las hojas de otro producto del mismo estado (otra cuenta, otro credito).
        contiene_tabla = (
            tiene_encabezado
            and "GráficoTransaccional" not in texto
            and "REGIOCUENTA" not in texto
        )

        if contiene_tabla:
            en_tabla = True
            movimientos = extraer_movimientos_pagina(caracteres, texto)
            movimientos_paginas.append(movimientos)
            continue

        if en_tabla and not tiene_encabezado:
            break

    if movimientos_paginas:
        df = pd.concat(movimientos_paginas, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["Fecha", "Concepto", "Origen", "Deposito", "Retiro", "Saldo", "Top"])
    df = df.reset_index(drop=True)
    df = unificar_variaciones_altura(df)
    df = incluir_movimientos(df)
    df = unificar_tabla(df)
    return df


def normalizar_texto_chars(caracteres):
    ordenados = sorted(caracteres, key=lambda c: (round(c.get("top", 0.0), 1), c.get("x0", c.get("x1", 0.0))))
    texto = "".join(c.get("text", "") for c in ordenados)
    return RE_NOSPACE.sub("", texto)



    

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


def extraer_movimientos_pagina(caracteres,texto):
    columnas = agrupar_columnas(caracteres)
    filas = unificar_columnas(columnas)
    filas = eliminar_movimientos_no_deseados(filas)
    incluir_anio_mes(filas,texto)
    return filas

def incluir_anio_mes(filas,texto):
    anios = {"ENERO":"ENE","FEBRERO":"FEB","MARZO":"MAR","ABRIL":"ABR","MAYO":"MAY","JUNIO":"JUN","JULIO":"JUL","AGOSTO":"AGO","SEPTIEMBRE":"SEP","OCTUBRE":"OCT","NOVIEMBRE":"NOV","DICIEMBRE":"DIC"}
    periodo = re.search(r"del\d{2}al\d{2}de\w+\d{4}",texto)
    if not periodo:
        return
    periodo = periodo.group(0).replace("del","")
    periodo = periodo.split("de")[1]
    anio = periodo[-4:]
    mes = periodo[:-4]
    mes = anios[mes.upper()]
    mask_fechas = filas["Fecha"].astype(str).str.match(RE_FECHA)
    filas.loc[mask_fechas, "Fecha"] = filas.loc[mask_fechas, "Fecha"] + "/" + mes + "/" + str(anio)




# Los caracteres de una misma linea visual pueden venir con 'top' distintos por
# ~1 pt (p. ej. 231.07 / 231.17 / 232.07); las lineas reales distan ~10 pt o mas.
TOLERANCIA_TOP = 2.0


def _agrupar_tops(tops):
    """Une los 'top' consecutivos que distan <= TOLERANCIA_TOP en un mismo valor
    (el menor del grupo), para que cada linea visual quede en una sola fila."""
    unicos = np.sort(tops.round(4).unique())
    if len(unicos) == 0:
        return tops
    grupo = np.concatenate([[0], np.cumsum(np.diff(unicos) > TOLERANCIA_TOP)])
    inicio_grupo = pd.Series(unicos).groupby(grupo).transform("min").to_numpy()
    return tops.round(4).map(dict(zip(unicos, inicio_grupo)))


def agrupar_columnas(caracteres):
    if not caracteres:
        return pd.DataFrame(columns=["Caracter", "Top", "X", "Columna"])

    columnas = pd.DataFrame(caracteres)[["text", "top", "x1"]].rename(columns={"text": "Caracter", "top": "Top", "x1": "X"})
    columnas["Top"] = _agrupar_tops(columnas["Top"])

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
        # El estado imprime CARGOS (x1 <= 420) antes que ABONOS: cargo = retiro, abono = depósito
        elif row["Columna"] == 2:
            retiro = retiro + row["Caracter"]
        elif row["Columna"] == 3:
            deposito = deposito + row["Caracter"]
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
            # CARGOS (col 2) = retiro, ABONOS (col 3) = depósito
            "Deposito": pivot.get(3, ""),
            "Retiro": pivot.get(2, ""),
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
