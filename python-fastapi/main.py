"""python-fastapi/main.py — RAG-Enhanced FastAPI Compliance Checker Agent v2.0"""
import os, json, sys, tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import io
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from python_fastapi.docx_generator import generate_compliance_docx
from python_fastapi.models import ComplianceRequest, ComplianceResponse
load_dotenv()

app = FastAPI(title="Credit Card Compliance Checker (RAG)", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_checker(): return RAGComplianceChecker(use_rag=True)

@app.get("/")
def root(): return {"version":"2.0.0","rag_enabled":True,"endpoints":["POST /check/text","POST /check/file","POST /check/image","POST /check/export","POST /docx","GET /kb/stats","GET /kb/sources","POST /kb/ingest/text","POST /kb/ingest/file","POST /kb/ingest/url","DELETE /kb/source/{name}","GET /kb/retrieve"]}

@app.get("/regulations")
def list_regs(): return {"regulations": REGULATIONS}

@app.post("/check/text")
async def check_text_ep(request: ComplianceRequest):
    try: return get_checker().check_text(request.text, request.regulations)
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/check/file")
async def check_file_ep(file: UploadFile=File(...), regulations: str=Form(...)):
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    suffix = Path(file.filename or "upload").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read()); tp=tmp.name
    try: return JSONResponse(get_checker().check_file(tp, reg_ids))
    except Exception as e: raise HTTPException(500, str(e))
    finally: os.unlink(tp)

@app.post("/check/image")
async def check_image_ep(file: UploadFile=File(...), regulations: str=Form(...)):
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    img = await file.read()
    try: return JSONResponse(get_checker().check_image(img, file.content_type or "image/png", reg_ids))
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/check/export")
async def check_export(file: UploadFile=File(...), regulations: str=Form(...)):
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    suf = Path(file.filename or "upload").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
        tmp.write(await file.read()); tp=tmp.name
    try:
        result = get_checker().check_file(tp, reg_ids)
        docx = generate_compliance_docx(result, document_name=file.filename or "Document")
        return StreamingResponse(io.BytesIO(docx), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition":'attachment; filename="compliance_report.docx"'})
    finally: os.unlink(tp)

@app.post("/docx")
async def gen_docx(findings: str=Form(...), document_name: Optional[str]=Form("Document"), original_excerpt: Optional[str]=Form("")):
    try: fd = json.loads(findings)
    except: raise HTTPException(400,"Invalid JSON")
    docx = generate_compliance_docx(fd, document_name=document_name, original_text_excerpt=original_excerpt or "")
    return StreamingResponse(io.BytesIO(docx), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition":'attachment; filename="compliance_report.docx"'})

@app.post("/kb/ingest/text")
async def kb_text(text: str=Form(...), source: str=Form(...), regulation: str=Form("general"), doc_type: str=Form("regulation")):
    try: n=get_checker().ingest_text(text,source=source,regulation=regulation,doc_type=doc_type); return {"status":"ok","chunks_added":n}
    except Exception as e: raise HTTPException(500,str(e))

@app.post("/kb/ingest/file")
async def kb_file(file: UploadFile=File(...), source: Optional[str]=Form(None), regulation: str=Form("general"), doc_type: str=Form("regulation")):
    suf=Path(file.filename or "upload").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
        tmp.write(await file.read()); tp=tmp.name
    try:
        src=source or Path(file.filename or "upload").stem
        n=get_checker().ingest_file(tp, regulation=regulation, doc_type=doc_type, source=src)
        return {"status":"ok","chunks_added":n,"source":src}
    except Exception as e: raise HTTPException(500,str(e))
    finally: os.unlink(tp)

@app.post("/kb/ingest/url")
async def kb_url(url: str=Form(...), source: str=Form(...), regulation: str=Form("general"), doc_type: str=Form("regulation")):
    try:
        import requests; from bs4 import BeautifulSoup
        resp=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20); resp.raise_for_status()
        soup=BeautifulSoup(resp.text,"html.parser")
        for tag in soup.find_all(["script","style","nav","footer"]): tag.decompose()
        text=(soup.find("main") or soup.body or soup).get_text(separator="\n", strip=True)
        if len(text)<100: raise HTTPException(422,"Too little text from URL")
        n=get_checker().ingest_text(text, source=source, regulation=regulation, doc_type=doc_type)
        return {"status":"ok","chunks_added":n,"chars_fetched":len(text)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/kb/stats")
def kb_stats(): return get_checker().kb_stats()

@app.get("/kb/sources")
def kb_sources(): return {"sources": get_checker().kb_sources()}

@app.delete("/kb/source/{source_name}")
def kb_delete(source_name: str):
    n=get_checker().kb.delete_source(source_name)
    return {"status":"deleted","chunks_removed":n}

@app.get("/kb/retrieve")
def kb_retrieve(q: str, regulation: Optional[str]=None, top_k: int=5):
    return {"query":q,"results":get_checker().kb.retrieve(q, regulation=regulation, top_k=top_k)}
