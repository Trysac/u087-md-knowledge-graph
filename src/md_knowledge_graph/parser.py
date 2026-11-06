"""Parse one Markdown note: frontmatter, title, tags and wiki links."""

from __future__ import annotations

import importlib
import math
import re
from datetime import date
from types import MappingProxyType
from typing import Any

from .errors import KnowledgeGraphError, clip
from .models import Link, Note, stem_of

# PyYAML ships no type information; importing it dynamically keeps mypy --strict clean.
yaml: Any = importlib.import_module("yaml")

DEFAULT_MAX_FRONTMATTER_BYTES = 65_536
MAX_YAML_DEPTH = 32

_BOM = "\ufeff"
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_WIKI_RE = re.compile(r"\[\[([^\[\]]*)\]\]")
_TAG_RE = re.compile(r"(?<!\S)#([A-Za-z0-9_/-]+)")
_BACKTICKS_RE = re.compile(r"`+")
_SPLIT_RE = re.compile(r"[,\s]+")
_Scanned = list[tuple[int, str, str]]


def parse_note(
    path: str,
    text: str,
    *,
    max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
) -> Note:
    """Parse one Markdown note.

    Args:
        path: POSIX path relative to the notes root (backslashes are converted).
        text: Full text of the note; a BOM and CRLF line endings are accepted.
        max_frontmatter_bytes: Maximum UTF-8 size of the frontmatter block.

    Returns:
        The parsed note. Its id is the lowercase file stem.

    Raises:
        KnowledgeGraphError: ``frontmatter`` for unclosed or invalid frontmatter, YAML
            anchors or aliases, non-mapping documents, non-string keys, non-finite
            numbers and unsupported value types; ``too_large`` when the frontmatter
            exceeds ``max_frontmatter_bytes``.
        ValueError: If ``path`` is empty.
    """
    if not path.strip():
        raise ValueError("path must not be empty")
    posix = path.replace("\\", "/")
    front, lines, first = _split_frontmatter(posix, text, max_frontmatter_bytes)
    scanned = _scan_lines(lines, first)
    stem = stem_of(posix)
    tags = {_normalize_tag(item) for item in _as_strings(front.get("tags"), split=True)}
    tags.discard("")
    tags.update(_inline_tags(scanned))
    return Note(
        id=stem.lower(),
        path=posix,
        title=_pick_title(front, _first_h1(scanned), stem),
        frontmatter=MappingProxyType(front),
        tags=tuple(sorted(tags)),
        aliases=_aliases(front.get("aliases")),
        links=_links(scanned),
    )


def _error(path: str, message: str) -> KnowledgeGraphError:
    return KnowledgeGraphError("frontmatter", message, path)


def _split_frontmatter(
    path: str,
    text: str,
    limit: int,
) -> tuple[dict[str, Any], list[str], int]:
    """Return the frontmatter mapping, the body lines and the number of the first body line."""
    if text.startswith(_BOM):
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].rstrip() != "---":
        return {}, lines, 1
    for index in range(1, len(lines)):
        if lines[index].rstrip() in ("---", "..."):
            block = "\n".join(lines[1:index])
            start = index + 1
            return _load_frontmatter(path, block, limit), lines[start:], index + 2
    raise _error(path, "unclosed frontmatter block")


def _load_frontmatter(path: str, block: str, limit: int) -> dict[str, Any]:
    if len(block.encode("utf-8", "surrogatepass")) > limit:
        raise KnowledgeGraphError("too_large", f"frontmatter exceeds {limit} bytes", path)
    if not block.strip():
        return {}
    try:
        _scan_events(block, path)
        data = yaml.safe_load(block)
    except (yaml.YAMLError, ValueError, OverflowError, RecursionError) as exc:
        raise _error(path, f"invalid YAML: {_yaml_problem(exc)}") from exc
    if not isinstance(data, dict):
        raise _error(path, "frontmatter must be a mapping")
    _validate(data, path)
    return data


def _yaml_problem(exc: Exception) -> str:
    problem = getattr(exc, "problem", None)
    return clip(str(problem) if problem else type(exc).__name__, 80)


def _scan_events(block: str, path: str) -> None:
    """Reject anchors, aliases and excessive nesting before any object is built."""
    depth = 0
    for event in yaml.parse(block, Loader=yaml.SafeLoader):
        if getattr(event, "anchor", None) is not None:
            raise _error(path, "YAML anchors and aliases are not allowed")
        if isinstance(event, yaml.MappingStartEvent | yaml.SequenceStartEvent):
            depth += 1
            if depth > MAX_YAML_DEPTH:
                raise _error(path, "frontmatter is nested too deeply")
        elif isinstance(event, yaml.MappingEndEvent | yaml.SequenceEndEvent):
            depth -= 1


def _validate(value: Any, path: str) -> None:
    """Require string keys, finite numbers and JSON-compatible value types."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _error(path, "frontmatter keys must be strings")
            _validate(item, path)
    elif isinstance(value, list):
        for item in value:
            _validate(item, path)
    elif isinstance(value, float) and not math.isfinite(value):
        raise _error(path, "non-finite number in frontmatter")
    elif value is not None and not isinstance(value, str | int | float | date):
        name = type(value).__name__
        raise _error(path, f"unsupported value type: {name}")


def _as_strings(value: Any, *, split: bool) -> list[str]:
    if isinstance(value, str):
        return _SPLIT_RE.split(value) if split else [value]
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str | int) and not isinstance(v, bool)]
    return []


def _normalize_tag(item: str) -> str:
    return item.strip().lstrip("#").strip().lower()


def _aliases(value: Any) -> tuple[str, ...]:
    cleaned = (item.strip() for item in _as_strings(value, split=False))
    return tuple(dict.fromkeys(item for item in cleaned if item))


def _pick_title(front: dict[str, Any], heading: str | None, stem: str) -> str:
    value = front.get("title")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return heading or stem


def _scan_lines(lines: list[str], first: int) -> _Scanned:
    """Return ``(number, raw, masked)`` for every line outside fenced code blocks."""
    result: _Scanned = []
    fence: tuple[str, int] | None = None
    for number, raw in enumerate(lines, start=first):
        if fence is not None:
            if _closes_fence(raw, fence):
                fence = None
            continue
        fence = _open_fence(raw)
        if fence is None:
            result.append((number, raw, _mask_inline_code(raw)))
    return result


def _open_fence(raw: str) -> tuple[str, int] | None:
    match = _FENCE_RE.match(raw)
    if match is None:
        return None
    run, info = match.group(1), match.group(2)
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


def _closes_fence(raw: str, fence: tuple[str, int]) -> bool:
    match = _FENCE_RE.match(raw)
    if match is None:
        return False
    run = match.group(1)
    return run[0] == fence[0] and len(run) >= fence[1] and not match.group(2).strip()


def _mask_inline_code(line: str) -> str:
    """Replace inline code spans by NUL characters, keeping the line length (linear time)."""
    if "`" not in line:
        return line
    runs = [(match.start(), match.end()) for match in _BACKTICKS_RE.finditer(line)]
    partner: list[int | None] = [None] * len(runs)
    last_seen: dict[int, int] = {}
    for index in range(len(runs) - 1, -1, -1):
        size = runs[index][1] - runs[index][0]
        partner[index] = last_seen.get(size)
        last_seen[size] = index
    chars = list(line)
    index = 0
    while index < len(runs):
        closer = partner[index]
        if closer is None:
            index += 1
            continue
        start, end = runs[index][0], runs[closer][1]
        chars[start:end] = "\0" * (end - start)
        index = closer + 1
    return "".join(chars)


def _first_h1(lines: _Scanned) -> str | None:
    for _, raw, _ in lines:
        text = _h1_text(raw)
        if text:
            return text
    return None


def _h1_text(line: str) -> str | None:
    indent = len(line) - len(line.lstrip(" "))
    rest = line[indent:]
    if indent > 3 or len(rest) < 2 or rest[0] != "#" or rest[1] not in " \t":
        return None
    text = rest[1:].strip()
    stripped = text.rstrip("#")
    if stripped != text and (not stripped or stripped[-1] in " \t"):
        text = stripped.strip()
    return text or None


def _inline_tags(lines: _Scanned) -> set[str]:
    tags: set[str] = set()
    for _, _, masked in lines:
        for match in _TAG_RE.finditer(masked):
            tag = match.group(1)
            if not tag.isdigit():
                tags.add(tag.lower())
    return tags


def _links(lines: _Scanned) -> tuple[Link, ...]:
    found: list[Link] = []
    for number, _, masked in lines:
        for match in _WIKI_RE.finditer(masked):
            link = _parse_link(match.group(1), number)
            if link is not None:
                found.append(link)
    return tuple(found)


def _parse_link(inner: str, line: int) -> Link | None:
    if "\0" in inner:
        return None
    target_part, _, label_part = inner.partition("|")
    target, _, heading_part = target_part.partition("#")
    target = target.strip()
    if target.lower().endswith(".md"):
        target = target[:-3].strip()
    if not target:
        return None
    return Link(target, label_part.strip() or None, heading_part.strip() or None, line)
