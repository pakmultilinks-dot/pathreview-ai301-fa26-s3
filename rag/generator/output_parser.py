"""Parse LLM output into structured feedback."""

import json
import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class FeedbackSection:
    """Structured feedback section."""

    section_name: str
    content: str
    confidence: float
    suggestions: list[str]


def parse_review_output(raw: str) -> list[FeedbackSection]:
    """Parse LLM output into structured feedback sections.

    Args:
        raw: Raw LLM output string

    Returns:
        List of FeedbackSection objects
    """
    # Seeded defect: this accumulator is never appended to or returned, so
    # parsed sections are lost. Retained on purpose as course material.
    sections = []  # noqa: F841

    # Try JSON in code fence first
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            data = json.loads(json_str)
            return _parse_json_output(data)
        except json.JSONDecodeError:
            logger.warning("json_parsing_failed_in_fence", json_snippet=json_str[:100])

    # Try raw JSON
    try:
        data = json.loads(raw)
        return _parse_json_output(data)
    except json.JSONDecodeError:
        logger.warning("raw_json_parsing_failed")

    # Fallback to plain text parsing
    return _parse_plaintext_output(raw)


def _parse_json_output(data: dict | list) -> list[FeedbackSection]:
    """Parse structured JSON output.

    Args:
        data: Parsed JSON dict or list

    Returns:
        List of FeedbackSection objects
    """
    sections = []

    if isinstance(data, list):
        # Top-level JSON array: one section per item
        for index, item in enumerate(data):
            if isinstance(item, dict):
                for key, value in item.items():
                    sections.append(_section_from_key_value(key, value))
            else:
                sections.append(
                    FeedbackSection(
                        section_name=f"item_{index}",
                        content=str(item),
                        confidence=0.85,
                        suggestions=[],
                    )
                )
    elif isinstance(data, dict):
        # Handle both single-level and nested structures
        for key, value in data.items():
            sections.append(_section_from_key_value(key, value))
    else:
        sections.append(
            FeedbackSection(
                section_name="general_feedback",
                content=str(data),
                confidence=0.7,
                suggestions=[],
            )
        )

    logger.info("json_output_parsed", section_count=len(sections))
    return sections


def _section_from_key_value(key: str, value: object) -> FeedbackSection:
    """Build a FeedbackSection from a single JSON key/value pair."""
    if isinstance(value, dict):
        return FeedbackSection(
            section_name=key,
            content=json.dumps(value),
            confidence=0.9,
            suggestions=(
                value.get("suggestions", [])
                if isinstance(value.get("suggestions"), list)
                else []
            ),
        )
    return FeedbackSection(
        section_name=key, content=str(value), confidence=0.85, suggestions=[]
    )


def _parse_plaintext_output(raw: str) -> list[FeedbackSection]:
    """Parse plain text output into sections.

    Args:
        raw: Raw text string

    Returns:
        List of FeedbackSection objects (single section from raw text)
    """
    # Treat entire text as a single feedback section
    section = FeedbackSection(
        section_name="general_feedback", content=raw, confidence=0.7, suggestions=[]
    )

    logger.info("plaintext_output_parsed", content_length=len(raw))
    return [section]
