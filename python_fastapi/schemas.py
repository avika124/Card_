from pydantic import BaseModel
from typing import Optional, List


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    name: str
    role: str  # submitter | compliance | legal | admin
    department: str = ""
    password: str


class ReviewDecisionRequest(BaseModel):
    decision: str  # approved | rejected | escalated | in_review
    notes: str = ""


class KBIngestUrlRequest(BaseModel):
    url: str
    source: str
    regulation: str = "general"
    doc_type: str = "regulation"


class KBLoadPresetRequest(BaseModel):
    name: str


class RegWatchRequest(BaseModel):
    url: str
    name: str
    regulation: str = "general"


class MemoryTextRequest(BaseModel):
    text: str
    source: str
    doc_type: str = "marketing"
    product: str = "general"
    date: str = ""
    version: str = ""
