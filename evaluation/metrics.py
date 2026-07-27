from __future__ import annotations

import re


def normalise_identifier(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string.")

    normalised = value.strip().lower()
    normalised = re.sub(r"\s+", " ", normalised)

    return normalised


def normalise_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string.")

    return re.sub(r"\s+", " ", value.strip().lower())


def hit_at_k(
    retrieved: list[str],
    expected: list[str],
    k: int,
) -> bool:
    if k < 1:
        raise ValueError("k must be at least 1.")

    if not expected:
        return False

    expected_normalised = {
        normalise_identifier(item)
        for item in expected
        if item and str(item).strip()
    }

    if not expected_normalised:
        return False

    for item in retrieved[:k]:
        if normalise_identifier(item) in expected_normalised:
            return True

    return False


def reciprocal_rank(
    retrieved: list[str],
    expected: list[str],
) -> float:
    if not expected:
        return 0.0

    expected_normalised = {
        normalise_identifier(item)
        for item in expected
        if item and str(item).strip()
    }

    if not expected_normalised:
        return 0.0

    for index, item in enumerate(retrieved, start=1):
        if normalise_identifier(item) in expected_normalised:
            return 1.0 / float(index)

    return 0.0


def term_recall(
    answer: str,
    expected_terms: list[str],
) -> tuple[list[str], list[str], float]:
    if not expected_terms:
        return [], [], 1.0

    normalised_answer = normalise_text(answer)
    found: list[str] = []
    missing: list[str] = []

    for term in expected_terms:
        if not term or not str(term).strip():
            continue

        if normalise_text(term) in normalised_answer:
            found.append(term)
        else:
            missing.append(term)

    total = len(found) + len(missing)

    if total == 0:
        return [], [], 1.0

    return found, missing, len(found) / float(total)


def forbidden_term_matches(
    answer: str,
    forbidden_terms: list[str],
) -> list[str]:
    if not forbidden_terms:
        return []

    normalised_answer = normalise_text(answer)
    matches: list[str] = []

    for term in forbidden_terms:
        if not term or not str(term).strip():
            continue

        if normalise_text(term) in normalised_answer:
            matches.append(term)

    return matches


def source_match(
    sources: list[dict],
    expected_identifiers: list[str],
) -> bool:
    if not expected_identifiers:
        return False

    expected_normalised = {
        normalise_identifier(item)
        for item in expected_identifiers
        if item and str(item).strip()
    }

    if not expected_normalised:
        return False

    for source in sources:
        for field_name in ("drawing_id", "drawing_number", "filename"):
            value = source.get(field_name)

            if value is None:
                continue

            if normalise_identifier(str(value)) in expected_normalised:
                return True

    return False


def mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / float(len(values))


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0

    if percentile_value < 0 or percentile_value > 100:
        raise ValueError("percentile_value must be between 0 and 100.")

    ordered = sorted(values)

    if len(ordered) == 1:
        return float(ordered[0])

    rank = (percentile_value / 100.0) * (len(ordered) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = rank - lower_index

    lower_value = float(ordered[lower_index])
    upper_value = float(ordered[upper_index])

    return lower_value + (upper_value - lower_value) * weight
