import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Union

import pdfplumber
import pandas as pd


@dataclass
class Movement:
    fecha: Optional[str]
    descripcion: str
    monto_raw: Optional[str]  # e.g. "+$75.00" o "-$1,234.50"


class NuTableExtractor:
    """
    Extrae movimientos de estados de cuenta NU (o similares) siguiendo patrones:
      - Inicio de tabla: "FECHA DEL 01 AL 30 SEP 2025 (30 DÍAS) MONTO EN PESOS MEXICANOS"
      - Fin de tabla:   "Con estos movimientos, tu saldo promedio del periodo fue de $196,778.29"
      - Bloques por fecha: "30 SEP 2025"
      - Monto: "+$75.00" / "-$1,234.56" (también acepta sin signo, aunque tú usas signo)
    """

    def __init__(
        self,
        begin_table_pattern: Union[str, Pattern[str]] = r"FECHA DEL \d{2} AL \d{2} [A-Z]{3} \d{4} \(\d{2} DÍAS\) MONTO EN PESOS MEXICANOS",
        end_table_pattern: Union[str, Pattern[str]] = r"Con estos movimientos, tu saldo promedio del periodo fue de [+-]?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
        date_pattern: Union[str, Pattern[str]] = r"\b(\d{2} [A-Z]{3} \d{4})\b",
        money_pattern: Union[str, Pattern[str]] = r"([+-]?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        verbose: bool = False,
    ):
        self.begin_table_pattern: Pattern[str] = re.compile(begin_table_pattern) if isinstance(begin_table_pattern, str) else begin_table_pattern
        self.end_table_pattern: Pattern[str] = re.compile(end_table_pattern) if isinstance(end_table_pattern, str) else end_table_pattern
        self.date_pattern: Pattern[str] = re.compile(date_pattern) if isinstance(date_pattern, str) else date_pattern
        self.money_pattern: Pattern[str] = re.compile(money_pattern) if isinstance(money_pattern, str) else money_pattern
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def extract_pages_text(self, pdf_path: str) -> List[str]:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for i, page in enumerate(pdf.pages):
                txt = page.extract_text() or ""
                pages_text.append(txt)
                self._log(f"[extract_pages_text] Page {i}: {len(txt)} chars")
        return pages_text

    def extract_movements(self, pdf_path: str) -> List[Movement]:
        pages_text = self.extract_pages_text(pdf_path)

        movimientos: List[Movement] = []
        in_table = False

        for page_idx, page_text in enumerate(pages_text):
            if not page_text:
                continue

            # 1) Detectar inicio de tabla (solo la primera vez)
            if not in_table:
                m_begin = self.begin_table_pattern.search(page_text)
                if not m_begin:
                    continue
                in_table = True
                self._log(f"[extract_movements] ✅ Tabla encontrada en página {page_idx}")
                page_text = page_text[m_begin.end():]  # cortamos desde el final del header

            # 2) Si estamos dentro de tabla, extraer bloques por fecha
            date_matches = list(self.date_pattern.finditer(page_text))
            if self.verbose:
                self._log(f"[extract_movements] Page {page_idx} dates: {[m.group(0) for m in date_matches]}")
                self._log(f"[extract_movements] Page {page_idx} indexes: {[m.start() for m in date_matches]}")

            indexes = [m.start() for m in date_matches]

            for i in range(len(indexes)):
                start_idx = indexes[i]
                end_idx = indexes[i + 1] if i + 1 < len(indexes) else len(page_text)

                movimiento_text = page_text[start_idx:end_idx].strip()
                if not movimiento_text:
                    continue

                date_block = self.date_pattern.search(movimiento_text)
                fecha = date_block.group(0) if date_block else None

                money_blocks = self.money_pattern.findall(movimiento_text)
                monto_raw = money_blocks[0] if money_blocks else None

                # Limpieza: quitar monto y fecha del texto completo
                movimiento_text_clean = self.money_pattern.sub("", movimiento_text).strip()
                movimiento_text_clean = self.date_pattern.sub("", movimiento_text_clean).strip()

                movimientos.append(
                    Movement(
                        fecha=fecha,
                        descripcion=movimiento_text_clean,
                        monto_raw=monto_raw,
                    )
                )

                if self.verbose:
                    self._log("-" * 100)
                    self._log(f"[block] fecha={fecha}")
                    self._log(f"[block] monto_raw={monto_raw}")
                    self._log(f"[block] descripcion={movimiento_text_clean}")

            # 3) Detectar fin de tabla (en la misma página ya recortada)
            if self.end_table_pattern.search(page_text):
                self._log(f"[extract_movements] 🛑 Fin de tabla detectado en página {page_idx}")
                break

        return movimientos

    @staticmethod
    def _money_to_float(m: Optional[str]) -> Optional[float]:
        """
        Convierte:
          "+$1,234.50" -> 1234.50
          "-$1,234.50" -> -1234.50
          "$1,234.50"  -> 1234.50
        """
        if not m:
            return None
        sign = -1.0 if m.strip().startswith("-") else 1.0
        # quitamos signos, $ y comas
        cleaned = re.sub(r"[\+\-\$,]", "", m).strip()
        try:
            return float(cleaned) * sign
        except ValueError:
            return None

    def to_dataframe(self, pdf_path: str) -> pd.DataFrame:
        movimientos = self.extract_movements(pdf_path)

        rows: List[Dict[str, Any]] = []
        for mov in movimientos:
            amount = self._money_to_float(mov.monto_raw)

            # Deposito y retiro como en tu lógica:
            deposito = amount if (amount is not None and amount > 0) else None
            retiro = -amount if (amount is not None and amount < 0) else None
            # retiro ya viene negativo

            rows.append(
                {
                    "fecha": mov.fecha,
                    "descripcion": mov.descripcion,
                    "deposito": deposito,
                    "retiro": retiro,
                }
            )
        df = pd.DataFrame(rows, columns=["fecha", "descripcion", "deposito", "retiro"])
        df['saldo'] = None
        df = df[['fecha', 'descripcion', 'deposito', 'retiro', 'saldo']]
        return df

# Ejemplo de uso:
# extractor = NuTableExtractor(verbose=True)
# df_movimientos = extractor.to_dataframe("ruta/al/estado_de_cuenta.pdf")