import pandas as pd
import re
import pdfplumber

from ._normalizacion import normalizar_columnas_estandar, montos_cero

@montos_cero
def Scrap_Estado_Santander(ruta_archivo):
    estado = pdfplumber.open(ruta_archivo)
    tabla = analizar_estados(estado)
    tabla2 = analisis_movimientos(tabla)
    tabla2["descripcion"] = tabla2["descripcion"].map(limpiar_descripcion)
    return tabla2

def limpiar_descripcion(texto):
    """Descripción final en una sola línea: las líneas del movimiento vienen
    unidas con '|' y el folio pegado a la descripción ('|0000000COMISION...');
    se separa el folio con un espacio, '|' pasa a espacio y se colapsan
    espacios repetidos."""
    texto = re.sub(r"^[\s|]*(\d{7})(?=[^\d\s|])", r"\1 ", str(texto))
    return " ".join(texto.replace("|", " ").split())

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
    return normalizar_columnas_estandar(df)

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
            if "ENVIADOA" in row["Concepto"]:
                banco = row["Concepto"].split("ENVIADOA")[1].split("|")[0]
            elif "RECIBIDODE" in row["Concepto"]:
                banco = row["Concepto"].split("RECIBIDODE")[1].split("|")[0]
        df.loc[index,"InstitucionContraparte"] = banco
    return df

def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        destinatario = "-"
        if re.search("SPEI",row["Concepto"]) and "AL CLIENTE" in row["Concepto"]:
            destinatario = row["Concepto"].split("AL CLIENTE")[1]

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
        if re.search("FECHAFOLIODESCRIPCIONDEPOSITOS?RETIROS?SALDO", texto) :
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
    # Límites de columna (x1) calibrados contra estados reales: Fecha
    # "DD-MES-AAAA" siempre termina en x1<=78.5; Folio+Descripcion vienen
    # pegados sin espacio ("0000000COMISION...") así que se tratan como un
    # solo campo (columna 2); Deposito/Retiro/Saldo son columnas justificadas
    # a la derecha con ancho fijo (394-430 / 462-497 / 542-581 respectivamente
    # en los estados usados para calibrar), con margen de sobra entre cada una.
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 80 and coordenada >= 16:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 388  and coordenada > 80:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 440  and coordenada > 388:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 515  and coordenada > 440:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 590  and coordenada > 515:
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
            elif "SALDOFINALDELPERIODO" in row["Concepto"] and "ANTERIOR" not in row["Concepto"]:
                # Cierra la tabla de esta página ("SALDO FINAL DEL PERIODO:",
                # el saldo de cierre, no el de apertura). Corta antes de esta
                # fila para no arrastrar el pie de página / firma digital del
                # CFDI hacia la descripción del último movimiento real.
                filas = filas[filas["Top"] < row["Top"]]
            elif len(row["Concepto"]) > 150 and row["Concepto"].count(" ") < 5:
                # Bloque de sello/cadena digital del CFDI: una sola cadena
                # larga sin espacios que no es texto de ningún movimiento (una
                # descripción larga pero con palabras sí se conserva).
                filas = filas[filas["Top"] < row["Top"]]

    for index,row in filas.iterrows():
        if index > 0:
            if "SALDOFINALDELPERIODOANTERIOR" in row["Concepto"]:
                # Saldo de apertura del periodo: no es un movimiento en sí,
                # solo se descarta esta fila (las siguientes sí son reales).
                filas = filas.drop(index)
    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match(r"\d{2}-\w{3}-\d{4}", fila["Fecha"]):
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


import re
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import pandas as pd

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Constantes y regex compilados
# El render/OCR mete ruido entre fecha y folio ("|", "/", "(", "}") y a veces
# confunde 0 con O, por eso se toleran separadores (incluido '_', p. ej.
# "06-ENE-2025_9331569") y se normaliza después.
SEP = r"[\s|/\\(){}\[\]!,._':;-]*"
DATE_FOLIO_PATTERN = re.compile(
    rf"^\s*[(|/]?\s*(?P<fecha>[\dO]{{2}}-[A-Za-z0]{{3}}-\d{{4}}){SEP}(?P<folio>[\dO]{{7,9}})(?!\d)",
    flags=re.IGNORECASE,
)
MONEY_PATTERN = re.compile(r"(?P<monto>\d{1,3}(?:[.,]\d{3})*[.,]\d{2})")
# Línea que es solo un monto (el render pone retiro/depósito y saldo en líneas aparte)
MONEY_LINE_PATTERN = re.compile(r"^\W*(?P<monto>\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\W*$")
SALDO_ANTERIOR_PATTERN = re.compile(
    r"SALDO\s*FINAL\s*DEL\s*PERIODO\s*ANTERIOR\D{0,80}?(?P<saldo>\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    flags=re.IGNORECASE,
)
ABONO_PATTERN = re.compile(r"\b(ABONO|DEPOSITO|DEPOSITOI|CASHBACK)", flags=re.IGNORECASE)
# Líneas que ya no son detalle del movimiento (pie de página, encabezado de la
# siguiente hoja, totales, sello digital): al encontrar una se corta el detalle.
FIN_DETALLE_PATTERN = re.compile(
    r"BANCO\s*SANTANDER|SALDO\s*FINAL|^\W*TOTAL\b|FECHA\W+FOLIO|ESTADO\s*DE\s*CUENTA|"
    r"CADENA\s*ORIGINAL|SELLO|FOLIO\s*FISCAL|CFDI|COMUNIQUE|P[AÁ]GINA|HOJA\s*\d|"
    r"CARGOS\s*OBJETADOS|\bRFC\s*:?\s*BSM",
    flags=re.IGNORECASE,
)

@dataclass
class Transaccion:
    fecha: str
    folio: str
    descripcion: str
    monto: float
    saldo: Optional[float]
    detalle: str = ""

class ParserTransacciones:
    """
    Parser para extraer transacciones de un texto crudo.
    """

    def __init__(self, texto: str, ocr: dict | None = None):
        self.texto = texto
        self.ocr = ocr
        self.flattened_ocr = self.flatten_doctr_ocr(ocr) if ocr else None

    def separar_grupos(self) -> List[str]:
        """Divide el texto en grupos iniciando en líneas fecha-folio."""
        grupos, actual = [], []
        for linea in self.texto.splitlines():
            if DATE_FOLIO_PATTERN.match(linea):
                if actual:
                    grupos.append("\n".join(actual))
                actual = [linea]
            elif actual:
                actual.append(linea)
        if actual:
            grupos.append("\n".join(actual))
        logger.debug("Divididos en %d grupos", len(grupos))
        return grupos

    @staticmethod
    def _normalizar_monto(cadena: str) -> float:
        """Convierte '1.234.567,89' o '1,234,567.89' a float 1234567.89"""
        limpio = re.sub(r"[.,](?=\d{3})", "", cadena)
        if "," in limpio and "." not in limpio:
            limpio = limpio.replace(',', '.')
        return float(limpio)

    def saldo_anterior(self) -> Optional[float]:
        """Saldo de apertura impreso ('SALDO FINAL DEL PERIODO ANTERIOR: $1,037.11')."""
        m = SALDO_ANTERIOR_PATTERN.search(self.texto.replace('\n', ' '))
        return self._normalizar_monto(m.group('saldo')) if m else None

    def parsear_grupo(self, grupo: str, first_movement: bool) -> Optional[Transaccion]:
        """Extrae los campos de un grupo de texto.

        `monto` regresa positivo; el signo (depósito/retiro) lo resuelve
        to_dataframe contra el saldo corrido. `saldo` es None si el render
        dañó ese monto (se reconstruye después).
        """
        encabezado = grupo.replace('(', '').replace(')', '')
        coincidencia = DATE_FOLIO_PATTERN.search(encabezado)
        if not coincidencia:
            logger.error("No se encontró fecha/folio en grupo")
            return None

        dd, mes, anio = coincidencia.group('fecha').upper().split('-')
        fecha = f"{dd.replace('O', '0')}/{mes.replace('0', 'O')}/{anio}"
        folio = coincidencia.group('folio').upper().replace('O', '0')

        # Los montos van en la primera línea (texto de pdftotext) o en las líneas
        # siguientes que son solo un monto (render del GPU); las líneas de detalle
        # (cuenta, rastreo, pie de página) no deben aportar montos.
        lineas = encabezado.splitlines()
        primera = lineas[0][coincidencia.end():]
        montos = MONEY_PATTERN.findall(primera)
        inicio_detalle = 1
        for linea in lineas[1:]:
            if len(montos) >= 2:
                break
            m = MONEY_LINE_PATTERN.match(linea)
            if not m:
                break
            montos.append(m.group('monto'))
            inicio_detalle += 1
        if not montos:
            logger.warning("Grupo sin montos omitido")
            return None

        monto_str = montos[0]
        monto = self._normalizar_monto(monto_str)
        saldo = self._normalizar_monto(montos[1]) if len(montos) > 1 else None

        # Descripción: texto entre folio y primer monto de la primera línea
        descripcion = primera.split(monto_str)[0]
        descripcion = descripcion.strip(' |/}{!').replace('\n', ' ').strip()
        # Detalle de las líneas siguientes (cuenta, rastreo, concepto de pago...)
        # hasta el pie de página o la siguiente hoja; se omiten las líneas que
        # son solo un monto y las cadenas largas sin espacios (sello digital).
        detalle = []
        for linea in lineas[inicio_detalle:]:
            if FIN_DETALLE_PATTERN.search(linea):
                break
            if MONEY_LINE_PATTERN.match(linea):
                continue
            linea = linea.replace('|', ' ').strip(' /}{!')
            if len(linea) > 100 and ' ' not in linea:
                break
            if linea:
                detalle.append(linea)
        return Transaccion(fecha=fecha, folio=folio, descripcion=descripcion, monto=monto, saldo=saldo,
                           detalle=' '.join(detalle))

    def to_dataframe(self) -> pd.DataFrame:
        """Devuelve un DataFrame con todas las transacciones parseadas."""
        grupos = self.separar_grupos()
        transacciones = [t for t in (self.parsear_grupo(g, i == 0) for i, g in enumerate(grupos)) if t]

        prev = self.saldo_anterior()
        registros = []
        for t in transacciones:
            signo = None
            if t.saldo is not None and prev is not None:
                if abs(prev + t.monto - t.saldo) < 0.005:
                    signo = 1
                elif abs(prev - t.monto - t.saldo) < 0.005:
                    signo = -1
            saldo = t.saldo
            if signo is None:
                # Sin saldo previo, saldo ilegible o que no cuadra: se decide por texto
                # y, si hay saldo previo, el saldo se reconstruye con la cadena.
                if prev is None and t.saldo is not None:
                    signo = 1 if ABONO_PATTERN.search(t.descripcion) else -1
                else:
                    signo = 1 if ABONO_PATTERN.search(t.descripcion) else -1
                    if prev is not None:
                        if saldo is not None:
                            logger.warning("Saldo no cuadra en %s %s (previo=%s, monto=%s, saldo=%s)",
                                           t.fecha, t.folio, prev, t.monto, t.saldo)
                        saldo = round(prev + signo * t.monto, 2)
                if saldo is None:
                    saldo = round((prev or 0.0) + signo * t.monto, 2)
            registros.append({
                'fecha': t.fecha,
                'descripcion': " ".join(f"{t.folio} {t.descripcion} {t.detalle}".replace('|', ' ').split()),
                'deposito': t.monto if signo > 0 else 0.0,
                'retiro': t.monto if signo < 0 else 0.0,
                'saldo': saldo,
            })
            prev = saldo
        return pd.DataFrame(registros, columns=['fecha', 'descripcion', 'deposito', 'retiro', 'saldo'])

    def flatten_doctr_ocr(self, doctr_ocr: dict) -> dict:
        words = []
        for page in doctr_ocr:
            for item in page['items']:
                for block in item['blocks']:
                    for line in block['lines']:
                        for word in line['words']:
                            words.append((word['value'], word['geometry']))
                            
        words = pd.DataFrame(words, columns=['word', 'geometry'])
        return words