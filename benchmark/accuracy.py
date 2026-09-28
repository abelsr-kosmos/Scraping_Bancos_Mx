#!/usr/bin/env python3
"""
Benchmark de precisión para Scraping_Bancos_MX.

Tiene dos partes:

1. Precisión real (BBVA): compara Scrap_Estado_BBVA contra ground truth
   validado a mano (fecha + monto de cada movimiento, y sumas de depósitos/
   retiros que ya vienen cuadradas contra la carátula del estado de cuenta).
   El ground truth y los PDFs viven en otro repo del mismo workspace
   (Joseph-Data/ground_truth y Joseph-Data/KOSMOS/KOSMOS), por eso las rutas
   por defecto apuntan ahí en vez de vivir dentro de este repo. Ajusta
   --gt-dir/--pdf-dir si los mueves.

2. Robustez + reconciliación de saldo (resto de bancos): no hay ground truth
   para los otros 15 bancos, así que en su lugar se valida, con los PDFs de
   ejemplo que ya existen en notebooks/, que (a) el parser no truena y (b)
   saldo[i] == saldo[i-1] + deposito[i] - retiro[i] para cada fila. Este
   segundo chequeo es justo el que habría detectado los bugs de inversión de
   signo que se corrigieron en Bancoppel/Banamex/HSBC.

Uso:
    python benchmark/accuracy.py
    python benchmark/accuracy.py --gt-dir /ruta/a/ground_truth --pdf-dir /ruta/a/pdfs
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import Scraping_Bancos_MX as sbm  # noqa: E402

# Ground truth externo (ver docstring). Solo cubre los 3 estados BBVA "nativos"
# (texto real); los "NoNativo*" son escaneos puros, fuera del alcance de esta
# librería (README: "must be digitized/text-based, not scanned images").
DEFAULT_GT_DIR = Path("/data/Kosmos/Proyects/OCR-General/Joseph-Data/ground_truth")
DEFAULT_PDF_DIR = Path("/data/Kosmos/Proyects/OCR-General/Joseph-Data/KOSMOS/KOSMOS")
BBVA_NATIVE_CASES = ["Nativo1", "Nativo2", "Nativo3"]

# Bancos sin ground truth, pero con al menos un PDF de ejemplo en notebooks/.
ROBUSTNESS_CASES = {
    "Banjercito": (
        "Scrap_Estado_Banjercito",
        [
            "notebooks/19991988_15122025_151027.pdf",
            "notebooks/19991988_17122025_115800.pdf",
        ],
    ),
}


MESES_ES = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}


def _parse_fecha(value) -> str | None:
    """Normaliza una fecha a ISO (YYYY-MM-DD); None si no se pudo parsear."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None

    # Formato BBVA: "04/FEB/2025" (mes en español, abreviado)
    partes = value.upper().split("/")
    if len(partes) == 3 and partes[1] in MESES_ES:
        dia, mes, anio = partes
        try:
            return datetime(int(anio), int(MESES_ES[mes]), int(dia)).date().isoformat()
        except ValueError:
            return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _movs_from_gt(gt: dict) -> list[tuple[str | None, float]]:
    movs = []
    for m in gt["movimientos"]:
        fecha = _parse_fecha(m.get("fecha"))
        deposito = float(m.get("deposito") or 0.0)
        retiro = float(m.get("retiro") or 0.0)
        movs.append((fecha, round(deposito - retiro, 2)))
    return movs


def _movs_from_df(df: pd.DataFrame) -> list[tuple[str | None, float]]:
    movs = []
    for _, row in df.iterrows():
        fecha = _parse_fecha(row.get("fecha"))
        deposito = float(row["deposito"]) if pd.notna(row.get("deposito")) else 0.0
        retiro = float(row["retiro"]) if pd.notna(row.get("retiro")) else 0.0
        movs.append((fecha, round(deposito - retiro, 2)))
    return movs


def _match(gt_movs: list, pred_movs: list) -> int:
    """Empareja por (fecha, monto) como multiconjunto (greedy)."""
    remaining = list(pred_movs)
    matched = 0
    for mov in gt_movs:
        if mov in remaining:
            remaining.remove(mov)
            matched += 1
    return matched


def score_bbva(gt_dir: Path, pdf_dir: Path) -> list[dict]:
    results = []
    for case in BBVA_NATIVE_CASES:
        gt_path = gt_dir / f"{case}.json"
        pdf_path = pdf_dir / f"{case}.pdf"
        if not gt_path.exists() or not pdf_path.exists():
            faltante = gt_path if not gt_path.exists() else pdf_path
            results.append({"banco": "BBVA", "caso": case, "error": f"no encontrado: {faltante}"})
            continue

        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        gt_movs = _movs_from_gt(gt)
        gt_sum_dep = sum(float(m.get("deposito") or 0) for m in gt["movimientos"])
        gt_sum_ret = sum(float(m.get("retiro") or 0) for m in gt["movimientos"])

        try:
            df = sbm.Scrap_Estado_BBVA(str(pdf_path))
            error = None
        except Exception as e:  # noqa: BLE001
            df = pd.DataFrame(columns=["fecha", "descripcion", "retiro", "deposito", "saldo"])
            error = repr(e)

        pred_movs = _movs_from_df(df)
        pred_sum_dep = float(pd.to_numeric(df.get("deposito"), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
        pred_sum_ret = float(pd.to_numeric(df.get("retiro"), errors="coerce").fillna(0).sum()) if not df.empty else 0.0

        matched = _match(gt_movs, pred_movs)
        n_gt, n_pred = len(gt_movs), len(pred_movs)
        recall = matched / n_gt if n_gt else 0.0
        precision = matched / n_pred if n_pred else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        results.append({
            "banco": "BBVA",
            "caso": case,
            "error": error,
            "movimientos_gt": n_gt,
            "movimientos_extraidos": n_pred,
            "coincidencias_fecha_monto": matched,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "suma_depositos_gt": round(gt_sum_dep, 2),
            "suma_depositos_extraida": round(pred_sum_dep, 2),
            "suma_retiros_gt": round(gt_sum_ret, 2),
            "suma_retiros_extraida": round(pred_sum_ret, 2),
        })
    return results


def check_saldo_reconciliation(df: pd.DataFrame, tol: float = 1.0) -> float | None:
    """% de filas consecutivas donde saldo[i] == saldo[i-1] + deposito[i] - retiro[i]."""
    if df.empty or len(df) < 2 or "saldo" not in df.columns:
        return None
    saldo = pd.to_numeric(df["saldo"], errors="coerce")
    deposito = pd.to_numeric(df.get("deposito"), errors="coerce").fillna(0.0)
    retiro = pd.to_numeric(df.get("retiro"), errors="coerce").fillna(0.0)

    ok = total = 0
    for i in range(1, len(df)):
        if pd.isna(saldo.iloc[i]) or pd.isna(saldo.iloc[i - 1]):
            continue
        esperado = saldo.iloc[i - 1] + deposito.iloc[i] - retiro.iloc[i]
        total += 1
        if abs(esperado - saldo.iloc[i]) <= tol:
            ok += 1
    return (ok / total) if total else None


def run_robustness() -> list[dict]:
    results = []
    for banco, (func_name, pdfs) in ROBUSTNESS_CASES.items():
        func = getattr(sbm, func_name)
        for pdf_rel in pdfs:
            pdf_path = REPO_ROOT / pdf_rel
            if not pdf_path.exists():
                continue
            try:
                df = func(str(pdf_path))
                reconciliacion = check_saldo_reconciliation(df)
                results.append({
                    "banco": banco,
                    "archivo": pdf_path.name,
                    "error": None,
                    "filas_extraidas": len(df),
                    "reconciliacion_saldo": round(reconciliacion, 4) if reconciliacion is not None else None,
                })
            except Exception as e:  # noqa: BLE001
                results.append({
                    "banco": banco,
                    "archivo": pdf_path.name,
                    "error": repr(e),
                    "filas_extraidas": 0,
                    "reconciliacion_saldo": None,
                })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gt-dir", type=Path, default=DEFAULT_GT_DIR, help="Carpeta con los JSON de ground truth")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR, help="Carpeta con los PDFs correspondientes")
    args = parser.parse_args()

    print("=" * 78)
    print("BENCHMARK DE PRECISIÓN — BBVA (contra ground truth real)")
    print("=" * 78)
    bbva_results = score_bbva(args.gt_dir, args.pdf_dir)
    for r in bbva_results:
        print(json.dumps(r, indent=2, ensure_ascii=False))

    print()
    print("=" * 78)
    print("BENCHMARK DE ROBUSTEZ — otros bancos (sin ground truth disponible)")
    print("=" * 78)
    rob_results = run_robustness()
    for r in rob_results:
        print(json.dumps(r, indent=2, ensure_ascii=False))

    out_path = REPO_ROOT / "benchmark" / "last_run.json"
    out_path.write_text(
        json.dumps({"bbva_precision": bbva_results, "robustez": rob_results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nResultados guardados en {out_path}")


if __name__ == "__main__":
    main()
