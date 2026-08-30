import os
from dotenv import load_dotenv

# Load env variables from a local .env file if it exists (local development)
load_dotenv()

class Config:
    """Class to securely manage application configurations."""
    
    # Monday.com API Secrets
    MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
    DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID")
    WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID")
    
    # LLM API Secrets
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # Local Development Fallback Toggle (restricted for local tests only)
    USE_LOCAL_EXCEL = os.getenv("USE_LOCAL_EXCEL", "false").lower() == "true"
    
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
