
import pathlib
from setuptools import find_packages, setup

HERE = pathlib.Path(__file__).parent

VERSION = '0.1.0' 
PACKAGE_NAME = 'Scraping_Bancos_MX' 
AUTHOR = 'Abel Santillan Rodriguez' 
AUTHOR_EMAIL = 'abelsantillanrdz@gmail.com' 
URL = 'https://github.com/abelsr-kosmos/Scraping_Bancos_Mx' 

LICENSE = 'MIT' #Tipo de licencia
DESCRIPTION = 'Librería para extraer datos de movimientos de los estados de cuenta de bancos Mexicanos' #Descripción corta
LONG_DESCRIPTION = (HERE / "README.md").read_text(encoding='utf-8') #Referencia al documento README con una descripción más elaborada
LONG_DESC_TYPE = "text/markdown"


#Paquetes necesarios para que funcione la libreía. Se instalarán a la vez si no lo tuvieras ya instalado
INSTALL_REQUIRES = [
        'pymupdf',
        "pdfplumber",
        "pandas"
      ]

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type=LONG_DESC_TYPE,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    install_requires=INSTALL_REQUIRES,
    license=LICENSE,
    packages=find_packages(),
    include_package_data=True
)
