# Scraping Bancos MX

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/pypi-v0.1.0-brightgreen?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI version">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License: MIT">
  <img src="https://img.shields.io/badge/Made%20with-❤️-red?style=for-the-badge" alt="Made with love">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/pdfplumber-✓-orange?style=flat-square" alt="pdfplumber">
  <img src="https://img.shields.io/badge/pandas-✓-purple?style=flat-square" alt="pandas">
  <img src="https://img.shields.io/badge/numpy-✓-lightblue?style=flat-square" alt="numpy">
</p>

---

<p align="center">
  <b>A Python library to extract transaction data from PDF bank statements of major Mexican banks</b>
</p>

---

## Features

- Extract transactions from PDF bank statements
- Supports 16 Mexican banks
- Returns standardized pandas DataFrames
- Easy-to-use API with consistent interface per bank

## Installation

### From PyPI (recommended)

```bash
pip install Scraping-Bancos-MX
```

### From Source

```bash
git clone https://github.com/abelsr-kosmos/Scraping_Bancos_Mx.git
cd Scraping_Bancos_Mx
pip install -e .
```

## Quick Start

```python
from Scraping_Bancos_MX import Scrap_Estado_BBVA

# Extract data from a bank statement PDF
df = Scrap_Estado_BBVA("path/to/statement.pdf")

# View the extracted transactions
print(df.head())
```

## Supported Banks

| Bank | Function Name |
|------|---------------|
| Afirme | `Scrap_Estado_Afirme` |
| Azteca | `Scrap_Estado_Azteca` |
| BanBajio | `Scrap_Estado_BanBajio` |
| Banamex | `Scrap_Estado_Banamex` |
| BanCoppel | `BancoppelMovimientosExtractor` (class) |
| Banjercito | `Scrap_Estado_Banjercito` |
| Banorte | `Scrap_Estado_Banorte` |
| BanRegio | `Scrap_Estado_BanRegio` |
| BBVA | `Scrap_Estado_BBVA` |
| HeyBanco | `Scrap_Estado_HeyBanco` |
| HSBC | `ParserHSBC` (class) |
| Inbursa | `Scrap_Estado_Inbursa` |
| MercadoPago | `EstadoCuentaMovimientosExtractor` (class) |
| Nu | `NuTableExtractor` (class) |
| Santander | `Scrap_Estado_Santander` |
| Scotiabank | `Scrap_Estado_Scotiabank` |

## Usage Examples

### Simple Function Interface (Most Banks)

```python
from Scraping_Bancos_MX import Scrap_Estado_BBVA, Scrap_Estado_Banorte

# BBVA
df_bbva = Scrap_Estado_BBVA("bbva_statement.pdf")

# Banorte
df_banorte = Scrap_Estado_Banorte("banorte_statement.pdf")
```

### Class-Based Interface (Some Banks)

```python
from Scraping_Bancos_MX import (
    BancoppelMovimientosExtractor,
    EstadoCuentaMovimientosExtractor,
    NuTableExtractor,
    ParserHSBC
)

# Bancoppel
extractor = BancoppelMovimientosExtractor()
df_bancoppel = extractor.run("bancoppel_statement.pdf")

# MercadoPago
extractor = EstadoCuentaMovimientosExtractor()
df_mp = extractor.run("mercadopago_statement.pdf")

# Nu
extractor = NuTableExtractor()
df_nu = extractor.to_dataframe("nu_statement.pdf")

# HSBC (requires text extraction first)
import pdfplumber
with pdfplumber.open("hsbc_statement.pdf") as pdf:
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    parser = ParserHSBC(text)
    df_hsbc = parser.to_dataframe()
```

## Output DataFrame Structure

All functions return a pandas DataFrame with the following columns:

| Column | Description |
|--------|-------------|
| `fecha` | Transaction date (DD/MM/YYYY) |
| `descripcion` | Full transaction description |
| `deposito` | Deposit amount (if applicable) |
| `retiro` | Withdrawal amount (if applicable) |
| `saldo` | Account balance after transaction |

Additional columns may be present depending on the bank:
- `concepto` - Transaction concept/type
- `origen` - Reference/origin of the transaction
- `contraparte` - Counterparty (sender/recipient)
- `institucion_contraparte` - Counterparty's bank institution
- `tipo_movimiento` - Transaction type (SPEI, PAGO, COMPRA, COMISION, etc.)

## Requirements

- Python >= 3.9
- pdfplumber >= 0.10.0
- pandas >= 1.5.0
- numpy >= 1.21.0

## Important Notes

- The PDF file must be **digitized/text-based**, not scanned images
- The statement must be from one of the supported Mexican banks
- The library was tested with bank statements up to July 2023. Newer or significantly older formats may not work correctly
- Some banks may not provide complete details as the extraction relies on text descriptions in the PDF
- Afirme and Inbursa were tested with limited sample data (only one statement each)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please [open an issue](https://github.com/abelsr-kosmos/Scraping_Bancos_Mx/issues) on GitHub.
