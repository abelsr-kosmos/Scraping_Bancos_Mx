"""
Interfaz común para los parsers de estados de cuenta.

BankStatementParser no reemplaza la lógica de extracción de cada banco
(las funciones/clases en Funciones_<Banco>.py siguen siendo la fuente de
verdad, y son las que corren en el benchmark de precisión); solo la envuelve
bajo un contrato uniforme .parse(pdf_path) -> DataFrame para quien prefiera
programar contra una interfaz común en vez de importar una función distinta
por banco.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Sequence, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .models import EstadoCuenta


class BankStatementParser(ABC):
    """Clase base abstracta para todos los parsers de estados de cuenta."""

    #: Nombre del banco (debe coincidir con la llave usada en PARSERS).
    banco: ClassVar[str]

    #: Columnas mínimas que debe tener el DataFrame de salida (ver README).
    REQUIRED_COLUMNS: ClassVar[Sequence[str]] = ("fecha", "descripcion", "deposito", "retiro", "saldo")

    @abstractmethod
    def parse(self, pdf_path: str) -> pd.DataFrame:
        """Extrae los movimientos del PDF en `pdf_path`."""
        raise NotImplementedError

    def parse_validado(self, pdf_path: str) -> pd.DataFrame:
        """Como parse(), pero valida que el DataFrame tenga REQUIRED_COLUMNS.

        Útil para detectar en el momento si un parser dejó de producir el
        esquema esperado (el bug que __init__.py tenía con varios bancos).
        """
        df = self.parse(pdf_path)
        faltantes = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if faltantes:
            raise ValueError(f"{self.banco}: el DataFrame no tiene las columnas requeridas {faltantes}")
        return df

    def to_estado_cuenta(self, pdf_path: str) -> "EstadoCuenta":
        """Como parse_validado(), pero regresa un EstadoCuenta tipado."""
        from .models import EstadoCuenta

        df = self.parse_validado(pdf_path)
        return EstadoCuenta.from_dataframe(self.banco, df)
