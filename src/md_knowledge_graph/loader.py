"""Load Markdown notes from a directory tree."""

from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import KnowledgeGraphError, clip
from .models import Note
from .parser import parse_note

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDE: tuple[str, ...] = (".git", "node_modules", "INDEX.md")
MAX_WARNINGS = 1000


@dataclass(frozen=True)
class LoadResult:
    """Notes loaded from a directory and the warnings produced while loading."""

    notes: list[Note]
    warnings: list[str]


class _Warnings:
    """Collect warnings, keeping at most ``MAX_WARNINGS`` and counting the rest."""

    def __init__(self) -> None:
        self._items: list[str] = []
        self._dropped = 0

    def add(self, message: str) -> None:
        logger.debug("%s", message)
        if len(self._items) < MAX_WARNINGS:
            self._items.append(message)
        else:
            self._dropped += 1

    def result(self) -> list[str]:
        items = list(self._items)
        if self._dropped:
            items.append(f"and {self._dropped} more")
        return items


def load_notes(
    root: Path,
    *,
    exclude: Sequence[str] = DEFAULT_EXCLUDE,
    strict: bool = False,
    max_file_bytes: int = 1_048_576,
    max_notes: int = 20_000,
) -> LoadResult:
    """Load every ``.md`` file below ``root``.

    Args:
        root: Directory holding the notes.
        exclude: Glob patterns matched against file or directory names and against
            root-relative POSIX paths. Matching directories are not entered.
        strict: Raise on invalid frontmatter and oversized files instead of warning.
        max_file_bytes: Largest accepted file size.
        max_notes: Largest accepted number of notes.

    Returns:
        The notes sorted by path and the warnings (capped at 1000 plus one summary line).

    Raises:
        KnowledgeGraphError: ``root_missing`` if ``root`` is not a directory;
            ``too_many_notes`` if more than ``max_notes`` files are found; in strict mode
            also ``frontmatter`` and ``too_large``.

    Symlinks that resolve outside ``root`` and symlinked directories are never followed.
    Files that are not valid UTF-8 become warnings.
    """
    base = Path(root)
    if not base.is_dir():
        message = f"not a directory: {clip(str(base))}"
        raise KnowledgeGraphError("root_missing", message, str(base))
    real_root = base.resolve()
    notes: list[Note] = []
    warnings = _Warnings()
    for full in _iter_markdown(base, real_root, exclude):
        rel = full.relative_to(base).as_posix()
        if len(notes) >= max_notes:
            raise KnowledgeGraphError("too_many_notes", f"more than {max_notes} notes", str(base))
        text = _read(full, rel, max_file_bytes, strict, warnings)
        if text is None:
            continue
        try:
            notes.append(parse_note(rel, text))
        except KnowledgeGraphError as exc:
            if strict:
                raise
            warnings.add(f"{clip(rel)}: {exc}")
    notes.sort(key=lambda note: note.path)
    return LoadResult(notes, warnings.result())


def _read(full: Path, rel: str, limit: int, strict: bool, warnings: _Warnings) -> str | None:
    try:
        with full.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        warnings.add(f"{clip(rel)}: cannot be read")
        return None
    if len(data) > limit:
        if strict:
            raise KnowledgeGraphError("too_large", f"file exceeds {limit} bytes", rel)
        warnings.add(f"{clip(rel)}: skipped, larger than {limit} bytes")
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        warnings.add(f"{clip(rel)}: skipped, not valid UTF-8")
        return None


def _rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _excluded(rel: str, name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) or fnmatch.fnmatchcase(rel, p) for p in patterns)


def _inside(path: Path, real_root: Path) -> bool:
    try:
        path.resolve().relative_to(real_root)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _iter_markdown(base: Path, real_root: Path, exclude: Sequence[str]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if not _excluded(_rel(here / name, base), name, exclude):
                kept.append(name)
        dirnames[:] = sorted(kept)
        for name in sorted(filenames):
            full = here / name
            if not name.lower().endswith(".md") or _excluded(_rel(full, base), name, exclude):
                continue
            if full.is_symlink() and not _inside(full, real_root):
                logger.debug("skipped a symlink that leaves the root")
                continue
            yield full
