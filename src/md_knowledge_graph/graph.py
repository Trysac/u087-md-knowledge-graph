"""Build the link graph of a set of notes and render it."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any, Literal

from .errors import KnowledgeGraphError
from .models import Link, Note, stem_of, strip_md_suffix

Reason = Literal["missing", "ambiguous"]
GroupBy = Literal["folder", "tag"]

GRAPH_VERSION = 1
UNTAGGED = "Untagged"
_MAX_JSON_DEPTH = 64


@dataclass(frozen=True)
class Edge:
    """A resolved link between two notes, identified by note id."""

    source: str
    target: str
    label: str | None


@dataclass(frozen=True)
class BrokenLink:
    """A link that does not resolve to exactly one note."""

    source: str
    target: str
    line: int
    reason: Reason


@dataclass(frozen=True)
class Graph:
    """The link graph of a set of notes.

    Attributes:
        nodes: Notes sorted by id.
        edges: Deduplicated resolved links sorted by (source, target, label).
        broken: Unresolved links, ``missing`` or ``ambiguous``.
        orphans: Ids of notes without links to or from another note (sorted).
        backlinks: For every id, the sorted ids of the other notes that link to it.
    """

    nodes: tuple[Note, ...]
    edges: tuple[Edge, ...]
    broken: tuple[BrokenLink, ...]
    orphans: tuple[str, ...]
    backlinks: Mapping[str, tuple[str, ...]]

    def to_json(self) -> dict[str, Any]:
        """Return the graph as JSON-compatible data (``version`` 1).

        Frontmatter dates and datetimes become ISO 8601 strings; numbers stay ``int`` or
        finite ``float``.

        Raises:
            KnowledgeGraphError: ``frontmatter`` if a note holds a value JSON cannot carry.
        """
        return {
            "version": GRAPH_VERSION,
            "nodes": [_node_json(node) for node in self.nodes],
            "edges": [_edge_json(edge) for edge in self.edges],
            "broken": [_broken_json(item) for item in self.broken],
            "orphans": list(self.orphans),
            "backlinks": {key: list(value) for key, value in self.backlinks.items()},
        }


def dump_json(graph: Graph) -> str:
    """Serialize ``graph`` to the canonical, byte-deterministic JSON text."""
    text = json.dumps(
        graph.to_json(),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )
    return text + "\n"


def _jsonable(value: Any, path: str, depth: int = 0) -> Any:
    if depth > _MAX_JSON_DEPTH:
        raise KnowledgeGraphError("frontmatter", "frontmatter is nested too deeply", path)
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise KnowledgeGraphError("frontmatter", "non-finite number in frontmatter", path)
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise KnowledgeGraphError("frontmatter", "keys must be strings", path)
            result[key] = _jsonable(item, path, depth + 1)
        return result
    if isinstance(value, list | tuple):
        return [_jsonable(item, path, depth + 1) for item in value]
    name = type(value).__name__
    raise KnowledgeGraphError("frontmatter", f"unsupported frontmatter type: {name}", path)


def _link_json(link: Link) -> dict[str, Any]:
    return {
        "target": link.target,
        "label": link.label,
        "heading": link.heading,
        "line": link.line,
    }


def _node_json(node: Note) -> dict[str, Any]:
    return {
        "id": node.id,
        "path": node.path,
        "title": node.title,
        "frontmatter": _jsonable(dict(node.frontmatter), node.path),
        "tags": list(node.tags),
        "aliases": list(node.aliases),
        "links": [_link_json(link) for link in node.links],
    }


def _edge_json(edge: Edge) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "label": edge.label}


def _broken_json(item: BrokenLink) -> dict[str, Any]:
    return {
        "source": item.source,
        "target": item.target,
        "line": item.line,
        "reason": item.reason,
    }


def _edge_key(edge: Edge) -> tuple[str, str, str]:
    return (edge.source, edge.target, edge.label or "")


def _broken_key(item: BrokenLink) -> tuple[str, int, str, str]:
    return (item.source, item.line, item.target, item.reason)


def _requalify(notes: Sequence[Note], make_id: Callable[[str], str]) -> list[Note]:
    counts = Counter(note.id for note in notes)
    result: list[Note] = []
    for note in notes:
        if counts[note.id] > 1:
            note = replace(note, id=make_id(note.path))
        result.append(note)
    return result


def _assign_ids(notes: Sequence[Note]) -> list[Note]:
    """Give duplicate stems path-qualified ids; fall back to the case-preserved path."""
    staged = _requalify(notes, lambda path: strip_md_suffix(path).lower())
    return _requalify(staged, strip_md_suffix)


def build_graph(notes: Sequence[Note]) -> Graph:
    """Resolve the links of ``notes`` and build the graph.

    A target resolves by lowercase stem or path (``folder/stem``), then by frontmatter
    alias. A target matching several notes is ``ambiguous``; one matching none is
    ``missing``. Notes sharing a stem get the id ``folder/stem``. A note is an orphan
    when it has no links to or from another note; broken links count as outbound links
    and a link to itself does not count.
    """
    nodes = sorted(_assign_ids(notes), key=lambda node: node.id)
    stems: dict[str, set[str]] = {}
    paths: dict[str, set[str]] = {}
    aliases: dict[str, set[str]] = {}
    for node in nodes:
        stems.setdefault(stem_of(node.path).lower(), set()).add(node.id)
        paths.setdefault(strip_md_suffix(node.path).lower(), set()).add(node.id)
        for alias in node.aliases:
            aliases.setdefault(alias.lower(), set()).add(node.id)
    edges: set[Edge] = set()
    broken: list[BrokenLink] = []
    for node in nodes:
        for link in node.links:
            key = link.target.lower()
            found = stems.get(key, set()) | paths.get(key, set())
            found = found or aliases.get(key, set())
            if len(found) == 1:
                edges.add(Edge(node.id, next(iter(found)), link.label))
            else:
                reason: Reason = "ambiguous" if found else "missing"
                broken.append(BrokenLink(node.id, link.target, link.line, reason))
    inbound: dict[str, set[str]] = {node.id: set() for node in nodes}
    linked: set[str] = {item.source for item in broken}
    for edge in edges:
        if edge.source != edge.target:
            inbound[edge.target].add(edge.source)
            linked.update((edge.source, edge.target))
    backlinks = {key: tuple(sorted(value)) for key, value in sorted(inbound.items())}
    return Graph(
        nodes=tuple(nodes),
        edges=tuple(sorted(edges, key=_edge_key)),
        broken=tuple(sorted(broken, key=_broken_key)),
        orphans=tuple(node.id for node in nodes if node.id not in linked),
        backlinks=MappingProxyType(backlinks),
    )


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _encode_path(path: str) -> str:
    return path.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def _group_names(node: Note, group_by: GroupBy) -> list[str]:
    if group_by == "tag":
        return list(node.tags) or [UNTAGGED]
    return [PurePosixPath(node.path).parent.as_posix()]


def render_index(graph: Graph, *, group_by: GroupBy = "folder") -> str:
    """Render ``graph`` as the text of an ``INDEX.md`` file.

    The index has an H1 ``Index``, one H2 per group (folder path or tag, ``Untagged``
    last) and one line ``- [Title](path) (N backlinks)`` per note, sorted by title then id.
    Link text escapes ``\\``, ``[`` and ``]``; paths percent-encode spaces and parentheses.

    Raises:
        ValueError: If ``group_by`` is neither ``folder`` nor ``tag``.
    """
    if group_by not in ("folder", "tag"):
        raise ValueError("group_by must be 'folder' or 'tag'")
    groups: dict[str, list[Note]] = {}
    for node in graph.nodes:
        for name in _group_names(node, group_by):
            groups.setdefault(name, []).append(node)
    ordered = sorted(groups, key=lambda name: (group_by == "tag" and name == UNTAGGED, name))
    lines = ["# Index"]
    for name in ordered:
        lines.extend(["", f"## {_escape(name)}", ""])
        for node in sorted(groups[name], key=lambda item: (item.title, item.id)):
            count = len(graph.backlinks.get(node.id, ()))
            label = _escape(_one_line(node.title))
            lines.append(f"- [{label}]({_encode_path(node.path)}) ({count} backlinks)")
    return "\n".join(lines) + "\n"
