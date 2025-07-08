import re
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Pattern
import pandas as pd

@dataclass
class MovimientoHSBC:
    fecha: str
    detalles: str
    retiros: float
    abonos: float
    saldo: float

class ParserHSBC:
    """Parser específico para extracto HSBC delimitado por 'Abono Saldo' y 'CoDI'."""

    P1: Pattern = re.compile(r'Abono\s+Saldo', flags=re.IGNORECASE)
    P2: Pattern = re.compile(r'CoDI', flags=re.IGNORECASE)
    P3: Pattern = re.compile(r'(\d{2}\s+[A-Z]+\s+.*?\n\d{8}\n\$\s?[0-9,]+\.[0-9]{1,2}\n\$\s?[0-9,]+\.[0-9]{1,2})', flags=re.DOTALL)
    P4: Pattern = re.compile(r"(?<!\d)([1-9]\d{0,2}(?:[.,]\d{3})*\.[0-9]{2})(?!\d)")
    P5: Pattern = re.compile(r'\s\d{2}\s')

    def __init__(self, texto: str):
        self.texto = texto

    def clean_section(self) -> str:
        i1 = self.P1.search(self.texto).end()
        i2 = self.P2.search(self.texto).start()
        section = self.texto[i1:i2].replace('. ', '.')
        return section

    def split_movimientos(self, section: str) -> List[str]:
        parts = re.split(self.P3, section)
        return [p.strip() for p in parts if p and p.strip()]

    def to_dataframe(self) -> pd.DataFrame:
        sec = self.clean_section()
        bloques = self.split_movimientos(sec)
        rows = []
        prev_saldo = 0

        for b in bloques:
            det = b.replace('\n', ' ').replace(', ', ',')
            nums = self.P4.findall(det)
            if not nums:
                continue

            fechas = self.P5.findall(det)
            fecha = fechas[0].strip() if fechas else det[:2]
            fecha = fecha if not prev_saldo or int(fecha) - int(prev_saldo) <= 3 else str(prev_saldo)

            movs = nums if len(nums) == 2 else [nums[0], None]
            abono = float(movs[0].replace(',', ''))
            saldo = float(movs[1].replace(',', '')) if movs[1] else prev_saldo
            signo = 1 if saldo >= prev_saldo else -1

            valor = signo * abono
            retiro = min(0, valor)
            deposito = max(0, valor)
            prev_saldo = saldo

            rows.append(MovimientoHSBC(fecha, det, -retiro, deposito, saldo))

        df = pd.DataFrame([asdict(r) for r in rows])
        return df[['fecha', 'detalles', 'retiros', 'abonos', 'saldo']]