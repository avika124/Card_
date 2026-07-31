FROM python:3.11-slim

# pandoc is required for .docx/.doc text extraction (rag/rag_compliance.py, python_fastapi/routers/*)
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/var/data
EXPOSE 8000

CMD ["uvicorn", "python_fastapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
