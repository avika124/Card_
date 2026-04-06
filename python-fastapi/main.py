"""
main.py — FastAPI Credit Card Compliance Checker Agent
"""

import os
import json
import tempfile
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import io
from dotenv import load_dotenv

from compliance import check_text, check_image, check_file, REGULATIONS
from docx_generator import generate_compliance_docx
from models import ComplianceRequest, ComplianceResponse

load_dotenv()

app = FastAPI(
    title="Credit Card Compliance Checker Agent",
    description="AI-powered compliance analysis against UDAAP, TILA/Reg Z, ECOA, FCRA, BSA/AML, PCI DSS, SCRA, Collections, and SR 11-7",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "Credit Card Compliance Checker Agent",
        "version": "1.0.0",
        "endpoints": {
            "POST /check/text":  "Check plain text",
            "POST /check/file":  "Check uploaded file (PDF, DOCX, TXT, image)",
            "POST /check/image": "Check image (OCR + compliance)",
            "GET  /regulations": "List available regulations",
            "POST /docx":        "Generate color-coded DOCX from findings JSON",
        }
    }


@app.get("/regulations")
def list_regulations():
    return {"regulations": REGULATIONS}


@app.post("/check/text", response_model=ComplianceResponse)
async def check_text_endpoint(request: ComplianceRequest):
    """
    Check plain text content against selected regulations.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text content is required.")
    if not request.regulations:
        raise HTTPException(status_code=400, detail="At least one regulation must be selected.")

    try:
        result = check_text(request.text, request.regulations)
        return result
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Claude returned invalid JSON. Try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/check/file")
async def check_file_endpoint(
    file: UploadFile = File(...),
    regulations: str = Form(...),  # comma-separated list e.g. "udaap,tila,ecoa"
):
    """
    Upload a file (PDF, DOCX, TXT, PNG, JPG) and check it against selected regulations.
    """
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    if not reg_ids:
        raise HTTPException(status_code=400, detail="At least one regulation must be selected.")

    suffix = Path(file.filename or "upload").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = check_file(tmp_path, reg_ids)
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Claude returned invalid JSON. Try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/check/image")
async def check_image_endpoint(
    file: UploadFile = File(...),
    regulations: str = Form(...),
):
    """
    Upload an image and check extracted text against selected regulations.
    """
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    image_bytes = await file.read()
    media_type = file.content_type or "image/png"

    try:
        result = check_image(image_bytes, media_type, reg_ids)
        return JSONResponse(content=result)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Claude returned invalid JSON. Try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docx")
async def generate_docx_endpoint(
    findings: str = Form(...),  # JSON string of findings result
    document_name: Optional[str] = Form("Analyzed Document"),
    original_excerpt: Optional[str] = Form(""),
):
    """
    Generate a color-coded compliance DOCX from a findings JSON payload.
    Returns the .docx file as a download.
    """
    try:
        findings_dict = json.loads(findings)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid findings JSON.")

    docx_bytes = generate_compliance_docx(
        findings_result=findings_dict,
        document_name=document_name or "Analyzed Document",
        original_text_excerpt=original_excerpt or "",
    )

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="compliance_report.docx"'},
    )


@app.post("/check-and-export")
async def check_and_export(
    file: UploadFile = File(...),
    regulations: str = Form(...),
):
    """
    Single endpoint: upload file → check → return color-coded DOCX in one call.
    """
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    suffix = Path(file.filename or "upload").suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = check_file(tmp_path, reg_ids)
        docx_bytes = generate_compliance_docx(
            findings_result=result,
            document_name=file.filename or "Uploaded Document",
            original_text_excerpt="",
        )
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="compliance_report.docx"'},
        )
    finally:
        os.unlink(tmp_path)
