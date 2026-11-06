"""Index and link graph for Markdown notes with YAML frontmatter and wiki links."""

from __future__ import annotations

import logging

from .errors import KnowledgeGraphError
from .graph import BrokenLink, Edge, Graph, build_graph, render_index
from .loader import LoadResult, load_notes
from .models import Link, Note
from .parser import parse_note

__all__ = [
    "BrokenLink",
    "Edge",
    "Graph",
    "KnowledgeGraphError",
    "Link",
    "LoadResult",
    "Note",
    "__version__",
    "build_graph",
    "load_notes",
    "parse_note",
    "render_index",
]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
