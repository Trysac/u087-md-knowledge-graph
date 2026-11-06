"""Immutable data model shared by the parser, the graph builder and the loader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Link:
    """A wiki link found in the body of a note.

    Attributes:
        target: Link target, stripped and without a ``.md`` suffix.
        label: Display text after ``|``, if any.
        heading: Heading after ``#``, if any.
        line: 1-based line number in the note file.
    """

    target: str
    label: str | None
    heading: str | None
    line: int


@dataclass(frozen=True)
class Note:
    """A parsed Markdown note.

    Attributes:
        id: Lowercase stem, or the path-qualified id once the graph is built.
        path: POSIX path relative to the notes root.
        title: Frontmatter title, else the first H1, else the file stem.
        frontmatter: Read-only mapping of the YAML frontmatter.
        tags: Sorted, lowercase, deduplicated tags.
        aliases: Frontmatter aliases in document order.
        links: Wiki links in document order.
    """

    id: str
    path: str
    title: str
    frontmatter: Mapping[str, Any]
    tags: tuple[str, ...]
    aliases: tuple[str, ...]
    links: tuple[Link, ...]


def strip_md_suffix(path: str) -> str:
    """Return ``path`` without a trailing ``.md`` (case-insensitive)."""
    if path.lower().endswith(".md"):
        return path[:-3]
    return path


def stem_of(path: str) -> str:
    """Return the last component of ``path`` without its ``.md`` suffix."""
    return strip_md_suffix(path).rsplit("/", 1)[-1]
