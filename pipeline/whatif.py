"""Digital twin lite: simulasi "bagaimana jika klaim dikoreksi secara sah".

Bukan grouper INA-CBGs beneran — mensimulasikan outcome administratif bila
temuan detektor diperbaiki: severity -> yang didukung narasi, fragmen ->
kode paket. Tarif dari pipeline/tariff.py (ILUSTRATIF).

AI tidak menyarankan manipulasi: hanya skenario koreksi yang sah
(didukung bukti), sesuai disiplin doc Nailu.
"""

from .detector import BUNDLED, infer_severity
from .tariff import lookup


def simulate(claimed, extracted, detection):
    """Return dict skenario sebelum vs sesudah koreksi."""
    c_procs = [p["code"] if isinstance(p, dict) else p
               for p in claimed.get("proc", [])]
    inferred = detection.get("inferred_severity",
                             infer_severity(extracted.get("severity_signals", [])))

    corrected_procs = list(c_procs)
    corrections = []

    # Koreksi 1: severity -> yang didukung narasi
    sev_before, sev_after = claimed.get("severity", 1), inferred
    if sev_before != sev_after:
        corrections.append(
            f"Severity {sev_before} -> {sev_after} (didukung narasi)")

    # Koreksi 2: fragmen -> kode paket
    for bcode, info in BUNDLED.items():
        frags = [c for c in corrected_procs if c in info["fragments"]]
        if frags and bcode not in corrected_procs \
                and bcode in extracted.get("procedures", []):
            corrected_procs = [c for c in corrected_procs if c not in frags]
            corrected_procs.append(bcode)
            corrections.append(
                f"Unbundling dikoreksi: {', '.join(frags)} -> {bcode} ({info['name']})")

    dx = claimed.get("dx", "")
    tarif_before = lookup(dx, sev_before)
    tarif_after = lookup(dx, sev_after)
    delta = (tarif_before - tarif_after) \
        if tarif_before and tarif_after else None

    return {
        "corrections": corrections,
        "before": {"dx": dx, "proc": c_procs, "severity": sev_before,
                   "tarif": tarif_before},
        "after": {"dx": dx, "proc": corrected_procs, "severity": sev_after,
                  "tarif": tarif_after},
        "selisih_tarif": delta,   # positif = potensi penghematan bila dikoreksi
        "catatan": "Tarif ilustratif, bukan tarif resmi INA-CBGs.",
    }
