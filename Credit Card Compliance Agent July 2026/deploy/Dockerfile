# Dockerfile — full Credit Card Compliance Agent
#
# Covers every module: compliance_engine, consistency_checker, revenue_optimizer,
# web_scraper, regulatory_monitor, daily_scanner, report_generator, app.
#
# Python is pinned to 3.11. The agent has been compiled under both 3.10 and 3.14;
# 3.14 is too new for several of these dependencies and 3.10 is past its most
# convenient support window, so 3.11 is the version to standardise on.

FROM python:3.11-slim

WORKDIR /app

# pandoc  → DOCX text extraction
# curl    → healthcheck
# fonts   → PyMuPDF text extraction on PDFs with embedded fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data directories live on the mounted disk so the scanner and the UI share
# state, and so a redeploy does not wipe scan history or the reference corpus.
ENV DATA_DIR=/var/data
RUN mkdir -p /var/data/input/marketing_copy \
             /var/data/input/policy_documents \
             /var/data/scraping_info \
             /var/data/regulatory_updates \
             /var/data/alerts \
             /var/data/output

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
