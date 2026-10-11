"""Tabel tarif ILUSTRATIF per (kode diagnosis ICD-10, severity).

⚠️  BUKAN tarif resmi INA-CBGs Kemenkes — hanya untuk mendemonstrasikan
mekanisme what-if simulator (digital twin lite). Orde magnitudenya dibuat
masuk akal (severity 3 > 2 > 1), tetapi JANGAN dipakai untuk klaim apapun
di proposal sebagai angka resmi. Tulis "tarif ilustratif" di UI & pitch.
"""

# dx_code -> {severity: tarif IDR}
TARIFFS = {
    "A91":   {1: 2_400_000,  2: 4_100_000,  3: 8_900_000},    # DBD
    "K35.8": {1: 3_200_000,  2: 6_500_000,  3: 12_000_000},   # Apendisitis + apendektomi
    "O80":   {1: 1_800_000,  2: 2_600_000,  3: 4_500_000},    # Partus spontan
    "J18.9": {1: 2_100_000,  2: 3_800_000,  3: 9_500_000},    # Pneumonia
    "O82":   {1: 3_500_000,  2: 5_800_000,  3: 11_000_000},   # Sectio caesarea
    "I10":   {1: 900_000,    2: 1_700_000,  3: 3_200_000},    # Hipertensi
}


def lookup(dx_code, severity):
    """Kembalikan tarif ilustratif; None bila kombinasi tak dikenal."""
    return TARIFFS.get(dx_code, {}).get(severity)


def fmt_idr(n):
    if n is None:
        return "-"
    return f"Rp{n:,}".replace(",", ".")
