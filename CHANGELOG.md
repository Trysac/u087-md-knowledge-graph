# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `md_knowledge_graph`: parse Markdown notes with YAML frontmatter and wiki links, build a byte-deterministic JSON graph and `INDEX.md`, report broken links and orphans, with a CI-friendly `md-knowledge-graph` CLI (`--strict`, `--check`).
- Initial project structure from the factory utility template.
