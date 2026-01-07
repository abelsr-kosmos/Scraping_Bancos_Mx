import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import pdfplumber
import pandas as pd


@dataclass
class EstadoCuentaMovimientosExtractor:
    """
    Extrae movimientos de un estado de cuenta PDF a partir de un 'checkpoint'
    y patrones regex para fecha, comisión (fin de bloque), dinero y hora.
    """
    checkpoint: str = "DETALLE DE MOVIMIENTOS Período"

    # Patrones por defecto (puedes sobreescribir al instanciar)
    date_pattern: str = r"\d{2}/[a-zA-Z]{3}/\d{4}"
    comision_pattern: str = r"Comisión\s+\d+\.\d{2}"
    money_pattern: str = r"[+-]\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?"
    time_pattern: str = r"\d{2}:\d{2}:\d{2}"

    # Opcional: normalizar espacios en descripción
    collapse_spaces: bool = True

    def read_pdf_text(self, pdf_path: str) -> List[str]:
        """Lee el PDF y regresa una lista con el texto de cada página."""
        all_text: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""  # evitar None
                all_text.append(text)
        return all_text

    def find_checkpoints(self, all_text: List[str]) -> List[Tuple[int, int, int]]:
        """
        Encuentra ocurrencias del checkpoint.
        Regresa lista de tuplas: (page_index, start, end)
        """
        matches: List[Tuple[int, int, int]] = []
        for page_idx, page_text in enumerate(all_text):
            for m in re.finditer(re.escape(self.checkpoint), page_text):
                matches.append((page_idx, m.start(), m.end()))
        return matches

    def _clean_description(self, transaction_text: str) -> str:
        """Remueve fecha, dinero y hora; deja descripción limpia."""
        desc = transaction_text
        desc = re.sub(self.date_pattern, "", desc)
        desc = re.sub(self.money_pattern, "", desc)
        desc = re.sub(self.time_pattern, "", desc)
        desc = desc.strip()

        if self.collapse_spaces:
            desc = re.sub(r"\s+", " ", desc)

        return desc

    def extract_movimientos(self, all_text: List[str]) -> List[Dict[str, Optional[str]]]:
        """
        Extrae movimientos como lista de dicts:
        {'date','time','description','money'}
        """
        movimientos: List[Dict[str, Optional[str]]] = []

        for page_text in all_text:
            if self.checkpoint not in page_text:
                continue

            date_matches = list(re.finditer(self.date_pattern, page_text))
            comision_matches = list(re.finditer(self.comision_pattern, page_text))

            # Empareja por orden (como en tu código)
            for d_match, c_match in zip(date_matches, comision_matches):
                block = page_text[d_match.start(): c_match.end()].replace("\n", " ")

                money_m = re.search(self.money_pattern, block)
                time_m = re.search(self.time_pattern, block)

                movimientos.append({
                    "date": d_match.group(),
                    "time": time_m.group() if time_m else None,
                    "description": self._clean_description(block),
                    "money": money_m.group() if money_m else None,
                })

        return movimientos

    @staticmethod
    def _money_to_float(money_str: Optional[str]) -> Optional[float]:
        """
        Convierte strings tipo '+$ 1,234.56' o '-$12.00' a float positivo (magnitud),
        dejando el signo para decidir depósito/retiro.
        """
        if not money_str:
            return None
        # quitar espacios
        s = money_str.replace(" ", "")
        # s ejemplo: "+$1,234.56" o "-$12.00"
        # remover +$ o -$
        s = s.replace("+$", "").replace("-$", "")
        # quitar comas
        s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None

    def to_dataframe(self, movimientos: List[Dict[str, Optional[str]]]) -> pd.DataFrame:
        """Convierte la lista de movimientos a un DataFrame con columnas finales."""
        df = pd.DataFrame(movimientos)

        if df.empty:
            return pd.DataFrame(columns=["fecha", "hora", "descripcion", "deposito", "retiro"])

        # deposito / retiro según el signo de money
        df["deposito"] = df["money"].apply(
            lambda x: self._money_to_float(x) if x and x.replace(" ", "").startswith("+$") else None
        )
        df["retiro"] = df["money"].apply(
            lambda x: self._money_to_float(x) if x and x.replace(" ", "").startswith("-$") else None
        )

        # Selección y rename final
        df = df[["date", "time", "description", "deposito", "retiro"]].copy()
        df.rename(columns={"date": "fecha", "time": "hora", "description": "descripcion"}, inplace=True)
        # df with columns: fecha, hora, descripcion, deposito, retiro
        df['saldo'] = None
        df = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
        return df

    def run(self, pdf_path: str) -> pd.DataFrame:
        """Pipeline completo: lee PDF → extrae movimientos → devuelve DataFrame."""
        all_text = self.read_pdf_text(pdf_path)
        movimientos = self.extract_movimientos(all_text)
        return self.to_dataframe(movimientos)
    
# Ejemplo de uso:
# extractor = EstadoCuentaMovimientosExtractor()
# df_movimientos = extractor.run("ruta/al/estado_de_cuenta.pdf")