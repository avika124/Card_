"""
streamlit/app.py — Credit Card Compliance Checker (RAG-Enhanced)
Run: streamlit run app.py
"""

import os, sys, json, tempfile
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from python_fastapi.docx_generator import generate_compliance_docx

load_dotenv()

st.set_page_config(page_title="Credit Card Compliance Checker", page_icon="⚖️", layout="wide")
st.markdown("""<style>
.sev-high{background:#FFCCCC;padding:3px 10px;border-radius:12px;font-weight:600;color:#C00000;display:inline-block;}
.sev-medium{background:#FFF2CC;padding:3px 10px;border-radius:12px;font-weight:600;color:#BF8F00;display:inline-block;}
.sev-low{background:#E8F5E9;padding:3px 10px;border-radius:12px;font-weight:600;color:#2E7D32;display:inline-block;}
.sev-pass{background:#CCFFCC;padding:3px 10px;border-radius:12px;font-weight:600;color:#007000;display:inline-block;}
.rag-badge{background:#E3F2FD;padding:2px 8px;border-radius:8px;font-size:12px;color:#1565C0;display:inline-block;}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def get_checker(key): return RAGComplianceChecker(api_key=key, use_rag=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ Compliance Checker")
    st.caption("Powered by Anthropic Claude + RAG")
    api_key = st.text_input("ANTHROPIC_API_KEY", type="password", value=os.environ.get("ANTHROPIC_API_KEY",""))
    st.divider()
    st.subheader("📋 Regulations")
    sel_all = st.checkbox("Select all", value=True)
    active_regs = [rid for rid,info in REGULATIONS.items()
                   if st.checkbox(f"**{info['label']}**", value=sel_all, help=info["description"], key=f"r_{rid}")]
    st.divider()
    st.subheader("🧠 Knowledge Base")
    if api_key:
        try:
            chk = get_checker(api_key)
            s = chk.kb_stats()
            total = s.get("total_chunks",0)
            if total > 0:
                st.success(f"✅ {total:,} chunks loaded")
                st.caption(f"Regs:{s.get('regulations',0)} | Policies:{s.get('policies',0)} | Agreements:{s.get('agreements',0)}")
            else:
                st.info("Empty — use **Train** tab to add regulations")
        except Exception as e:
            st.warning(f"KB: {e}")
    else:
        st.caption("Enter API key to see KB status")

# ── Main tabs ──────────────────────────────────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["🔍 Check Document","📚 Train / Upload","🗂️ Knowledge Base","⚡ Batch Check"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 1: CHECK ━━━━━━━━━━━━━━━━━━━━━━━━━━
with t1:
    st.header("Check a Document")
    ti1, ti2, ti3 = st.tabs(["📋 Paste Text","📄 Upload File","🖼️ Upload Image"])
    rdy, itype, idata = False, None, None
    with ti1:
        txt = st.text_area("Paste content to analyze", height=220,
                           placeholder="Cardholder agreement, marketing copy, collection script, adverse action notice...")
        if txt.strip(): rdy,itype,idata = True,"text",txt
    with ti2:
        uf = st.file_uploader("Upload file", type=["txt","pdf","docx","doc","json"], key="cf")
        if uf: rdy,itype,idata = True,"file",uf
    with ti3:
        ui = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="ci")
        if ui:
            st.image(ui, use_column_width=True)
            rdy,itype,idata = True,"image",ui

    st.divider()
    ca, cb = st.columns([1,3])
    with ca:
        run = st.button("🔍 Run Compliance Check", type="primary",
                        disabled=not rdy or not active_regs or not api_key,
                        use_container_width=True)
    with cb:
        if not api_key: st.warning("Enter API key in sidebar")
        elif not active_regs: st.warning("Select at least one regulation")
        elif not rdy: st.info("Provide content above")

    if run:
        checker = get_checker(api_key)
        with st.spinner(f"Analyzing against {len(active_regs)} frameworks…"):
            try:
                if itype=="text":
                    result = checker.check_text(idata, active_regs)
                    exc, dname = idata[:500], "Pasted Text"
                elif itype=="file":
                    suf = Path(idata.name).suffix.lower()
                    with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
                        tmp.write(idata.read()); tp=tmp.name
                    result = checker.check_file(tp, active_regs)
                    os.unlink(tp); exc,dname = "","idata.name"
                elif itype=="image":
                    result = checker.check_image(idata.read(), idata.type, active_regs)
                    exc,dname = "","idata.name"
                st.session_state.update({"result":result,"original_excerpt":exc,"doc_name":dname})
            except Exception as e:
                st.error(f"Analysis failed: {e}")

    if "result" in st.session_state:
        result = st.session_state["result"]
        findings = result.get("findings",[])
        overall = result.get("overall_risk","unknown")
        if result.get("rag_enhanced"):
            st.markdown(f'<span class="rag-badge">🧠 RAG-enhanced — {result.get("rag_chunks_retrieved",0)} regulatory chunks retrieved</span>', unsafe_allow_html=True)
        bgs = {"high":"#FFCCCC","medium":"#FFF2CC","low":"#E8F5E9","pass":"#CCFFCC"}
        st.markdown(f'<div style="background:{bgs.get(overall,"#F5F5F5")};padding:1rem 1.5rem;border-radius:8px;margin:1rem 0;"><strong style="font-size:16px;">Overall Risk: {overall.upper()}</strong><br>{result.get("summary","")}</div>', unsafe_allow_html=True)
        counts = {"high":0,"medium":0,"low":0,"pass":0}
        for f in findings: counts[f.get("severity","low")] = counts.get(f.get("severity","low"),0)+1
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("🔴 High",counts["high"]); c2.metric("🟡 Medium",counts["medium"])
        c3.metric("🟠 Low",counts["low"]); c4.metric("🟢 Pass",counts["pass"])
        st.divider(); st.subheader("Findings")
        order = {"high":0,"medium":1,"low":2,"pass":3}
        for f in sorted(findings, key=lambda x: order.get(x.get("severity","low"),2)):
            sev = f.get("severity","low")
            with st.expander(f"**{f.get('regulation','')}** — {f.get('issue','')}"):
                st.markdown(f'<span class="sev-{sev}">{sev.upper()}</span>', unsafe_allow_html=True)
                st.write(f.get("detail",""))
                if f.get("regulatory_citation"): st.code(f.get("regulatory_citation"), language=None)
                if f.get("excerpt"): st.info(f"📌 **Excerpt:** *\"{f['excerpt']}\"*")
                if f.get("recommendation"): st.success(f"✅ **Recommendation:** {f['recommendation']}")
        st.divider()
        dl1,dl2 = st.columns(2)
        with dl1:
            if st.button("📥 Generate DOCX"):
                docx_bytes = generate_compliance_docx(result, document_name=st.session_state.get("doc_name",""), original_text_excerpt=st.session_state.get("original_excerpt",""))
                st.download_button("⬇️ Download compliance_report.docx", data=docx_bytes, file_name="compliance_report.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with dl2:
            st.download_button("⬇️ Download findings.json", data=json.dumps(result,indent=2), file_name="findings.json", mime="application/json")
        with st.expander("🔧 Raw JSON"): st.json(result)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 2: TRAIN ━━━━━━━━━━━━━━━━━━━━━━━━━━
with t2:
    st.header("Train — Add Policies & Regulations")
    st.caption("Everything added here becomes authoritative context Claude uses when checking documents.")
    if not api_key: st.warning("Enter API key in sidebar."); st.stop()
    checker = get_checker(api_key)

    # Upload file
    st.subheader("📄 Upload a Document")
    with st.form("uf"):
        c1,c2 = st.columns(2)
        with c1:
            uf2 = st.file_uploader("File", type=["txt","pdf","docx","doc","md"])
            sn = st.text_input("Source name", placeholder="e.g. CFPB UDAAP Guidance 2024")
        with c2:
            ur = st.selectbox("Regulation", ["general"]+list(REGULATIONS.keys()),
                              format_func=lambda x: f"{x} — {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
            ut = st.selectbox("Type", ["regulation","policy","agreement"])
        if st.form_submit_button("📥 Add to Knowledge Base", type="primary") and uf2 and sn:
            suf = Path(uf2.name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
                tmp.write(uf2.read()); tp=tmp.name
            try:
                n = checker.ingest_file(tp, regulation=ur, doc_type=ut, source=sn)
                os.unlink(tp); st.success(f"✅ {uf2.name} — {n} chunks as '{sn}'")
                st.cache_resource.clear()
            except Exception as e: st.error(f"Failed: {e}")

    st.divider()

    # Paste text
    st.subheader("📋 Paste Text")
    with st.form("pf"):
        pt = st.text_area("Regulation or policy text", height=180)
        c1,c2,c3 = st.columns(3)
        with c1: ps = st.text_input("Source name", placeholder="12 CFR 1026 Reg Z")
        with c2: pr = st.selectbox("Regulation", ["general"]+list(REGULATIONS.keys()), key="pr",
                                   format_func=lambda x: f"{x} — {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
        with c3: ptp = st.selectbox("Type", ["regulation","policy","agreement"], key="ptp")
        if st.form_submit_button("📥 Add to Knowledge Base", type="primary") and pt.strip() and ps:
            try:
                n = checker.ingest_text(pt, source=ps, regulation=pr, doc_type=ptp)
                st.success(f"✅ '{ps}' — {n} chunks"); st.cache_resource.clear()
            except Exception as e: st.error(f"Failed: {e}")

    st.divider()

    # Scrape URL
    st.subheader("🌐 Scrape from URL")
    with st.form("urlf"):
        url_i = st.text_input("URL", placeholder="https://www.consumerfinance.gov/rules-policy/regulations/1026/")
        c1,c2,c3 = st.columns(3)
        with c1: us = st.text_input("Source name", placeholder="CFPB Reg Z")
        with c2: ureg = st.selectbox("Regulation", ["general"]+list(REGULATIONS.keys()), key="ureg",
                                     format_func=lambda x: f"{x} — {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
        with c3: utp = st.selectbox("Type", ["regulation","policy","agreement"], key="utp2")
        if st.form_submit_button("🌐 Scrape & Add", type="primary") and url_i and us:
            with st.spinner(f"Fetching {url_i}…"):
                try:
                    import requests; from bs4 import BeautifulSoup
                    resp = requests.get(url_i, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
                    soup = BeautifulSoup(resp.text,"html.parser")
                    for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                    text = (soup.find("main") or soup.body or soup).get_text(separator="\n", strip=True)
                    if len(text)<100: st.error("Too little text extracted")
                    else:
                        n = checker.ingest_text(text, source=us, regulation=ureg, doc_type=utp)
                        st.success(f"✅ '{us}' — {n} chunks from {len(text):,} chars"); st.cache_resource.clear()
                except Exception as e: st.error(f"Failed: {e}")

    st.divider()

    # Quick-load presets
    st.subheader("⚡ Quick-Load Preset Regulations")
    PRESETS = {
        "CFPB UDAAP Guidance":       ("https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/","udaap"),
        "Regulation Z (TILA)":       ("https://www.consumerfinance.gov/rules-policy/regulations/1026/","tila"),
        "Regulation B (ECOA)":       ("https://www.consumerfinance.gov/rules-policy/regulations/1002/","ecoa"),
        "Regulation V (FCRA)":       ("https://www.consumerfinance.gov/rules-policy/regulations/1022/","fcra"),
        "Regulation F (FDCPA)":      ("https://www.consumerfinance.gov/rules-policy/regulations/1006/","collections"),
        "CFPB SCRA Guide":           ("https://www.consumerfinance.gov/consumer-tools/military-financial-relief/","scra"),
        "Fed SR 11-7 Model Risk":    ("https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm","sr117"),
    }
    cols = st.columns(3)
    for i,(name,(url,reg)) in enumerate(PRESETS.items()):
        with cols[i%3]:
            if st.button(f"📥 {name}", key=f"preset_{i}", use_container_width=True):
                with st.spinner(f"Loading {name}…"):
                    try:
                        import requests; from bs4 import BeautifulSoup
                        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
                        soup = BeautifulSoup(resp.text,"html.parser")
                        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                        text = (soup.find("main") or soup.body or soup).get_text(separator="\n", strip=True)
                        if len(text)>100:
                            n = checker.ingest_text(text, source=name, regulation=reg, doc_type="regulation")
                            st.success(f"✅ {n} chunks"); st.cache_resource.clear()
                        else: st.warning("Too little text")
                    except Exception as e: st.error(str(e))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 3: KB VIEWER ━━━━━━━━━━━━━━━━━━━━━━
with t3:
    st.header("Knowledge Base")
    if not api_key: st.warning("Enter API key in sidebar.")
    else:
        checker = get_checker(api_key); s = checker.kb_stats()
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Chunks",s.get("total_chunks",0)); c2.metric("Regulations",s.get("regulations",0))
        c3.metric("Policies",s.get("policies",0)); c4.metric("Agreements",s.get("agreements",0))
        st.divider(); st.subheader("Ingested Sources")
        sources = checker.kb_sources()
        if not sources: st.info("No sources yet. Go to **Train / Upload** to add regulations.")
        else:
            for src in sources:
                ca,cb = st.columns([5,1])
                with ca: st.markdown(f"📄 **{src}**")
                with cb:
                    if st.button("🗑️", key=f"del_{src}", help=f"Delete {src}"):
                        n = checker.kb.delete_source(src)
                        st.warning(f"Deleted {n} chunks from '{src}'"); st.cache_resource.clear(); st.rerun()
        st.divider(); st.subheader("Test Retrieval")
        q = st.text_input("Query", placeholder="APR disclosure in advertising")
        if q:
            chunks = checker.kb.retrieve(q, top_k=5)
            if chunks:
                for c in chunks:
                    with st.expander(f"[{c['score']}] {c['source']} — {c['regulation']}"): st.write(c["text"])
            else: st.info("No results. Ingest some documents first.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 4: BATCH ━━━━━━━━━━━━━━━━━━━━━━━━━━
with t4:
    st.header("Batch Check")
    if not api_key: st.warning("Enter API key in sidebar.")
    else:
        bf = st.file_uploader("Upload files", type=["txt","pdf","docx","doc"], accept_multiple_files=True)
        if bf and active_regs and st.button("⚡ Run Batch Check", type="primary"):
            checker = get_checker(api_key); results=[]; prog=st.progress(0); stat=st.empty()
            for i,f in enumerate(bf):
                stat.text(f"Checking {f.name}… ({i+1}/{len(bf)})")
                suf=Path(f.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                    tmp.write(f.read()); tp=tmp.name
                try:
                    r=checker.check_file(tp,active_regs); results.append({"file":f.name,"status":"ok","result":r})
                except Exception as e: results.append({"file":f.name,"status":"error","error":str(e)})
                finally:
                    if os.path.exists(tp): os.unlink(tp)
                prog.progress((i+1)/len(bf))
            stat.empty(); st.subheader("Results")
            order={"high":0,"medium":1,"low":2,"pass":3,"error":4}
            results.sort(key=lambda r: order.get(r.get("result",{}).get("overall_risk","error"),4))
            icons={"high":"🔴","medium":"🟡","low":"🟠","pass":"🟢"}
            for r in results:
                if r["status"]=="error": st.error(f"❌ **{r['file']}** — {r['error']}")
                else:
                    risk=r["result"].get("overall_risk","unknown")
                    with st.expander(f"{icons.get(risk,'⚪')} **{r['file']}** — {risk.upper()}"):
                        st.write(r["result"].get("summary",""))
                        for f2 in r["result"].get("findings",[]):
                            sev=f2.get("severity","low")
                            st.markdown(f'<span class="sev-{sev}">{sev.upper()}</span> **{f2.get("regulation","")}** — {f2.get("issue","")}', unsafe_allow_html=True)
            summary=[{"file":r["file"],"overall_risk":r.get("result",{}).get("overall_risk","error"),"summary":r.get("result",{}).get("summary",r.get("error",""))} for r in results]
            st.download_button("⬇️ batch_summary.json", data=json.dumps(summary,indent=2), file_name="batch_summary.json", mime="application/json")
