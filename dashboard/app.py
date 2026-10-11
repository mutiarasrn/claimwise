"""ClaimWise verifier workbench (Streamlit).

Alur: Antrian Klaim (skrining 100% klaim pra-pembayaran, triage by risk)
 -> Review Kasus (side-by-side narasi vs kode + flag ber-bukti + what-if)
 -> Keputusan verifikator tercatat di Jejak Audit.
AI menyaring, manusia memutuskan.

Run: streamlit run dashboard/app.py   (dari root repo)
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import streamlit as st

from pipeline.detector import detect
from pipeline.extractor import MockExtractor, get_extractor
from pipeline.tariff import fmt_idr
from pipeline.whatif import simulate

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "synthetic", "cases.jsonl")
DECISIONS_PATH = os.path.join(ROOT, "data", "synthetic", "decisions.csv")

st.set_page_config(page_title="ClaimWise", layout="wide")


@st.cache_data
def load_cases():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@st.cache_data
def cached_review(case_id, narrative, claimed_json, ext_name):
    """Analisis satu kasus (di-cache agar LLM tidak dipanggil ulang)."""
    ext = get_extractor() if ext_name == "GeminiExtractor" else MockExtractor()
    extracted = ext.extract(narrative)
    result = detect(json.loads(claimed_json), extracted)
    return extracted, result


def related_evidence(flag_type, evidence):
    if flag_type == "upcoding":
        keys = ("Sinyal",)
    elif flag_type == "unbundling":
        keys = ("Prosedur",)
    else:
        keys = ("Diagnosis",)
    return [e for e in evidence if e["fact"].startswith(keys)]


def open_case_review(case_id):
    st.session_state["selected"] = case_id
    st.session_state["nav"] = "Review Kasus"


# ---------------- data ----------------
cases = load_cases()
if not cases:
    st.warning("Belum ada data. Jalankan dulu: `python data/generator.py --n 200`")
    st.stop()

# Antrian selalu pakai skrining cepat (mock): 200 klaim dalam <1 detik.
# Review mendalam per kasus memakai LLM bila GEMINI_API_KEY tersedia.
triage_ext = MockExtractor()
if "triage" not in st.session_state:
    with st.spinner("Skrining antrian klaim..."):
        rows = []
        for c in cases:
            extd = triage_ext.extract(c["narrative"])
            res = detect(c["claimed"], extd)
            rows.append({
                "case_id": c["case_id"],
                "diagnosis": c["claimed"]["dx_name"],
                "dx": c["claimed"]["dx"],
                "sev_klaim": c["claimed"]["severity"],
                "risk": res["risk_score"],
                "status": res["decision"],
            })
        st.session_state["triage"] = pd.DataFrame(rows).sort_values("risk", ascending=False)
triage = st.session_state["triage"]

review_ext = get_extractor()
ext_name = type(review_ext).__name__
if "selected" not in st.session_state:
    st.session_state["selected"] = triage.iloc[0]["case_id"]

# ---------------- sidebar ----------------
st.sidebar.title("ClaimWise")
st.sidebar.caption("Healthkathon 2026")
page = st.sidebar.radio("Navigasi", ["Antrian Klaim", "Review Kasus", "Jejak Audit"], key="nav")
st.sidebar.divider()
st.sidebar.caption(f"Review engine: {ext_name}")
st.sidebar.caption("Antrian menggunakan skrining cepat. Review menganalisis kasus terpilih.")

# ================= ANTRIAN =================
if page == "Antrian Klaim":
    st.title("Antrian Klaim")
    st.caption("Seluruh klaim diskrining sebelum pembayaran. Verifikator memprioritaskan klaim berisiko.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total klaim", len(triage))
    m2.metric("Ditandai", int((triage["status"] == "flag").sum()))
    m3.metric("Perlu review", int((triage["status"] == "review").sum()))
    m4.metric("Tidak ditandai", int((triage["status"] == "clear").sum()))

    view = triage.copy()
    view["status"] = view["status"].map({
        "flag": "Ditandai", "review": "Perlu review", "clear": "Tidak ditandai",
    })
    st.dataframe(
        view[["case_id", "diagnosis", "dx", "sev_klaim", "risk", "status"]].head(50),
        use_container_width=True, hide_index=True,
    )
    st.caption("Menampilkan 50 risiko tertinggi.")
    ids = triage["case_id"].tolist()
    triage_by_id = triage.set_index("case_id").to_dict("index")
    status_label = {"flag": "DITANDAI", "review": "PERLU REVIEW", "clear": "TIDAK DITANDAI"}
    pick = st.selectbox("Pilih kasus untuk direview",
                        ids, index=ids.index(st.session_state["selected"]),
                        format_func=lambda case_id: (
                            f"{case_id} | Risiko {triage_by_id[case_id]['risk']}/100 | "
                            f"{status_label[triage_by_id[case_id]['status']]} | "
                            f"{triage_by_id[case_id]['diagnosis']}"
                        ))
    st.button("Buka review", type="primary", on_click=open_case_review, args=(pick,))

# ================= REVIEW =================
elif page == "Review Kasus":
    case = next(c for c in cases if c["case_id"] == st.session_state["selected"])
    claimed, narrative = case["claimed"], case["narrative"]

    # tombol hero untuk demo cepat (memakai label data demo)
    h1, h2, h3 = st.columns(3)
    def hero_pick(fraud_type, label):
        hits = [c["case_id"] for c in cases if c["truth"]["fraud_type"] == fraud_type]
        if hits and st.button(label, use_container_width=True):
            st.session_state["selected"] = hits[0]
            st.rerun()
    with h1:
        hero_pick("upcoding", "Contoh upcoding")
    with h2:
        hero_pick("unbundling", "Contoh unbundling")
    with h3:
        clean = [c["case_id"] for c in cases if not c["truth"]["is_fraud"]]
        if clean and st.button("Contoh tanpa temuan", use_container_width=True):
            st.session_state["selected"] = clean[0]
            st.rerun()

    extracted, result = cached_review(
        case["case_id"], narrative, json.dumps(claimed, ensure_ascii=False), ext_name)

    decision_label = {
        "flag": "Ditandai",
        "review": "Perlu review",
        "clear": "Tidak ditandai",
    }[result["decision"]]
    st.title(f"Review {case['case_id']}")
    st.caption(f"Status: {decision_label} | Diagnosis: {claimed['dx']} - {claimed['dx_name']}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Narasi medis")
        st.info(narrative)
        with st.expander("Bukti dari narasi"):
            ev = extracted.get("evidence", [])
            if ev:
                for e in ev:
                    st.write(f"**{e['fact']}**")
                    st.caption(f"\u201c{e['quote']}\u201d")
            else:
                st.write("Tidak ada bukti terekstrak.")
    with col2:
        st.subheader("Kode klaim")
        st.write(f"**Diagnosis (ICD-10):** {claimed['dx']} - {claimed['dx_name']}")
        st.write("**Prosedur (ICD-9-CM):**")
        if claimed["proc"]:
            for p in claimed["proc"]:
                st.write(f"- {p['code']} - {p['name']}")
        else:
            st.write("- (tidak ada)")
        st.write(f"**Severity diklaim:** {claimed['severity']} "
                 f"| **didukung narasi:** {result['inferred_severity']}")
        st.write("**Sinyal klinis:** " + (", ".join(extracted.get("severity_signals", [])) or "-"))

    st.divider()
    st.subheader("Ringkasan pemeriksaan")
    st.progress(result["risk_score"] / 100)
    if result["decision"] == "flag":
        st.metric("Skor risiko", f"{result['risk_score']}/100", "Perlu tindak lanjut",
                  delta_color="inverse")
    elif result["decision"] == "review":
        st.metric("Skor risiko", f"{result['risk_score']}/100", "Perlu review",
                  delta_color="inverse")
    else:
        st.metric("Skor risiko", f"{result['risk_score']}/100", "Tidak ditandai", delta_color="normal")

    if result["flags"]:
        for fl in result["flags"]:
            st.error(f"**[{fl['type'].upper()}]** (+{fl['points']}): {fl['evidence']}")
            for e in related_evidence(fl["type"], extracted.get("evidence", [])):
                st.caption(f"Bukti: \u201c{e['quote']}\u201d")
    else:
        st.success("Tidak ditemukan ketidaksesuaian antara narasi dan kode klaim.")

    if result["decision"] != "clear":
        with st.expander("Simulasi dampak koreksi",
                         expanded=True):
            sim = simulate(claimed, extracted, result)
            if sim["corrections"]:
                for c_ in sim["corrections"]:
                    st.write(f"- {c_}")
                df = pd.DataFrame([
                    {"": "Kode diagnosis", "Sebelum": sim["before"]["dx"],
                     "Sesudah (koreksi sah)": sim["after"]["dx"]},
                    {"": "Prosedur", "Sebelum": ", ".join(sim["before"]["proc"]) or "-",
                     "Sesudah (koreksi sah)": ", ".join(sim["after"]["proc"]) or "-"},
                    {"": "Severity", "Sebelum": sim["before"]["severity"],
                     "Sesudah (koreksi sah)": sim["after"]["severity"]},
                    {"": "Tarif", "Sebelum": fmt_idr(sim["before"]["tarif"]),
                     "Sesudah (koreksi sah)": fmt_idr(sim["after"]["tarif"])},
                ])
                st.table(df)
                if sim["selisih_tarif"]:
                    st.metric("Potensi selisih tarif", fmt_idr(sim["selisih_tarif"]))
            else:
                st.write("Tidak ada koreksi yang disarankan untuk kasus ini.")
            st.caption(f"Catatan: {sim['catatan']}")

    st.divider()
    st.subheader("Keputusan verifikator")
    decision = st.radio("Keputusan", ["Setujui klaim", "Investigasi lanjut", "Tolak klaim"],
                        horizontal=True, key=f"dec_{case['case_id']}")
    note = st.text_area("Catatan verifikator", placeholder="Alasan keputusan...",
                        key=f"note_{case['case_id']}")
    if st.button("Simpan keputusan", type="primary"):
        new_file = not os.path.exists(DECISIONS_PATH)
        with open(DECISIONS_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["case_id", "risk_score", "ai_decision", "verifier_decision", "note"])
            w.writerow([case["case_id"], result["risk_score"], result["decision"], decision, note])
        st.success(f"Keputusan untuk {case['case_id']} tersimpan di Jejak Audit.")

    with st.expander("ℹ️ Tentang prototipe ini"):
        st.write(
            "Memvalidasi klaim INA-CBGs terhadap narasi klinis tak-terstruktur berbahasa Indonesia "
            "untuk mendeteksi upcoding dan unbundling sebelum pembayaran disetujui. "
            "Scope: coding fraud pada pasien real; tidak mencakup phantom billing/pasien fiktif."
        )

# ================= AUDIT =================
else:
    st.title("Jejak Audit")
    st.caption("Setiap keputusan verifikator tercatat: siapa memutuskan apa, berdasarkan apa.")
    if os.path.exists(DECISIONS_PATH):
        df = pd.read_csv(DECISIONS_PATH)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Unduh CSV", df.to_csv(index=False).encode("utf-8"),
                           "jejak-audit.csv", "text/csv")
    else:
        st.info("Belum ada keputusan tersimpan. Buka Review Kasus dan simpan keputusan.")
