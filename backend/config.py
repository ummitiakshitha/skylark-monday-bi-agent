import os
from dotenv import load_dotenv

# Load env variables from a local .env file if it exists (local development)
load_dotenv()

def _get_secret(key: str, default: str = None) -> str:
    """Read a secret from OS env first, then fall back to Streamlit secrets (cloud deployment)."""
    value = os.getenv(key)
    if value:
        return value
    # Fall back to Streamlit secrets when running on Streamlit Cloud
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

class Config:
    """Class to securely manage application configurations."""

    @classmethod
    def _load(cls):
        """Lazily load all config values so Streamlit secrets are available at read time."""
        cls.MONDAY_API_TOKEN = _get_secret("MONDAY_API_TOKEN")
        cls.DEALS_BOARD_ID = _get_secret("DEALS_BOARD_ID")
        cls.WORK_ORDERS_BOARD_ID = _get_secret("WORK_ORDERS_BOARD_ID")
        cls.OPENAI_API_KEY = _get_secret("OPENAI_API_KEY")
        cls.OPENAI_MODEL = _get_secret("OPENAI_MODEL", "gpt-4o")
        use_excel = _get_secret("USE_LOCAL_EXCEL", "false")
        cls.USE_LOCAL_EXCEL = str(use_excel).lower() == "true"

    @classmethod
    def get_missing_credentials(cls) -> list:
        """Returns a list of missing required credentials for live production."""
        missing = []
        if not cls.MONDAY_API_TOKEN:
            missing.append("MONDAY_API_TOKEN")
        if not cls.DEALS_BOARD_ID:
            missing.append("DEALS_BOARD_ID")
        if not cls.WORK_ORDERS_BOARD_ID:
            missing.append("WORK_ORDERS_BOARD_ID")
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        return missing

# Load config values at import time (Streamlit is already initialized by this point)
Config._load()
