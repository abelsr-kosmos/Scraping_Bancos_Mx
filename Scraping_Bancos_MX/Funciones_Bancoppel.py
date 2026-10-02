import re
from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Optional, Tuple

import pdfplumber
import pandas as pd
from ._normalizacion import montos_cero


@dataclass
class BancoppelMovimientosExtractor:
    """
    Extrae movimientos de un estado de cuenta Bancoppel (PDF)
    basado en la lógica de 'Detalle de Movimientos'.
    """
    checkpoint: str = "Detalle de Movimientos"
    
    # Patrón: dd/mm, texto var, monto, monto (saldo)
    # Grupos: 1=Fecha, 2=ParteDescripcion, 3=Monto, 4=Saldo
    pattern: str = r'(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})'

    def read_pdf_text(self, pdf_path: str) -> List[str]:
        """Lee el PDF y regresa una lista con el texto de cada página."""
        all_text: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text.append(text)
        return all_text

    def extract_movimientos(self, all_text: List[str]) -> List[Dict]:
        """
        Identifica páginas con la tabla y extrae los movimientos básicos.
        Regresa lista de dicts: {'fecha', 'descripcion', 'monto', 'saldo'}
        """
        table_pages_indices = []
        for i, page_text in enumerate(all_text):
            if re.search(self.checkpoint, page_text):
                table_pages_indices.append(i)
        
        movimientos = []
        
        for i in table_pages_indices:
            page_content = all_text[i]
            
            # Iterar sobre matches para extraer info y el texto intermedio (multiline description)
            for match in re.finditer(self.pattern, page_content):
                # Calcular texto entre este match y el siguiente
                start = match.end()
                remaining = page_content[start:]
                next_match = re.search(self.pattern, remaining)
                
                text_between = ""
                if next_match:
                    text_between = remaining[:next_match.start()]
                else:
                    # Si no hay siguiente match, tomamos el resto de la línea o bloque
                    # (Aquí asumimos el comportamiento lógico de capturar hasta el final del contexto relevante)
                    text_between = remaining
                
                # Procesar grupos del match actual
                date = match.group(0).split()[0]
                # El grupo 0 es toda la cadena match. El split puede ser arriesgado si hay espacios raros,
                # pero seguimos la lógica del prototipo.
                # Mejor usar los grupos capturados por el regex si es posible, pero el prototipo hacía split.
                # El prototipo:
                # date = match.group(0).split()[0]
                # saldo = match.group(0).split()[-1]
                # monto = match.group(0).split()[-2]
                # descripcion = match.group(0).split()[1:-2]
                
                parts = match.group(0).split()
                date_val = parts[0]
                saldo_val = parts[-1]
                monto_val = parts[-2]
                
                # Descripción dentro del match principal
                desc_parts = parts[1:-2]
                base_desc = ' '.join(desc_parts)
                
                # Descripción completa
                full_desc = base_desc + ' ' + text_between.strip()
                
                movimientos.append({
                    'fecha': date_val,
                    'descripcion': full_desc.strip(),
                    'monto': monto_val,
                    'saldo': saldo_val
                })
                
        return movimientos

    MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
             "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}

    def extract_periodo(self, all_text: List[str]) -> Optional[Tuple[date, date]]:
        """Periodo impreso ("Período: 02/SEP./2021 AL 01/OCT./2021") como (inicio, fin)."""
        patron = r'Per[ií]odo:\s*(\d{1,2})/([A-Za-z]{3})\.?/(\d{4})\s+AL\s+(\d{1,2})/([A-Za-z]{3})\.?/(\d{4})'
        for page_text in all_text:
            m = re.search(patron, page_text)
            if m:
                try:
                    ini = date(int(m.group(3)), self.MESES[m.group(2).upper()], int(m.group(1)))
                    fin = date(int(m.group(6)), self.MESES[m.group(5).upper()], int(m.group(4)))
                except (KeyError, ValueError):
                    return None
                return ini, fin
        return None

    def extract_saldo_final(self, all_text: List[str]) -> Optional[float]:
        """Saldo Actual de la carátula (resumen de la cuenta)."""
        for page_text in all_text:
            m = re.search(r'Saldo Actual\s+([\d,]+\.\d{2})', page_text)
            if m:
                return float(m.group(1).replace(',', ''))
        return None

    @staticmethod
    def _fecha_completa(mm_dd: str, periodo: Optional[Tuple[date, date]]) -> str:
        """mm/dd (como lo imprime Bancoppel) -> dd/mm/aaaa con el año del periodo."""
        mes, dia = (int(x) for x in mm_dd.split('/'))
        if periodo is None:
            return f"{dia:02d}/{mes:02d}"
        ini, fin = periodo
        for anio in sorted({ini.year, fin.year}):
            try:
                if ini <= date(anio, mes, dia) <= fin:
                    return f"{dia:02d}/{mes:02d}/{anio}"
            except ValueError:
                continue
        return f"{dia:02d}/{mes:02d}/{ini.year}"

    def to_dataframe(self, movimientos: List[Dict], periodo: Optional[Tuple[date, date]] = None,
                     saldo_final: Optional[float] = None) -> pd.DataFrame:
        """Genera el DataFrame en orden cronológico ascendente.

        El estado de cuenta lista los movimientos del más nuevo al más viejo y la
        columna Saldo es el saldo ANTES de cada movimiento (el más viejo trae el
        saldo anterior de la carátula y el más nuevo, el saldo previo al Saldo
        Actual). Por eso el saldo después de cada movimiento es el saldo impreso en
        la fila siguiente del listado (más nueva), y el del movimiento más nuevo
        es `saldo_final`. El signo sale de la diferencia entre ambos saldos.
        """
        movimientos_df = pd.DataFrame(movimientos)

        if movimientos_df.empty:
            return pd.DataFrame(columns=['fecha', 'descripcion', 'retiro', 'deposito', 'saldo'])

        montos = movimientos_df['monto'].str.replace(',', '', regex=False).astype(float).tolist()
        antes = movimientos_df['saldo'].str.replace(',', '', regex=False).astype(float).tolist()
        n = len(montos)

        filas = []
        for k in range(n):
            if k > 0:
                despues = antes[k - 1]
            elif saldo_final is not None:
                despues = saldo_final
            else:
                despues = None

            monto = montos[k]
            if despues is not None:
                dif = round(despues - antes[k], 2)
                signo = 1 if dif > 0 else -1 if dif < 0 else None
            else:
                signo = None
            if signo is None:
                # Sin saldo posterior (o sin cambio): se deduce del texto del concepto.
                desc = movimientos_df['descripcion'].iloc[k].upper()
                signo = 1 if re.match(r'(ABONO|DEPOSITO|DEPÓSITO|DEVOLUCION|PAGO DE INTERESES)', desc) else -1
                despues = round(antes[k] + signo * monto, 2)

            filas.append({
                'fecha': self._fecha_completa(movimientos_df['fecha'].iloc[k], periodo),
                'descripcion': movimientos_df['descripcion'].iloc[k],
                'retiro': monto if signo < 0 else None,
                'deposito': monto if signo > 0 else None,
                'saldo': despues,
            })

        # Listado más nuevo -> más viejo: se entrega en orden cronológico ascendente.
        return pd.DataFrame(filas[::-1], columns=['fecha', 'descripcion', 'retiro', 'deposito', 'saldo'])

    @montos_cero
    def run(self, pdf_path: str) -> pd.DataFrame:
        """Ejecuta el pipeline completo."""
        all_text = self.read_pdf_text(pdf_path)
        movimientos = self.extract_movimientos(all_text)
        return self.to_dataframe(movimientos, self.extract_periodo(all_text), self.extract_saldo_final(all_text))
