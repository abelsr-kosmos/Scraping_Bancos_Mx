"""
Scraping_Bancos_MX - Librería para extraer datos de estados de cuenta bancarios mexicanos.
"""

__version__ = "0.1.0"
__author__ = "Abel Santillan Rodriguez"
__email__ = "abelsantillanrdz@gmail.com"

from .Funciones_Afirme import *
from .Funciones_BBVA import *
from .Funciones_Banorte import *
from .Funciones_BanRegio import *
from .Funciones_BanBajio import *
from .Funciones_Inbursa import *
from .Funciones_Santander import *
from .Funciones_Scotiabank import *
from .Funciones_HeyBanco import *
from .Funciones_Banamex import *
from .Funciones_Azteca import *
from .Funciones_HSBC import *
from .Funciones_MercadoPago import *
from .Funciones_Nu import *
from .Funciones_Bancoppel import *
from .Funciones_Banjercito import *
from .Funciones_Libranza_IMSS import *
from .Funciones_Base import *
from .Funciones_Intercam import *
from .Funciones_Multiva import *
from .Funciones_Monex import *

from .base import BankStatementParser
from .models import Movimiento, EstadoCuenta
from .parsers import (
    AfirmeParser,
    AztecaParser,
    BanBajioParser,
    BanamexParser,
    BanRegioParser,
    BanjercitoParser,
    BanorteParser,
    BBVAParser,
    HeyBancoParser,
    InbursaParser,
    SantanderParser,
    ScotiabankParser,
    HSBCParser,
    MercadoPagoParser,
    NuParser,
    BancoppelParser,
    LibranzaIMSSParser,
    BaseParser,
    IntercamParser,
    MultivaParser,
    MonexParser,
    PARSERS,
    get_parser,
)

__all__ = [
    "Scrap_Estado_Afirme",
    "Scrap_Estado_BBVA",
    "Scrap_Estado_Banorte",
    "Scrap_Estado_BanRegio",
    "Scrap_Estado_BanBajio",
    "Scrap_Estado_Inbursa",
    "Scrap_Estado_Santander",
    "Scrap_Estado_Scotiabank",
    "Scrap_Estado_HeyBanco",
    "Scrap_Estado_Banamex",
    "Scrap_Estado_Azteca",
    "ParserHSBC",
    "EstadoCuentaMovimientosExtractor",
    "NuTableExtractor",
    "BancoppelMovimientosExtractor",
    "Scrap_Estado_Banjercito",
    "Scrap_Libranza_IMSS",
    "Scrap_Estado_Base",
    "Scrap_Estado_Intercam",
    "Scrap_Estado_Multiva",
    "Scrap_Estado_Monex",
    # Interfaz unificada (opcional): modelos + clases parser por banco
    "BankStatementParser",
    "Movimiento",
    "EstadoCuenta",
    "AfirmeParser",
    "AztecaParser",
    "BanBajioParser",
    "BanamexParser",
    "BanRegioParser",
    "BanjercitoParser",
    "BanorteParser",
    "BBVAParser",
    "HeyBancoParser",
    "InbursaParser",
    "SantanderParser",
    "ScotiabankParser",
    "HSBCParser",
    "MercadoPagoParser",
    "NuParser",
    "BancoppelParser",
    "LibranzaIMSSParser",
    "BaseParser",
    "IntercamParser",
    "MultivaParser",
    "MonexParser",
    "PARSERS",
    "get_parser",
]