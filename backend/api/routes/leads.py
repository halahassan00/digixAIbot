"""
backend/api/routes/leads.py

POST /leads — manual lead submission.

API contract (from CONTEXT.md):
  Request:  { "name": "Ahmed", "email": "a@b.com", "org": "XYZ",
              "interest": "training", "language": "ar" }
  Response: { "success": true }

The lead is pushed to DIGIX AI's Google Sheet via the Sheets API.
collector.py owns the conversational lead flow triggered from /chat;
this endpoint handles direct form submissions from the frontend's
LeadForm.jsx component.

Interface expected from leads modules (not yet built):
  backend/leads/google_sheets.py must export:
      push_lead(lead: dict) -> None
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from backend.leads.google_sheets import push_lead
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
async def submit_lead(req: LeadRequest) -> LeadResponse:
    logger.info(
        "lead | name=%r email=%r org=%r interest=%r lang=%s",
        req.name, req.email, req.org, req.interest, req.language,
    )

    try:
        push_lead({
            "name":     req.name,
            "email":    req.email,
            "org":      req.org,
            "interest": req.interest,
            "language": req.language,
        })
    except Exception as exc:
        log_error("Google Sheets push failed", context={"error": str(exc)})
        raise HTTPException(
            status_code=502,
            detail="تعذّر حفظ بياناتك. يرجى المحاولة مرة أخرى.",
        )

    return LeadResponse(success=True)
