from pydantic import BaseModel, Field
from typing import Optional, List


class ComplianceRequest(BaseModel):
    text: str = Field(..., description="Text content to analyze")
    regulations: List[str] = Field(
        ...,
        description="List of regulation IDs to check against",
        example=["udaap", "tila", "ecoa", "fcra", "bsa", "pci", "scra", "collections", "sr117"]
    )


class Finding(BaseModel):
    regulation: str
    severity: str  # high | medium | low | pass
    issue: str
    detail: str
    excerpt: Optional[str] = ""
    recommendation: Optional[str] = ""


class ComplianceResponse(BaseModel):
    overall_risk: str  # high | medium | low | pass
    summary: str
    findings: List[Finding]
