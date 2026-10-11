# Verifikasi Klaim INA-CBGs Berbasis Narasi Klinis 🏥

**Tim Dampit — BPJS Healthkathon 2026**

Platform validasi pengkodean medis otomatis: membandingkan **narasi klinis tak-terstruktur**
(resume medis, CPPT — berbahasa Indonesia) dengan **kode klaim ICD-10/ICD-9-CM** yang diajukan
faskes, **sebelum pembayaran disetujui**. Fokus: **upcoding** & **unbundling**.

## Kenapa ini addressing the problem

- Fraud JKN itu masalah triliunan rupiah (BPJS: kerugian fraud ~Rp6 T per Jul 2026; KPK: kasus
  Rp34 M markup + phantom billing; upcoding disebut eksplisit sebagai modus).
- Verifikasi klaim hari ini: rule-based pada field terstruktur + audit manual (sampling) →
  **buta terhadap narasi teks bebas**, tempat kecurangan terselubung disembunyikan.
- Arah Healthkathon 2026: *problem-first*, AI menyaring klaim/pola berisiko lebih cepat,
  **keputusan akhir tetap manusia** → dashboard human-in-the-loop.

## Novelty (klaim yang defensible)

1. Validasi terhadap **narasi klinis unstructured Bahasa Indonesia** (blind spot rule-based).
2. **Spesifik INA-CBGs**: logika severity level & bundling ala casemix Indonesia
   (literatur/produk existing kebanyakan US-centric: DRG/CPT).
3. **Pre-payment**: dicek sebelum bayar, bukan audit post-hoc.
4. **Explainable + human-in-the-loop by design**, bukan black-box scorer.

**Scope jujur:** mencakup upcoding & unbundling (pasien real, kode dimanipulasi).
Tidak mencakup phantom billing / pasien fiktif / pemalsuan identitas.

## Struktur

```
healthkathon-dampit/
├── data/
│   ├── generator.py      # bikin data sintetis: narasi klinis ID + klaim + label fraud (seeded)
│   └── synthetic/        # cases.jsonl hasil generate
├── pipeline/
│   ├── extractor.py      # LLM/NLP: ekstrak diagnosis, prosedur, sinyal severity dari narasi
│   └── detector.py       # deteksi upcoding/unbundling + risk score 0-100 + evidence
├── dashboard/
│   └── app.py            # Streamlit: side-by-side narasi vs kode klaim (human-in-the-loop)
├── eval/
│   └── evaluate.py       # precision/recall/F1 di atas data sintetis berlabel
└── requirements.txt
```

## Quickstart

```bash
pip install -r requirements.txt

# 1. Generate data sintetis (200 kasus, 30% fraud)
python data/generator.py --n 200 --fraud-rate 0.3 --seed 42

# 2. Jalankan evaluasi detektor (mock extractor, tanpa API key)
python eval/evaluate.py --n 200

# 3. Jalankan dashboard verifikator
streamlit run dashboard/app.py
```

Pakai LLM beneran (opsional, free tier): set `GEMINI_API_KEY`, lalu extractor otomatis
pakai `GeminiExtractor` alih-alih `MockExtractor`. Tanpa API key semuanya tetap jalan
dalam mock mode — demo tidak mati.

## Roadmap singkat

- [x] Scaffold + synthetic data + detector + dashboard + eval
- [x] What-if simulator (digital twin lite) + panel di dashboard
- [x] IMPLEMENTATION.md + demo script
- [ ] Ganti MockExtractor → GeminiExtractor, ukur selisih akurasinya (`--extractor gemini`)
- [ ] Tambah `evidence_spans` (kutip kalimat sumber per fakta)
- [ ] Perkaya knowledge base bundling INA-CBGs (dari regulasi Kemenkes)
- [ ] Tambah kasus fraud adversarial (narasi dibuat "mendukung" klaim palsu)
- [ ] Proposal + pitch deck (problem-first!)
