# md-knowledge-graph

[![PyPI version](https://img.shields.io/pypi/v/trysac-md-knowledge-graph)](https://pypi.org/project/trysac-md-knowledge-graph/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-md-knowledge-graph)](LICENSE)
[![CI](https://github.com/Trysac/u087-md-knowledge-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u087-md-knowledge-graph/actions/workflows/ci.yml)

Build an INDEX.md and a JSON graph from Markdown notes with YAML frontmatter and wiki links, reporting broken links and orphans

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-md-knowledge-graph
# or
uv add trysac-md-knowledge-graph
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import md_knowledge_graph

# normalize() trims surrounding whitespace and lower-cases the text.
print(md_knowledge_graph.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    md_knowledge_graph.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
