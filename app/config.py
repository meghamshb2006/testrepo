import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

OPENAI_ANSWER_MODEL = os.getenv("OPENAI_ANSWER_MODEL") or OPENAI_MODEL

DRAWING_DATABASE_PATH = os.getenv(
    "DRAWING_DATABASE_PATH",
    "data/engineering_drawings.db",
)

SEARCH_DATABASE_PATH = os.getenv(
    "SEARCH_DATABASE_PATH",
    "data/drawing_search.db",
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

RETRIEVAL_CONFIDENCE_HIGH_THRESHOLD = float(
    os.getenv("RETRIEVAL_CONFIDENCE_HIGH_THRESHOLD", "0.80")
)
RETRIEVAL_CONFIDENCE_MEDIUM_THRESHOLD = float(
    os.getenv("RETRIEVAL_CONFIDENCE_MEDIUM_THRESHOLD", "0.50")
)
RETRIEVAL_EXACT_IDENTIFIER_BOOST_WEIGHT = float(
    os.getenv("RETRIEVAL_EXACT_IDENTIFIER_BOOST_WEIGHT", "0.25")
)

RETRIEVAL_OBSERVABILITY_LOGGING = os.getenv(
    "RETRIEVAL_OBSERVABILITY_LOGGING",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}

RETRIEVAL_LOG_LEVEL = os.getenv("RETRIEVAL_LOG_LEVEL", "INFO").strip().upper()


def validate_config() -> None:
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


def validate_answer_config() -> None:
    missing = []

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if not OPENAI_ANSWER_MODEL:
        missing.append("OPENAI_ANSWER_MODEL or OPENAI_MODEL")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )