"""Detektor upcoding & unbundling + risk score + evidence (explainable).

Input : klaim faskes {dx, proc[], severity} + hasil ekstraksi narasi.
Output: {risk_score 0-100, flags[{type, evidence, points}], decision}

Aturan knowledge base INA-CBGs di sini DISEDERHANAKAN untuk prototipe —
ganti dengan tabel resmi Kemenkes untuk versi produksi.
"""

# prosedur paket -> komponen yang TIDAK BOLEH diklaim terpisah (unbundling)
BUNDLED = {
    "74.99": {"name": "Sectio caesarea (paket)", "fragments": ["74.0", "54.11", "99.04"]},
    "47.09": {"name": "Apendektomi (paket)", "fragments": ["47.0", "54.11"]},
}

SEV3_SIGNALS = {"syok", "icu", "ventilator"}
SEV2_SIGNALS = {"operasi", "transfusi", "trombosit_rendah", "o2_kanul", "infiltrat"}


def infer_severity(signals):
    s = set(signals)
    if s & SEV3_SIGNALS:
        return 3
    if s & SEV2_SIGNALS:
        return 2
    return 1


def detect(claimed, extracted):
    flags = []
    c_sev = claimed.get("severity", 1)
    c_dx = claimed.get("dx", "")
    c_procs = [p["code"] if isinstance(p, dict) else p for p in claimed.get("proc", [])]

    # 1) UPCODING: severity klaim > severity yang didukung narasi
    inferred = infer_severity(extracted.get("severity_signals", []))
    if c_sev > inferred:
        diff = c_sev - inferred
        # selisih 2 level = indikasi kuat -> langsung flag
        pts = 40 if diff == 1 else 65
        flags.append({
            "type": "upcoding",
            "evidence": (f"Klaim severity {c_sev}, tetapi narasi hanya mendukung "
                         f"severity {inferred} (sinyal: {', '.join(extracted.get('severity_signals', [])) or '-'})."),
            "points": pts,
        })

    # 2) DX MISMATCH: diagnosis klaim tidak didukung narasi
    if c_dx and c_dx not in extracted.get("diagnoses", []):
        flags.append({
            "type": "dx_mismatch",
            "evidence": (f"Kode diagnosis klaim {c_dx} tidak ditemukan dalam narasi. "
                         f"Narasi mendukung: {', '.join(extracted.get('diagnoses', [])) or '-'})."),
            "points": 25,
        })

    # 3) UNBUNDLING: komponen paket diklaim terpisah tanpa kode paketnya
    for bcode, info in BUNDLED.items():
        frags_found = [c for c in c_procs if c in info["fragments"]]
        if frags_found and bcode not in c_procs and bcode in extracted.get("procedures", []):
            flags.append({
                "type": "unbundling",
                "evidence": (f"Prosedur '{info['name']}' ({bcode}) dipecah menjadi klaim terpisah: "
                             f"{', '.join(frags_found)}. Seharusnya satu paket."),
                "points": 45,
            })

    risk = min(100, sum(f["points"] for f in flags))
    decision = "flag" if risk >= 60 else ("review" if risk >= 30 else "clear")
    return {
        "risk_score": risk,
        "inferred_severity": inferred,
        "flags": flags,
        "decision": decision,  # flag | review | clear  (verifikator ambil keputusan akhir)
    }
