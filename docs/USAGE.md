# Usage

## Python API

```python
from pathlib import Path

from md_knowledge_graph import build_graph, load_notes, render_index

result = load_notes(Path("notes"), strict=False)
graph = build_graph(result.notes)
print(graph.broken, graph.orphans)
Path("notes/INDEX.md").write_text(render_index(graph, group_by="tag"), encoding="utf-8")
```

- `parse_note(path, text)` parses one note (frontmatter, title, tags, wiki links).
- `load_notes(root)` reads every `.md` file below `root`. It skips `.git`, `node_modules` and
  `INDEX.md` by default, never follows symlinks that leave the root and turns non-UTF-8 files
  into warnings (at most 1000, plus one `and N more` line).
- `build_graph(notes)` resolves links and returns a `Graph` with `nodes`, `edges`, `broken`,
  `orphans` and `backlinks`. `Graph.to_json()` returns JSON-compatible data (`version` 1).
- `render_index(graph, group_by="folder" | "tag")` returns the text of `INDEX.md`.

Every failure is a `KnowledgeGraphError` with a stable `code` (`frontmatter`, `too_large`,
`root_missing`, `too_many_notes`) and the `path` it refers to.

## Command line

```text
md-knowledge-graph ROOT [--index PATH] [--json PATH] [--group-by folder|tag] [--strict] [--check]
```

Without `--index` and `--json` the outputs are `ROOT/INDEX.md` and `ROOT/graph.json`. With
`--check` nothing is written; the exit code is 1 when an output differs from what would be
generated. Output is byte-deterministic, so it can run in CI.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | broken links under `--strict`, outdated output under `--check`, or a size limit exceeded |
| 2 | usage error, IO error, missing root or invalid frontmatter in strict mode |

## Resolution rules

- Targets are matched case-insensitively by file stem or by `folder/stem`, then by frontmatter
  `aliases`. A target matching several notes is `ambiguous`; matching none is `missing`.
- Notes sharing a stem get the id `folder/stem`; bare links to them are ambiguous.
- A note is an orphan when it has no links to or from another note. Broken links count as
  outbound links; a link to itself does not count.
- Notes with unclosed or invalid frontmatter are skipped with a warning unless `strict` is set.
