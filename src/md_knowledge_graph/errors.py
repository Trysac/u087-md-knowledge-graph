"""Typed errors for ``md_knowledge_graph``."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal["frontmatter", "too_large", "root_missing", "too_many_notes"]

MAX_MESSAGE_CHARS = 200


def clip(text: str, limit: int = 120) -> str:
    """Return ``text`` shortened to at most ``limit`` characters."""
    if len(text) <= limit:
        return text
    end = max(limit - 3, 0)
    return text[:end] + "..."


class KnowledgeGraphError(Exception):
    """Base error of the library.

    Attributes:
        code: Stable machine-readable error code.
        path: Note path (or root directory) the error refers to, when known.
    """

    def __init__(self, code: ErrorCode, message: str, path: str | None = None) -> None:
        super().__init__(clip(message, MAX_MESSAGE_CHARS))
        self.code: ErrorCode = code
        self.path: str | None = path
