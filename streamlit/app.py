"""
streamlit/app.py — Credit Card Compliance Checker v3 (RAG + Company Memory)
"""
import os, sys, json, tempfile
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from rag.company_memory import DOC_TYPES
from python_fastapi.docx_generator import generate_compliance_docx

load_dotenv()
st.set_page_config(page_title="Credit Card Compliance Checker", page_icon="⚖️", layout="wide")
st.markdown("""<style>
.sev-high{background:#FFCCCC;padding:3px 10px;border-radius:12px;font-weight:600;color:#C00000;display:inline-block;}
.sev-medium{background:#FFF2CC;padding:3px 10px;border-radius:12px;font-weight:600;color:#BF8F00;display:inline-block;}
.sev-low{background:#E8F5E9;padding:3px 10px;border-radius:12px;font-weight:600;color:#2E7D32;display:inline-block;}
.sev-pass{background:#CCFFCC;padding:3px 10px;border-radius:12px;font-weight:600;color:#007000;display:inline-block;}
.sev-none{background:#F5F5F5;padding:3px 10px;border-radius:12px;font-weight:600;color:#666;display:inline-block;}
.rag-badge{background:#E3F2FD;padding:2px 8px;border-radius:8px;font-size:12px;color:#1565C0;display:inline-block;margin-right:6px;}
.mem-badge{background:#F3E5F5;padding:2px 8px;border-radius:8px;font-size:12px;color:#6A1B9A;display:inline-block;}
.conflict-box{background:#FFF8E1;border-left:4px solid #FF8F00;padding:12px 16px;border-radius:4px;margin:8px 0;}
.conflict-high{background:#FFEBEE;border-left:4px solid #C62828;}
.conflict-medium{background:#FFF8E1;border-left:4px solid #E65100;}
.conflict-low{background:#F1F8E9;border-left:4px solid #558B2F;}
.mem-card{background:#F8F0FF;border:1px solid #CE93D8;border-radius:8px;padding:10px 14px;margin-bottom:6px;}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def get_checker(key, company):
    return RAGComplianceChecker(api_key=key, use_rag=True, company_name=company)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ Compliance Checker")
    st.caption("Regulations + Company Memory · Anthropic Claude")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    company_name = st.text_input("Company name", value="Prama Capital Partners", help="Used to label your prior communications store")
    st.divider()
    st.subheader("📋 Regulations")
    sel_all = st.checkbox("Select all", value=True)
    active_regs = [rid for rid,info in REGULATIONS.items() if st.checkbox(f"**{info['label']}**", value=sel_all, help=info["description"], key=f"r_{rid}")]
    st.divider()
    # KB status
    st.subheader("🧠 Regulatory KB")
    if api_key:
        try:
            chk = get_checker(api_key, company_name); s = chk.kb_stats()
            t = s.get("total_chunks",0)
            st.success(f"✅ {t:,} chunks") if t>0 else st.info("Empty — use Train tab")
        except Exception as e: st.warning(str(e))
    st.subheader("🏢 Company Memory")
    if api_key:
        try:
            chk = get_checker(api_key, company_name); ms = chk.memory_stats()
            mt = ms.get("total",0)
            st.success(f"✅ {mt:,} docs indexed") if mt>0 else st.info("Empty — use Company Memory tab")
            if mt>0:
                st.caption(f"Marketing:{ms.get('marketing',0)} | Policy:{ms.get('policy',0)} | Disclosure:{ms.get('disclosure',0)}")
        except Exception as e: st.warning(str(e))

# ── Tabs ───────────────────────────────────────────────────────────────────────
t1,t2,t3,t4,t5,t6 = st.tabs(["🔍 Check Document","🏢 Company Memory","📚 Train Regulations","🗂️ Knowledge Base","⚡ Batch Check","🏛️ About Prama Capital"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 1: CHECK ━━━━━━━━━━━━━━━━━━━━━━━━━━
with t1:
    st.header("Check a Document")
    st.caption("Checks against regulations AND your prior company communications for conflicts")

    ti1,ti2,ti3 = st.tabs(["📋 Paste Text","📄 Upload File","🖼️ Upload Image"])
    rdy,itype,idata = False,None,None
    with ti1:
        txt = st.text_area("Paste content", height=200, placeholder="Marketing copy, cardholder agreement, collection script, adverse action notice...")
        if txt.strip(): rdy,itype,idata=True,"text",txt
    with ti2:
        uf = st.file_uploader("Upload file", type=["txt","pdf","docx","doc"], key="cf")
        if uf: rdy,itype,idata=True,"file",uf
    with ti3:
        ui = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="ci")
        if ui: st.image(ui,use_column_width=True); rdy,itype,idata=True,"image",ui

    with st.expander("⚙️ Check options"):
        col_a, col_b = st.columns(2)
        with col_a:
            run_conflicts = st.checkbox("Check against prior company communications", value=True,
                                        help="Compare new document against your uploaded marketing materials and policies")
            product_filter = st.text_input("Product filter (optional)", placeholder="e.g. Sapphire Reserve",
                                            help="Limit company memory search to a specific product")
        with col_b:
            st.info("💡 Upload your prior marketing materials and policies in the **Company Memory** tab to enable conflict detection.")

    st.divider()
    ca,cb = st.columns([1,3])
    with ca:
        run = st.button("🔍 Run Compliance Check", type="primary", disabled=not rdy or not active_regs or not api_key, use_container_width=True)
    with cb:
        if not api_key: st.warning("Enter API key in sidebar")
        elif not active_regs: st.warning("Select at least one regulation")
        elif not rdy: st.info("Provide content above")

    if run:
        checker = get_checker(api_key, company_name)
        with st.spinner(f"Running compliance + conflict check…"):
            try:
                pf = product_filter.strip() or None
                if itype=="text":
                    result=checker.check_text(idata, active_regs, product=pf, run_conflict_check=run_conflicts)
                    exc,dname=idata[:500],"Pasted Text"
                elif itype=="file":
                    suf=Path(idata.name).suffix.lower()
                    with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                        tmp.write(idata.read()); tp=tmp.name
                    result=checker.check_file(tp,active_regs,product=pf,run_conflict_check=run_conflicts)
                    os.unlink(tp); exc,dname="",idata.name
                elif itype=="image":
                    result=checker.check_image(idata.read(),idata.type,active_regs,product=pf)
                    exc,dname="",idata.name
                st.session_state.update({"result":result,"exc":exc,"dname":dname})
            except Exception as e: st.error(f"Analysis failed: {e}")

    if "result" in st.session_state:
        result=st.session_state["result"]
        findings=result.get("findings",[])
        overall=result.get("overall_risk","unknown")
        conflict_result=result.get("conflict_check")

        # Badges
        badges = []
        if result.get("rag_enhanced"): badges.append(f'<span class="rag-badge">🧠 RAG: {result.get("rag_chunks_retrieved",0)} reg chunks</span>')
        if conflict_result and not conflict_result.get("memory_empty"): badges.append(f'<span class="mem-badge">🏢 Company memory: {conflict_result.get("prior_docs_checked",0)} docs checked</span>')
        if badges: st.markdown(" ".join(badges), unsafe_allow_html=True)

        # Risk banner
        bgs={"high":"#FFCCCC","medium":"#FFF2CC","low":"#E8F5E9","pass":"#CCFFCC"}
        st.markdown(f'<div style="background:{bgs.get(overall,"#F5F5F5")};padding:1rem 1.5rem;border-radius:8px;margin:1rem 0;"><strong style="font-size:16px;">Overall Risk: {overall.upper()}</strong><br>{result.get("summary","")}</div>', unsafe_allow_html=True)

        # Stats row
        counts={"high":0,"medium":0,"low":0,"pass":0}
        for f in findings: counts[f.get("severity","low")]=counts.get(f.get("severity","low"),0)+1
        conflict_count = len(conflict_result.get("conflicts",[])) if conflict_result else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("🔴 High",counts["high"]); c2.metric("🟡 Medium",counts["medium"])
        c3.metric("🟠 Low",counts["low"]); c4.metric("🟢 Pass",counts["pass"])
        c5.metric("🏢 Conflicts",conflict_count, delta="vs prior comms" if conflict_count>0 else None, delta_color="inverse")

        # ── Section 1: Regulatory Findings ───────────────────────────────────
        st.divider()
        st.subheader("📋 Regulatory Findings")
        order={"high":0,"medium":1,"low":2,"pass":3}
        for f in sorted(findings, key=lambda x: order.get(x.get("severity","low"),2)):
            sev=f.get("severity","low")
            with st.expander(f"**{f.get('regulation','')}** — {f.get('issue','')}"):
                st.markdown(f'<span class="sev-{sev}">{sev.upper()}</span>', unsafe_allow_html=True)
                st.write(f.get("detail",""))
                if f.get("regulatory_citation"): st.code(f.get("regulatory_citation"), language=None)
                if f.get("excerpt"): st.info(f"📌 **Excerpt:** *\"{f['excerpt']}\"*")
                if f.get("recommendation"): st.success(f"✅ **Recommendation:** {f['recommendation']}")

        # ── Section 2: Company Conflict Check ─────────────────────────────────
        st.divider()
        st.subheader("🏢 Prior Communications Conflict Check")

        if not conflict_result:
            st.info("Conflict check was not run. Enable it in Check Options above.")
        elif conflict_result.get("memory_empty"):
            st.info("📭 No prior company communications in memory.\n\nGo to the **Company Memory** tab to upload your marketing materials and policies. Once uploaded, every compliance check will automatically look for contradictions with your prior communications.")
        else:
            c_risk = conflict_result.get("conflict_risk","none")
            c_bgs = {"high":"#FFEBEE","medium":"#FFF8E1","low":"#F1F8E9","none":"#F5F5F5"}
            st.markdown(f'<div style="background:{c_bgs.get(c_risk,"#F5F5F5")};padding:1rem 1.5rem;border-radius:8px;margin:0.5rem 0;"><strong>Conflict Risk: {c_risk.upper()}</strong><br>{conflict_result.get("summary","")}</div>', unsafe_allow_html=True)

            conflicts = conflict_result.get("conflicts",[])
            if conflicts:
                for c in conflicts:
                    sev=c.get("severity","low")
                    css_class = f"conflict-{sev}"
                    with st.expander(f"⚠️ [{sev.upper()}] {c.get('title','')} — {c.get('category','')}"):
                        col_x, col_y = st.columns(2)
                        with col_x:
                            st.markdown("**New document says:**")
                            st.warning(c.get("new_document_says",""))
                        with col_y:
                            st.markdown(f"**Prior communication says** *(from: {c.get('prior_source','')})*:")
                            st.info(c.get("prior_communication_says",""))
                        st.error(f"**Why it matters:** {c.get('explanation','')}")
                        st.success(f"**Fix:** {c.get('recommendation','')}")
            else:
                st.success("✅ No conflicts found with prior company communications.")

            consistent = conflict_result.get("consistent_items",[])
            if consistent:
                with st.expander(f"✅ {len(consistent)} consistent area(s) with prior communications"):
                    for item in consistent: st.write(f"• {item}")

        # ── Export ────────────────────────────────────────────────────────────
        st.divider()
        dl1,dl2 = st.columns(2)
        with dl1:
            if st.button("📥 Generate DOCX Report"):
                docx_bytes = generate_compliance_docx(result, document_name=st.session_state.get("dname",""), original_text_excerpt=st.session_state.get("exc",""))
                st.download_button("⬇️ compliance_report.docx", data=docx_bytes, file_name="compliance_report.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with dl2:
            st.download_button("⬇️ findings.json", data=json.dumps(result,indent=2), file_name="findings.json", mime="application/json")
        with st.expander("🔧 Raw JSON"): st.json(result)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 2: COMPANY MEMORY ━━━━━━━━━━━━━━━━━
with t2:
    st.header("🏢 Company Memory")
    st.markdown("""
    Upload your company's **prior marketing materials, internal policies, cardholder agreements, 
    collection scripts, and other communications**. The compliance engine will automatically check 
    every new document against these to detect contradictions and conflicts.
    
    **Examples of conflicts it catches:**
    - New marketing says "0% APR for 18 months" but a prior disclosure says "0% for 15 months"
    - New collection script threatens legal action that your own policy says requires manager approval
    - New rewards terms forfeit points on closure but prior marketing promised "points never expire"
    - New cardholder agreement changes dispute window but no prior notice was given
    """)

    if not api_key:
        st.warning("Enter API key in sidebar.")
        st.stop()

    checker = get_checker(api_key, company_name)

    # Stats
    ms = checker.memory_stats()
    mt = ms.get("total",0)
    if mt > 0:
        cols = st.columns(len(DOC_TYPES))
        for i,(dt,label) in enumerate(DOC_TYPES.items()):
            cols[i].metric(label, ms.get(dt,0))
    st.divider()

    # Upload document
    st.subheader("📄 Upload Prior Document")
    with st.form("mem_upload"):
        c1,c2 = st.columns(2)
        with c1:
            mem_file = st.file_uploader("File", type=["txt","pdf","docx","doc","md"])
            mem_source = st.text_input("Document name / ID", placeholder="e.g. Freedom Unlimited Email Campaign Q2 2024")
            mem_date = st.text_input("Date", placeholder="2024-06-01")
        with c2:
            mem_type = st.selectbox("Document type", list(DOC_TYPES.keys()),
                                     format_func=lambda x: DOC_TYPES[x])
            mem_product = st.text_input("Product", placeholder="e.g. Freedom Unlimited (or leave blank for all products)")
            mem_version = st.text_input("Version (optional)", placeholder="v2.1")
            mem_tags = st.text_input("Tags (optional)", placeholder="email, promo, 2024-q2")

        if st.form_submit_button("📥 Add to Company Memory", type="primary") and mem_file and mem_source:
            suf=Path(mem_file.name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                tmp.write(mem_file.read()); tp=tmp.name
            try:
                n=checker.add_company_file(tp, doc_type=mem_type, source=mem_source,
                                            product=mem_product or "general",
                                            date=mem_date, version=mem_version)
                os.unlink(tp)
                st.success(f"✅ Added **{mem_file.name}** as '{mem_source}' — {n} chunks indexed")
                st.cache_resource.clear()
            except Exception as e: st.error(f"Failed: {e}")

    st.divider()

    # Paste text
    st.subheader("📋 Paste Prior Document Text")
    with st.form("mem_paste"):
        mem_text = st.text_area("Paste document content", height=180,
                                 placeholder="Paste prior marketing email, policy section, cardholder agreement text, call script...")
        c1,c2,c3,c4 = st.columns(4)
        with c1: ps=st.text_input("Document name", placeholder="Q1 2024 Promo Email")
        with c2: pt=st.selectbox("Type", list(DOC_TYPES.keys()), format_func=lambda x:DOC_TYPES[x], key="pt")
        with c3: pp=st.text_input("Product", placeholder="Freedom Unlimited", key="pp")
        with c4: pd=st.text_input("Date", placeholder="2024-01-15", key="pd")
        if st.form_submit_button("📥 Add to Company Memory", type="primary") and mem_text.strip() and ps:
            try:
                n=checker.add_company_document(mem_text, source=ps, doc_type=pt, product=pp or "general", date=pd)
                st.success(f"✅ '{ps}' — {n} chunks indexed"); st.cache_resource.clear()
            except Exception as e: st.error(f"Failed: {e}")

    st.divider()

    # Quick bulk load
    st.subheader("📂 Bulk Load from Test Documents")
    st.caption("Load the Chase sample documents included in this repo as example prior communications")
    test_dir = Path(__file__).parent.parent / "test-docs"
    if test_dir.exists():
        test_files = list(test_dir.glob("*.txt")) + list(test_dir.glob("*.docx"))
        if test_files:
            if st.button(f"📥 Load all {len(test_files)} test documents as prior communications", use_container_width=True):
                checker = get_checker(api_key, company_name)
                progress = st.progress(0)
                for i,f in enumerate(test_files):
                    try:
                        # Guess doc type from filename
                        fn = f.stem.lower()
                        if "marketing" in fn or "promo" in fn: dt="marketing"
                        elif "agreement" in fn or "terms" in fn or "disclosure" in fn: dt="disclosure"
                        elif "collection" in fn or "script" in fn: dt="script"
                        elif "policy" in fn or "reward" in fn: dt="policy"
                        else: dt="other"
                        checker.add_company_file(str(f), doc_type=dt, source=f.stem)
                    except: pass
                    progress.progress((i+1)/len(test_files))
                st.success(f"✅ Loaded {len(test_files)} documents into company memory")
                st.cache_resource.clear()
    st.divider()

    # View stored documents
    st.subheader("📋 Stored Documents")
    filter_type = st.selectbox("Filter by type", ["all"]+list(DOC_TYPES.keys()),
                                format_func=lambda x: "All types" if x=="all" else DOC_TYPES.get(x,x))
    docs = checker.memory_documents(doc_type=None if filter_type=="all" else filter_type)
    if not docs:
        st.info("No documents stored yet. Upload documents above.")
    else:
        for doc in docs:
            ca,cb = st.columns([5,1])
            with ca:
                dt_label = DOC_TYPES.get(doc.get("doc_type","other"),"Other")
                st.markdown(f'<div class="mem-card"><strong>{doc["source"]}</strong> &nbsp;·&nbsp; <span style="color:#888;font-size:12px;">{dt_label} | {doc.get("product","general")} | {doc.get("date","")}</span></div>', unsafe_allow_html=True)
            with cb:
                if st.button("🗑️", key=f"mdel_{doc['source']}", help=f"Delete {doc['source']}"):
                    n = checker.delete_company_document(doc["source"])
                    st.warning(f"Deleted {n} chunks from '{doc['source']}'"); st.cache_resource.clear(); st.rerun()

    if docs:
        st.divider()
        if st.button("🗑️ Clear all company memory", type="secondary"):
            if checker.memory:
                n = checker.memory.clear_all()
                st.warning(f"Cleared {n} chunks from company memory"); st.cache_resource.clear(); st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 3: TRAIN REGULATIONS ━━━━━━━━━━━━━━
with t3:
    st.header("Train — Add Regulatory Knowledge")
    st.caption("Add official regulations so Claude cites specific CFR sections and statutes in findings")
    if not api_key: st.warning("Enter API key in sidebar."); st.stop()
    checker = get_checker(api_key, company_name)

    with st.form("reg_upload"):
        c1,c2=st.columns(2)
        with c1:
            rf=st.file_uploader("File",type=["txt","pdf","docx","doc","md"]); rsn=st.text_input("Source name",placeholder="CFPB Reg Z 2024")
        with c2:
            rr=st.selectbox("Regulation",["general"]+list(REGULATIONS.keys()),format_func=lambda x:f"{x} — {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
            rt=st.selectbox("Type",["regulation","policy","agreement"])
        if st.form_submit_button("📥 Add Regulation",type="primary") and rf and rsn:
            suf=Path(rf.name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                tmp.write(rf.read()); tp=tmp.name
            try:
                n=checker.ingest_file(tp,regulation=rr,doc_type=rt,source=rsn)
                os.unlink(tp); st.success(f"✅ {rf.name} — {n} chunks"); st.cache_resource.clear()
            except Exception as e: st.error(f"Failed: {e}")

    st.divider()
    st.subheader("⚡ Quick-Load Preset Regulations")
    PRESETS={"CFPB UDAAP Guidance":("https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/","udaap"),"Regulation Z (TILA)":("https://www.consumerfinance.gov/rules-policy/regulations/1026/","tila"),"Regulation B (ECOA)":("https://www.consumerfinance.gov/rules-policy/regulations/1002/","ecoa"),"Regulation V (FCRA)":("https://www.consumerfinance.gov/rules-policy/regulations/1022/","fcra"),"Regulation F (FDCPA)":("https://www.consumerfinance.gov/rules-policy/regulations/1006/","collections"),"CFPB SCRA Guide":("https://www.consumerfinance.gov/consumer-tools/military-financial-relief/","scra"),"Fed SR 11-7":("https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm","sr117")}
    cols=st.columns(3)
    for i,(name,(url,reg)) in enumerate(PRESETS.items()):
        with cols[i%3]:
            if st.button(f"📥 {name}",key=f"p_{i}",use_container_width=True):
                with st.spinner(f"Loading…"):
                    try:
                        import requests; from bs4 import BeautifulSoup
                        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20)
                        soup=BeautifulSoup(r.text,"html.parser")
                        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                        text=(soup.find("main") or soup.body or soup).get_text(separator="\n",strip=True)
                        if len(text)>100:
                            n=checker.ingest_text(text,source=name,regulation=reg,doc_type="regulation")
                            st.success(f"✅ {n} chunks"); st.cache_resource.clear()
                        else: st.warning("Too little text")
                    except Exception as e: st.error(str(e))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 4: KB VIEWER ━━━━━━━━━━━━━━━━━━━━━━
with t4:
    st.header("Knowledge Base")
    if not api_key: st.warning("Enter API key.")
    else:
        checker=get_checker(api_key,company_name)
        s=checker.kb_stats()
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Total Chunks",s.get("total_chunks",0)); c2.metric("Regulations",s.get("regulations",0))
        c3.metric("Policies",s.get("policies",0)); c4.metric("Agreements",s.get("agreements",0))
        st.subheader("Ingested Sources")
        srcs=checker.kb_sources()
        if not srcs: st.info("No sources. Use Train tab.")
        else:
            for src in srcs:
                ca,cb=st.columns([5,1])
                with ca: st.markdown(f"📄 **{src}**")
                with cb:
                    if st.button("🗑️",key=f"kd_{src}"):
                        checker.kb.delete_source(src); st.cache_resource.clear(); st.rerun()
        st.divider()
        st.subheader("Test Retrieval")
        q=st.text_input("Query",placeholder="APR disclosure in advertising")
        if q:
            for c in checker.kb.retrieve(q,top_k=5):
                with st.expander(f"[{c['score']}] {c['source']} — {c['regulation']}"): st.write(c["text"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 5: BATCH ━━━━━━━━━━━━━━━━━━━━━━━━━━
with t5:
    st.header("Batch Check")
    st.caption("Check multiple files against regulations AND company memory in one run")
    if not api_key: st.warning("Enter API key.")
    else:
        bf=st.file_uploader("Upload files",type=["txt","pdf","docx","doc"],accept_multiple_files=True)
        bc1,bc2=st.columns(2)
        with bc1: batch_conflicts=st.checkbox("Include conflict check",value=True)
        with bc2: batch_product=st.text_input("Product filter",placeholder="Optional")
        if bf and active_regs and st.button("⚡ Run Batch Check",type="primary"):
            checker=get_checker(api_key,company_name); results=[]; prog=st.progress(0); stat=st.empty()
            for i,f in enumerate(bf):
                stat.text(f"Checking {f.name}…")
                suf=Path(f.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                    tmp.write(f.read()); tp=tmp.name
                try:
                    r=checker.check_file(tp,active_regs,product=batch_product or None,run_conflict_check=batch_conflicts)
                    results.append({"file":f.name,"status":"ok","result":r})
                except Exception as e: results.append({"file":f.name,"status":"error","error":str(e)})
                finally:
                    if os.path.exists(tp): os.unlink(tp)
                prog.progress((i+1)/len(bf))
            stat.empty()
            icons={"high":"🔴","medium":"🟡","low":"🟠","pass":"🟢"}
            order={"high":0,"medium":1,"low":2,"pass":3,"error":4}
            results.sort(key=lambda r: order.get(r.get("result",{}).get("overall_risk","error"),4))
            for r in results:
                if r["status"]=="error": st.error(f"❌ **{r['file']}** — {r['error']}")
                else:
                    res=r["result"]; risk=res.get("overall_risk","?"); cc=res.get("conflict_check")
                    conflict_flag = f" | 🏢 {len(cc.get('conflicts',[]))} conflict(s)" if cc and cc.get("has_conflicts") else ""
                    with st.expander(f"{icons.get(risk,'⚪')} **{r['file']}** — {risk.upper()}{conflict_flag}"):
                        st.write(res.get("summary",""))
                        for f2 in res.get("findings",[]):
                            sev=f2.get("severity","low")
                            st.markdown(f'<span class="sev-{sev}">{sev.upper()}</span> **{f2.get("regulation","")}** — {f2.get("issue","")}',unsafe_allow_html=True)
                        if cc and cc.get("conflicts"):
                            st.warning(f"🏢 **Conflicts with prior communications:** {cc.get('summary','')}")
            summary=[{"file":r["file"],"overall_risk":r.get("result",{}).get("overall_risk","error"),"conflict_risk":r.get("result",{}).get("conflict_risk","none"),"conflicts_found":len(r.get("result",{}).get("conflict_check",{}).get("conflicts",[])),"summary":r.get("result",{}).get("summary",r.get("error",""))} for r in results]
            st.download_button("⬇️ batch_summary.json",data=json.dumps(summary,indent=2),file_name="batch_summary.json",mime="application/json")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ TAB 6: ABOUT PRAMA CAPITAL ━━━━━━━━━━━━━
with t6:
    st.header("🏛️ About Prama Capital Partners")
    st.caption("Boutique advisory firm powering this compliance platform — lending strategy, risk analytics & AI")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        ### Building the Future of Lending — One Smart Decision at a Time.

        **Prama Capital Partners** is a boutique advisory and investment firm specializing in
        lending sector growth strategy. We bring senior-level expertise across risk, data, AI,
        and capital strategy to help financial institutions scale responsibly.
        """)
    with col2:
        st.markdown("""
        **Contact**
        📧 khemuka@gmail.com
        📍 Austin, Texas (global clients)
        🔗 [linkedin.com/in/atul-khemuka](https://linkedin.com/in/atul-khemuka)
        """)

    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("### 💼\n**Lending Growth & Capital Strategy**\nMarket expansion, customer acquisition, revenue modeling")
    c2.markdown("### 📊\n**Risk, Data & Analytics**\nCredit frameworks, portfolio analysis, governance structures")
    c3.markdown("### 🤖\n**Predictive Modeling & AI**\nMachine learning, fraud detection, behavioral scoring")
    c4.markdown("### 👔\n**Fractional C-Suite Leadership**\nOn-demand senior advisory roles")

    st.divider()
    st.subheader("👤 Founder — Atul Khemuka")
    st.markdown("""
    **20+ years** in credit and growth transformations. Previously served as **Chief Intelligence Officer**
    and **Chief Growth Officer** at Mercury Financial, helping scale the platform to over **2 million customers**.
    """)

    st.divider()
    st.subheader("🌐 Full Website")
    st.markdown("View the complete Prama Capital Partners website below:")
    import streamlit.components.v1 as components
    components.iframe("https://pramacapitalpartners.in/", height=700, scrolling=True)
