"""
backend/leads/google_sheets.py

Stub — logs leads to console until the Google Sheets integration is built.
Replace the body of push_lead() with the real Sheets API call when ready.
"""

from backend.utils.logger import get_logger

logger = get_logger("leads")


def push_lead(lead: dict) -> None:
    logger.info("LEAD (stub, not yet sent to Sheets): %s", lead)
