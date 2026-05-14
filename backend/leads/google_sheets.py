"""
backend/leads/google_sheets.py

Appends lead data to the DIGIX AI Google Sheet.

Columns (in order):
  Timestamp | Name | Contact | Organisation | Interest | Language | Session ID

The blocking gspread call is run in a thread pool so it is safe to
call from an async (FastAPI) context.

Configuration (via backend/utils/config.py):
  GOOGLE_SERVICE_ACCOUNT_JSON — path to the service account credentials file
  GOOGLE_SHEET_ID             — the spreadsheet ID from the Sheet URL
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class LeadSubmissionError(Exception):
    """Raised when the Google Sheets API call fails."""


def _sync_submit(name: str, contact: str, org: str, interest: str,
                 language: str, session_id: str) -> None:
    """
    Blocking gspread call — must be run in a thread pool executor, never
    called directly from an async context.
    """
    import gspread
    from backend.utils.config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID

    try:
        gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_JSON)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.sheet1
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        ws.append_row([timestamp, name, contact, org, interest, language, session_id])
    except gspread.exceptions.GSpreadException as e:
        logger.error(
            "gspread error submitting lead session=%s name=%r: %s",
            session_id, name, e,
        )
        raise LeadSubmissionError(str(e)) from e


async def submit_lead(lead, session_id: str) -> None:
    """
    Append one row to the configured Google Sheet.

    Parameters
    ----------
    lead       : LeadSession dataclass instance
    session_id : the chat session ID (written to the Sheet for traceability)

    Raises LeadSubmissionError on failure (after logging the error).
    """
    await asyncio.to_thread(
        _sync_submit,
        lead.name,
        lead.contact,
        lead.org,
        lead.interest,
        lead.language,
        session_id,
    )
