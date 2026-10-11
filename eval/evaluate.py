"""Evaluasi detektor di atas data sintetis berlabel (seeded fraud).

Mengukur: precision / recall / F1 deteksi fraud + recall per tipe
(upcoding vs unbundling). Angka ini yang dibawa ke juri.

Usage:
    python eval/evaluate.py --n 300 --seed 123
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.generator import generate
from pipeline.detector import detect
from pipeline.extractor import MockExtractor, get_extractor


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--extractor", choices=["mock", "gemini"], default="mock",
                    help="mock = tanpa API key; gemini = LLM beneran (butuh GEMINI_API_KEY)")
    args = ap.parse_args()

    cases = generate(args.n, fraud_rate=0.3, seed=args.seed)
    ext = get_extractor() if args.extractor == "gemini" else MockExtractor()
    print(f"Extractor: {type(ext).__name__}")

    tp = fp = fn = 0
    per_type = {}  # fraud_type -> [tp, fn]
    for c in cases:
        result = detect(c["claimed"], ext.extract(c["narrative"]))
        pred_fraud = result["decision"] in ("flag", "review")
        actual_fraud = c["truth"]["is_fraud"]
        ftype = c["truth"]["fraud_type"]
        per_type.setdefault(ftype, [0, 0])
        if pred_fraud and actual_fraud:
            tp += 1
            per_type[ftype][0] += 1
        elif pred_fraud and not actual_fraud:
            fp += 1
        elif not pred_fraud and actual_fraud:
            fn += 1
            per_type[ftype][1] += 1

    p, r, f1 = prf(tp, fp, fn)
    print(f"\n=== Eval: {args.n} kasus sintetis (mock extractor) ===")
    print(f"Fraud aktual: {tp+fn} | terdeteksi benar: {tp} | false alarm: {fp} | lolos: {fn}")
    print(f"Precision: {p:.2%}   Recall: {r:.2%}   F1: {f1:.2%}")
    print("\nRecall per tipe fraud:")
    for ftype, (t, f) in per_type.items():
        if ftype == "none":
            continue
        rec = t / (t + f) if (t + f) else 0.0
        print(f"  - {ftype:10s}: recall {rec:.2%}  ({t}/{t+f})")
    print("\nCatatan: mock extractor ~sempurna by design; angka real diukur ulang")
    print("dengan GeminiExtractor (LLM beneran) sebelum dibawa ke juri.\n")


if __name__ == "__main__":
    main()
