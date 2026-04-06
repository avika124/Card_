"""
app.py — Streamlit Credit Card Compliance Checker Agent
Run: streamlit run app.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Add parent for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent / "python-fastapi"))
from compliance import check_text, check_image, check_file, REGULATIONS
from docx_generator import generate_compliance_docx

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Card Compliance Checker",
    page_icon="⚖️",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.severity-high   { background:#FFCCCC; padding:4px 12px; border-radius:12px; font-weight:600; color:#C00000; display:inline-block; }
.severity-medium { background:#FFF2CC; padding:4px 12px; border-radius:12px; font-weight:600; color:#BF8F00; display:inline-block; }
.severity-low    { background:#E8F5E9; padding:4px 12px; border-radius:12px; font-weight:600; color:#2E7D32; display:inline-block; }
.severity-pass   { background:#CCFFCC; padding:4px 12px; border-radius:12px; font-weight:600; color:#007000; display:inline-block; }
.stat-box        { text-align:center; padding:1rem; border-radius:8px; }
.finding-card    { border:1px solid #e0e0e0; border-radius:8px; padding:1rem; margin-bottom:0.75rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚖️ Credit Card Compliance Checker")
st.caption("AI-powered regulatory analysis · Powered by Anthropic Claude")

# ── Sidebar — Regulation selection ───────────────────────────────────────────
with st.sidebar:
    st.header("Regulations")
    st.caption("Select frameworks to check against")

    select_all = st.checkbox("Select all", value=True)

    selected_regs = {}
    for reg_id, reg_info in REGULATIONS.items():
        default = select_all
        selected_regs[reg_id] = st.checkbox(
            f"**{reg_info['label']}**  \n{reg_info['description']}",
            value=default,
            key=f"reg_{reg_id}"
        )

    active_regs = [rid for rid, checked in selected_regs.items() if checked]

    st.divider()
    st.caption("Configure API key if not set in .env")
    api_key_input = st.text_input("ANTHROPIC_API_KEY", type="password",
                                   value=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── Input tabs ────────────────────────────────────────────────────────────────
tab_paste, tab_file, tab_image = st.tabs(["📋 Paste Text", "📄 Upload File", "🖼️ Upload Image"])

input_ready = False
input_type = None
input_data = None

with tab_paste:
    text_input = st.text_area(
        "Paste your document, policy, marketing copy, or credit card content here",
        height=200,
        placeholder="Paste credit card terms, marketing language, collection scripts, policy documents..."
    )
    if text_input.strip():
        input_ready = True
        input_type = "text"
        input_data = text_input

with tab_file:
    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["txt", "pdf", "docx", "doc"],
        help="Supported: TXT, PDF, DOCX, DOC"
    )
    if uploaded_file:
        input_ready = True
        input_type = "file"
        input_data = uploaded_file

with tab_image:
    uploaded_image = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        help="Claude will read text from the image and check it",
        key="image_uploader"
    )
    if uploaded_image:
        st.image(uploaded_image, use_column_width=True)
        input_ready = True
        input_type = "image"
        input_data = uploaded_image

# ── Run button ────────────────────────────────────────────────────────────────
st.divider()
col_btn, col_status = st.columns([1, 3])
with col_btn:
    run_btn = st.button(
        "🔍 Run Compliance Check",
        type="primary",
        disabled=not input_ready or not active_regs,
        use_container_width=True,
    )

if not active_regs:
    st.warning("Please select at least one regulation in the sidebar.")

# ── Run check ─────────────────────────────────────────────────────────────────
if run_btn and input_ready and active_regs:
    api_key = api_key_input or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY is required. Set it in .env or enter it in the sidebar.")
        st.stop()

    with st.spinner(f"Analyzing against {len(active_regs)} regulation frameworks…"):
        try:
            if input_type == "text":
                result = check_text(input_data, active_regs, api_key)
                original_excerpt = input_data[:500]

            elif input_type == "file":
                suffix = Path(uploaded_file.name).suffix.lower()
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                result = check_file(tmp_path, active_regs, api_key)
                original_excerpt = ""
                os.unlink(tmp_path)

            elif input_type == "image":
                image_bytes = uploaded_image.read()
                result = check_image(image_bytes, uploaded_image.type, active_regs, api_key)
                original_excerpt = ""

            st.session_state["result"] = result
            st.session_state["original_excerpt"] = original_excerpt
            st.session_state["doc_name"] = getattr(input_data, "name", "Analyzed Document")

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

# ── Results ───────────────────────────────────────────────────────────────────
if "result" in st.session_state:
    result = st.session_state["result"]
    findings = result.get("findings", [])

    # Overall risk banner
    overall = result.get("overall_risk", "unknown")
    color_map = {"high": "#FFCCCC", "medium": "#FFF2CC", "low": "#E8F5E9", "pass": "#CCFFCC"}
    st.markdown(f"""
    <div style="background:{color_map.get(overall,'#F5F5F5')};padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem;">
        <strong>Overall Risk: {overall.upper()}</strong><br>
        {result.get('summary','')}
    </div>""", unsafe_allow_html=True)

    # Stats
    counts = {"high": 0, "medium": 0, "low": 0, "pass": 0}
    for f in findings:
        counts[f.get("severity", "low")] = counts.get(f.get("severity", "low"), 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 High Risk",   counts["high"])
    c2.metric("🟡 Medium Risk", counts["medium"])
    c3.metric("🟠 Low Risk",    counts["low"])
    c4.metric("🟢 Passing",     counts["pass"])

    st.divider()
    st.subheader("Findings")

    order = {"high": 0, "medium": 1, "low": 2, "pass": 3}
    sorted_findings = sorted(findings, key=lambda f: order.get(f.get("severity","low"), 2))

    for f in sorted_findings:
        sev = f.get("severity", "low")
        with st.expander(f"**{f.get('regulation','')}** — {f.get('issue','')}"):
            st.markdown(f'<span class="severity-{sev}">{sev.upper()}</span>', unsafe_allow_html=True)
            st.write(f.get("detail", ""))
            if f.get("excerpt"):
                st.info(f"📌 **Excerpt:** *\"{f['excerpt']}\"*")
            if f.get("recommendation"):
                st.success(f"✅ **Recommendation:** {f['recommendation']}")

    # ── Download DOCX ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Export")

    if st.button("📥 Generate Color-Coded DOCX Report"):
        with st.spinner("Building Word document…"):
            docx_bytes = generate_compliance_docx(
                findings_result=result,
                document_name=st.session_state.get("doc_name", "Analyzed Document"),
                original_text_excerpt=st.session_state.get("original_excerpt", ""),
            )
        st.download_button(
            label="⬇️ Download compliance_report.docx",
            data=docx_bytes,
            file_name="compliance_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # Raw JSON
    with st.expander("🔧 Raw JSON findings"):
        st.json(result)
