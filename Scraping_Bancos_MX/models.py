"""
Modelos de datos de entrada/salida para Scraping_Bancos_MX.

Estos modelos son una capa opcional por encima de las funciones/clases
Scrap_Estado_<Banco> ya existentes: no cambian lo que esas funciones hacen,
solo dan una representación tipada del resultado para quien la prefiera a
un DataFrame "suelto".
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from typing import List, Optional

import pandas as pd


@dataclass
class Movimiento:
    """Un movimiento (fila) del esquema estándar documentado en el README:
    fecha, descripcion, deposito, retiro, saldo, + columnas opcionales que
    algunos bancos agregan (concepto, origen, contraparte, etc.)."""

    fecha: str
    descripcion: str
    deposito: Optional[float] = None
    retiro: Optional[float] = None
    saldo: Optional[float] = None
    concepto: Optional[str] = None
    origen: Optional[str] = None
    contraparte: Optional[str] = None
    institucion_contraparte: Optional[str] = None
    tipo_movimiento: Optional[str] = None

    @classmethod
    def from_row(cls, row: "pd.Series") -> "Movimiento":
        """Construye un Movimiento a partir de una fila de DataFrame,
        ignorando columnas que el modelo no conoce y normalizando NaN a None."""
        campos_conocidos = {f.name for f in fields(cls)}
        kwargs = {
            nombre: (None if pd.isna(valor) else valor)
            for nombre, valor in row.to_dict().items()
            if nombre in campos_conocidos
        }
        return cls(**kwargs)


@dataclass
class EstadoCuenta:
    """Estado de cuenta completo: banco + lista de movimientos."""

    banco: str
    movimientos: List[Movimiento] = field(default_factory=list)

    @classmethod
    def from_dataframe(cls, banco: str, df: pd.DataFrame) -> "EstadoCuenta":
        return cls(banco=banco, movimientos=[Movimiento.from_row(fila) for _, fila in df.iterrows()])

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(m) for m in self.movimientos])

    @property
    def total_depositos(self) -> float:
        return sum(m.deposito or 0.0 for m in self.movimientos)

    @property
    def total_retiros(self) -> float:
        return sum(m.retiro or 0.0 for m in self.movimientos)

    def __len__(self) -> int:
        return len(self.movimientos)
