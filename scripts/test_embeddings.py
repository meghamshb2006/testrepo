from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)

EMBEDDING_MODEL = "text-embedding-ada-002"


def main() -> None:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=120.0,
        max_retries=1,
    )

    print(f"Testing embedding deployment: {EMBEDDING_MODEL}")
    print(f"Endpoint: {OPENAI_BASE_URL}")

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input="Engineering drawing of a mechanical housing.",
            encoding_format="float",
        )

        embedding = response.data[0].embedding

        print("SUCCESS")
        print(f"Embedding dimensions: {len(embedding)}")
        print(f"First five values: {embedding[:5]}")
        print(f"Usage: {response.usage}")

    except Exception as exc:
        print("FAILED")
        print(f"Error type: {type(exc).__name__}")
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()