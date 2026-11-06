# md-knowledge-graph

[![PyPI version](https://img.shields.io/pypi/v/trysac-md-knowledge-graph)](https://pypi.org/project/trysac-md-knowledge-graph/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-md-knowledge-graph)](LICENSE)
[![CI](https://github.com/Trysac/u087-md-knowledge-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u087-md-knowledge-graph/actions/workflows/ci.yml)

Build an INDEX.md and a JSON graph from Markdown notes with YAML frontmatter and wiki links, reporting broken links and orphans.

## Problem

Folders of Markdown notes with frontmatter and wiki-style links become hard to navigate as they grow, and broken links accumulate unnoticed. Obsidian and Foam draw graphs inside an editor but provide nothing for CI or scripts. This utility parses the notes, resolves their links, and writes a deterministic index and JSON graph. In strict mode it exits with status 1 when links are broken.

## Install

```sh
pip install trysac-md-knowledge-graph
# or
uv add trysac-md-knowledge-graph
```

Requires Python 3.10 or newer. The only runtime dependency is PyYAML (>=6.0,<7).

## Usage

```python
from pathlib import Path
from md_knowledge_graph import build_graph, load_notes, render_index

result = load_notes(Path("notes"))
graph = build_graph(result.notes)
print(len(graph.broken), "broken links,", len(graph.orphans), "orphans")
Path("notes/INDEX.md").write_text(render_index(graph), encoding="utf-8")
```

Command line: `python -m md_knowledge_graph notes --strict` writes `notes/INDEX.md` and `notes/graph.json`; add `--check` to verify them without writing.

## Public API

Import name `md_knowledge_graph`, exported names: `load_notes`, `parse_note`, `build_graph`, `render_index`, `Graph`, `Edge`, `BrokenLink`, `Link`, `LoadResult`, `Note`, `KnowledgeGraphError`, `__version__`.

- `load_notes(root, *, exclude=('.git', 'node_modules', 'INDEX.md'), strict=False, max_file_bytes=1_048_576, max_notes=20_000) -> LoadResult` reads every `.md` file below `root`. `LoadResult` holds `notes` and `warnings`.
- `parse_note(path, text, *, max_frontmatter_bytes=65_536) -> Note` parses one note: frontmatter, title, tags and wiki links.
- `build_graph(notes) -> Graph` resolves links and computes edges, broken links, orphans and backlinks.
- `render_index(graph, *, group_by='folder') -> str` renders INDEX.md; `group_by` is `'folder'` or `'tag'`.
- `Graph.to_json() -> dict` returns JSON-compatible data with `version` 1.

Link resolution: a target matches by lowercase stem or path (`folder/stem`), then by frontmatter alias. A target matching several notes gives a broken link with reason `ambiguous`; one matching none gives reason `missing`.

### Errors

`KnowledgeGraphError` carries `code` and `path`. Codes: `frontmatter` (invalid or unsafe frontmatter), `too_large` (frontmatter or file over its limit, strict mode), `root_missing` (root is not a directory), `too_many_notes` (more than `max_notes` files).

### Limits and behaviour

- Frontmatter is limited to 65,536 bytes by default; YAML anchors and aliases are rejected.
- Files larger than 1 MiB are skipped with a warning (an error in strict mode).
- Symlinks that resolve outside the root and symlinked directories are not followed.
- Files that are not valid UTF-8 become warnings. Warnings are capped at 1000 plus one summary line.
- Output is byte-deterministic: the same input always yields the same index and JSON.

### CLI exit codes

0 success; 1 findings (broken links under `--strict`, outdated files under `--check`) or a size-limit failure; 2 usage, IO or parse error.

## Why not Obsidian or Foam?

Obsidian and Foam are editor-bound graph views. This utility is scriptable, runs in CI, and produces the same output bytes on every run.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
