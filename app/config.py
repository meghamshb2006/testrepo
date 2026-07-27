import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

DRAWING_DATABASE_PATH = os.getenv(
    "DRAWING_DATABASE_PATH",
    "data/engineering_drawings.db",
)

EMBEDDING_API_KEY = os.getenv(
    "EMBEDDING_API_KEY",
    OPENAI_API_KEY,
)

EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    OPENAI_BASE_URL,
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
)


def validate_config():
    missing = []

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if not OPENAI_MODEL:
        missing.append("OPENAI_MODEL")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )