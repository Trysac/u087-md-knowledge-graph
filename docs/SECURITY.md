# Security notes

## Threat model

`trysac-md-knowledge-graph` reads files from a directory and writes INDEX.md and graph.json. Its input is untrusted note content.

### Defended

- **Unsafe YAML**: frontmatter is parsed with `yaml.safe_load`; the document is first scanned with `yaml.parse`, and any anchor or alias is rejected before objects are built. Nesting depth is bounded.
- **Oversized input**: frontmatter is limited to 65,536 bytes by default, files to 1 MiB, and the number of notes to 20,000.
- **Path escape**: symlinks that resolve outside the root and symlinked directories are not followed.
- **Markdown injection in INDEX.md**: link text escapes backslash, `[` and `]`; paths percent-encode spaces and parentheses.
- **Invalid JSON values**: non-finite floats and non-string keys are rejected, and JSON is written with `allow_nan=False`.
- **Invalid encodings**: files that are not valid UTF-8 are skipped with a warning.
- **Code execution**: no `eval`, `exec` or pickle is used.

### Not defended

- **Resource use below the limits**: many files just under the size limits, or deep but permitted structures, still consume CPU and memory; the whole file is read into memory.
- **Race conditions**: files may change between listing and reading; the tool does not lock the directory.
- **Output overwrite**: without `--check`, the CLI overwrites `--index` and `--json` targets (default `ROOT/INDEX.md` and `ROOT/graph.json`) without confirmation.
- **Dependency vulnerabilities**: PyYAML is pinned to the 6.x line; its own parser flaws are not mitigated here.
- **Trust of the notes themselves**: note text is treated as data, not sanitised for HTML or other renderers.

## Supply chain

No runtime dependencies other than PyYAML. Dependabot runs weekly; actions are pinned to major versions; workflow permissions are minimal. `gitleaks` runs in the local gates and in CI; `.env` files are git-ignored.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
