"""
Adaptadores que envuelven las funciones/clases Scrap_Estado_<Banco> ya
existentes bajo la interfaz común BankStatementParser, sin tocar su lógica
de extracción (esa lógica sigue viviendo en Funciones_<Banco>.py, que es lo
que corre el benchmark de precisión).

Uso:
    from Scraping_Bancos_MX import get_parser
    df = get_parser("BBVA").parse("estado.pdf")
"""

from __future__ import annotations

from typing import Dict, Type

import pdfplumber

from .base import BankStatementParser
from .Funciones_Afirme import Scrap_Estado_Afirme
from .Funciones_Azteca import Scrap_Estado_Azteca
from .Funciones_BanBajio import Scrap_Estado_BanBajio
from .Funciones_Banamex import Scrap_Estado_Banamex
from .Funciones_BanRegio import Scrap_Estado_BanRegio
from .Funciones_Banjercito import Scrap_Estado_Banjercito
from .Funciones_Banorte import Scrap_Estado_Banorte
from .Funciones_BBVA import Scrap_Estado_BBVA
from .Funciones_HeyBanco import Scrap_Estado_HeyBanco
from .Funciones_Inbursa import Scrap_Estado_Inbursa
from .Funciones_Santander import Scrap_Estado_Santander
from .Funciones_Scotiabank import Scrap_Estado_Scotiabank
from .Funciones_HSBC import ParserHSBC
from .Funciones_MercadoPago import EstadoCuentaMovimientosExtractor
from .Funciones_Nu import NuTableExtractor
from .Funciones_Bancoppel import BancoppelMovimientosExtractor
from .Funciones_Libranza_IMSS import Scrap_Libranza_IMSS
from .Funciones_Base import Scrap_Estado_Base
from .Funciones_Intercam import Scrap_Estado_Intercam
from .Funciones_Multiva import Scrap_Estado_Multiva
from .Funciones_Monex import Scrap_Estado_Monex


def _make_function_parser(banco: str, func) -> Type[BankStatementParser]:
    """Crea una clase parser a partir de una función Scrap_Estado_X ya
    existente, delegando toda la lógica a esa función."""

    class _FunctionParser(BankStatementParser):
        def parse(self, pdf_path: str):
            return func(pdf_path)

    _FunctionParser.banco = banco
    _FunctionParser.__name__ = f"{banco}Parser"
    _FunctionParser.__qualname__ = _FunctionParser.__name__
    _FunctionParser.__doc__ = f"Adaptador de Scrap_Estado_{banco} a la interfaz BankStatementParser."
    return _FunctionParser


AfirmeParser = _make_function_parser("Afirme", Scrap_Estado_Afirme)
AztecaParser = _make_function_parser("Azteca", Scrap_Estado_Azteca)
BanBajioParser = _make_function_parser("BanBajio", Scrap_Estado_BanBajio)
BanamexParser = _make_function_parser("Banamex", Scrap_Estado_Banamex)
BanRegioParser = _make_function_parser("BanRegio", Scrap_Estado_BanRegio)
BanjercitoParser = _make_function_parser("Banjercito", Scrap_Estado_Banjercito)
BanorteParser = _make_function_parser("Banorte", Scrap_Estado_Banorte)
BBVAParser = _make_function_parser("BBVA", Scrap_Estado_BBVA)
HeyBancoParser = _make_function_parser("HeyBanco", Scrap_Estado_HeyBanco)
InbursaParser = _make_function_parser("Inbursa", Scrap_Estado_Inbursa)
SantanderParser = _make_function_parser("Santander", Scrap_Estado_Santander)
ScotiabankParser = _make_function_parser("Scotiabank", Scrap_Estado_Scotiabank)
BaseParser = _make_function_parser("Base", Scrap_Estado_Base)
IntercamParser = _make_function_parser("Intercam", Scrap_Estado_Intercam)
MultivaParser = _make_function_parser("Multiva", Scrap_Estado_Multiva)
MonexParser = _make_function_parser("Monex", Scrap_Estado_Monex)


class HSBCParser(BankStatementParser):
    """Adaptador de ParserHSBC (requiere extraer el texto del PDF primero).

    ParserHSBC.to_dataframe() regresa columnas propias (fecha, detalles,
    retiros, abonos, saldo) en vez del esquema estándar; aquí se renombran
    para que parse_validado()/to_estado_cuenta() funcionen igual que con
    cualquier otro banco, sin tocar Funciones_HSBC.py (que sigue exportando
    ParserHSBC con su forma original para quien ya la use directamente).
    """

    banco = "HSBC"

    def parse(self, pdf_path: str):
        with pdfplumber.open(pdf_path) as pdf:
            texto = "\n".join(page.extract_text() or "" for page in pdf.pages)
        df = ParserHSBC(texto).to_dataframe()
        df = df.rename(columns={"detalles": "descripcion", "retiros": "retiro", "abonos": "deposito"})
        return df[["fecha", "descripcion", "deposito", "retiro", "saldo"]]


class MercadoPagoParser(BankStatementParser):
    """Adaptador de EstadoCuentaMovimientosExtractor."""

    banco = "MercadoPago"

    def parse(self, pdf_path: str):
        return EstadoCuentaMovimientosExtractor().run(pdf_path)


class NuParser(BankStatementParser):
    """Adaptador de NuTableExtractor."""

    banco = "Nu"

    def parse(self, pdf_path: str):
        return NuTableExtractor().to_dataframe(pdf_path)


class BancoppelParser(BankStatementParser):
    """Adaptador de BancoppelMovimientosExtractor."""

    banco = "Bancoppel"

    def parse(self, pdf_path: str):
        return BancoppelMovimientosExtractor().run(pdf_path)


class LibranzaIMSSParser(BankStatementParser):
    """Adaptador de Scrap_Libranza_IMSS.

    OJO: esta carta de libranza IMSS no es un estado de cuenta bancario,
    es una tabla de amortización con un esquema distinto (sin fecha/
    descripcion/deposito/retiro/saldo), así que parse_validado() y
    to_estado_cuenta() de la clase base no aplican aquí; usa parse()
    directo.
    """

    banco = "LibranzaIMSS"

    def parse(self, pdf_path: str):
        return Scrap_Libranza_IMSS(pdf_path)


PARSERS: Dict[str, Type[BankStatementParser]] = {
    "Afirme": AfirmeParser,
    "Azteca": AztecaParser,
    "BanBajio": BanBajioParser,
    "Banamex": BanamexParser,
    "BanRegio": BanRegioParser,
    "Banjercito": BanjercitoParser,
    "Banorte": BanorteParser,
    "BBVA": BBVAParser,
    "HeyBanco": HeyBancoParser,
    "Inbursa": InbursaParser,
    "Santander": SantanderParser,
    "Scotiabank": ScotiabankParser,
    "HSBC": HSBCParser,
    "MercadoPago": MercadoPagoParser,
    "Nu": NuParser,
    "Bancoppel": BancoppelParser,
    # LibranzaIMSSParser NO se registra aquí a propósito: no es un estado de
    # cuenta bancario (es una tabla de amortización con un esquema distinto),
    # así que meterlo en este diccionario rompería cualquier código genérico
    # que itere PARSERS/get_parser esperando el esquema estándar de los
    # demás. Sigue disponible directo como Scraping_Bancos_MX.LibranzaIMSSParser.
    "Base": BaseParser,
    "Intercam": IntercamParser,
    "Multiva": MultivaParser,
    "Monex": MonexParser,
}


def get_parser(banco: str) -> BankStatementParser:
    """Regresa una instancia del parser para `banco`.

    >>> get_parser("BBVA").parse("estado.pdf")

    Lanza ValueError si `banco` no está en PARSERS.
    """
    try:
        clase = PARSERS[banco]
    except KeyError:
        raise ValueError(f"Banco no soportado: {banco!r}. Opciones: {sorted(PARSERS)}") from None
    return clase()
