"""
Utilidades internas compartidas entre módulos Funciones_<Banco>.py.

No es parte del API público del paquete (por eso el nombre empieza con "_":
`from Scraping_Bancos_MX import *` no lo trae).
"""

import functools

import pandas as pd

COLUMNAS_ESTANDAR = ["fecha", "descripcion", "deposito", "retiro", "saldo"]


def normalizar_columnas_estandar(df: pd.DataFrame, columna_concepto: str = "concepto") -> pd.DataFrame:
    """Baja a minúsculas, renombra `columna_concepto` -> 'descripcion',
    convierte deposito/retiro/saldo a numérico y deja las columnas del
    esquema estándar primero (seguidas de cualquier columna extra que el
    banco haya agregado, p. ej. contraparte/tipo_movimiento).

    Usada por los bancos cuyo pipeline construye la tabla con columnas
    capitalizadas al estilo Fecha/Concepto/Origen/Deposito/Retiro/Saldo
    (Afirme, HeyBanco, Inbursa, Santander) para llegar al mismo esquema de
    salida que el resto de la librería.
    """
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df = df.rename(columns={columna_concepto: "descripcion"})
    for col in ("deposito", "retiro", "saldo"):
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
    columnas_extra = [c for c in df.columns if c not in COLUMNAS_ESTANDAR]
    return df[COLUMNAS_ESTANDAR + columnas_extra]


def montos_cero(func):
    """Decorador para los puntos de entrada que regresan un DataFrame:
    reemplaza los nulos de las columnas de retiros y depósitos ('retiro'/
    'deposito', o 'retiros'/'depositos'/'abonos' en los esquemas que las
    nombran así) por 0.0. Los demás valores no se tocan."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        df = func(*args, **kwargs)
        if isinstance(df, pd.DataFrame):
            for col in ("retiro", "retiros", "deposito", "depositos", "abonos"):
                if col in df.columns:
                    df[col] = df[col].fillna(0.0)
        return df

    return wrapper
