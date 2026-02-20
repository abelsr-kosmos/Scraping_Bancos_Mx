
import pathlib
from setuptools import find_packages, setup

HERE = pathlib.Path(__file__).parent

VERSION = '0.1.0'
PACKAGE_NAME = 'Scraping-Bancos-MX'
AUTHOR = 'Abel Santillan Rodriguez'
AUTHOR_EMAIL = 'abelsantillanrdz@gmail.com'
URL = 'https://github.com/abelsr-kosmos/Scraping_Bancos_Mx'

LICENSE = 'MIT'
DESCRIPTION = 'Librería para extraer datos de movimientos de los estados de cuenta de bancos Mexicanos'
LONG_DESCRIPTION = (HERE / "README.md").read_text(encoding='utf-8')
LONG_DESC_TYPE = "text/markdown"

INSTALL_REQUIRES = [
    'pdfplumber>=0.10.0',
    'pandas>=1.5.0',
    'numpy>=1.21.0'
]

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Topic :: Office/Business :: Financial',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

KEYWORDS = 'pdf scraping bank statement extractor mexico bancos'

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type=LONG_DESC_TYPE,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license=LICENSE,
    packages=find_packages(exclude=['tests', 'notebooks', 'benchmarks']),
    python_requires='>=3.9',
    install_requires=INSTALL_REQUIRES,
    classifiers=CLASSIFIERS,
    keywords=KEYWORDS,
    include_package_data=True,
    zip_safe=False,
)
