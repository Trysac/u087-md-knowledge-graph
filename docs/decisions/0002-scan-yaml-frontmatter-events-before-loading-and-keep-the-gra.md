# Scan YAML frontmatter events before loading and keep the graph canonical

Status: accepted (generated, pending human review)

## Context

Notes carry untrusted YAML frontmatter and the output must be byte-deterministic so CI can diff it. yaml.safe_load alone allows alias expansion (billion laughs) and deep nesting, and PyYAML has no type information, which breaks mypy --strict when it is imported directly.

## Decision

Frontmatter is size-limited first, then walked with yaml.parse: any anchor or alias is rejected and nesting deeper than 32 levels is refused before any object is built; only then is yaml.safe_load called and the result validated (string keys, finite numbers, JSON-compatible types). PyYAML is imported with importlib so strict typing does not need a stubs package. Ids, edges, broken links, orphans and backlinks are sorted, duplicate stems become path-qualified ids, and the canonical JSON dump uses sort_keys, indent 2 and ensure_ascii=False.

## Consequences

Hostile frontmatter cannot allocate unbounded memory, and two runs over the same notes produce identical bytes, so --check works in CI. Legitimate YAML that uses anchors is rejected on purpose. Notes with invalid frontmatter are skipped in lenient mode and therefore show up as missing link targets. The importlib import trades static typing of PyYAML calls for a dependency-free strict-mypy build.
