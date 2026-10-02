import re
import itertools
from dataclasses import dataclass, asdict
from typing import List, Optional, Pattern, Tuple
import pandas as pd
from ._normalizacion import montos_cero

@dataclass
class MovimientoHSBC:
    fecha: str
    detalles: str
    retiros: float
    abonos: float
    saldo: float

class ParserHSBC:
    """Parser para el render (una palabra/fragmento por línea) del estado de cuenta HSBC.

    Cada movimiento empieza en una línea "DD descripción" y trae dos montos
    con "$": retiro/depósito y saldo. El render ensucia los montos ("$1 140,628.44",
    "$5 58.00", "$ 66,366.4 41"), por eso cada monto se resuelve contra el saldo
    corrido: se elige la lectura con la que saldo = saldo_previo ± monto.
    """

    HEADER_END: Pattern = re.compile(r'^Saldo$')
    STOP: Pattern = re.compile(r'^(Emitido por:|CoDi)', flags=re.IGNORECASE)
    ROW_START: Pattern = re.compile(r'^(0[1-9]|[12]\d|3[01])\s+(\S.*)$')
    MONEY: Pattern = re.compile(r'\$\s*(\d[\d,\s]*(?:\.\s*\d[\d\s]*)?)')
    SALDO_INICIAL: Pattern = re.compile(
        r'Saldo\s+Inicial(?:\s+del)?\s+(?:Periodo\s+)?\$\s*([\d,]+\.\d{2})', flags=re.IGNORECASE)
    CARGO: Pattern = re.compile(r'\b(CGO|CARGO|RETIRO|POLIZA|PAGO\s+DE\s+TARJETA|COMISION)', flags=re.IGNORECASE)
    ABONO: Pattern = re.compile(r'\b(ABONO|NOMINA|DEPOSITO)', flags=re.IGNORECASE)

    def __init__(self, texto: str):
        self.texto = texto

    # ------------------------------------------------------------------ montos
    @staticmethod
    def _candidatos(raw: str) -> List[float]:
        """Lecturas posibles de un monto ensuciado por el render, de la más a la menos probable."""
        raw = raw.strip()
        ent, _, frac = raw.partition('.')
        enteros = []
        extra = ''
        if ' ' in ent.strip():
            # "49,6 698" -> el fragmento sobrante "6" se pega al grupo de miles ya presente
            izq, der = ent.strip().rsplit(None, 1)
            if ',' in izq:
                extra = re.sub(r'\d+$', '', izq) + der
        for e in (ent.replace(' ', ''), ent.split()[-1] if ent.split() else '', extra):
            if e and e not in enteros:
                enteros.append(e)
        frac = re.sub(r'\s+', '', frac)
        fracs = []
        if frac:
            for f in (frac[:2], frac[-2:]):
                if len(f) == 2 and f not in fracs:
                    fracs.append(f)
        else:
            fracs = ['00']
        out = []
        for e, f in itertools.product(enteros, fracs):
            try:
                v = float(f'{e.replace(",", "")}.{f}')
            except ValueError:
                continue
            if v not in out:
                out.append(v)
        return out

    def _saldo_inicial(self) -> Optional[float]:
        m = self.SALDO_INICIAL.search(self.texto)
        return float(m.group(1).replace(',', '')) if m else None

    # ----------------------------------------------------------------- filas
    def _filas(self) -> List[Tuple[str, str, List[str]]]:
        """Regresa (día, descripción, [textos de monto $]) por movimiento, solo dentro de la tabla."""
        filas = []
        activo = False
        prev_header = []
        cur = None
        for linea in self.texto.splitlines():
            ln = linea.strip()
            if not ln:
                continue
            if self.STOP.match(ln):
                activo = False
                cur = None
                if ln.lower().startswith('codi'):
                    break
                continue
            if not activo:
                prev_header = (prev_header + [ln])[-3:]
                if self.HEADER_END.match(ln) and any('Deposito/Abono' in h for h in prev_header[:-1]):
                    activo = True
                    cur = None
                    prev_header = []
                continue
            m = self.ROW_START.match(ln)
            if m:
                cur = [m.group(1), [], []]
                filas.append(cur)
                ln = m.group(2)
            if cur is None:
                continue
            montos = self.MONEY.findall(ln)
            if montos:
                texto_previo = ln[:ln.index('$')].strip()
                if texto_previo and not cur[2]:
                    cur[1].append(texto_previo)
                cur[2].extend(montos)
            elif not cur[2]:
                cur[1].append(ln)
        return [(d, ' '.join(desc), montos) for d, desc, montos in filas if montos]

    def _clasificar(self, desc: str) -> Optional[int]:
        """+1 si por texto parece abono, -1 si cargo, None si no se sabe."""
        if self.CARGO.search(desc):
            return -1
        if self.ABONO.search(desc):
            return 1
        return None

    @montos_cero
    def to_dataframe(self) -> pd.DataFrame:
        prev = self._saldo_inicial()
        rows = []
        for dia, desc, montos in self._filas():
            hint = self._clasificar(desc)
            cand_a = self._candidatos(montos[0])
            cand_s = self._candidatos(montos[-1]) if len(montos) > 1 else []
            monto = saldo = signo = None

            if prev is not None and cand_s:
                encontrados = []
                for a, s in itertools.product(cand_a, cand_s):
                    for sg in (1, -1):
                        if abs(prev + sg * a - s) < 0.005:
                            encontrados.append((a, s, sg))
                if encontrados:
                    preferidos = [e for e in encontrados if hint is None or e[2] == hint]
                    monto, saldo, signo = (preferidos or encontrados)[0]

            if monto is None:
                # Sin saldo previo o sin lectura que cuadre: mejor lectura individual.
                monto = cand_a[0] if cand_a else 0.0
                if cand_s:
                    saldo = cand_s[0]
                    signo = hint or (1 if prev is None or saldo >= prev else -1)
                else:
                    signo = hint or -1
                    saldo = round((prev or 0.0) + signo * monto, 2)

            prev = saldo
            rows.append(MovimientoHSBC(
                dia, desc,
                monto if signo < 0 else 0.0,
                monto if signo > 0 else 0.0,
                saldo))

        df = pd.DataFrame([asdict(r) for r in rows], columns=['fecha', 'detalles', 'retiros', 'abonos', 'saldo'])
        return df
