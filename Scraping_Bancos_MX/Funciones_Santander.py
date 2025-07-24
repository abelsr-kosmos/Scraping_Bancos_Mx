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
        if re.search("CONCEPTOADM",row["Concepto"]):
            concepto = row["Concepto"].split("CONCEPTOADM")[1]
            
        df.loc[index,"ConceptoMovimiento"] = concepto

    return df

def analisis_institucion_contraparte(df):
    df["InstitucionContraparte"] = ""
    for index,row in df.iterrows():
        banco = "-"
        if re.search("SPEI",row["Concepto"]):
            try:
                banco = row["Concepto"].split("ENVIADOA")[1]
            except:
                banco = row["Concepto"].split("RECIBIDODE")[1]
            banco = banco.split("|")[0]
        df.loc[index,"InstitucionContraparte"] = banco
    return df

def analisis_contraparte(df):
    df["Contraparte"] = ""
    for index,row in df.iterrows():
        destinatario = "-"
        if re.search("SPEI",row["Concepto"]):
            destinatario = row["Concepto"].split("LCLIENTE")[1]
            
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
        if re.search("FECHAFOLIODESCRIPCIONDEPOSITOSRETIROSSALDO", texto) :
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
    columnas = []
    for caracter in caracteres:
        coordenada = (caracter["x1"])
        if coordenada <= 61 and coordenada >= 16:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 0})
        elif coordenada <= 96  and coordenada > 68:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 1})
        elif coordenada <= 326  and coordenada > 96:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 2})
        elif coordenada <= 415  and coordenada > 326:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 3})
        elif coordenada <= 495  and coordenada > 415:
            columnas.append({"Caracter": caracter["text"], "Top": caracter["top"],"X":caracter["x1"],"Columna": 4})
        elif coordenada <= 577  and coordenada > 495:
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
                
    for index,row in filas.iterrows():
        if index > 0:
            if row["Concepto"] == "SALDOFINALDELPERIODOANTERIOR":
                filas = filas.drop(index)
    return filas


def incluir_movimientos(df):
    df = df.reset_index(drop=True)
    df["Movimiento"] = 0
    contador_movimiento = 0
    for index, fila in df.iterrows():
        if  re.match("\d{2}-\w{3}-\d{4}", fila["Fecha"]):
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
DATE_FOLIO_PATTERN = re.compile(r"^\s*\(?(?P<fecha>\d{2}-[A-Za-z]{3}-\d{4})\)?\s+(?P<folio>\d{7})", flags=re.IGNORECASE)
MONEY_PATTERN = re.compile(r"(?P<monto>\d{1,3}(?:[.,]\d{3})*[.,]\d{2})")

@dataclass
class Transaccion:
    fecha: str
    folio: str
    descripcion: str
    monto: float
    saldo: float

class ParserTransacciones:
    """
    Parser para extraer transacciones de un texto crudo.
    """

    def __init__(self, texto: str, ocr: dict | None = None):
        self.texto = texto
        self.ocr = ocr
        if ocr:
            self.flattened_ocr = self.flatten_doctr_ocr(ocr)

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

    def parsear_grupo(self, grupo: str, first_movement: bool) -> Optional[Transaccion]:
        """Extrae los campos de un grupo de texto."""
        montos = MONEY_PATTERN.findall(grupo)
        if len(montos) < 2:
            logger.warning("Grupo con menos de 2 montos omitido")
            return None

        # Encuentra fecha y folio
        encabezado = grupo.replace('(', '').replace(')', '')
        coincidencia = DATE_FOLIO_PATTERN.search(encabezado)
        if not coincidencia:
            logger.error("No se encontró fecha/folio en grupo")
            return None

        fecha = coincidencia.group('fecha')
        folio = coincidencia.group('folio')

        # Montos
        monto_str, saldo_str = montos[0], montos[1]
        monto = self._normalizar_monto(monto_str)
        saldo = self._normalizar_monto(saldo_str)

        # Descripción: texto entre folio y primer monto
        inicio = coincidencia.end()
        descripcion = grupo[inicio:].split(monto_str)[0].strip().replace('\n', ' ')
        
        # Asignar signo al monto
        if first_movement and self.flattened_ocr is not None:
            word_data = self.flattened_ocr[self.flattened_ocr['word'] == monto_str]
            if (word_data.geometry.values[0][0] + word_data.geometry.values[0][2])/2 > 0.76:
                monto = -monto
            else:
                monto = monto

        return Transaccion(
            fecha=fecha,
            folio=folio,
            descripcion=descripcion,
            monto=monto,
            saldo=saldo
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Devuelve un DataFrame con todas las transacciones parseadas."""
        grupos = self.separar_grupos()
        first_movement = True
        transacciones = []
        for grupo in grupos:
            transacciones.append(self.parsear_grupo(grupo, first_movement))
            first_movement = False
        registros = [asdict(t) for t in transacciones if t]
        df = pd.DataFrame(registros)

        # Cálculo de depósitos y retiros
        df['saldo_previo'] = df['saldo'].shift(1)
        df['delta_saldo'] = df['saldo'] - df['saldo_previo']
        df['monto_signado'] = df['monto'] * df['delta_saldo'].apply(lambda x: -1 if x < 0 else 1)
        df['deposito'] = df['monto_signado'].clip(lower=0)
        df['retiro'] = (-df['monto_signado']).clip(lower=0)
        # Unir folio y descripcion en una sola columna
        df['descripcion'] = df['folio'].astype(str) + ' ' + df['descripcion'].str.replace('\n', ' ')
        # Eliminar col de folio
        df = df.drop(columns=['folio'])

        # Selección y renombrado de columnas finales en español
        df_final = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
        return df_final
    
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