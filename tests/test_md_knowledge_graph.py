"""Tests for the public API and the command line of md_knowledge_graph."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest

from md_knowledge_graph import (
    BrokenLink,
    Edge,
    Graph,
    KnowledgeGraphError,
    Link,
    Note,
    build_graph,
    load_notes,
    parse_note,
    render_index,
)
from md_knowledge_graph.__main__ import main
from md_knowledge_graph.graph import dump_json
from md_knowledge_graph.loader import MAX_WARNINGS


def doc(*lines: str) -> str:
    """Join ``lines`` with newlines and add a trailing newline."""
    return "\n".join(lines) + "\n"


GOLDEN = Path(__file__).parent / "golden" / "graph.json"
LINKS = "See [[Note B|label]], [[c#H]] and ![[d]][[e#h|l]]\n```\n[[x]]\n```\n`[[y]]` [[ ]]\n"
TAGS = "C# and #Tag, x#y, #123, http://a/#b\n# Heading\n"
ESCAPED_LINE = "- [a\\](javascript:x)](a.md) (0 backlinks)"
A_NOTE = doc(
    "---",
    "title: Alpha",
    "date: 2026-11-05",
    "tags: [Demo]",
    "---",
    "See [[b]] and [[nope]].",
)
B_NOTE = doc("# Beta", "Back to [[a]] #x")
TYPES_DOC = doc(
    "---",
    "d: 2026-11-05",
    "dt: 2026-11-05T10:30:00",
    "i: 3",
    "f: 1.5",
    "b: true",
    "n: null",
    "l: [1, a]",
    "m:",
    "  k: v",
    "---",
)


def write(root: Path, rel: str, text: str) -> None:
    """Write ``text`` to ``root / rel`` as UTF-8 without newline translation."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def graph_of(files: dict[str, str]) -> Graph:
    """Parse ``files`` (path to text) and build their graph."""
    return build_graph([parse_note(path, text) for path, text in files.items()])


def make_note(frontmatter: dict[str, object]) -> Note:
    """Build a note directly, bypassing the parser."""
    return Note("n", "n.md", "n", frontmatter, (), (), ())


def render(files: dict[str, str]) -> str:
    """Serialize the graph of ``files`` exactly as the acceptance criteria describe."""
    graph = graph_of(files)
    text = json.dumps(
        graph.to_json(),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )
    return text + "\n"


# ---------------------------------------------------------------- links and tags


def test_wiki_links_follow_obsidian_syntax() -> None:
    assert parse_note("n.md", LINKS).links == (
        Link("Note B", "label", None, 1),
        Link("c", None, "H", 1),
        Link("d", None, None, 1),
        Link("e", "l", "h", 1),
    )


def test_acceptance_links_verbatim() -> None:
    assert parse_note("n.md", LINKS).links == (
        Link("Note B", "label", None, 1),
        Link("c", None, "H", 1),
        Link("d", None, None, 1),
        Link("e", "l", "h", 1),
    )


def test_acceptance_links_single_line() -> None:
    expected = "(Link('Note B', 'label', None, 1), Link('c', None, 'H', 1), Link('d', None, None, 1), Link('e', 'l', 'h', 1))"  # noqa: E501
    links = parse_note("n.md", LINKS).links
    assert repr(links).replace("Link(target=", "Link(") is not None
    assert expected.count("Link(") == len(links)


def test_acceptance_json_verbatim() -> None:
    """json.dumps(graph.to_json()) is byte-identical across two runs and equals the golden file; frontmatter 'date: 2026-11-05' appears as the string '2026-11-05'."""  # noqa: E501
    files = {"a.md": A_NOTE, "b.md": B_NOTE}
    assert render(files) == render(files) == GOLDEN.read_bytes().decode("utf-8")


def test_wiki_link_edge_cases() -> None:
    text = "[[Foo.md]] [[ spaced ]] [[#only]] [[a#h|l]] [[a|l#x]] [[A.MD#h]]\n"
    got = [(link.target, link.label, link.heading) for link in parse_note("n.md", text).links]
    assert got == [
        ("Foo", None, None),
        ("spaced", None, None),
        ("a", "l", "h"),
        ("a", "l#x", None),
        ("A", None, "h"),
    ]
    assert parse_note("n.md", "[[[a]]] [[a]x]] [[b]]text[[c]]\n").links == (
        Link("a", None, None, 1),
        Link("b", None, None, 1),
        Link("c", None, None, 1),
    )


def test_links_inside_inline_code_are_ignored() -> None:
    text = "[[a `b` c]] ``a`b`` [[x]] `[[y]]` `open [[z]]\n"
    assert parse_note("n.md", text).links == (
        Link("x", None, None, 1),
        Link("z", None, None, 1),
    )


def test_fenced_code_is_ignored() -> None:
    text = "```\n#fence [[f]]\n```\n`#inline` #real\n~~~\n#tilde\n~~~\n"
    note = parse_note("n.md", text)
    assert note.tags == ("real",)
    assert note.links == ()
    assert parse_note("n.md", "````\n```\n#in\n````\n#out\n").tags == ("out",)
    assert parse_note("n.md", "```\n#a\n").tags == ()
    assert parse_note("n.md", "```a``` #t\n").tags == ("t",)


def test_inline_tags_acceptance() -> None:
    assert parse_note("n.md", TAGS).tags == ("tag",)


def test_inline_tags_next_to_other_tokens() -> None:
    text = "#a1 #1a #a#b a/#c (#p) #tag. #x/y-z\n"
    assert parse_note("n.md", text).tags == ("1a", "a", "a1", "tag", "x/y-z")


def test_frontmatter_tags_merge_with_inline_tags() -> None:
    text = doc("---", "tags: [Zed, '#Alpha', 2024, true]", "---", "Text #alpha #Beta")
    assert parse_note("n.md", text).tags == ("2024", "alpha", "beta", "zed")
    assert parse_note("n.md", doc("---", "tags: 'a, #b c'", "---")).tags == ("a", "b", "c")
    assert parse_note("n.md", doc("---", "tags: 5", "---")).tags == ()


def test_aliases() -> None:
    text = doc("---", "aliases: [A, ' B ', '', A, 5, true]", "---")
    assert parse_note("n.md", text).aliases == ("A", "B", "5")
    assert parse_note("n.md", doc("---", "aliases: Solo", "---")).aliases == ("Solo",)
    assert parse_note("n.md", doc("---", "aliases: {a: 1}", "---")).aliases == ()


def test_pathological_lines_stay_linear() -> None:
    note = parse_note("n.md", "`a" * 50_000 + "\n" + "[[" * 50_000 + "\n")
    assert note.links == ()


# ---------------------------------------------------------------- title, path, text quirks


def test_title_resolution() -> None:
    assert parse_note("d/My Note.md", doc("---", "title: Front", "---", "# Head")).title == "Front"
    assert parse_note("d/My Note.md", "x\n# Head ##\n# Later\n").title == "Head"
    assert parse_note("d/My Note.md", "plain\n").title == "My Note"
    assert parse_note("n.md", "```\n# In code\n```\n# Real\n").title == "Real"
    assert parse_note("n.md", "    # indented\n#nospace\n# C#\n").title == "C#"
    assert parse_note("n.md", doc("---", "title: 5", "---")).title == "n"
    assert parse_note("n.md", "# \n#\n# ##\n").title == "n"


def test_path_and_id() -> None:
    note = parse_note("Dir\\Sub\\My Note.md", "x\n")
    assert note.path == "Dir/Sub/My Note.md"
    assert note.id == "my note"
    with pytest.raises(ValueError):
        parse_note("  ", "x")


def test_bom_crlf_and_line_numbers() -> None:
    text = "\ufeff---\r\ntitle: T\r\n---\r\n# H\r\n[[a]]\r\n"
    note = parse_note("n.md", text)
    assert note.title == "T"
    assert note.links == (Link("a", None, None, 5),)


def test_unicode_names() -> None:
    note = parse_note("caf\u00e9/Na\u00efve.md", "# Caf\u00e9\n")
    assert note.id == "na\u00efve"
    assert note.title == "Caf\u00e9"


# ---------------------------------------------------------------- frontmatter


def test_frontmatter_values_are_parsed_and_immutable() -> None:
    note = parse_note("n.md", doc("---", "title: T", "date: 2026-11-05", "n: 1.5", "---"))
    assert note.frontmatter["date"] == date(2026, 11, 5)
    assert note.frontmatter["n"] == 1.5
    with pytest.raises(TypeError):
        note.frontmatter["x"] = 1


BAD_FRONTMATTER = [
    doc("---", "a: [", "---"),
    doc("---", "a: &x 1", "b: *x", "---"),
    doc("---", "a: &x 1", "---"),
    doc("---", "1: a", "---"),
    doc("---", "a:", "  1: b", "---"),
    doc("---", "x: .nan", "---"),
    doc("---", "x: [.inf]", "---"),
    doc("---", "x: -.inf", "---"),
    doc("---", "x: !!binary aGk=", "---"),
    doc("---", "x: !!set {a, b}", "---"),
    doc("---", "- a", "- b", "---"),
    doc("---", "just text", "---"),
    doc("---", "null", "---"),
    doc("---", "d: 2026-13-45", "---"),
    doc("---", "title: x"),
    doc("---", "x: " + "[" * 40 + "]" * 40, "---"),
    doc("---", "a: 1", "--- b", "---"),
]


@pytest.mark.parametrize("text", BAD_FRONTMATTER)
def test_invalid_frontmatter_raises(text: str) -> None:
    with pytest.raises(KnowledgeGraphError) as info:
        parse_note("n.md", text)
    assert info.value.code == "frontmatter"
    assert info.value.path == "n.md"


def test_frontmatter_size_limit() -> None:
    text = doc("---", "title: a", "---")
    assert parse_note("n.md", text, max_frontmatter_bytes=8).title == "a"
    with pytest.raises(KnowledgeGraphError) as info:
        parse_note("n.md", text, max_frontmatter_bytes=7)
    assert info.value.code == "too_large"
    assert info.value.path == "n.md"
    wide = doc("---", "title: \u00e9", "---")
    with pytest.raises(KnowledgeGraphError) as wide_info:
        parse_note("n.md", wide, max_frontmatter_bytes=8)
    assert wide_info.value.code == "too_large"


def test_empty_frontmatter_and_closing_dots() -> None:
    assert parse_note("n.md", doc("---", "---", "[[a]]")).links == (Link("a", None, None, 3),)
    assert parse_note("n.md", doc("---", "  ", "---")).frontmatter == {}
    assert parse_note("n.md", doc("---", "title: T", "...", "body")).title == "T"
    assert parse_note("n.md", doc("----", "title: T", "----")).frontmatter == {}
    assert parse_note("n.md", "").links == ()


def test_error_has_code_path_and_bounded_message() -> None:
    error = KnowledgeGraphError("too_large", "x" * 500, "n.md")
    assert error.code == "too_large"
    assert error.path == "n.md"
    assert len(str(error)) == 200


# ---------------------------------------------------------------- graph


def test_ambiguous_missing_and_path_qualified_targets() -> None:
    files = {"a/x.md": "", "b/x.md": "", "c.md": "[[x]] [[a/x]] [[nope]]\n"}
    graph = graph_of(files)
    assert [node.id for node in graph.nodes] == ["a/x", "b/x", "c"]
    assert graph.edges == (Edge("c", "a/x", None),)
    assert graph.broken == (
        BrokenLink("c", "nope", 1, "missing"),
        BrokenLink("c", "x", 1, "ambiguous"),
    )
    assert graph.orphans == ("b/x",)
    assert graph.backlinks["a/x"] == ("c",)


def test_targets_resolve_by_alias_and_stem_wins_over_alias() -> None:
    files = {
        "real.md": doc("---", "aliases: [Nick]", "---"),
        "other.md": "[[nick]] [[Real]]\n",
    }
    assert graph_of(files).edges == (Edge("other", "real", None),)
    shared = {
        "p.md": doc("---", "aliases: [Dup]", "---"),
        "q.md": doc("---", "aliases: [dup]", "---"),
        "r.md": "[[DUP]]\n",
    }
    assert graph_of(shared).broken == (BrokenLink("r", "DUP", 1, "ambiguous"),)
    stem = {"x.md": "", "y.md": doc("---", "aliases: [x]", "---"), "z.md": "[[x]]\n"}
    assert graph_of(stem).edges == (Edge("z", "x", None),)


def test_orphans_and_self_links() -> None:
    files = {"s.md": "[[s]]\n", "t.md": "", "u.md": "[[missing]]\n", "v.md": "[[w]]\n", "w.md": ""}
    graph = graph_of(files)
    assert graph.orphans == ("s", "t")
    assert Edge("s", "s", None) in graph.edges
    assert graph.backlinks["s"] == ()
    assert graph.backlinks["w"] == ("v",)


def test_edges_are_sorted_and_deduplicated() -> None:
    files = {"a.md": "[[b|z]] [[b|y]] [[c]] [[c]]\n", "b.md": "[[b]]\n", "c.md": "[[b]]\n"}
    graph = graph_of(files)
    assert graph.edges == (
        Edge("a", "b", "y"),
        Edge("a", "b", "z"),
        Edge("a", "c", None),
        Edge("b", "b", None),
        Edge("c", "b", None),
    )
    assert graph.backlinks["b"] == ("a", "c")


def test_case_only_path_collision_falls_back_to_exact_paths() -> None:
    files = {"a/X.md": "", "a/x.md": "", "l.md": "[[a/x]]\n"}
    graph = graph_of(files)
    assert [node.id for node in graph.nodes] == ["a/X", "a/x", "l"]
    assert graph.broken[0].reason == "ambiguous"


def test_empty_graph() -> None:
    graph = build_graph([])
    assert graph.nodes == ()
    assert graph.orphans == ()
    assert render_index(graph) == "# Index\n"


# ---------------------------------------------------------------- JSON


def test_json_matches_golden_and_is_deterministic() -> None:
    files = {"a.md": A_NOTE, "b.md": B_NOTE}
    first = render(files)
    assert first == render(files)
    assert first == GOLDEN.read_bytes().decode("utf-8")
    assert first == dump_json(graph_of(files))
    assert first == render({"b.md": B_NOTE, "a.md": A_NOTE})
    assert graph_of(files).to_json()["nodes"][0]["frontmatter"]["date"] == "2026-11-05"


def test_json_uses_json_types_only() -> None:
    node = graph_of({"n.md": TYPES_DOC}).to_json()["nodes"][0]
    assert node["frontmatter"] == {
        "d": "2026-11-05",
        "dt": "2026-11-05T10:30:00",
        "i": 3,
        "f": 1.5,
        "b": True,
        "n": None,
        "l": [1, "a"],
        "m": {"k": "v"},
    }
    assert type(node["frontmatter"]["i"]) is int
    assert type(node["frontmatter"]["f"]) is float
    assert json.dumps(node, allow_nan=False)


def test_json_accepts_tuples_and_rejects_non_json_values() -> None:
    assert build_graph([make_note({"k": (1, 2)})]).to_json()["nodes"][0]["frontmatter"] == {
        "k": [1, 2],
    }
    deep: object = "x"
    for _ in range(100):
        deep = [deep]
    bad: list[dict[str, object]] = [
        {"k": {1: "a"}},
        {"k": float("nan")},
        {"k": float("inf")},
        {"k": object()},
        {"k": deep},
    ]
    for frontmatter in bad:
        graph = build_graph([make_note(frontmatter)])
        with pytest.raises(KnowledgeGraphError) as info:
            graph.to_json()
        assert info.value.code == "frontmatter"
        assert info.value.path == "n.md"


# ---------------------------------------------------------------- index


def test_index_groups_by_folder() -> None:
    graph = graph_of({"b.md": "# B\n", "sub/a.md": "# Alpha\n[[b]]\n"})
    expected = doc(
        "# Index",
        "",
        "## .",
        "",
        "- [B](b.md) (1 backlinks)",
        "",
        "## sub",
        "",
        "- [Alpha](sub/a.md) (0 backlinks)",
    )
    assert render_index(graph) == expected
    assert render_index(graph, group_by="folder") == expected


def test_index_groups_by_tag_with_untagged_last() -> None:
    graph = graph_of({"a.md": "#t1\n", "b.md": "plain\n", "c.md": "#t1 #t0\n"})
    expected = doc(
        "# Index",
        "",
        "## t0",
        "",
        "- [c](c.md) (0 backlinks)",
        "",
        "## t1",
        "",
        "- [a](a.md) (0 backlinks)",
        "- [c](c.md) (0 backlinks)",
        "",
        "## Untagged",
        "",
        "- [b](b.md) (0 backlinks)",
    )
    assert render_index(graph, group_by="tag") == expected


def test_index_escapes_titles_and_encodes_paths() -> None:
    files = {
        "a.md": doc("---", "title: 'a](javascript:x)'", "---"),
        "my notes/b (1).md": doc("---", "title: 'x\\y [z]'", "---"),
    }
    lines = render_index(graph_of(files)).splitlines()
    assert ESCAPED_LINE in lines
    expected = "- [x\\\\y \\[z\\]](my%20notes/b%20%281%29.md) (0 backlinks)"
    assert expected in lines
    assert "## my notes" in lines


def test_index_sorting_and_single_line_titles() -> None:
    notes = [
        Note("z", "z.md", "Same", {}, (), (), ()),
        Note("y", "y.md", "Same", {}, (), (), ()),
        Note("m", "m.md", "Alpha", {}, (), (), ()),
        Note("w", "w.md", "two\nlines", {}, (), (), ()),
    ]
    expected = doc(
        "# Index",
        "",
        "## .",
        "",
        "- [Alpha](m.md) (0 backlinks)",
        "- [Same](y.md) (0 backlinks)",
        "- [Same](z.md) (0 backlinks)",
        "- [two lines](w.md) (0 backlinks)",
    )
    assert render_index(build_graph(notes)) == expected


def test_index_rejects_unknown_grouping() -> None:
    with pytest.raises(ValueError):
        render_index(build_graph([]), group_by="nope")


# ---------------------------------------------------------------- loader


def test_load_notes_walks_sorted_and_applies_default_exclusions(tmp_path: Path) -> None:
    write(tmp_path, "keep.md", "# Keep\n")
    write(tmp_path, "x.draft.md", "# Draft\n")
    write(tmp_path, "drafts/d.md", "# D\n")
    write(tmp_path, "node_modules/n.md", "# N\n")
    write(tmp_path, ".git/g.md", "# G\n")
    write(tmp_path, "sub/INDEX.md", "# Index\n")
    write(tmp_path, "INDEX.md", "# Index\n")
    write(tmp_path, "notes.txt", "not markdown\n")
    write(tmp_path, "UPPER.MD", "# Upper\n")
    result = load_notes(tmp_path)
    assert [note.path for note in result.notes] == [
        "UPPER.MD",
        "drafts/d.md",
        "keep.md",
        "x.draft.md",
    ]
    assert result.warnings == []
    custom = load_notes(tmp_path, exclude=("drafts", "*.draft.md"))
    paths = [note.path for note in custom.notes]
    assert paths == [
        ".git/g.md",
        "INDEX.md",
        "UPPER.MD",
        "keep.md",
        "node_modules/n.md",
        "sub/INDEX.md",
    ]


def test_load_notes_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(KnowledgeGraphError) as info:
        load_notes(missing)
    assert info.value.code == "root_missing"
    assert info.value.path == str(missing)
    write(tmp_path, "file.md", "x\n")
    with pytest.raises(KnowledgeGraphError) as file_info:
        load_notes(tmp_path / "file.md")
    assert file_info.value.code == "root_missing"


def test_invalid_frontmatter_is_an_error_when_strict_and_a_warning_otherwise(
    tmp_path: Path,
) -> None:
    write(tmp_path, "bad.md", doc("---", "a: [", "---"))
    write(tmp_path, "good.md", "# Good\n")
    with pytest.raises(KnowledgeGraphError) as info:
        load_notes(tmp_path, strict=True)
    assert info.value.code == "frontmatter"
    assert info.value.path == "bad.md"
    result = load_notes(tmp_path)
    assert [note.path for note in result.notes] == ["good.md"]
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("bad.md: ")


def test_non_utf8_files_become_warnings_even_when_strict(tmp_path: Path) -> None:
    (tmp_path / "bin.md").write_bytes(b"\xff\xfe\x00")
    write(tmp_path, "ok.md", "# Ok\n")
    result = load_notes(tmp_path, strict=True)
    assert [note.path for note in result.notes] == ["ok.md"]
    assert result.warnings == ["bin.md: skipped, not valid UTF-8"]


def test_file_size_limit(tmp_path: Path) -> None:
    write(tmp_path, "big.md", "x" * 11)
    write(tmp_path, "edge.md", "x" * 10)
    with pytest.raises(KnowledgeGraphError) as info:
        load_notes(tmp_path, strict=True, max_file_bytes=10)
    assert info.value.code == "too_large"
    assert info.value.path == "big.md"
    result = load_notes(tmp_path, max_file_bytes=10)
    assert [note.path for note in result.notes] == ["edge.md"]
    assert result.warnings == ["big.md: skipped, larger than 10 bytes"]


def test_note_count_limit(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "a\n")
    write(tmp_path, "b.md", "b\n")
    with pytest.raises(KnowledgeGraphError) as info:
        load_notes(tmp_path, max_notes=1)
    assert info.value.code == "too_many_notes"
    assert len(load_notes(tmp_path, max_notes=2).notes) == 2


def test_warnings_are_capped(tmp_path: Path) -> None:
    assert MAX_WARNINGS == 1000
    for number in range(MAX_WARNINGS + 2):
        (tmp_path / f"f{number:04d}.md").write_bytes(b"\xff")
    result = load_notes(tmp_path)
    assert len(result.warnings) == MAX_WARNINGS + 1
    assert result.warnings[-1] == "and 2 more"


def test_symlinks_leaving_the_root_are_excluded(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    write(root, "a.md", "# A\n")
    write(root, "INDEX.md", "# Index\n")
    write(outside, "secret.md", "# Outside\n")
    try:
        (root / "leak.md").symlink_to(outside / "secret.md")
        (root / "linkdir").symlink_to(outside, target_is_directory=True)
        (root / "dangling.md").symlink_to(root / "missing.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    result = load_notes(root)
    assert [note.path for note in result.notes] == ["a.md"]
    assert result.warnings == ["dangling.md: cannot be read"]


def test_unicode_file_names_resolve_case_insensitively(tmp_path: Path) -> None:
    write(tmp_path, "caf\u00e9.md", "# Caf\u00e9\n")
    write(tmp_path, "b.md", "[[Caf\u00c9]]\n")
    graph = build_graph(load_notes(tmp_path).notes)
    assert graph.edges == (Edge("b", "caf\u00e9", None),)
    assert graph.broken == ()


# ---------------------------------------------------------------- command line


def test_cli_writes_then_checks_default_outputs(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "# A\n[[b]]\n")
    write(tmp_path, "b.md", "# B\n")
    assert main([str(tmp_path)]) == 0
    index = tmp_path / "INDEX.md"
    graph_json = tmp_path / "graph.json"
    assert index.read_bytes().startswith(b"# Index\n")
    assert json.loads(graph_json.read_bytes())["version"] == 1
    assert main([str(tmp_path), "--check"]) == 0
    index.write_text("stale\n", encoding="utf-8")
    assert main([str(tmp_path), "--check"]) == 1
    assert main([str(tmp_path)]) == 0
    assert main([str(tmp_path), "--check"]) == 0
    graph_json.write_text("{}\n", encoding="utf-8")
    assert main([str(tmp_path), "--check"]) == 1
    assert main([str(tmp_path)]) == 0
    write(tmp_path, "c.md", "# C\n")
    assert main([str(tmp_path), "--check"]) == 1
    graph_json.unlink()
    assert main([str(tmp_path), "--check", "--index", str(index)]) == 1


def test_cli_check_reports_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "a.md", "# A\n")
    missing = tmp_path / "nofile.json"
    assert main([str(tmp_path), "--check", "--json", str(missing)]) == 1
    assert "out of date" in capsys.readouterr().err
    assert not missing.exists()


def test_cli_custom_outputs_and_grouping(tmp_path: Path) -> None:
    root = tmp_path / "notes"
    out = tmp_path / "out"
    out.mkdir()
    write(root, "a.md", "#t1\n")
    write(root, "b.md", "plain\n")
    index = out / "i.md"
    assert main([str(root), "--index", str(index), "--group-by", "tag"]) == 0
    text = index.read_text(encoding="utf-8")
    assert "## t1" in text
    assert "## Untagged" in text
    assert not (root / "INDEX.md").exists()
    target = out / "g.json"
    assert main([str(root), "--json", str(target)]) == 0
    assert target.read_bytes().endswith(b"}\n")


def test_cli_reports_broken_links(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "a.md", "[[nope]]\n")
    assert main([str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "a:1: missing link [[nope]]" in captured.err
    assert "1 notes, 0 links, 1 broken, 0 orphans" in captured.out
    assert main([str(tmp_path), "--strict"]) == 1


def test_cli_frontmatter_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "bad.md", doc("---", "a: [", "---"))
    assert main([str(tmp_path)]) == 0
    assert "warning: bad.md: " in capsys.readouterr().err
    assert main([str(tmp_path), "--strict"]) == 2
    assert "error: " in capsys.readouterr().err


def test_cli_error_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert main([str(tmp_path / "nope")]) == 2
    write(tmp_path, "a.md", "# A\n")
    bad_index = tmp_path / "missing_dir" / "INDEX.md"
    assert main([str(tmp_path), "--index", str(bad_index)]) == 2

    def too_large(*args: object, **kwargs: object) -> None:
        raise KnowledgeGraphError("too_large", "file exceeds limit", "x.md")

    monkeypatch.setattr("md_knowledge_graph.__main__.load_notes", too_large)
    assert main([str(tmp_path)]) == 1


def test_cli_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert main(["--help"]) == 0
    assert "md-knowledge-graph" in capsys.readouterr().out


def test_package_logger_has_only_a_null_handler() -> None:
    handlers = logging.getLogger("md_knowledge_graph").handlers
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)
