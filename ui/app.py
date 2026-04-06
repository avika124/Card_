"""
ui/app.py — Credit Card Compliance Platform v4
Full production UI with auth, workflow, analytics, monitoring
Run: streamlit run ui/app.py
"""
import os, sys, json, tempfile
from pathlib import Path
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from core.database import (init_db, authenticate_user, create_user, get_users,
    create_submission, get_submissions, get_submission, update_submission_status,
    save_findings, save_conflicts, get_findings, get_conflicts, create_review,
    get_reviews, mark_false_positive, log_action, get_audit_log,
    create_notification, get_notifications, mark_notifications_read,
    add_reg_watch, get_reg_watches, get_analytics)
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from rag.company_memory import DOC_TYPES
from python_fastapi.docx_generator import generate_compliance_docx

load_dotenv()
init_db()

st.set_page_config(page_title="Compliance Platform", page_icon="\u2696\ufe0f", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.5rem !important;}
[data-testid="stSidebar"]{background:#1C2D4F !important;}
[data-testid="stSidebar"] *{color:white !important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.2) !important;}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;}
.badge-high{background:#FFCCCC;color:#C00000;}.badge-medium{background:#FFF2CC;color:#BF8F00;}
.badge-low{background:#E8F5E9;color:#2E7D32;}.badge-pass{background:#CCFFCC;color:#007000;}
.badge-pending{background:#E3F2FD;color:#1565C0;}.badge-approved{background:#CCFFCC;color:#007000;}
.badge-rejected{background:#FFCCCC;color:#C00000;}.badge-escalated{background:#FFF2CC;color:#BF8F00;}
.badge-in_review{background:#F3E5F5;color:#6A1B9A;}
.card{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:0.75rem;}
.stat-card{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;text-align:center;}
.stat-num{font-size:2rem;font-weight:700;color:#1C2D4F;}
.stat-lbl{font-size:0.75rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;}
.finding-row{border-left:4px solid #e5e7eb;padding:10px 14px;margin:6px 0;border-radius:0 6px 6px 0;background:#fafafa;}
.finding-high{border-left-color:#C00000;background:#fff5f5;}.finding-medium{border-left-color:#BF8F00;background:#fffbf0;}
.finding-low{border-left-color:#2E7D32;background:#f0fff4;}.finding-pass{border-left-color:#007000;background:#f0fff4;}
</style>""", unsafe_allow_html=True)

if "user" not in st.session_state: st.session_state.user = None
if "page" not in st.session_state: st.session_state.page = "dashboard"
if "view_submission" not in st.session_state: st.session_state.view_submission = None

def nav(page, **kwargs):
    st.session_state.page = page
    for k,v in kwargs.items(): st.session_state[k] = v
    st.rerun()

def cu(): return st.session_state.user
def is_role(*roles): u=cu(); return u and u.get("role") in roles

@st.cache_resource
def get_checker(k, co): return RAGComplianceChecker(api_key=k, use_rag=True, company_name=co)

def get_api_key(): return st.session_state.get("sidebar_key","") or os.environ.get("ANTHROPIC_API_KEY","")

# LOGIN
def page_login():
    _,col,_ = st.columns([1,2,1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<div style="text-align:center"><h1 style="color:#1C2D4F;font-size:2.2rem;">\u2696\ufe0f Compliance Platform</h1><p style="color:#6b7280;font-size:1.1rem;">Credit Card Regulatory Compliance</p></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="compliance@company.com")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                user = authenticate_user(email, password)
                if user:
                    st.session_state.user = user
                    log_action(user["id"], user["email"], "login")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
        st.markdown('''<div style="background:#f0f4ff;border-radius:8px;padding:12px 16px;margin-top:16px;font-size:13px;color:#333;">
        <strong>Demo accounts (all passwords: password123)</strong><br>
        admin@company.com &nbsp;·&nbsp; compliance@company.com &nbsp;·&nbsp; legal@company.com &nbsp;·&nbsp; marketing@company.com
        </div>''', unsafe_allow_html=True)

# SIDEBAR
def render_sidebar():
    user = cu()
    if not user: return
    with st.sidebar:
        st.markdown(f'<div style="padding:8px 0 4px;font-size:18px;font-weight:700;">\u2696\ufe0f Compliance</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:13px;opacity:0.9;">{user["name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;opacity:0.6;">{user["company"]} \u00b7 {user["role"].upper()}</div>', unsafe_allow_html=True)
        st.divider()
        notifs = get_notifications(user["id"], unread_only=True)
        nb = f' ({len(notifs)})' if notifs else ''
        pages = [("\U0001f4ca","Dashboard","dashboard"),("\u2795","Submit Document","submit"),("\U0001f4cb","My Submissions","my_submissions")]
        if is_role("compliance","legal","admin"):
            pages += [(("\U0001f50d",f"Review Queue{nb}","review_queue")),("\u2705","All Reviews","all_reviews")]
        pages += [("\U0001f3e2","Company Memory","company_memory"),("\U0001f4da","Train Regulations","train_regs"),("\U0001f6f0\ufe0f","Reg Monitor","reg_monitor")]
        if is_role("compliance","legal","admin"):
            pages += [("\U0001f4c8","Analytics","analytics"),("\U0001f4dc","Audit Log","audit_log")]
        if is_role("admin"):
            pages += [("\u2699\ufe0f","Settings","settings")]
        for icon,label,pk in pages:
            active = st.session_state.page == pk
            if isinstance(icon, tuple): icon, label, pk = icon
            if st.button(f"{icon} {label}", key=f"nav_{pk}", use_container_width=True):
                nav(pk)
        st.divider()
        st.text_input("ANTHROPIC_API_KEY", type="password", value=os.environ.get("ANTHROPIC_API_KEY",""), key="sidebar_key")
        if st.button("\U0001f6aa Sign Out", use_container_width=True):
            log_action(cu()["id"],cu()["email"],"logout")
            st.session_state.user=None; st.rerun()

# DASHBOARD
def page_dashboard():
    user=cu()
    st.markdown(f"## \U0001f44b Welcome back, {user['name'].split()[0]}")
    st.caption(f"{user['company']} \u00b7 {datetime.now().strftime('%B %d, %Y')}")
    a=get_analytics(user["company"])
    notifs=get_notifications(user["id"])
    c1,c2,c3,c4,c5=st.columns(5)
    for col,val,lbl in [(c1,a["total_submissions"],"Total"),(c2,a["pending"],"Pending"),(c3,a["by_status"].get("approved",0),"Approved"),(c4,a["by_status"].get("rejected",0),"Rejected"),(c5,a["total_conflicts"],"Conflicts")]:
        with col: st.markdown(f'<div class="stat-card"><div class="stat-num">{val}</div><div class="stat-lbl">{lbl}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    cl,cr=st.columns([2,1])
    with cl:
        st.subheader("Recent Submissions")
        subs=get_submissions(user["company"])[:8]
        if not subs: st.info("No submissions yet. Click **Submit Document** to get started.")
        for s in subs:
            findings=get_findings(s["id"]); high=sum(1 for f in findings if f["severity"]=="high" and not f["is_false_positive"])
            rb=f'<span class="badge badge-high">HIGH</span>' if high else f'<span class="badge badge-pass">PASS</span>'
            sb=f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>'
            st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;"><div><strong>{s["title"]}</strong><br><span style="font-size:12px;color:#6b7280;">{s.get("submitter_name","?")} \u00b7 {s["submitted_at"][:10]}</span></div><div>{rb} {sb}</div></div></div>', unsafe_allow_html=True)
            if st.button("View \u2192", key=f"db_{s['id']}"): nav("review_detail",view_submission=s["id"])
    with cr:
        st.subheader("\U0001f514 Notifications")
        if not notifs: st.info("All caught up!")
        for n in notifs[:5]:
            icon={"reg_change":"\u26a0\ufe0f","review":"\U0001f4cb","decision":"\u2705","high_risk":"\U0001f534"}.get(n["type"],"\U0001f514")
            with st.expander(f"{icon} {n['title']}{'  \U0001f535' if not n['is_read'] else ''}"):
                st.write(n["message"]); st.caption(n["created_at"][:16].replace("T"," "))
        if any(not n["is_read"] for n in notifs):
            if st.button("Mark all read"): mark_notifications_read(user["id"]); st.rerun()
        st.divider(); st.subheader("\U0001f4ca Risk Breakdown")
        for risk,icon in [("high","\U0001f534"),("medium","\U0001f7e1"),("low","\U0001f7e0"),("pass","\U0001f7e2")]:
            n=a["by_risk"].get(risk,0)
            if n: st.markdown(f"{icon} **{risk.upper()}**: {n}")

# SUBMIT
def page_submit():
    user=cu(); api_key=get_api_key()
    st.header("\u2795 Submit Document for Compliance Review")
    if not api_key: st.error("Add ANTHROPIC_API_KEY in the sidebar."); return
    with st.form("sub_form"):
        c1,c2=st.columns(2)
        with c1: title=st.text_input("Document title *",placeholder="Q2 2025 Freedom Unlimited Campaign"); product=st.text_input("Product",placeholder="Freedom Unlimited"); priority=st.selectbox("Priority",["normal","high","urgent"])
        with c2: doc_type=st.selectbox("Document type",list(DOC_TYPES.keys()),format_func=lambda x:DOC_TYPES[x]); channel=st.selectbox("Channel",["email","web","print","in-branch","mobile","call-center","general"])
        st.subheader("Content")
        method=st.radio("Input",["Paste text","Upload file"],horizontal=True)
        doc_text,doc_name="",""
        if method=="Paste text":
            doc_text=st.text_area("Content *",height=180,placeholder="Paste marketing copy, agreement, policy, script..."); doc_name="Pasted Text"
        else:
            uf=st.file_uploader("File",type=["txt","pdf","docx","doc"])
            if uf:
                doc_name=uf.name; suf=Path(uf.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp: tmp.write(uf.read()); tp=tmp.name
                try:
                    from pypdf import PdfReader; import subprocess
                    if suf==".txt": doc_text=open(tp).read()
                    elif suf==".pdf": doc_text="\n\n".join(p.extract_text() or "" for p in PdfReader(tp).pages)
                    elif suf in (".docx",".doc"): doc_text=subprocess.run(["pandoc",tp,"-t","plain"],capture_output=True,text=True).stdout
                    os.unlink(tp)
                except: pass
        st.subheader("Regulations & Options")
        ca,cb=st.columns(2)
        with ca:
            sel_all=st.checkbox("All regulations",value=True)
            active_regs=[r for r in REGULATIONS if st.checkbox(REGULATIONS[r]["label"],value=sel_all,key=f"sr_{r}")]
        with cb:
            run_conflict=st.checkbox("Check against prior company communications",value=True)
            st.caption("Upload your prior materials in the Company Memory section to enable this.")
        submitted=st.form_submit_button("\U0001f50d Submit for Analysis",type="primary",use_container_width=True)
    if submitted:
        if not title or not doc_text.strip() or not active_regs:
            st.error("Title, content, and at least one regulation are required."); return
        with st.spinner("Running compliance analysis\u2026 30\u201360 seconds"):
            try:
                checker=get_checker(api_key,user["company"])
                result=checker.check_text(doc_text,active_regs,product=product or None,run_conflict_check=run_conflict)
                sid=create_submission(title=title,document_text=doc_text,document_name=doc_name,doc_type=doc_type,product=product or "general",channel=channel,submitted_by=user["id"],company=user["company"],regulations=active_regs,run_conflict=run_conflict,priority=priority)
                save_findings(sid,result.get("findings",[])); save_conflicts(sid,(result.get("conflict_check") or {}).get("conflicts",[]))
                for cu2 in [u for u in get_users(user["company"]) if u["role"] in ("compliance","legal","admin")]:
                    create_notification(cu2["id"],"review",f"New: {title}",f"{user['name']} submitted \u2018{title}\u2019. Risk: {result.get('overall_risk','?').upper()}")
                log_action(user["id"],user["email"],"submit","submission",sid,title)
                st.success(f"\u2705 Submitted! {len(result.get('findings',[]))} regulatory findings, {len((result.get('conflict_check') or {}).get('conflicts',[]))} conflicts.")
                st.balloons()
                ca2,cb2=st.columns(2)
                with ca2:
                    if st.button("View full results \u2192",type="primary"): nav("review_detail",view_submission=sid)
                with cb2:
                    docx=generate_compliance_docx(result,document_name=title)
                    st.download_button("\u2b07\ufe0f Download DOCX",data=docx,file_name=f"compliance_{sid[:8]}.docx",mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e: st.error(f"Analysis failed: {e}")

# MY SUBMISSIONS
def page_my_submissions():
    user=cu(); subs=get_submissions(user["company"],submitted_by=user["id"])
    st.header("\U0001f4cb My Submissions")
    if not subs: st.info("No submissions yet."); st.button("Submit your first document",type="primary",on_click=lambda:nav("submit")); return
    for s in subs:
        ca,cb,cc,cd=st.columns([3,1,1,1])
        with ca: st.markdown(f"**{s['title']}**\n{s['submitted_at'][:10]} \u00b7 {s.get('product','general')}")
        with cb: st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>',unsafe_allow_html=True)
        with cc:
            findings=get_findings(s["id"]); high=sum(1 for f in findings if f["severity"]=="high")
            st.markdown("\U0001f534 High risk" if high else "\u2705 OK")
        with cd:
            if st.button("View",key=f"ms_{s['id']}"): nav("review_detail",view_submission=s["id"])
        st.divider()

# REVIEW QUEUE
def page_review_queue():
    user=cu(); mark_notifications_read(user["id"])
    st.header("\U0001f50d Review Queue")
    c1,c2=st.columns(2)
    with c1: sf=st.selectbox("Status",["pending","in_review","all"])
    with c2: pf=st.text_input("Product filter")
    subs=get_submissions(user["company"],status=None if sf=="all" else sf)
    if pf: subs=[s for s in subs if pf.lower() in s.get("product","").lower()]
    if not subs: st.info("No submissions match your filters."); return
    for s in subs:
        findings=get_findings(s["id"]); high=sum(1 for f in findings if f["severity"]=="high" and not f["is_false_positive"])
        ca,cb,cc,cd=st.columns([3,1,1,1])
        with ca: st.markdown(f"**{'\U0001f6a8 ' if s.get('priority') in ('urgent','high') or high else ''}{s['title']}**\n{s.get('submitter_name','?')}")
        with cb: st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>',unsafe_allow_html=True)
        with cc: st.write(f"\U0001f534 {high} high" if high else "\u2705 Clean")
        with cd:
            if st.button("Review \u2192",key=f"rq_{s['id']}",type="primary"): nav("review_detail",view_submission=s["id"])
        st.divider()

# REVIEW DETAIL
def page_review_detail():
    sid=st.session_state.get("view_submission")
    if not sid: nav("review_queue"); return
    sub=get_submission(sid)
    if not sub: st.error("Not found."); return
    user=cu(); findings=get_findings(sid); conflicts=get_conflicts(sid); reviews=get_reviews(sid)
    ch,cv=st.columns([3,1])
    with ch:
        st.markdown(f"## {sub['title']}"); st.caption(f"{sub.get('submitter_name','?')}" + f" \u00b7 {sub['submitted_at'][:16].replace('T',' ')} \u00b7 {DOC_TYPES.get(sub.get('doc_type',''),'')}")
    with cv:
        st.markdown(f'<span class="badge badge-{sub["status"]}" style="font-size:14px;padding:6px 14px;">{sub["status"].upper().replace("_"," ")}</span>',unsafe_allow_html=True)
        full_result={"findings":findings,"conflict_check":{"conflicts":conflicts}}
        docx=generate_compliance_docx(full_result,document_name=sub["title"])
        st.download_button("\u2b07\ufe0f DOCX",data=docx,file_name=f"report_{sid[:8]}.docx",mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    high_f=sum(1 for f in findings if f["severity"]=="high" and not f["is_false_positive"])
    c1,c2,c3,c4=st.columns(4)
    c1.metric("High Risk",high_f); c2.metric("Med Risk",sum(1 for f in findings if f["severity"]=="medium" and not f["is_false_positive"]))
    c3.metric("Conflicts",len(conflicts)); c4.metric("Reviews",len(reviews))
    st.divider()
    tf,tc,tr,td,th=st.tabs([f"\U0001f4cb Findings ({len(findings)})",f"\U0001f3e2 Conflicts ({len(conflicts)})","\u2705 Review","\U0001f4c4 Document",f"\U0001f4dc History ({len(reviews)})"])
    sev_order={"high":0,"medium":1,"low":2,"pass":3}
    with tf:
        if not findings: st.success("No regulatory findings.")
        for f in sorted(findings,key=lambda x:sev_order.get(x["severity"],2)):
            sev=f["severity"]; fp=f["is_false_positive"]
            st.markdown(f'<div class="finding-row finding-{sev}" style="{"opacity:0.4;" if fp else ""}"><span class="badge badge-{sev}">{sev.upper()}</span> <strong>{f["regulation"]}</strong> \u00b7 {f["issue"]}{"  <em style='color:#999;font-size:11px;'>(false positive)</em>" if fp else ""}</div>',unsafe_allow_html=True)
            with st.expander(f"Details: {f['issue']}"):
                st.write(f["detail"])
                if f.get("regulatory_citation"): st.code(f["regulatory_citation"])
                if f.get("excerpt"): st.info(f"\U0001f4cc \"{f['excerpt']}\"")
                if f.get("recommendation"): st.success(f["recommendation"])
                if is_role("compliance","legal","admin") and not fp:
                    if st.button("Mark false positive",key=f"fp_{f['id']}"): mark_false_positive(f["id"],"findings",user["id"]); st.rerun()
    with tc:
        if not conflicts: st.success("No conflicts with prior communications.")
        for c in conflicts:
            sev=c["severity"]; fp=c["is_false_positive"]
            with st.expander(f"[{sev.upper()}] {c['title']}"):
                ca2,cb2=st.columns(2)
                with ca2: st.markdown("**New doc says:**"); st.warning(c["new_doc_says"])
                with cb2: st.markdown(f"**Prior says** *(from: {c['prior_source']})*:"); st.info(c["prior_says"])
                st.error(c["explanation"]); st.success(c["recommendation"])
                if is_role("compliance","legal","admin") and not fp:
                    if st.button("Mark false positive",key=f"cfp_{c['id']}"): mark_false_positive(c["id"],"conflicts",user["id"]); st.rerun()
    with tr:
        if is_role("compliance","legal","admin"):
            with st.form("rev_form"):
                decision=st.selectbox("Decision",["approved","rejected","escalated","in_review"],format_func=lambda x:{"approved":"\u2705 Approve","rejected":"\u274c Reject","escalated":"\u26a0\ufe0f Escalate","in_review":"\U0001f440 In Review"}[x])
                notes=st.text_area("Notes",height=100)
                if st.form_submit_button("Submit Decision",type="primary"):
                    if decision in ("rejected","escalated") and not notes: st.error("Notes required for reject/escalate.")
                    else:
                        create_review(sid,user["id"],decision,notes)
                        sub_user=next((u for u in get_users(sub["company"]) if u["id"]==sub["submitted_by"]),None)
                        if sub_user: create_notification(sub_user["id"],"decision",f"Decision: {decision.upper()}",f"Your submission \u2018{sub['title']}\u2019 was {decision}. {notes[:80]}")
                        from integrations.notifier import dispatch
                        dispatch("review_decision",submission=sub,decision=decision,reviewer_name=user["name"],notes=notes,submitter_email=sub_user["email"] if sub_user else None,submitter_name=sub_user["name"] if sub_user else None)
                        log_action(user["id"],user["email"],"review_decision","submission",sid,decision)
                        st.success(f"Decision: {decision.upper()}"); st.rerun()
        else:
            if reviews:
                r=reviews[0]; st.markdown(f"**Latest:** {r['decision'].upper()} by {r.get('reviewer_name','?')}")
                if r.get("notes"): st.write(r["notes"])
            else: st.info("No decision yet.")
    with td:
        st.text_area("Document",value=sub["document_text"],height=400,disabled=True)
    with th:
        if not reviews: st.info("No history.")
        for r in reviews:
            icon={"approved":"\u2705","rejected":"\u274c","escalated":"\u26a0\ufe0f","in_review":"\U0001f440"}.get(r["decision"],"\U0001f4cb")
            st.markdown(f"{icon} **{r['decision'].upper()}** by {r.get('reviewer_name','?')} \u00b7 {r['reviewed_at'][:16].replace('T',' ')}"); 
            if r.get("notes"): st.write(r["notes"])
            st.divider()

# COMPANY MEMORY
def page_company_memory():
    user=cu(); api_key=get_api_key()
    st.header("\U0001f3e2 Company Memory")
    st.markdown("Upload **prior marketing, policies, agreements, scripts** — every new submission is checked against these for contradictions.")
    if not api_key: st.error("Add API key in sidebar."); return
    checker=get_checker(api_key,user["company"])
    ms=checker.memory_stats()
    cols=st.columns(7)
    for i,(dt,label) in enumerate(DOC_TYPES.items()): cols[i].metric(label,ms.get(dt,0))
    st.divider()
    with st.form("mem_form2"):
        c1,c2=st.columns(2)
        with c1: mf=st.file_uploader("File",type=["txt","pdf","docx","doc","md"]); msrc=st.text_input("Name *",placeholder="Q2 2024 Email Campaign"); mdate=st.text_input("Date",placeholder="2024-06-01")
        with c2: mtype=st.selectbox("Type",list(DOC_TYPES.keys()),format_func=lambda x:DOC_TYPES[x]); mprod=st.text_input("Product",placeholder="Freedom Unlimited"); mver=st.text_input("Version",placeholder="v2.1")
        paste_text=st.text_area("Or paste text directly",height=100)
        if st.form_submit_button("\U0001f4e5 Add to Company Memory",type="primary") and msrc.strip():
            with st.spinner("Indexing\u2026"):
                try:
                    if mf:
                        suf=Path(mf.name).suffix.lower()
                        with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp: tmp.write(mf.read()); tp=tmp.name
                        n=checker.add_company_file(tp,doc_type=mtype,source=msrc,product=mprod or "general",date=mdate,version=mver); os.unlink(tp)
                    elif paste_text.strip(): n=checker.add_company_document(paste_text,source=msrc,doc_type=mtype,product=mprod or "general",date=mdate,version=mver)
                    else: st.warning("Upload a file or paste text."); st.stop()
                    log_action(user["id"],user["email"],"add_company_memory","memory",msrc)
                    st.success(f"\u2705 \u2018{msrc}\u2019 \u2014 {n} chunks indexed"); st.cache_resource.clear()
                except Exception as e: st.error(f"Failed: {e}")
    st.divider()
    test_dir=ROOT/"test-docs"
    if test_dir.exists():
        tfiles=list(test_dir.glob("*.txt"))+list(test_dir.glob("*.docx"))
        if tfiles and st.button(f"\u26a1 Bulk load {len(tfiles)} Chase sample documents"):
            checker=get_checker(api_key,user["company"]); p=st.progress(0)
            for i,f in enumerate(tfiles):
                fn=f.stem.lower()
                dt="marketing" if "marketing" in fn else "disclosure" if "agreement" in fn or "disclosure" in fn else "script" if "collection" in fn else "policy"
                try: checker.add_company_file(str(f),doc_type=dt,source=f.stem)
                except: pass
                p.progress((i+1)/len(tfiles))
            st.success(f"\u2705 Loaded {len(tfiles)} documents"); st.cache_resource.clear(); st.rerun()
    st.divider(); st.subheader("\U0001f4cb Stored Documents")
    fdt=st.selectbox("Filter",["all"]+list(DOC_TYPES.keys()),format_func=lambda x:"All types" if x=="all" else DOC_TYPES.get(x,x))
    docs=checker.memory_documents(doc_type=None if fdt=="all" else fdt)
    if not docs: st.info("No documents stored.")
    for doc in docs:
        ca,cb=st.columns([5,1])
        with ca: st.markdown(f"\U0001f4c4 **{doc['source']}** \u00b7 <span style='color:#6b7280;font-size:12px;'>{DOC_TYPES.get(doc.get('doc_type',''),'')} | {doc.get('product','general')} | {doc.get('date','')}</span>",unsafe_allow_html=True)
        with cb:
            if st.button("\U0001f5d1\ufe0f",key=f"dm_{doc['source']}"): checker.delete_company_document(doc["source"]); st.cache_resource.clear(); st.rerun()

# TRAIN REGULATIONS
def page_train_regs():
    user=cu(); api_key=get_api_key()
    st.header("\U0001f4da Train — Regulatory Knowledge Base")
    if not api_key: st.error("Add API key in sidebar."); return
    checker=get_checker(api_key,user["company"])
    s=checker.kb_stats()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Total Chunks",s.get("total_chunks",0)); c2.metric("Regulations",s.get("regulations",0)); c3.metric("Policies",s.get("policies",0)); c4.metric("Agreements",s.get("agreements",0))
    st.divider()
    st.subheader("\u26a1 One-Click Load — Official Regulations")
    PRESETS={"CFPB UDAAP":("https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/","udaap"),"Reg Z (TILA)":("https://www.consumerfinance.gov/rules-policy/regulations/1026/","tila"),"Reg B (ECOA)":("https://www.consumerfinance.gov/rules-policy/regulations/1002/","ecoa"),"Reg V (FCRA)":("https://www.consumerfinance.gov/rules-policy/regulations/1022/","fcra"),"Reg F (FDCPA)":("https://www.consumerfinance.gov/rules-policy/regulations/1006/","collections"),"SCRA Guide":("https://www.consumerfinance.gov/consumer-tools/military-financial-relief/","scra"),"Fed SR 11-7":("https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm","sr117")}
    cols=st.columns(4)
    for i,(name,(url,reg)) in enumerate(PRESETS.items()):
        with cols[i%4]:
            if st.button(f"\U0001f4e5 {name}",key=f"tp_{i}",use_container_width=True):
                with st.spinner("Loading\u2026"):
                    try:
                        import requests; from bs4 import BeautifulSoup
                        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20)
                        soup=BeautifulSoup(r.text,"html.parser")
                        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                        text=(soup.find("main") or soup.body or soup).get_text(separator="\n",strip=True)
                        if len(text)>100: n=checker.ingest_text(text,source=name,regulation=reg,doc_type="regulation"); st.success(f"\u2705 {n} chunks"); st.cache_resource.clear()
                    except Exception as e: st.error(str(e))
    st.divider()
    st.subheader("Upload or Scrape")
    cu2,cu3=st.columns(2)
    with cu2:
        with st.form("reg_up"):
            rf=st.file_uploader("File",type=["txt","pdf","docx"]); rsrc=st.text_input("Source name")
            rr=st.selectbox("Regulation",["general"]+list(REGULATIONS.keys()),format_func=lambda x:f"{x} \u2014 {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
            if st.form_submit_button("\U0001f4e5 Add",type="primary") and rf and rsrc:
                suf=Path(rf.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp: tmp.write(rf.read()); tp=tmp.name
                try: n=checker.ingest_file(tp,regulation=rr,doc_type="regulation",source=rsrc); os.unlink(tp); st.success(f"\u2705 {n} chunks"); st.cache_resource.clear()
                except Exception as e: st.error(f"Failed: {e}")
    with cu3:
        with st.form("reg_url"):
            url_i=st.text_input("URL",placeholder="https://www.consumerfinance.gov/..."); us=st.text_input("Source name")
            ureg=st.selectbox("Regulation",["general"]+list(REGULATIONS.keys()),key="ureg2",format_func=lambda x:f"{x} \u2014 {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
            if st.form_submit_button("\U0001f310 Scrape & Add",type="primary") and url_i and us:
                with st.spinner("Fetching\u2026"):
                    try:
                        import requests; from bs4 import BeautifulSoup
                        r=requests.get(url_i,headers={"User-Agent":"Mozilla/5.0"},timeout=20)
                        soup=BeautifulSoup(r.text,"html.parser")
                        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                        text=(soup.find("main") or soup.body or soup).get_text(separator="\n",strip=True)
                        if len(text)>100: n=checker.ingest_text(text,source=us,regulation=ureg,doc_type="regulation"); st.success(f"\u2705 {n} chunks"); st.cache_resource.clear()
                    except Exception as e: st.error(str(e))
    st.divider(); st.subheader("\U0001f50d Test Retrieval")
    q=st.text_input("Query",placeholder="APR disclosure in advertising")
    if q:
        for c in checker.kb.retrieve(q,top_k=5):
            with st.expander(f"[{c['score']}] {c['source']} \u2014 {c['regulation']}"): st.write(c["text"])

# REG MONITOR
def page_reg_monitor():
    user=cu()
    st.header("\U0001f6f0\ufe0f Regulatory Change Monitor")
    st.caption("Watches government websites for changes and alerts your compliance team.")
    watches=get_reg_watches(user["company"])
    ch,cv=st.columns([3,1])
    with ch: st.info(f"**{len(watches)}** sources monitored")
    with cv:
        if st.button("\u25b6\ufe0f Run Check Now",type="primary",use_container_width=True):
            with st.spinner("Checking\u2026"):
                from monitor.reg_monitor import run_once, _seed_default_watches
                if not watches: _seed_default_watches(user["company"]); watches=get_reg_watches(user["company"])
                results=run_once(user["company"])
                st.success(f"Done: {results['checked']} checked, {results['changed']} changed"); st.rerun()
    st.divider()
    if not watches:
        if st.button("\u26a1 Load all default sources",type="primary"):
            from monitor.reg_monitor import _seed_default_watches
            _seed_default_watches(user["company"]); st.rerun()
    else:
        for w in watches:
            ca,cb=st.columns([4,1])
            with ca: st.markdown(f"**{w['source_name']}** \u00b7 <span style='font-size:12px;color:#6b7280;'>{w['regulation'].upper()} \u00b7 Last: {(w.get('last_checked') or 'Never')[:10]}</span>",unsafe_allow_html=True)
            with cb: st.markdown("\u2705 Active" if w["is_active"] else "\u23f8\ufe0f Paused")
    st.divider()
    st.subheader("\u2795 Add Custom Source")
    with st.form("watch_form"):
        c1,c2=st.columns(2)
        with c1: wu=st.text_input("URL",placeholder="https://www.cfpb.gov/..."); wn=st.text_input("Name",placeholder="CFPB Final Rules")
        with c2: wr=st.selectbox("Regulation",["general"]+list(REGULATIONS.keys()),format_func=lambda x:f"{x} \u2014 {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
        if st.form_submit_button("Add Watch",type="primary") and wu and wn:
            add_reg_watch(user["company"],wr,wu,wn,user["id"])
            st.success(f"\u2705 Now watching: {wn}"); st.rerun()

# ANALYTICS
def page_analytics():
    user=cu(); a=get_analytics(user["company"])
    st.header("\U0001f4c8 Analytics & Reporting")
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Total",a["total_submissions"]); c2.metric("Approved",a["by_status"].get("approved",0))
    c3.metric("Rejected",a["by_status"].get("rejected",0)); c4.metric("Pending",a["pending"]); c5.metric("Conflicts",a["total_conflicts"])
    st.divider()
    cl,cr=st.columns(2)
    with cl:
        st.subheader("By Status")
        for status,cnt in a["by_status"].items():
            icon={"pending":"\U0001f550","approved":"\u2705","rejected":"\u274c","escalated":"\u26a0\ufe0f","in_review":"\U0001f440"}.get(status,"\U0001f4cb")
            pct=int(cnt/max(a["total_submissions"],1)*100)
            st.markdown(f"{icon} **{status.upper().replace('_',' ')}**: {cnt} ({pct}%)"); st.progress(pct/100)
    with cr:
        st.subheader("Top Issues")
        for r in a["top_regulations"]: st.markdown(f'<span class="badge badge-{r["severity"]}">{r["severity"].upper()}</span> **{r["regulation"]}** \u2014 {r["cnt"]}\u00d7',unsafe_allow_html=True)
    st.divider(); st.subheader("\U0001f4e5 Export")
    c1,c2,c3=st.columns(3)
    with c1:
        subs=get_submissions(user["company"])
        st.download_button("\u2b07\ufe0f Submissions (JSON)",data=json.dumps([{"id":s["id"],"title":s["title"],"status":s["status"]} for s in subs],indent=2),file_name="submissions.json",mime="application/json",use_container_width=True)
    with c2: st.download_button("\u2b07\ufe0f Analytics (JSON)",data=json.dumps(a,indent=2),file_name="analytics.json",mime="application/json",use_container_width=True)
    with c3:
        audit=get_audit_log(user["company"],limit=1000)
        st.download_button("\u2b07\ufe0f Audit Log (JSON)",data=json.dumps(audit,indent=2),file_name="audit_log.json",mime="application/json",use_container_width=True)

# AUDIT LOG
def page_audit_log():
    user=cu(); st.header("\U0001f4dc Audit Log")
    logs=get_audit_log(user["company"],limit=200)
    if not logs: st.info("No entries yet.")
    action_icons={"login":"\U0001f510","logout":"\U0001f6aa","submit":"\U0001f4e4","review_decision":"\u2705","mark_false_positive":"\u2611\ufe0f","add_company_memory":"\U0001f3e2","add_reg_watch":"\U0001f6f0\ufe0f","regulatory_change_detected":"\u26a0\ufe0f"}
    for e in logs:
        icon=action_icons.get(e.get("action",""),"\U0001f4cb")
        st.markdown(f"{icon} **{e.get('action','').replace('_',' ').title()}** \u00b7 {e.get('user_email','system')} \u00b7 {e.get('timestamp','')[:16].replace('T',' ')}")
        if e.get("detail"): st.caption(f"  {e['detail']}")
        st.divider()

# SETTINGS
def page_settings():
    user=cu(); st.header("\u2699\ufe0f Settings")
    t1,t2,t3=st.tabs(["\U0001f465 Users","\U0001f514 Notifications","\U0001f3e2 Company"])
    with t1:
        st.subheader("Users")
        for u in get_users(user["company"]):
            ca,cb=st.columns([4,1])
            with ca: st.markdown(f"**{u['name']}** \u00b7 {u['email']}  \n<span style='font-size:12px;color:#6b7280;'>{u['role'].upper()} \u00b7 {u.get('department','')}</span>",unsafe_allow_html=True)
            with cb: st.caption("\u2705 Active" if u["is_active"] else "\u23f8\ufe0f Inactive")
            st.divider()
        st.subheader("Add User")
        with st.form("add_user_f"):
            c1,c2=st.columns(2); 
            with c1: ne=st.text_input("Email"); nn=st.text_input("Name")
            with c2: nr=st.selectbox("Role",["submitter","compliance","legal","admin"]); nd=st.text_input("Department")
            np=st.text_input("Password",type="password")
            if st.form_submit_button("Add User",type="primary") and ne and nn and np:
                try: create_user(ne,nn,nr,user["company"],nd,np); st.success(f"\u2705 Created: {ne}"); st.rerun()
                except Exception as e: st.error(str(e))
    with t2:
        st.subheader("Notification Settings")
        st.text_input("Slack Webhook URL",type="password",value=os.environ.get("SLACK_WEBHOOK_URL",""),placeholder="https://hooks.slack.com/services/\u2026")
        st.text_input("SMTP Host",value=os.environ.get("SMTP_HOST",""),placeholder="smtp.gmail.com")
        st.text_input("SMTP Username",value=os.environ.get("SMTP_USER",""))
        st.text_input("SMTP Password",type="password")
        if st.button("\U0001f9ea Test Slack"):
            from integrations.notifier import send_slack
            ok=send_slack("\U0001f9ea Test notification from Compliance Platform!")
            st.success("\u2705 Sent!") if ok else st.error("\u274c Failed. Check your webhook URL in .env")
        st.info("Add SLACK_WEBHOOK_URL, SMTP_HOST, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL to .env to persist settings.")
    with t3:
        st.markdown(f"**Company:** {user['company']}  \n**Your role:** {user['role'].upper()}")
        st.text_input("App Base URL",value=os.environ.get("APP_BASE_URL","http://localhost:8501"))

# ROUTER
def main():
    user=cu()
    if not user: page_login(); return
    render_sidebar()
    p=st.session_state.page
    routes={"dashboard":page_dashboard,"submit":page_submit,"my_submissions":page_my_submissions,"review_queue":page_review_queue,"all_reviews":page_all_reviews if is_role("compliance","legal","admin") else page_my_submissions,"review_detail":page_review_detail,"company_memory":page_company_memory,"train_regs":page_train_regs,"reg_monitor":page_reg_monitor,"analytics":page_analytics,"audit_log":page_audit_log,"settings":page_settings}
    routes.get(p, page_dashboard)()

def page_all_reviews():
    user=cu(); st.header("\u2705 All Reviews")
    subs=[s for s in get_submissions(user["company"]) if s["status"] in ("approved","rejected","escalated")]
    if not subs: st.info("No reviewed submissions yet."); return
    for s in subs:
        ca,cb,cc=st.columns([3,1,1])
        with ca: st.markdown(f"**{s['title']}**  \n{s.get('submitter_name','?')}")
        with cb: st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper()}</span>',unsafe_allow_html=True)
        with cc:
            if st.button("View",key=f"ar_{s['id']}"): nav("review_detail",view_submission=s["id"])
        st.divider()

main()
