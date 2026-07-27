import base64
import io
import json
from pathlib import Path

import openai
from openai import OpenAI
from PIL import Image, ImageOps
from pydantic import ValidationError

from app.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    validate_config,
)
from app.schemas import DrawingAnalysis


ANALYSIS_PROMPT = """
You are analysing a detailed mechanical engineering drawing.

The drawing may contain:
- orthographic views
- sectional views
- detail views
- enlarged circular regions
- dimension chains
- diameter, radius and angular dimensions
- upper/lower limit dimensions
- plus-minus tolerances
- geometric dimensioning and tolerancing symbols
- datum references
- numbered balloons or callouts
- manufacturing and inspection notes
- a title block

You will receive:
1. the complete drawing page for layout context
2. overlapping cropped regions for reading small details

Extract only information that is visibly supported by the drawing.

Important rules:
- Never invent or estimate values.
- Preserve exact units, symbols, decimal places and tolerance notation.
- Keep diameter, radius, degree, datum and GD&T symbols where readable.
- Do not treat grid coordinates or border labels as part dimensions.
- Do not duplicate the same dimension when it appears in overlapping crops.
- Associate each dimension or callout with its drawing view where possible.
- Use null or an empty list when information is not readable.
- Put uncertain readings in ambiguities.
- Describe unreadable areas in unreadable_regions.
- Do not silently correct unusual values.
- Return only one valid JSON object.
- Do not wrap the JSON in Markdown code fences.
"""


class DrawingAnalyzer:
    def __init__(self) -> None:
        validate_config()

        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
            max_retries=2,
        )

    @staticmethod
    def _prepare_image(image_path: Path) -> Image.Image:
        if not image_path.exists():
            raise FileNotFoundError(
                f"Rendered page does not exist: {image_path}"
            )

        with Image.open(image_path) as source_image:
            image = ImageOps.exif_transpose(source_image)
            image = image.convert("RGB")

        # Rotate portrait pages clockwise so engineering drawings are
        # presented in a landscape orientation.
        if image.height > image.width:
            image = image.rotate(-90, expand=True)

        return image

    @staticmethod
    def _encode_pil_image(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _create_tiles(
        image: Image.Image,
        columns: int = 3,
        rows: int = 3,
        overlap_ratio: float = 0.12,
    ) -> list[tuple[str, Image.Image]]:
        width, height = image.size

        tile_width = width / columns
        tile_height = height / rows

        overlap_x = int(tile_width * overlap_ratio)
        overlap_y = int(tile_height * overlap_ratio)

        tiles: list[tuple[str, Image.Image]] = []

        for row in range(rows):
            for column in range(columns):
                left = max(
                    0,
                    int(column * tile_width) - overlap_x,
                )
                upper = max(
                    0,
                    int(row * tile_height) - overlap_y,
                )
                right = min(
                    width,
                    int((column + 1) * tile_width) + overlap_x,
                )
                lower = min(
                    height,
                    int((row + 1) * tile_height) + overlap_y,
                )

                tile = image.crop((left, upper, right, lower))

                label = (
                    f"region row {row + 1}, column {column + 1}, "
                    f"coordinates ({left}, {upper}) "
                    f"to ({right}, {lower})"
                )

                tiles.append((label, tile))

        return tiles

    def _build_content(
        self,
        page_paths: list[Path],
    ) -> list[dict]:
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Analyse the attached engineering drawing images. "
                    "The complete pages provide layout context, while "
                    "the crops provide readable details."
                ),
            }
        ]

        for page_number, page_path in enumerate(
            page_paths,
            start=1,
        ):
            image = self._prepare_image(page_path)

            full_page_encoded = self._encode_pil_image(image)

            content.append(
                {
                    "type": "text",
                    "text": (
                        f"Complete drawing page {page_number}. "
                        "Use this image for overall layout, drawing "
                        "views and relationships."
                    ),
                }
            )

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/png;base64,"
                            f"{full_page_encoded}"
                        ),
                        "detail": "high",
                    },
                }
            )

            tiles = self._create_tiles(image)

            for tile_number, (label, tile) in enumerate(
                tiles,
                start=1,
            ):
                tile_encoded = self._encode_pil_image(tile)

                content.append(
                    {
                        "type": "text",
                        "text": (
                            f"Page {page_number}, crop "
                            f"{tile_number}: {label}. "
                            "Read small dimensions, symbols, "
                            "callouts and notes from this region."
                        ),
                    }
                )

                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/png;base64,"
                                f"{tile_encoded}"
                            ),
                            "detail": "high",
                        },
                    }
                )

        return content

    @staticmethod
    def _extract_json(response_text: str) -> str:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")

        if first_brace == -1 or last_brace == -1:
            raise RuntimeError(
                "The model response did not contain a JSON object."
            )

        return cleaned[first_brace:last_brace + 1]

    def analyze(
        self,
        page_paths: list[Path],
    ) -> DrawingAnalysis:
        if not page_paths:
            raise ValueError(
                "No rendered drawing pages were supplied."
            )

        content = self._build_content(page_paths)

        drawing_schema = json.dumps(
            DrawingAnalysis.model_json_schema(),
            ensure_ascii=False,
        )

        system_prompt = (
            f"{ANALYSIS_PROMPT}\n\n"
            "Your JSON response must follow this JSON Schema:\n"
            f"{drawing_schema}"
        )

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": content,
                    },
                ],
                temperature=0,
            )

        except openai.AuthenticationError as exc:
            raise RuntimeError(
                "API authentication failed. "
                "Check OPENAI_API_KEY."
            ) from exc

        except openai.PermissionDeniedError as exc:
            raise RuntimeError(
                f"The API key cannot access model "
                f"'{OPENAI_MODEL}'."
            ) from exc

        except openai.NotFoundError as exc:
            raise RuntimeError(
                f"Model or deployment '{OPENAI_MODEL}' "
                "was not found."
            ) from exc

        except openai.RateLimitError as exc:
            raise RuntimeError(
                "API rate limit or account quota was exceeded."
            ) from exc

        except openai.APIConnectionError as exc:
            raise RuntimeError(
                "Could not connect to the configured AI endpoint."
            ) from exc

        except openai.APIStatusError as exc:
            raise RuntimeError(
                f"AI API request failed with status "
                f"{exc.status_code}: {exc}"
            ) from exc

        if not response.choices:
            raise RuntimeError(
                "The model returned no response choices."
            )

        response_text = response.choices[0].message.content

        if not response_text:
            raise RuntimeError(
                "The model returned an empty response."
            )

        json_text = self._extract_json(response_text)

        try:
            return DrawingAnalysis.model_validate_json(json_text)

        except ValidationError as exc:
            raise RuntimeError(
                "The model returned JSON, but it did not match "
                f"the DrawingAnalysis schema: {exc}"
            ) from exc

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The model returned invalid JSON."
            ) from exc


def analyze_drawing(
    page_paths: list[Path],
) -> DrawingAnalysis:
    return DrawingAnalyzer().analyze(page_paths)