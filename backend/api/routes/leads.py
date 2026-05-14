"""
backend/api/routes/leads.py

POST /leads — manual lead submission from the frontend LeadForm.jsx.

API contract (from CONTEXT.md):
  Request:  { "name": "Ahmed", "email": "a@b.com", "org": "XYZ",
              "interest": "training", "language": "ar" }
  Response: { "success": true }

collector.py owns the conversational lead flow triggered from /chat;
this endpoint handles direct form submissions from the frontend.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from backend.leads.collector import LeadSession
from backend.leads.google_sheets import LeadSubmissionError, submit_lead
from backend.utils.logger import get_logger, log_error

router = APIRouter()
logger = get_logger("api.leads")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class LeadRequest(BaseModel):
    name:     str = Field(..., min_length=1, max_length=100)
    email:    EmailStr
    org:      str = Field("", max_length=150)       # organisation — optional
    interest: str = Field("general", max_length=100)
    language: str = Field("ar", pattern="^(ar|en)$")


class LeadResponse(BaseModel):
    success: bool

# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/leads", response_model=LeadResponse)
async def post_lead(req: LeadRequest) -> LeadResponse:
    logger.info(
        "lead | name=%r email=%r org=%r interest=%r lang=%s",
        req.name, req.email, req.org, req.interest, req.language,
    )

    lead = LeadSession(
        name=req.name,
        contact=str(req.email),
        org=req.org,
        interest=req.interest,
        language=req.language,
        stage="SUBMITTED",
    )

    try:
        await submit_lead(lead, session_id="form-submission")
    except LeadSubmissionError as exc:
        log_error("Google Sheets push failed", context={"error": str(exc)})
        raise HTTPException(
            status_code=502,
            detail="تعذّر حفظ بياناتك. يرجى المحاولة مرة أخرى.",
        )

    return LeadResponse(success=True)
