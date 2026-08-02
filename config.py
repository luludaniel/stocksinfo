import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")
# Optional: without it, economic_cal.py falls back to a static recurring-events
# list (FRED requires api_key on every endpoint, so unset means every call 400s).
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


def validate():
    missing = [k for k, v in {
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "EMAIL_SENDER": EMAIL_SENDER,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
        "EMAIL_RECEIVER": EMAIL_RECEIVER,
    }.items() if not v]
    if missing:
        raise EnvironmentError(f"필수 환경변수 누락: {', '.join(missing)}")
