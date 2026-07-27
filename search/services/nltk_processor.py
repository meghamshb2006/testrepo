import re
from typing import Iterable

from nltk.stem import SnowballStemmer


class NLTKProcessor:
    """
    Lightweight text preprocessing for engineering drawing retrieval.
    """

    DEFAULT_STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "show",
        "find",
        "give",
        "get",
        "drawing",
        "drawings",
        "please",
    }

    ENGINEERING_TERMS = {
        "aluminium",
        "aluminum",
        "steel",
        "stainless",
        "copper",
        "brass",
        "plastic",
        "nylon",
        "titanium",
        "diameter",
        "radius",
        "length",
        "width",
        "height",
        "depth",
        "thickness",
        "tolerance",
        "surface",
        "finish",
        "revision",
        "material",
        "part",
        "assembly",
        "hole",
        "thread",
        "pitch",
        "chamfer",
        "fillet",
        "weld",
        "coating",
        "anodised",
        "anodized",
        "machined",
        "mm",
        "cm",
        "m",
        "inch",
        "inches",
        "iso",
        "din",
        "ansi",
        "astm",
        "plusminus",
        "degree",
    }

    TOKEN_PATTERN = re.compile(
            r"[a-zA-Z0-9]+(?:[-_/][a-zA-Z0-9]+)+|\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)*|[a-zA-Z]+"
    )

    def __init__(
        self,
        stopwords: Iterable[str] | None = None,
        use_stemming: bool = True,
    ):
        self.stopwords = set(stopwords or self.DEFAULT_STOPWORDS)
        self.use_stemming = use_stemming
        self.stemmer = SnowballStemmer("english")

    @staticmethod
    def normalise_symbols(text: str) -> str:
        replacements = {
            "(diameter)": " diameter ",
            "diam.": " diameter ",
            "+/-": " plusminus ",
            "deg": " degree ",
        }

        normalised = text

        for source, replacement in replacements.items():
            normalised = normalised.replace(source, replacement)

        return normalised

    @staticmethod
    def _is_engineering_identifier(token: str) -> bool:
        return (
            any(character.isdigit() for character in token)
            or "-" in token
            or "_" in token
            or "/" in token
        )

    def tokenise(self, text: str) -> list[str]:
        if not isinstance(text, str):
            raise TypeError("Text must be a string.")

        text = self.normalise_symbols(text).lower()

        return [
            match.group(0)
            for match in self.TOKEN_PATTERN.finditer(text)
        ]

    def preprocess(self, text: str) -> list[str]:
        processed_tokens = []

        for token in self.tokenise(text):
            if token in self.stopwords:
                continue

            if len(token) == 1 and not token.isdigit():
                continue

            if (
                not self.use_stemming
                or token in self.ENGINEERING_TERMS
                or self._is_engineering_identifier(token)
            ):
                processed_tokens.append(token)
                continue

            processed_tokens.append(self.stemmer.stem(token))

        return processed_tokens

    def preprocess_to_text(self, text: str) -> str:
        return " ".join(self.preprocess(text))