"""Locked document status transitions for v0.1."""

from __future__ import annotations

from typing import Literal

DocumentStatus = Literal[
    "uploaded",
    "processing",
    "needs_review",
    "approved",
    "exported",
]

# uploaded → processing → needs_review|approved → exported
ALLOWED_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    "uploaded": {"processing"},
    "processing": {"needs_review", "approved", "uploaded"},  # uploaded = hard failure rollback
    "needs_review": {"processing", "approved", "needs_review"},
    "approved": {"processing", "exported", "needs_review"},
    "exported": set(),
}

EXTRACT_FROM: set[DocumentStatus] = {"uploaded", "needs_review", "approved"}
REVIEW_FROM: set[DocumentStatus] = {"needs_review", "approved"}
APPROVE_FROM: set[DocumentStatus] = {"needs_review", "approved"}
EXPORT_FROM: set[DocumentStatus] = {"approved"}


def can_transition(current: str, target: str) -> bool:
    allowed = ALLOWED_TRANSITIONS.get(current)  # type: ignore[arg-type]
    if allowed is None:
        return False
    return target in allowed


def assert_status_in(current: str, allowed: set[str], action: str) -> None:
    if current not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(
            f"Cannot {action} while status is '{current}'. Allowed statuses: {allowed_list}."
        )
