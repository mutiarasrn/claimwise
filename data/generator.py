"""Synthetic Indonesian clinical case generator with SEEDED fraud labels.

Karena data klaim BPJS asli tidak accessible, prototipe memakai data sintetis:
narasi klinis Bahasa Indonesia (gaya resume medis/CPPT) + pasangan kode klaim
ICD-10/ICD-9-CM. Sebagian kasus di-inject fraud (upcoding / unbundling) dengan
label ground-truth, sehingga detektor bisa dievaluasi (precision/recall).

Kode ICD di sini DISEDERHANAKAN untuk prototipe, bukan tarif resmi INA-CBGs.

Usage:
    python data/generator.py --n 200 --fraud-rate 0.3 --seed 42
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NAMES = [
    "Siti Rahayu", "Budi Santoso", "Dewi Lestari", "Agus Wijaya", "Rina Marlina",
    "Joko Prasetyo", "Ayu Putri", "Hendra Gunawan", "Maria Ulfa", "Dedi Kurniawan",
    "Sri Wahyuni", "Andi Nugroho", "Fitri Handayani", "Rudi Hartono", "Nina Kurnia",
]

# severity: 1 = ringan, 2 = sedang, 3 = berat (ala level severity INA-CBGs, disederhanakan)
TEMPLATES = [
    {
        "key": "dbd",
        "dx": "A91", "dx_name": "Demam berdarah dengue",
        "proc": [], "severity": 2,
        "narrative": (
            "Pasien {nama}, {umur} tahun, datang dengan keluhan demam tinggi sejak {hari} hari "
            "yang lalu disertai nyeri otot dan mual. Hasil laboratorium: trombosit {trombosit}/uL, "
            "hematokrit {ht}% (meningkat dari baseline), leukosit dalam batas normal. Tidak ada "
            "tanda perdarahan spontan maupun tanda syok. Diagnosis: Demam Berdarah Dengue. "
            "Terapi: infus kristaloid, paracetamol, observasi tanda vital ketat. "
            "Pasien rawat inap di bangsal biasa."
        ),
    },
    {
        "key": "apendisitis",
        "dx": "K35.8", "dx_name": "Apendisitis akut",
        "proc": [{"code": "47.09", "name": "Apendektomi"}],
        "bundled": {"code": "47.09", "name": "Apendektomi (paket)",
                    "fragments": ["47.0", "54.11"]},
        "severity": 2,
        "narrative": (
            "Pasien {nama}, {umur} tahun, nyeri perut kanan bawah sejak 1 hari, disertai mual "
            "muntah dan demam {suhu}C. Pemeriksaan fisik: nyeri tekan McBurney (+), Rovsing (+). "
            "Leukosit {leuko}/uL. USG: apendiks non-kompresibel diameter {diam} mm. "
            "Dilakukan apendektomi terbuka. Post operasi stabil, tidak ada komplikasi, "
            "tidak masuk ICU."
        ),
    },
    {
        "key": "partus",
        "dx": "O80", "dx_name": "Persalinan spontan tunggal",
        "proc": [], "severity": 1,
        "narrative": (
            "Pasien {nama}, {umur} tahun, G1P0A0 hamil aterm datang dengan his teratur dan "
            "pembukaan {pemb} cm. Persalinan pervaginam spontan, bayi lahir {bb} gram, "
            "APGAR 8/9. Tidak ada robekan jalan lahir derajat berat maupun perdarahan "
            "postpartum berlebih. Ibu dan bayi stabil, rawat gabung."
        ),
    },
    {
        "key": "pneumonia",
        "dx": "J18.9", "dx_name": "Pneumonia, tidak spesifik",
        "proc": [], "severity": 2,
        "narrative": (
            "Pasien {nama}, {umur} tahun, batuk berdahak sejak {hari} hari, demam, sesak napas. "
            "Ronkhi (+/+), saturasi O2 {spo2}% dengan O2 nasal kanul {o2} L/menit. "
            "Foto toraks: infiltrat di {lobus}. Diberikan antibiotik {ab}, oksigen, dan "
            "fisioterapi napas. Tidak masuk ICU, tidak menggunakan ventilator."
        ),
    },
    {
        "key": "sectio",
        "dx": "O82", "dx_name": "Persalinan dengan sectio caesarea",
        "proc": [{"code": "74.99", "name": "Sectio caesarea (paket)"}],
        "bundled": {"code": "74.99", "name": "Sectio caesarea (paket)",
                    "fragments": ["74.0", "54.11", "99.04"]},
        "severity": 2,
        "narrative": (
            "Pasien {nama}, {umur} tahun, hamil aterm dengan indikasi {indikasi}. "
            "Dilakukan sectio caesarea. Bayi lahir {bb} gram, APGAR 7/8. "
            "Perdarahan {darah} cc, mendapat transfusi {transfusi} kolf PRC. "
            "Post operasi stabil di bangsal biasa, tidak masuk ICU."
        ),
    },
    {
        "key": "hipertensi",
        "dx": "I10", "dx_name": "Hipertensi esensial",
        "proc": [], "severity": 1,
        "narrative": (
            "Pasien {nama}, {umur} tahun, keluhan pusing dan tengkuk tegang. "
            "TD {td} mmHg. EKG dalam batas normal, tidak ada nyeri dada maupun "
            "defisit neurologis. Diberikan antihipertensi oral dan observasi {jam} jam "
            "di IGD. Dipulangkan dengan kontrol rawat jalan."
        ),
    },
]

FRAGMENT_NAMES = {
    "74.0": "Sectio caesarea klasik (komponen)",
    "54.11": "Laparotomi eksplorasi (komponen)",
    "99.04": "Transfusi darah (komponen)",
    "47.0": "Apendektomi parsial (komponen)",
}


def fill(template, rng):
    kw = {
        "nama": rng.choice(NAMES),
        "umur": rng.randint(19, 68),
        "hari": rng.randint(3, 7),
        "trombosit": rng.choice([38000, 45000, 52000, 61000]),
        "ht": rng.choice([44, 46, 48]),
        "suhu": round(rng.uniform(37.8, 38.9), 1),
        "leuko": rng.choice([13200, 14800, 16100]),
        "diam": rng.choice([8, 9, 11]),
        "pemb": rng.randint(4, 8),
        "bb": rng.choice([2700, 2900, 3100, 3300]),
        "spo2": rng.choice([91, 92, 93]),
        "o2": rng.choice([2, 3, 4]),
        "lobus": rng.choice(["lobus kanan bawah", "lobus kiri bawah"]),
        "ab": rng.choice(["seftriakson", "levofloksasin"]),
        "indikasi": rng.choice(["partus tak maju", "gawat janin", "disproporsi sefalopelvik"]),
        "darah": rng.choice([400, 500, 600]),
        "transfusi": rng.choice([1, 2]),
        "td": rng.choice(["160/100", "170/105", "165/95"]),
        "jam": rng.choice([4, 6, 8]),
    }
    return template["narrative"].format(**kw)


def inject_fraud(template, rng):
    """Return (claimed_dx, claimed_proc, claimed_severity, fraud_type).

    Tiga varian: upcoding saja, unbundling saja, atau kombinasi keduanya
    (kasus blatant -> risk score tinggi -> flag)."""
    truth_sev = template["severity"]
    has_bundled = "bundled" in template
    roll = rng.random()

    def bumped_sev():
        b = min(3, truth_sev + rng.choice([1, 2]))
        return b if b != truth_sev else min(3, truth_sev + 1)

    def fragments():
        bundled = template["bundled"]
        return [{"code": c, "name": FRAGMENT_NAMES.get(c, c)}
                for c in rng.sample(bundled["fragments"],
                                    k=rng.randint(2, len(bundled["fragments"])))]

    if not has_bundled or roll < 0.70:
        # UPCODING: narasi tidak berubah, severity yang diklaim dinaikkan
        return template["dx"], list(template["proc"]), bumped_sev(), "upcoding"
    elif roll < 0.85:
        # UNBUNDLING saja: prosedur paket dipecah jadi komponen terpisah
        return template["dx"], fragments(), truth_sev, "unbundling"
    else:
        # KOMBINASI blatant: severity dinaikkan + paket dipecah
        return template["dx"], fragments(), bumped_sev(), "upcoding+unbundling"


def generate(n, fraud_rate, seed):
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        t = rng.choice(TEMPLATES)
        narrative = fill(t, rng)
        # tentukan fraud / tidak sesuai fraud_rate
        is_fraud_case = rng.random() < fraud_rate
        if is_fraud_case:
            dx, proc, sev, ftype = inject_fraud(t, rng)
        else:
            dx, proc, sev, ftype = t["dx"], list(t["proc"]), t["severity"], "none"
        cases.append({
            "case_id": f"K-{i+1:04d}",
            "narrative": narrative,
            "claimed": {
                "dx": dx, "dx_name": t["dx_name"],
                "proc": proc, "severity": sev,
            },
            "truth": {
                "dx": t["dx"],
                "proc": [{"code": p["code"], "name": p["name"]} for p in t["proc"]],
                "severity": t["severity"],
                "is_fraud": ftype != "none",
                "fraud_type": ftype,
            },
        })
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--fraud-rate", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "synthetic", "cases.jsonl"))
    args = ap.parse_args()

    cases = generate(args.n, args.fraud_rate, args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    n_fraud = sum(1 for c in cases if c["truth"]["is_fraud"])
    print(f"OK: {len(cases)} kasus -> {args.out} ({n_fraud} fraud)")


if __name__ == "__main__":
    main()
