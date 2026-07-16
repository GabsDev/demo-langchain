import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_SANDBOX_NUMBER: str = os.getenv("TWILIO_SANDBOX_NUMBER", "")

    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_USER_ID: str = os.getenv("INSTAGRAM_USER_ID", "")

    IMGBB_API_KEY: str = os.getenv("IMGBB_API_KEY", "")

    FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))

    SERVER_PUBLIC_URL: str = os.getenv("SERVER_PUBLIC_URL", "http://localhost:5000")

    # Solo este número puede usar el bot en modo single-user
    ALLOWED_NUMBER: str = os.getenv("YOWN_WHATSAPP_NUMBER", "")

    TEMP_DIR: Path = Path(__file__).parent.parent / "temp"
    TEMP_IMAGE_TTL: int = 1800  # 30 min

    IMAGE_MODEL: str = "gemini-3.1-flash-lite-image"
    IMAGE_MAX_PER_DAY: int = 5
    IMAGE_MAX_RETRIES: int = 3
    IMAGE_RPM_LIMIT: int = 10

    IG_MAX_CAROUSEL_ITEMS: int = 10
    IG_POSTS_PER_DAY_LIMIT: int = 50

    @classmethod
    def instagram_flow(cls) -> str:
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        if token.startswith(("IGAA", "IGQW")):
            return "instagram-login"
        return "facebook-login"

    @classmethod
    def instagram_graph_host(cls) -> str:
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        if token.startswith(("IGAA", "IGQW")):
            return "https://graph.instagram.com"
        return "https://graph.facebook.com"

    @classmethod
    def validate(cls):
        missing = []
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not cls.TWILIO_ACCOUNT_SID:
            missing.append("TWILIO_ACCOUNT_SID")
        if not cls.TWILIO_AUTH_TOKEN:
            missing.append("TWILIO_AUTH_TOKEN")
        if not cls.TWILIO_SANDBOX_NUMBER:
            missing.append("TWILIO_SANDBOX_NUMBER")
        if missing:
            raise ValueError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"Instagram keys are optional until publishing."
            )
