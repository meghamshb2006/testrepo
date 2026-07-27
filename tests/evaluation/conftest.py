from __future__ import annotations

from search.services.question_answering_service import NO_EVIDENCE_ANSWER


class FakeAnswerGenerator:
    """Test-only deterministic answer generator."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        lowered = prompt.lower()

        for key, answer in self.answers.items():
            if key.lower() in lowered:
                return answer

        if "zz-9999" in lowered or "titanium" in lowered:
            return NO_EVIDENCE_ANSWER

        if "6061" in lowered or "br-1001" in lowered or "material" in lowered:
            return (
                "The specified material is Aluminium 6061-T6 "
                "(drawing DR-1001)."
            )

        if "revision" in lowered:
            return "The revision of drawing DR-1001 is C."

        if "10.5" in lowered or "hole diameter" in lowered:
            return "The hole diameter is 10.5 mm on DR-1001."

        if "iso-2768" in lowered or "tolerance" in lowered:
            return "The general tolerance standard is ISO-2768."

        if "dr-1001" in lowered:
            return "Drawing DR-1001 is the aluminium mounting bracket."

        return "Grounded answer from indexed drawing context."
