"""
streamlit/app.py — ComplyLine v4 (Streamlit Cloud)
Full compliance platform — works on Streamlit Cloud with secrets management.
"""
import os, sys, json, tempfile
from pathlib import Path
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv()

# ── Pull API key from Streamlit secrets if available ──────────────────────────
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

# ── Lazy imports ───────────────────────────────────────────────────────────────
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from rag.company_memory import DOC_TYPES

HAS_DB = False
try:
    from core.database import (
        init_db, authenticate_user, create_user, get_users,
        create_submission, get_submissions, get_submission,
        update_submission_status, save_findings, save_conflicts,
        get_findings, get_conflicts, create_review, get_reviews,
        mark_false_positive, log_action, get_audit_log,
        create_notification, get_notifications, mark_notifications_read,
        add_reg_watch, get_reg_watches, get_analytics,
    )
    init_db()
    HAS_DB = True
except Exception:
    pass

HAS_DOCX = False
try:
    from python_fastapi.docx_generator import generate_compliance_docx
    HAS_DOCX = True
except Exception:
    pass

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ComplyLine — Credit Card Compliance",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
.block-container{padding-top:1.5rem !important;}
[data-testid="stSidebar"]{background:#1C2D4F !important;}
[data-testid="stSidebar"] *{color:white !important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.2)!important;}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;}
.badge-high{background:#FFCCCC;color:#C00000;}
.badge-medium{background:#FFF2CC;color:#BF8F00;}
.badge-low,.badge-pass{background:#E8F5E9;color:#2E7D32;}
.badge-pending{background:#E3F2FD;color:#1565C0;}
.badge-approved{background:#CCFFCC;color:#007000;}
.badge-rejected{background:#FFCCCC;color:#C00000;}
.badge-escalated{background:#FFF2CC;color:#BF8F00;}
.badge-in_review{background:#F3E5F5;color:#6A1B9A;}
.card{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:.75rem;}
.stat-card{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;text-align:center;}
.stat-num{font-size:2rem;font-weight:700;color:#1C2D4F;}
.stat-lbl{font-size:.75rem;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-top:4px;}
.finding-row{border-left:4px solid #e5e7eb;padding:10px 14px;margin:6px 0;border-radius:0 6px 6px 0;background:#fafafa;}
.finding-high{border-left-color:#C00000;background:#fff5f5;}
.finding-medium{border-left-color:#BF8F00;background:#fffbf0;}
.finding-low,.finding-pass{border-left-color:#2E7D32;background:#f0fff4;}
.conflict-box{border-left:4px solid #BF8F00;padding:12px 16px;background:#FFF8E1;border-radius:0 6px 6px 0;margin-bottom:8px;}
.mem-card{background:#F8F0FF;border:1px solid #CE93D8;border-radius:8px;padding:10px 14px;margin-bottom:6px;}
</style>""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "view_submission" not in st.session_state:
    st.session_state.view_submission = None

def nav(page, **kwargs):
    st.session_state.page = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

def cu(): return st.session_state.user
def is_role(*roles): u = cu(); return u and u.get("role") in roles

@st.cache_resource
def get_checker(key, company):
    return RAGComplianceChecker(api_key=key, use_rag=False, company_name=company)

def get_api_key():
    return (st.session_state.get("sidebar_key", "")
            or os.environ.get("ANTHROPIC_API_KEY", ""))

# ── LOGIN ──────────────────────────────────────────────────────────────────────
def page_login():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center"><h1 style="color:#1C2D4F;font-size:2rem;">⚖️ ComplyLine</h1>'
            '<p style="color:#6b7280;">Credit Card Compliance Platform</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        if HAS_DB:
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
            st.markdown(
                '<div style="background:#f0f4ff;border-radius:8px;padding:12px 16px;margin-top:16px;font-size:13px;">'
                '<strong>Demo accounts (password: password123)</strong><br>'
                'admin@company.com &nbsp;·&nbsp; compliance@company.com &nbsp;·&nbsp; '
                'legal@company.com &nbsp;·&nbsp; marketing@company.com'
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            # No DB — simple single-user mode
            with st.form("login_simple"):
                name = st.text_input("Your name", value="Compliance Officer")
                if st.form_submit_button("Enter", type="primary", use_container_width=True):
                    st.session_state.user = {
                        "id": "user1", "name": name,
                        "email": "user@company.com", "role": "admin",
                        "company": "My Company",
                    }
                    st.rerun()

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
def render_sidebar():
    user = cu()
    if not user: return
    with st.sidebar:
        st.markdown(
            f'<div style="padding:8px 0 4px;font-size:18px;font-weight:700;">⚖️ ComplyLine</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div style="font-size:13px;opacity:.9;">{user["name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;opacity:.6;">{user["company"]} · {user["role"].upper()}</div>', unsafe_allow_html=True)
        st.divider()

        pages = [
            ("📊", "Dashboard", "dashboard"),
            ("➕", "Submit Document", "submit"),
            ("📋", "My Submissions", "my_submissions"),
        ]
        if is_role("compliance", "legal", "admin"):
            pages += [
                ("🔍", "Review Queue", "review_queue"),
                ("✅", "All Reviews", "all_reviews"),
            ]
        pages += [
            ("🏢", "Company Memory", "company_memory"),
            ("📚", "Train Regulations", "train_regs"),
            ("🛰️", "Reg Monitor", "reg_monitor"),
        ]
        if is_role("compliance", "legal", "admin"):
            pages += [
                ("📈", "Analytics", "analytics"),
                ("📜", "Audit Log", "audit_log"),
            ]
        if is_role("admin"):
            pages += [("⚙️", "Settings", "settings")]

        for icon, label, page_key in pages:
            active = st.session_state.page == page_key
            if st.button(f"{icon} {label}", key=f"nav_{page_key}", use_container_width=True):
                nav(page_key)

        st.divider()
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        st.text_input(
            "API Key",
            type="password",
            value=env_key,
            key="sidebar_key",
            help="Your Anthropic API key",
        )
        if env_key:
            st.markdown('<div style="font-size:11px;color:#4CAF50;">✅ Key loaded from secrets</div>', unsafe_allow_html=True)

        if st.button("🚪 Sign Out", use_container_width=True):
            if HAS_DB:
                log_action(cu()["id"], cu()["email"], "logout")
            st.session_state.user = None
            st.rerun()

# ── DASHBOARD ──────────────────────────────────────────────────────────────────
def page_dashboard():
    user = cu()
    st.markdown(f"## 👋 Welcome back, {user['name'].split()[0]}")
    st.caption(f"{user['company']} · {datetime.now().strftime('%B %d, %Y')}")

    if HAS_DB:
        a = get_analytics(user["company"])
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, val, lbl in [
            (c1, a["total_submissions"], "Total"),
            (c2, a["pending"], "Pending"),
            (c3, a["by_status"].get("approved", 0), "Approved"),
            (c4, a["by_status"].get("rejected", 0), "Rejected"),
            (c5, a["total_conflicts"], "Conflicts"),
        ]:
            with col:
                st.markdown(
                    f'<div class="stat-card"><div class="stat-num">{val}</div>'
                    f'<div class="stat-lbl">{lbl}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Recent Submissions")
        subs = get_submissions(user["company"])[:8]
        if not subs:
            st.info("No submissions yet — click **Submit Document** to get started.")
        for s in subs:
            findings = get_findings(s["id"])
            high = sum(1 for f in findings if f["severity"] == "high" and not f["is_false_positive"])
            rb = f'<span class="badge badge-high">HIGH</span>' if high else f'<span class="badge badge-pass">PASS</span>'
            sb = f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>'
            st.markdown(
                f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><strong>{s["title"]}</strong><br>'
                f'<span style="font-size:12px;color:#6b7280;">{s.get("submitter_name","?")} · {s["submitted_at"][:10]}</span>'
                f'</div><div>{rb} {sb}</div></div></div>',
                unsafe_allow_html=True,
            )
            if st.button("View →", key=f"db_{s['id']}"):
                nav("review_detail", view_submission=s["id"])
    else:
        st.info("Database not available. Submit documents using the Submit page.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Submit Document", type="primary", use_container_width=True):
                nav("submit")
        with col2:
            if st.button("🏢 Company Memory", use_container_width=True):
                nav("company_memory")

# ── SUBMIT DOCUMENT ────────────────────────────────────────────────────────────
def page_submit():
    user = cu()
    api_key = get_api_key()
    st.header("➕ Submit Document for Compliance Review")
    if not api_key:
        st.error("Add your Anthropic API key in the sidebar.")
        return

    with st.form("sub_form"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Document title *", placeholder="Q2 2025 Freedom Unlimited Email")
            product = st.text_input("Product", placeholder="Freedom Unlimited")
            priority = st.selectbox("Priority", ["normal", "high", "urgent"])
        with c2:
            doc_type = st.selectbox("Document type", list(DOC_TYPES.keys()), format_func=lambda x: DOC_TYPES[x])
            channel = st.selectbox("Channel", ["email","web","print","in-branch","mobile","call-center","general"])

        st.subheader("Content")
        method = st.radio("Input", ["Paste text", "Upload file"], horizontal=True)
        doc_text, doc_name = "", ""
        if method == "Paste text":
            doc_text = st.text_area("Content *", height=180, placeholder="Paste marketing copy, agreement, policy, script...")
            doc_name = "Pasted Text"
        else:
            uf = st.file_uploader("File", type=["txt", "pdf", "docx", "doc"])
            if uf:
                doc_name = uf.name
                suf = Path(uf.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
                    tmp.write(uf.read()); tp = tmp.name
                try:
                    import subprocess
                    from pypdf import PdfReader
                    if suf == ".txt": doc_text = open(tp).read()
                    elif suf == ".pdf": doc_text = "\n\n".join(p.extract_text() or "" for p in PdfReader(tp).pages)
                    elif suf in (".docx", ".doc"):
                        doc_text = subprocess.run(["pandoc", tp, "-t", "plain"], capture_output=True, text=True).stdout
                    os.unlink(tp)
                except Exception as e:
                    st.error(f"Could not extract text: {e}")

        st.subheader("Regulations & Options")
        ca, cb = st.columns(2)
        with ca:
            sel_all = st.checkbox("All regulations", value=True)
            active_regs = [r for r in REGULATIONS if st.checkbox(REGULATIONS[r]["label"], value=sel_all, key=f"sr_{r}")]
        with cb:
            run_conflict = st.checkbox("Check against company memory", value=True)
            st.caption("Upload prior materials in Company Memory to enable conflict detection.")

        submitted = st.form_submit_button("🔍 Submit for Analysis", type="primary", use_container_width=True)

    if submitted:
        if not title or not doc_text.strip() or not active_regs:
            st.error("Title, content, and at least one regulation are required.")
            return
        with st.spinner("Running compliance analysis… 30–60 seconds"):
            try:
                checker = get_checker(api_key, user["company"])
                result = checker.check_text(doc_text, active_regs, product=product or None, run_conflict_check=run_conflict)

                if HAS_DB:
                    sid = create_submission(
                        title=title, document_text=doc_text, document_name=doc_name,
                        doc_type=doc_type, product=product or "general", channel=channel,
                        submitted_by=user["id"], company=user["company"],
                        regulations=active_regs, run_conflict=run_conflict, priority=priority,
                    )
                    save_findings(sid, result.get("findings", []))
                    conflict_data = result.get("conflict_check") or {}
                    save_conflicts(sid, conflict_data.get("conflicts", []))
                    for cu2 in [u for u in get_users(user["company"]) if u["role"] in ("compliance", "legal", "admin")]:
                        create_notification(cu2["id"], "review", f"New: {title}",
                            f"{user['name']} submitted '{title}'. Risk: {result.get('overall_risk','?').upper()}")
                    log_action(user["id"], user["email"], "submit", "submission", sid, title)

                # Show results
                _render_results(result, title)

                if HAS_DB and HAS_DOCX:
                    docx = generate_compliance_docx(result, document_name=title)
                    st.download_button("⬇️ Download DOCX Report", data=docx,
                        file_name=f"compliance_{title[:30]}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

            except Exception as e:
                st.error(f"Analysis failed: {e}")
                import traceback; st.code(traceback.format_exc())

def _render_results(result, title=""):
    findings = result.get("findings", [])
    conflict_data = result.get("conflict_check") or {}
    conflicts = conflict_data.get("conflicts", [])
    overall = result.get("overall_risk", "unknown")
    bgs = {"high":"#FFCCCC","medium":"#FFF2CC","low":"#E8F5E9","pass":"#CCFFCC"}
    st.markdown(
        f'<div style="background:{bgs.get(overall,"#F5F5F5")};padding:1rem 1.5rem;border-radius:8px;margin:1rem 0;">'
        f'<strong style="font-size:16px;">Overall Risk: {overall.upper()}</strong><br>'
        f'{result.get("summary","")}</div>',
        unsafe_allow_html=True,
    )
    counts = {"high":0,"medium":0,"low":0,"pass":0}
    for f in findings: counts[f.get("severity","low")] = counts.get(f.get("severity","low"),0)+1
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("🔴 High", counts["high"]); c2.metric("🟡 Medium", counts["medium"])
    c3.metric("🟠 Low", counts["low"]); c4.metric("🟢 Pass", counts["pass"])
    c5.metric("⚠️ Conflicts", len(conflicts))
    st.divider()
    if findings:
        st.subheader("📋 Regulatory Findings")
        sev_order = {"high":0,"medium":1,"low":2,"pass":3}
        for f in sorted(findings, key=lambda x: sev_order.get(x.get("severity","low"),2)):
            sev = f.get("severity","low")
            with st.expander(f"**{f.get('regulation','')}** — {f.get('issue','')}"):
                st.markdown(f'<span class="badge badge-{sev}">{sev.upper()}</span>', unsafe_allow_html=True)
                st.write(f.get("detail",""))
                if f.get("regulatory_citation"): st.code(f.get("regulatory_citation"))
                if f.get("excerpt"): st.info(f"📌 \"{f['excerpt']}\"")
                if f.get("recommendation"): st.success(f"✅ {f['recommendation']}")
    if conflicts:
        st.divider()
        st.subheader("🏢 Prior Communication Conflicts")
        for c in conflicts:
            sev = c.get("severity","medium")
            with st.expander(f"⚠️ [{sev.upper()}] {c.get('title','')}"):
                col_x, col_y = st.columns(2)
                with col_x:
                    st.markdown("**New document says:**"); st.warning(c.get("new_document_says",""))
                with col_y:
                    st.markdown(f"**Prior says** *(from: {c.get('prior_source','')})*:")
                    st.info(c.get("prior_communication_says",""))
                st.error(c.get("explanation",""))
                st.success(f"✅ Fix: {c.get('recommendation','')}")
    st.download_button("⬇️ findings.json", data=json.dumps(result,indent=2),
        file_name="findings.json", mime="application/json")

# ── MY SUBMISSIONS ─────────────────────────────────────────────────────────────
def page_my_submissions():
    user = cu()
    st.header("📋 My Submissions")
    if not HAS_DB:
        st.info("Database not available in this deployment mode.")
        return
    subs = get_submissions(user["company"], submitted_by=user["id"])
    if not subs:
        st.info("No submissions yet.")
        if st.button("Submit your first document", type="primary"): nav("submit")
        return
    for s in subs:
        ca,cb,cc,cd = st.columns([3,1,1,1])
        with ca:
            st.markdown(f"**{s['title']}**  \n{s['submitted_at'][:10]} · {s.get('product','general')}")
        with cb:
            st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>', unsafe_allow_html=True)
        with cc:
            findings = get_findings(s["id"])
            high = sum(1 for f in findings if f["severity"]=="high")
            st.markdown("🔴 High risk" if high else "✅ OK")
        with cd:
            if st.button("View", key=f"ms_{s['id']}"): nav("review_detail", view_submission=s["id"])
        st.divider()

# ── REVIEW QUEUE ───────────────────────────────────────────────────────────────
def page_review_queue():
    user = cu()
    st.header("🔍 Review Queue")
    if not HAS_DB:
        st.info("Database not available.")
        return
    sf = st.selectbox("Status", ["pending","in_review","all"])
    subs = get_submissions(user["company"], status=None if sf=="all" else sf)
    if not subs:
        st.info("Queue is empty.")
        return
    for s in subs:
        findings = get_findings(s["id"])
        high = sum(1 for f in findings if f["severity"]=="high" and not f["is_false_positive"])
        ca,cb,cc,cd = st.columns([3,1,1,1])
        with ca:
            st.markdown(f"**{'🚨 ' if s.get('priority') in ('urgent','high') or high else ''}{s['title']}**  \n{s.get('submitter_name','?')}")
        with cb:
            st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper().replace("_"," ")}</span>', unsafe_allow_html=True)
        with cc:
            st.write(f"🔴 {high} high" if high else "✅ Clean")
        with cd:
            if st.button("Review →", key=f"rq_{s['id']}", type="primary"): nav("review_detail", view_submission=s["id"])
        st.divider()

# ── REVIEW DETAIL ──────────────────────────────────────────────────────────────
def page_review_detail():
    sid = st.session_state.get("view_submission")
    if not sid or not HAS_DB: nav("review_queue"); return
    sub = get_submission(sid)
    if not sub: st.error("Not found."); return
    user = cu()
    findings = get_findings(sid); conflicts = get_conflicts(sid); reviews = get_reviews(sid)
    ch,cv = st.columns([3,1])
    with ch:
        st.markdown(f"## {sub['title']}")
        st.caption(f"{sub.get('submitter_name','?')} · {sub['submitted_at'][:16].replace('T',' ')} · {DOC_TYPES.get(sub.get('doc_type',''),'')}")
    with cv:
        st.markdown(f'<span class="badge badge-{sub["status"]}" style="font-size:14px;padding:6px 14px;">{sub["status"].upper().replace("_"," ")}</span>', unsafe_allow_html=True)
        if HAS_DOCX:
            full = {"findings": findings, "conflict_check": {"conflicts": conflicts}}
            docx = generate_compliance_docx(full, document_name=sub["title"])
            st.download_button("⬇️ DOCX", data=docx, file_name=f"report_{sid[:8]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    high_f = sum(1 for f in findings if f["severity"]=="high" and not f["is_false_positive"])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("High Risk", high_f); c2.metric("Medium", sum(1 for f in findings if f["severity"]=="medium" and not f["is_false_positive"]))
    c3.metric("Conflicts", len(conflicts)); c4.metric("Reviews", len(reviews))
    st.divider()
    tf,tc,tr,td,th = st.tabs([f"📋 Findings ({len(findings)})",f"🏢 Conflicts ({len(conflicts)})","✅ Review","📄 Document",f"📜 History ({len(reviews)})"])
    sev_order = {"high":0,"medium":1,"low":2,"pass":3}
    with tf:
        if not findings: st.success("No regulatory findings.")
        for f in sorted(findings, key=lambda x: sev_order.get(x["severity"],2)):
            sev = f["severity"]; fp = f["is_false_positive"]
            with st.expander(f"{'☑️' if fp else ''} {f['regulation']} — {f['issue']}"):
                st.markdown(f'<span class="badge badge-{sev}">{sev.upper()}</span>', unsafe_allow_html=True)
                st.write(f["detail"])
                if f.get("regulatory_citation"): st.code(f["regulatory_citation"])
                if f.get("excerpt"): st.info(f"📌 \"{f['excerpt']}\"")
                if f.get("recommendation"): st.success(f["recommendation"])
                if is_role("compliance","legal","admin") and not fp:
                    if st.button("Mark false positive", key=f"fp_{f['id']}"):
                        mark_false_positive(f["id"],"findings",user["id"]); st.rerun()
    with tc:
        if not conflicts: st.success("No conflicts with prior communications.")
        for c in conflicts:
            sev = c["severity"]; fp = c["is_false_positive"]
            with st.expander(f"[{sev.upper()}] {c['title']}"):
                ca2,cb2 = st.columns(2)
                with ca2: st.markdown("**New doc says:**"); st.warning(c["new_doc_says"])
                with cb2: st.markdown(f"**Prior says** *(from: {c['prior_source']})*:"); st.info(c["prior_says"])
                st.error(c["explanation"]); st.success(c["recommendation"])
                if is_role("compliance","legal","admin") and not fp:
                    if st.button("Mark false positive", key=f"cfp_{c['id']}"):
                        mark_false_positive(c["id"],"conflicts",user["id"]); st.rerun()
    with tr:
        if is_role("compliance","legal","admin"):
            with st.form("rev_form"):
                decision = st.selectbox("Decision",["approved","rejected","escalated","in_review"],
                    format_func=lambda x: {"approved":"✅ Approve","rejected":"❌ Reject","escalated":"⚠️ Escalate","in_review":"👀 In Review"}[x])
                notes = st.text_area("Notes",height=100)
                if st.form_submit_button("Submit Decision",type="primary"):
                    if decision in ("rejected","escalated") and not notes:
                        st.error("Notes required for reject/escalate.")
                    else:
                        create_review(sid,user["id"],decision,notes)
                        sub_user = next((u for u in get_users(sub["company"]) if u["id"]==sub["submitted_by"]),None)
                        if sub_user:
                            create_notification(sub_user["id"],"decision",f"Decision: {decision.upper()}",
                                f"'{sub['title']}' was {decision}. {notes[:80]}")
                        log_action(user["id"],user["email"],"review_decision","submission",sid,decision)
                        st.success(f"Decision: {decision.upper()}"); st.rerun()
        else:
            if reviews:
                r = reviews[0]
                st.markdown(f"**Latest:** {r['decision'].upper()} by {r.get('reviewer_name','?')}")
                if r.get("notes"): st.write(r["notes"])
            else: st.info("No decision yet.")
    with td:
        st.text_area("Document", value=sub["document_text"], height=400, disabled=True)
    with th:
        if not reviews: st.info("No history.")
        for r in reviews:
            icon = {"approved":"✅","rejected":"❌","escalated":"⚠️","in_review":"👀"}.get(r["decision"],"📋")
            st.markdown(f"{icon} **{r['decision'].upper()}** by {r.get('reviewer_name','?')} · {r['reviewed_at'][:16].replace('T',' ')}")
            if r.get("notes"): st.write(r["notes"])
            st.divider()

# ── ALL REVIEWS ────────────────────────────────────────────────────────────────
def page_all_reviews():
    user = cu(); st.header("✅ All Reviews")
    if not HAS_DB: st.info("Database not available."); return
    subs = [s for s in get_submissions(user["company"]) if s["status"] in ("approved","rejected","escalated")]
    if not subs: st.info("No reviewed submissions yet."); return
    for s in subs:
        ca,cb,cc = st.columns([3,1,1])
        with ca: st.markdown(f"**{s['title']}**  \n{s.get('submitter_name','?')}")
        with cb: st.markdown(f'<span class="badge badge-{s["status"]}">{s["status"].upper()}</span>',unsafe_allow_html=True)
        with cc:
            if st.button("View", key=f"ar_{s['id']}"): nav("review_detail",view_submission=s["id"])
        st.divider()

# ── COMPANY MEMORY ─────────────────────────────────────────────────────────────
def page_company_memory():
    user = cu(); api_key = get_api_key()
    st.header("🏢 Company Memory")
    st.markdown("Upload prior marketing, policies, agreements, scripts — every new submission is checked against these for contradictions.")
    if not api_key: st.error("Add API key in sidebar."); return
    checker = get_checker(api_key, user["company"])
    ms = checker.memory_stats()
    cols = st.columns(7)
    for i,(dt,label) in enumerate(DOC_TYPES.items()): cols[i].metric(label,ms.get(dt,0))
    st.divider()
    with st.form("mem_form"):
        c1,c2 = st.columns(2)
        with c1:
            mf = st.file_uploader("File",type=["txt","pdf","docx","doc","md"])
            msrc = st.text_input("Name *",placeholder="Q2 2024 Email Campaign")
            mdate = st.text_input("Date",placeholder="2024-06-01")
        with c2:
            mtype = st.selectbox("Type",list(DOC_TYPES.keys()),format_func=lambda x:DOC_TYPES[x])
            mprod = st.text_input("Product",placeholder="Freedom Unlimited")
            mver = st.text_input("Version",placeholder="v2.1")
        paste = st.text_area("Or paste text directly",height=100)
        if st.form_submit_button("📥 Add to Company Memory",type="primary") and msrc.strip():
            with st.spinner("Indexing…"):
                try:
                    if mf:
                        suf=Path(mf.name).suffix.lower()
                        with tempfile.NamedTemporaryFile(suffix=suf,delete=False) as tmp:
                            tmp.write(mf.read()); tp=tmp.name
                        n=checker.add_company_file(tp,doc_type=mtype,source=msrc,product=mprod or "general",date=mdate,version=mver)
                        os.unlink(tp)
                    elif paste.strip():
                        n=checker.add_company_document(paste,source=msrc,doc_type=mtype,product=mprod or "general",date=mdate,version=mver)
                    else:
                        st.warning("Upload a file or paste text."); st.stop()
                    if HAS_DB: log_action(user["id"],user["email"],"add_company_memory","memory",msrc)
                    st.success(f"✅ '{msrc}' — {n} chunks indexed"); st.cache_resource.clear()
                except Exception as e: st.error(f"Failed: {e}")
    st.divider()
    st.subheader("📋 Stored Documents")
    docs = checker.memory_documents()
    if not docs: st.info("No documents stored yet.")
    for doc in docs:
        ca,cb = st.columns([5,1])
        with ca:
            st.markdown(f"📄 **{doc['source']}** · <span style='color:#6b7280;font-size:12px;'>{DOC_TYPES.get(doc.get('doc_type',''),'?')} | {doc.get('product','general')} | {doc.get('date','')}</span>",unsafe_allow_html=True)
        with cb:
            if st.button("🗑️",key=f"dm_{doc['source']}"):
                checker.delete_company_document(doc["source"]); st.cache_resource.clear(); st.rerun()

# ── TRAIN REGULATIONS ──────────────────────────────────────────────────────────
def page_train_regs():
    user = cu(); api_key = get_api_key()
    st.header("📚 Train — Regulatory Knowledge Base")
    if not api_key: st.error("Add API key in sidebar."); return
    checker = get_checker(api_key, user["company"])
    s = checker.kb_stats()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Chunks",s.get("total_chunks",0)); c2.metric("Regulations",s.get("regulations",0))
    c3.metric("Policies",s.get("policies",0)); c4.metric("Agreements",s.get("agreements",0))
    st.divider()
    st.subheader("⚡ One-Click Load Official Regulations")
    PRESETS = {
        "CFPB UDAAP":("https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/","udaap"),
        "Reg Z (TILA)":("https://www.consumerfinance.gov/rules-policy/regulations/1026/","tila"),
        "Reg B (ECOA)":("https://www.consumerfinance.gov/rules-policy/regulations/1002/","ecoa"),
        "Reg V (FCRA)":("https://www.consumerfinance.gov/rules-policy/regulations/1022/","fcra"),
        "Reg F (FDCPA)":("https://www.consumerfinance.gov/rules-policy/regulations/1006/","collections"),
        "SCRA Guide":("https://www.consumerfinance.gov/consumer-tools/military-financial-relief/","scra"),
        "Fed SR 11-7":("https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm","sr117"),
    }
    cols = st.columns(4)
    for i,(name,(url,reg)) in enumerate(PRESETS.items()):
        with cols[i%4]:
            if st.button(f"📥 {name}",key=f"tp_{i}",use_container_width=True):
                with st.spinner(f"Loading {name}…"):
                    try:
                        import requests; from bs4 import BeautifulSoup
                        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20)
                        soup=BeautifulSoup(r.text,"html.parser")
                        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
                        text=(soup.find("main") or soup.body or soup).get_text(separator="\n",strip=True)
                        if len(text)>100:
                            n=checker.ingest_text(text,source=name,regulation=reg,doc_type="regulation")
                            st.success(f"✅ {n} chunks"); st.cache_resource.clear()
                    except Exception as e: st.error(str(e))

# ── REG MONITOR ────────────────────────────────────────────────────────────────
def page_reg_monitor():
    user = cu(); st.header("🛰️ Regulatory Change Monitor")
    st.caption("Watches government websites for changes and alerts your compliance team.")
    if not HAS_DB:
        st.info("Regulatory monitor requires database. Running in demo mode.")
        st.markdown("""
        **Sources monitored when enabled:**
        - CFPB: Reg Z, Reg B, Reg V, FDCPA, UDAAP, SCRA
        - Federal Reserve: SR 11-7
        - FFIEC: BSA/AML Manual
        - OCC: Comptroller Handbook, Bulletins
        - FDIC: Financial Institution Letters
        - PCI SSC: DSS v4.0
        """)
        return
    watches = get_reg_watches(user["company"])
    col_i, col_r = st.columns([3,1])
    with col_i: st.info(f"**{len(watches)}** sources monitored")
    with col_r:
        if st.button("▶️ Run Check Now",type="primary",use_container_width=True):
            with st.spinner("Checking…"):
                from monitor.reg_monitor import run_once, _seed_default_watches
                if not watches: _seed_default_watches(user["company"])
                results = run_once(user["company"])
                st.success(f"Done: {results['checked']} checked, {results['changed']} changed")
                st.rerun()
    if not watches:
        if st.button("⚡ Load all default sources",type="primary"):
            from monitor.reg_monitor import _seed_default_watches
            _seed_default_watches(user["company"]); st.rerun()
    for w in watches:
        ca,cb = st.columns([4,1])
        with ca:
            st.markdown(f"**{w['source_name']}** · <span style='font-size:12px;color:#6b7280;'>{w['regulation'].upper()} · Last: {(w.get('last_checked') or 'Never')[:10]}</span>",unsafe_allow_html=True)
        with cb: st.markdown("✅ Active" if w["is_active"] else "⏸️ Paused")
    st.divider()
    st.subheader("➕ Add Custom Source")
    with st.form("watch_form"):
        c1,c2 = st.columns(2)
        with c1: wu=st.text_input("URL"); wn=st.text_input("Name")
        with c2: wr=st.selectbox("Regulation",["general"]+list(REGULATIONS.keys()),format_func=lambda x:f"{x} — {REGULATIONS[x]['label']}" if x in REGULATIONS else x)
        if st.form_submit_button("Add Watch",type="primary") and wu and wn:
            add_reg_watch(user["company"],wr,wu,wn,user["id"])
            st.success(f"✅ Now watching: {wn}"); st.rerun()

# ── ANALYTICS ──────────────────────────────────────────────────────────────────
def page_analytics():
    user = cu(); st.header("📈 Analytics & Reporting")
    if not HAS_DB: st.info("Analytics requires database."); return
    a = get_analytics(user["company"])
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total",a["total_submissions"]); c2.metric("Approved",a["by_status"].get("approved",0))
    c3.metric("Rejected",a["by_status"].get("rejected",0)); c4.metric("Pending",a["pending"]); c5.metric("Conflicts",a["total_conflicts"])
    st.divider()
    cl,cr = st.columns(2)
    with cl:
        st.subheader("By Status")
        for status,cnt in a["by_status"].items():
            icon={"pending":"🕐","approved":"✅","rejected":"❌","escalated":"⚠️","in_review":"👀"}.get(status,"📋")
            pct=int(cnt/max(a["total_submissions"],1)*100)
            st.markdown(f"{icon} **{status.upper().replace('_',' ')}**: {cnt} ({pct}%)")
            st.progress(pct/100)
    with cr:
        st.subheader("Top Issues")
        for r in a["top_regulations"]:
            st.markdown(f'<span class="badge badge-{r["severity"]}">{r["severity"].upper()}</span> **{r["regulation"]}** — {r["cnt"]}×',unsafe_allow_html=True)
    st.divider()
    col_e1,col_e2,col_e3 = st.columns(3)
    subs = get_submissions(user["company"])
    with col_e1:
        export_data=[{"id":s["id"],"title":s["title"],"status":s["status"]} for s in subs]
        st.download_button("⬇️ Submissions (JSON)",data=json.dumps(export_data,indent=2),file_name="submissions.json",mime="application/json",use_container_width=True)
    with col_e2: st.download_button("⬇️ Analytics (JSON)",data=json.dumps(a,indent=2),file_name="analytics.json",mime="application/json",use_container_width=True)
    with col_e3:
        audit=get_audit_log(user["company"],limit=1000)
        st.download_button("⬇️ Audit Log (JSON)",data=json.dumps(audit,indent=2),file_name="audit_log.json",mime="application/json",use_container_width=True)

# ── AUDIT LOG ──────────────────────────────────────────────────────────────────
def page_audit_log():
    user = cu(); st.header("📜 Audit Log")
    if not HAS_DB: st.info("Audit log requires database."); return
    logs = get_audit_log(user["company"],limit=200)
    if not logs: st.info("No entries yet."); return
    icons={"login":"🔐","logout":"🚪","submit":"📤","review_decision":"✅","mark_false_positive":"☑️","add_company_memory":"🏢","add_reg_watch":"🛰️","regulatory_change_detected":"⚠️"}
    for e in logs:
        icon=icons.get(e.get("action",""),"📋")
        st.markdown(f"{icon} **{e.get('action','').replace('_',' ').title()}** · {e.get('user_email','system')} · {e.get('timestamp','')[:16].replace('T',' ')}")
        if e.get("detail"): st.caption(f"  {e['detail']}")
        st.divider()

# ── SETTINGS ───────────────────────────────────────────────────────────────────
def page_settings():
    user = cu(); st.header("⚙️ Settings")
    if not is_role("admin"): st.error("Admin only."); return
    tab_u, tab_n = st.tabs(["👥 Users","🔔 Notifications"])
    with tab_u:
        if HAS_DB:
            st.subheader("Users")
            for u in get_users(user["company"]):
                ca,cb=st.columns([4,1])
                with ca: st.markdown(f"**{u['name']}** · {u['email']}  \n<span style='font-size:12px;color:#6b7280;'>{u['role'].upper()}</span>",unsafe_allow_html=True)
                with cb: st.caption("✅" if u["is_active"] else "⏸️")
                st.divider()
            st.subheader("Add User")
            with st.form("add_user"):
                c1,c2=st.columns(2); 
                with c1: ne=st.text_input("Email"); nn=st.text_input("Name")
                with c2: nr=st.selectbox("Role",["submitter","compliance","legal","admin"]); nd=st.text_input("Department")
                np=st.text_input("Password",type="password")
                if st.form_submit_button("Add User",type="primary") and ne and nn and np:
                    try: create_user(ne,nn,nr,user["company"],nd,np); st.success(f"✅ Created: {ne}"); st.rerun()
                    except Exception as e: st.error(str(e))
    with tab_n:
        st.text_input("Slack Webhook URL",type="password",placeholder="https://hooks.slack.com/services/…")
        st.text_input("SMTP Host",placeholder="smtp.gmail.com")
        st.text_input("From Email",placeholder="compliance@company.com")
        st.info("Add SLACK_WEBHOOK_URL, SMTP_HOST, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL to Streamlit Secrets.")

# ── ROUTER ─────────────────────────────────────────────────────────────────────
def main():
    user = cu()
    if not user: page_login(); return
    render_sidebar()
    p = st.session_state.page
    routes = {
        "dashboard":       page_dashboard,
        "submit":          page_submit,
        "my_submissions":  page_my_submissions,
        "review_queue":    page_review_queue,
        "all_reviews":     page_all_reviews,
        "review_detail":   page_review_detail,
        "company_memory":  page_company_memory,
        "train_regs":      page_train_regs,
        "reg_monitor":     page_reg_monitor,
        "analytics":       page_analytics,
        "audit_log":       page_audit_log,
        "settings":        page_settings,
    }
    routes.get(p, page_dashboard)()

main()
