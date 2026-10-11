"""Ekstraksi informasi klinis dari narasi medis tak-terstruktur.

Dua implementasi dengan interface yang sama:
- MockExtractor  : keyword-based, jalan tanpa API key (untuk dev & demo offline).
- GeminiExtractor : LLM beneran via free tier (pakai kalau GEMINI_API_KEY di-set).

Output keduanya:
    {
      "diagnoses": ["A91"],            # kode ICD-10 yang didukung narasi
      "procedures": ["74.99"],         # kode ICD-9-CM yang didukung narasi
      "severity_signals": [...],       # sinyal klinis penentu severity
      "notes": "...",
    }
"""
import json
import os
import re


# ---- Mock: keyword-based (simulasi LLM untuk dev/demo) -----------------------

DX_KEYWORDS = [
    ("demam berdarah", "A91"),
    ("dengue", "A91"),
    ("apendisitis", "K35.8"),
    ("apendiks", "K35.8"),
    ("pervaginam spontan", "O80"),
    ("partus spontan", "O80"),
    ("infiltrat", "J18.9"),
    ("pneumonia", "J18.9"),
    ("sectio", "O82"),
    ("caesarea", "O82"),
    ("hipertensi", "I10"),
    ("td ", "I10"),
]

PROC_KEYWORDS = [
    ("apendektomi", "47.09"),
    ("sectio caesarea", "74.99"),
]

SEV3 = ["syok", "icu", "ventilator", "gagal napas", "koma"]
SEV2 = ["operasi", "transfusi", "trombosit", "o2 nasal", "oksigen", "infiltrat"]


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _find_quote(sentences, keywords):
    for s in sentences:
        sl = s.lower()
        if any(k in sl for k in keywords):
            return s
    return None


# Negasi sederhana: kata SEV3 diabaikan bila didahului kata negasi
# ("tidak ada tanda ... syok", "tidak masuk ICU"). LLM produksi menangani
# ini secara linguistik (negation detection); mock meniru perilakunya.
NEG_WORDS = {"tidak", "tanpa", "belum", "bukan"}


def _negated(low, match_start, n_words=8):
    before = low[:match_start].split()
    return any(w.strip(".,;:") in NEG_WORDS for w in before[-n_words:])


# keyword -> kalimat bukti, per kode diagnosis/prosedur/sinyal
EVIDENCE_KW = {
    "A91": ["demam berdarah", "dengue"],
    "K35.8": ["apendisitis", "apendiks"],
    "O80": ["pervaginam spontan", "partus spontan"],
    "J18.9": ["infiltrat", "pneumonia"],
    "O82": ["sectio", "caesarea"],
    "I10": ["hipertensi"],
    "47.09": ["apendektomi"],
    "74.99": ["sectio caesarea"],
    "trombosit_rendah": ["trombosit"],
    "syok": ["syok"],
    "icu": ["icu"],
    "ventilator": ["ventilator"],
    "operasi": ["operasi", "apendektomi", "sectio"],
    "transfusi": ["transfusi"],
    "o2_kanul": ["o2 nasal", "oksigen"],
    "infiltrat": ["infiltrat"],
    "observasi": ["observasi"],
}


class MockExtractor:
    def extract(self, narrative):
        low = narrative.lower()
        diagnoses = [code for kw, code in DX_KEYWORDS if kw in low]
        procedures = [code for kw, code in PROC_KEYWORDS if kw in low]
        signals = []
        # trombosit rendah = sinyal severity sedang
        m = re.search(r"trombosit\s*(\d+)", low)
        if m and int(m.group(1)) < 100_000:
            signals.append("trombosit_rendah")
        for kw in SEV3:
            for m in re.finditer(re.escape(kw), low):
                if not _negated(low, m.start()):
                    signals.append(kw)
                    break
        for kw in SEV2:
            if kw in low:
                signals.append(kw)
        if "observasi" in low:
            signals.append("observasi")
        # evidence spans: tiap fakta menunjuk kalimat sumbernya di narasi
        sents = _sentences(narrative)
        evidence = []
        for code in sorted(set(diagnoses)):
            q = _find_quote(sents, EVIDENCE_KW.get(code, []))
            if q:
                evidence.append({"fact": f"Diagnosis {code}", "quote": q})
        for code in sorted(set(procedures)):
            q = _find_quote(sents, EVIDENCE_KW.get(code, []))
            if q:
                evidence.append({"fact": f"Prosedur {code}", "quote": q})
        for sig in sorted(set(signals)):
            q = _find_quote(sents, EVIDENCE_KW.get(sig, []))
            if q:
                evidence.append({"fact": f"Sinyal {sig}", "quote": q})
        return {
            "diagnoses": sorted(set(diagnoses)),
            "procedures": sorted(set(procedures)),
            "severity_signals": sorted(set(signals)),
            "evidence": evidence,
            "notes": "mock extractor (keyword-based)",
        }


# ---- LLM beneran via Gemini free tier ----------------------------------------

PROMPT = """Kamu adalah asisten koding medis. Baca narasi klinis berbahasa Indonesia berikut,
lalu ekstrak FAKTA yang tertulis eksplisit. Jangan mengarang.

Narasi:
\"\"\"{narrative}\"\"\"

Kembalikan HANYA JSON valid dengan format persis ini:
{{"diagnoses": ["<kode ICD-10>"], "procedures": ["<kode ICD-9-CM>"],
  "severity_signals": ["<sinyal>"],
  "evidence": [{{"fact": "<fakta singkat>", "quote": "<kalimat persis dari narasi>"}}],
  "notes": "<ringkasan 1 kalimat>"}}
severity_signals pilih dari: syok, icu, ventilator, operasi, transfusi,
trombosit_rendah, o2_kanul, observasi. Kosongkan list bila tidak ada.
Gunakan kode: A91 demam berdarah, K35.8 apendisitis, O80 partus spontan,
J18.9 pneumonia, O82 sectio caesarea, I10 hipertensi, 47.09 apendektomi,
74.99 sectio caesarea paket."""


class GeminiExtractor:
    def __init__(self, api_key=None, model="gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def extract(self, narrative):
        resp = self._get_client().generate_content(PROMPT.format(narrative=narrative))
        text = resp.text.strip().strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
        data = json.loads(text)
        return {
            "diagnoses": data.get("diagnoses", []),
            "procedures": data.get("procedures", []),
            "severity_signals": data.get("severity_signals", []),
            "evidence": data.get("evidence", []),
            "notes": data.get("notes", ""),
        }


def get_extractor():
    """Pilih Gemini kalau API key tersedia, else mock (demo tetap jalan)."""
    if os.environ.get("GEMINI_API_KEY"):
        try:
            import google.generativeai  # noqa: F401
            return GeminiExtractor()
        except ImportError:
            pass
    return MockExtractor()
