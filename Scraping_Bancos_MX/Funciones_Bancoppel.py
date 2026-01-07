import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import pdfplumber
import pandas as pd


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

    def to_dataframe(self, movimientos: List[Dict]) -> pd.DataFrame:
        """Procesa la lista de movimientos para generar el DataFrame final con signos correctos."""
        movimientos_df = pd.DataFrame(movimientos)
        
        if movimientos_df.empty:
            return pd.DataFrame(columns=['fecha', 'descripcion', 'retiro', 'deposito', 'saldo'])

        # Limpieza de números
        # El prototipo hace replace de comas
        movimientos_df['monto'] = movimientos_df['monto'].str.replace(',', '', regex=False).astype(float)
        movimientos_df['saldo'] = movimientos_df['saldo'].str.replace(',', '', regex=False).astype(float)

        # Lógica de inferencia de signo basada en cambios de saldo
        # NOTA: Esta lógica asume el orden de filas tal cual vienen al iterar (top-down extracción)
        
        saldo_inicial = movimientos_df['saldo'].iloc[0]
        
        # Iteramos para ajustar el signo de 'monto' según si el saldo subió o bajó
        # Prototipo: saldo baja -> monto positivo (Deposit??). Saldo sube -> monto negativo.
        # Se implementa tal cual el prototipo.
        
        for idx, row in movimientos_df.iterrows():
            if idx == 0:
                continue
                
            saldo_actual = row['saldo']
            monto = row['monto']
            
            # Comparación con el saldo anterior (del iterador)
            if saldo_actual - saldo_inicial < 0:
                pass 
            else:
                # Si el saldo subió (o igual), invertimos el signo del monto
                row['monto'] = -monto
                
            # Actualizamos en el DF
            movimientos_df.at[idx, 'monto'] = row['monto']
            
            # Actualizamos el saldo de referencia para la siguiente iteración
            saldo_inicial = saldo_actual
            
        # Asignación de columnas retiro/deposito
        # Prototipo: 
        # retiro = -x if x < 0 else None  (Si monto es negativo, retiro es positivo de ese valor)
        # deposito = x if x > 0 else None (Si monto es positivo, deposito es ese valor)
        
        movimientos_df['retiro'] = movimientos_df['monto'].apply(lambda x: -x if x < 0 else None)
        movimientos_df['deposito'] = movimientos_df['monto'].apply(lambda x: x if x > 0 else None)
        
        return movimientos_df[['fecha', 'descripcion', 'retiro', 'deposito', 'saldo']]

    def run(self, pdf_path: str) -> pd.DataFrame:
        """Ejecuta el pipeline completo."""
        all_text = self.read_pdf_text(pdf_path)
        movimientos = self.extract_movimientos(all_text)
        return self.to_dataframe(movimientos)
