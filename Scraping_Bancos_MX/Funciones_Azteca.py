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