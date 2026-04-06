"""
rag/rag_compliance.py — RAG-Enhanced Compliance Checker with Conflict Detection v2
"""
import os, json, base64, sys
from typing import Optional
from pathlib import Path
import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.knowledge_base import KnowledgeBase
from rag.company_memory import CompanyMemory
from rag.conflict_detector import ConflictDetector

REGULATIONS = {
    "udaap":       {"label": "UDAAP",                 "description": "Unfair, Deceptive, or Abusive Acts or Practices"},
    "tila":        {"label": "TILA / Reg Z / CARD Act","description": "Truth in Lending Act"},
    "ecoa":        {"label": "ECOA / Reg B",           "description": "Equal Credit Opportunity Act"},
    "fcra":        {"label": "FCRA / Reg V",           "description": "Fair Credit Reporting Act"},
    "bsa":         {"label": "BSA / AML / OFAC / CIP", "description": "Bank Secrecy Act / Anti-Money Laundering"},
    "pci":         {"label": "PCI DSS",                "description": "Payment Card Industry Data Security Standard"},
    "scra":        {"label": "SCRA",                   "description": "Servicemembers Civil Relief Act"},
    "collections": {"label": "Collections Conduct",    "description": "FDCPA / Collection Practices"},
    "sr117":       {"label": "SR 11-7",                "description": "Model Risk Management"},
}

COMPLIANCE_SYSTEM = """You are an expert credit card compliance attorney. Analyze the provided content and return ONLY valid JSON.

{{
  "overall_risk": "high|medium|low|pass",
  "summary": "2-3 sentence executive summary",
  "rag_enhanced": true,
  "findings": [
    {{
      "regulation": "regulation name",
      "severity": "high|medium|low|pass",
      "issue": "short title",
      "detail": "detailed explanation",
      "regulatory_citation": "e.g. 12 CFR 1026.16(b)",
      "excerpt": "quoted text from analyzed document",
      "recommendation": "specific action"
    }}
  ]
}}{context}"""

def _regs(ids): return "\n".join(f"- {REGULATIONS[r]['label']}: {REGULATIONS[r]['description']}" for r in ids if r in REGULATIONS)
def _parse(raw): return json.loads(raw.replace("```json","").replace("```","").strip())

class RAGComplianceChecker:
    def __init__(self, api_key=None, model=None, max_tokens=4000, use_rag=True, rag_top_k=6, company_name="Company"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY","")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model or os.environ.get("MODEL","claude-sonnet-4-20250514")
        self.max_tokens = max_tokens
        self.use_rag = use_rag
        self.rag_top_k = rag_top_k
        self.company_name = company_name
        self._conflict_detector = None

        if use_rag:
            try: self.kb = KnowledgeBase(); self._rag_ok = self.kb.stats()["total_chunks"] > 0
            except: self._rag_ok = False
        else: self._rag_ok = False

        try: self.memory = CompanyMemory(company_name=company_name); self._mem_ok = self.memory.stats()["total"] > 0
        except: self.memory = None; self._mem_ok = False

    def _detector(self):
        if not self._conflict_detector:
            self._conflict_detector = ConflictDetector(api_key=self.api_key, model=self.model, company_memory=self.memory, company_name=self.company_name)
        return self._conflict_detector

    def _ctx(self, sample, reg_ids):
        if not self._rag_ok: return ""
        try: return self.kb.build_context_block(sample[:500], reg_ids, top_k=self.rag_top_k)
        except: return ""

    def _claude(self, system, messages):
        resp = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, system=system, messages=messages)
        raw = "".join(b.text for b in resp.content if hasattr(b,"text"))
        r = _parse(raw)
        r["rag_enhanced"] = self._rag_ok
        r["rag_chunks_retrieved"] = self.rag_top_k if self._rag_ok else 0
        return r

    def _compliance(self, text, reg_ids):
        ctx = self._ctx(text, reg_ids)
        return self._claude(COMPLIANCE_SYSTEM.format(context=f"\n\nCheck against:\n{_regs(reg_ids)}" + (f"\n{ctx}" if ctx else "")), [{"role":"user","content":f"Analyze:\n---\n{text}\n---"}])

    def _conflict(self, text, product=None, run=True):
        if not run: return None
        try: return self._detector().check_conflicts(text, product=product)
        except Exception as e: return {"has_conflicts":False,"conflict_risk":"none","summary":f"Conflict check error: {e}","conflicts":[],"consistent_items":[]}

    def _merge(self, comp, conf):
        r = dict(comp)
        if conf:
            r["conflict_check"] = conf
            r["has_prior_conflicts"] = conf.get("has_conflicts",False)
            r["conflict_risk"] = conf.get("conflict_risk","none")
            order = {"high":3,"medium":2,"low":1,"pass":0,"none":0}
            if order.get(conf.get("conflict_risk","none"),0) > order.get(r.get("overall_risk","pass"),0):
                r["overall_risk"] = conf.get("conflict_risk")
                r["summary"] = r.get("summary","") + " " + conf.get("summary","")
        else:
            r["conflict_check"] = None; r["has_prior_conflicts"] = False
        return r

    def check_text(self, text, reg_ids, product=None, run_conflict_check=True):
        return self._merge(self._compliance(text, reg_ids), self._conflict(text, product=product, run=run_conflict_check))

    def check_image(self, image_bytes, media_type, reg_ids, product=None, run_conflict_check=True):
        ctx = self._ctx("credit card document image", reg_ids)
        b64 = base64.standard_b64encode(image_bytes).decode()
        comp = self._claude(COMPLIANCE_SYSTEM.format(context=f"\n\nCheck against:\n{_regs(reg_ids)}" + (f"\n{ctx}" if ctx else "")), [{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":media_type,"data":b64}},{"type":"text","text":"Analyze this document image for compliance. Extract all text and check thoroughly."}]}])
        return self._merge(comp, None)

    def check_file(self, file_path, reg_ids, product=None, run_conflict_check=True):
        import subprocess
        path = Path(file_path); ext = path.suffix.lower()
        imgs = {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}
        if ext in imgs:
            with open(file_path,"rb") as f: return self.check_image(f.read(), imgs[ext], reg_ids, product=product)
        if ext==".txt": text=path.read_text(encoding="utf-8",errors="ignore")
        elif ext==".pdf":
            from pypdf import PdfReader
            text="\n\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        elif ext in (".docx",".doc"):
            r=subprocess.run(["pandoc",str(path),"-t","plain"],capture_output=True,text=True); text=r.stdout
        elif ext==".json": text=path.read_text()
        else: raise ValueError(f"Unsupported: {ext}")
        if not text.strip(): raise ValueError("No text extracted")
        return self.check_text(text, reg_ids, product=product, run_conflict_check=run_conflict_check)

    # Company memory
    def add_company_document(self, text, source, doc_type="marketing", product="general", date="", version="", tags=""):
        if not self.memory: raise RuntimeError("Company memory not initialized")
        n = self.memory.add_document(text, source=source, doc_type=doc_type, product=product, date=date, version=version, tags=tags)
        self._mem_ok = True; return n

    def add_company_file(self, file_path, doc_type="marketing", source=None, product="general", date="", version=""):
        if not self.memory: raise RuntimeError("Company memory not initialized")
        n = self.memory.add_file(file_path, doc_type=doc_type, source=source, product=product, date=date, version=version)
        self._mem_ok = True; return n

    def add_company_directory(self, dir_path, doc_type="marketing", product="general"):
        if not self.memory: raise RuntimeError("Company memory not initialized")
        r = self.memory.add_directory(dir_path, doc_type=doc_type, product=product)
        self._mem_ok = True; return r

    def memory_stats(self): return self.memory.stats() if self.memory else {"total":0}
    def memory_documents(self, doc_type=None): return self.memory.list_documents(doc_type) if self.memory else []
    def delete_company_document(self, source): return self.memory.delete_document(source) if self.memory else 0

    # Regulatory KB
    def ingest_text(self, text, source, regulation="general", doc_type="regulation"):
        if not self.use_rag: raise RuntimeError("RAG disabled")
        n=self.kb.ingest_text(text,source=source,regulation=regulation,doc_type=doc_type); self._rag_ok=True; return n

    def ingest_file(self, file_path, regulation="general", doc_type="regulation", source=None):
        if not self.use_rag: raise RuntimeError("RAG disabled")
        n=self.kb.ingest_file(file_path,regulation=regulation,doc_type=doc_type,source=source); self._rag_ok=True; return n

    def kb_stats(self): return self.kb.stats() if self.use_rag else {"rag":"disabled"}
    def kb_sources(self): return self.kb.list_sources() if self.use_rag else []
