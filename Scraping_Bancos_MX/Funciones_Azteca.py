import re
import pdfplumber
import pandas as pd

def Scrap_Estado(ruta_archivo):
    df = procesar_pdf(ruta_archivo)
    return df


def es_linea_movimiento(linea):
    """
    Determina si la línea inicia un 'movimiento' nuevo
    en formato 'dd/mm/aaaa' en 3 tokens separados:
    - tokens[0] = día (2 dígitos)
    - tokens[1] = mes (2 dígitos)
    - tokens[2] = año (4 dígitos)
    """
    tokens = linea.split()[0].split('/')
    if len(tokens) < 3:
        return False

    # Verificar si tokens[0] es dd y tokens[1] es mm y tokens[2] es aaaa
    if not re.match(r'^\d{1,2}$', tokens[0]):
        return False
    if not re.match(r'^\d{1,2}$', tokens[1]):
        return False
    if not re.match(r'^\d{4}$', tokens[2]):
        return False
    return True

def parse_linea_movimiento(linea):
    fecha = linea.split()[0]
    linea = linea.replace(fecha, '')
    
    # patron para extraer el monto algo similar a (+) $50,000.00
    pattern = r'\(\s*(?P<sign>[+-])\s*\)\s*\$\s*(?P<amount>(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{2})?)'
    match = re.search(pattern, linea)
    
    # Quitael match de la linea
    linea = linea.replace(match.group(0), '')
    
    if match:
        sign = match.group('sign')
        amount = match.group('amount')
        amount = amount.replace(',', '')
        amount = float(amount)
        if sign == '+':
            monto = amount
        else:
            monto = -amount
    else: 
        monto = None
    
    return fecha, monto, linea

def procesar_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        movimientos = []
        for i, page in enumerate(pdf.pages):
            for line in page.extract_text().split('\n'):
                if es_linea_movimiento(line):
                    fecha, monto, linea = parse_linea_movimiento(line)
                    movimientos.append({
                        "Fecha": fecha,
                        "Descripcion": linea,
                        "Monto": monto
                    })
        if len(movimientos) == 0:
            raise Exception("Could not extract data from pdf")
        df = pd.DataFrame(movimientos)
        df["Retiro"] = df["Monto"].apply(lambda x: x if x < 0 else None)
        df["Deposito"] = df["Monto"].apply(lambda x: x if x > 0 else None)
        df["Saldo"] = [None] * len(df)
        df = df[["Fecha", "Descripcion", "Deposito", "Retiro", "Saldo"]]
        return df
    

import re
from typing import List, Dict, Optional
import pandas as pd

class BancoAztecaStatementParser:
    """
    Parser de estados de cuenta basado en bloques delimitados por fechas (dd/mm/yyyy).
    
    Uso:
        parser = BancoAztecaStatementParser()
        df = parser.parse(render_text)
    """

    # Compilamos los patrones para rendimiento
    DATE_PATTERN = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')  # dd/mm/yyyy
    # patrón de monto: ( + | - )  y luego $12,311.31
    MONEY_PATTERN = re.compile(r'\(([+-]?)\)\s*(\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
    # patrón para encontrar la posición del signo (inicia el bloque de monto)
    SIGN_PATTERN = re.compile(r'\([+-]?\)\s*')

    def __init__(self):
        pass

    def parse(self, render_text: str) -> pd.DataFrame:
        """
        Parsea el texto completo `render_text` y retorna un DataFrame con:
        [fecha, descripcion, deposito, retiro]
        """
        matches = list(self.DATE_PATTERN.finditer(render_text))
        data: List[Dict[str, Optional[float]]] = []

        if not matches:
            # Si no hay fechas, devolvemos DF vacío consistente.
            return pd.DataFrame(columns=["fecha", "descripcion", "deposito", "retiro"])

        # Recorremos los bloques de fecha a fecha (o hasta el final)
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(render_text)
            block = render_text[start:end].strip()

            fecha_str = match.group(0)  # "dd/mm/yyyy"

            # Buscamos monto y signo dentro del bloque
            monto_match = self.MONEY_PATTERN.search(block)
            if not monto_match:
                # Si no hay monto conforme al patrón, saltamos este bloque
                continue

            sign = (monto_match.group(1) or "").strip()  # '+' o '-' o ''
            monto_str = monto_match.group(2)            # '$12,311.31'

            # Para la descripción: desde el final de la fecha hasta el inicio del signo
            sign_pos = self.SIGN_PATTERN.search(block)
            if not sign_pos:
                # Si no encontramos el signo, no podemos delimitar la descripción de forma segura
                continue

            # La fecha está al principio del bloque; usamos el span de la ocurrencia de fecha dentro del bloque
            # Para eso, localizamos la fecha *dentro* del bloque:
            # Nota: como el bloque empieza en start, la fecha del bloque comienza en 0
            date_in_block = self.DATE_PATTERN.search(block)
            if not date_in_block:
                continue

            desc_start = date_in_block.end()  # justo después de la fecha
            desc_end = sign_pos.start()
            descripcion = block[desc_start:desc_end].replace('\n', ' ').strip()

            # Normalizamos el monto: "$12,311.31" -> 12311.31
            monto_val = self._money_to_float(monto_str)

            deposito = None
            retiro = None
            if sign == '-':
                retiro = monto_val
            elif sign == '+':
                deposito = monto_val
            else:
                # Si no hay signo claro, no etiquetamos como retiro/deposito
                # (podrías decidir aquí una política distinta)
                continue

            data.append({
                "fecha": fecha_str,
                "descripcion": descripcion,
                "deposito": deposito,
                "retiro": retiro,
            })

        df = pd.DataFrame(data, columns=["fecha", "descripcion", "deposito", "retiro"])
        return df

    @staticmethod
    def _money_to_float(money_str: str) -> float:
        """
        Convierte una cadena tipo '$12,311.31' en float 12311.31.
        Asume separador decimal '.' y miles ','.
        """
        normalized = money_str.replace("$", "").replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            # fallback defensivo
            return float('nan')
