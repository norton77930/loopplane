"""Documentation link contract (082, US4): every relative link and intra-repo
anchor in the published documentation resolves against the committed tree, and
every thematic guide is reachable from the documentation index (FR-010; SC-006).

Offline and standard-library only: external URLs are collected and checked for
shape, never fetched, so this test can never fail because a third-party site is
down.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
GUIDES = DOCS / "guides"

# Published Markdown: the docs tree plus the root-level documents a reader of the
# public repository lands on.
ROOT_DOCUMENTS = (
    "README.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
)

_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_REFERENCE_LINK = re.compile(r"^[ ]{0,3}\[[^\]\n]+\]:[ \t]+<?([^>\s]+)>?", re.MULTILINE)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.MULTILINE)
_INLINE_LINK_TEXT = re.compile(r"\[([^\]\n]*)\]\([^)\s]+\)")
_SLUG_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)


def published_documents() -> list[Path]:
    """Every Markdown file whose links this contract governs."""

    documents = sorted(DOCS.rglob("*.md"))
    documents += [REPO_ROOT / name for name in ROOT_DOCUMENTS]
    return [path for path in documents if path.is_file()]


def extract_links(text: str) -> list[str]:
    """Inline and reference-style Markdown targets, excluding fenced code."""

    unfenced = _FENCE.sub("", text)
    return _LINK.findall(unfenced) + _REFERENCE_LINK.findall(unfenced)


def heading_slugs(text: str) -> set[str]:
    """The anchor slugs a Markdown document exposes, GitHub-style."""

    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for _, raw in _HEADING.findall(_FENCE.sub("", text)):
        rendered = _INLINE_LINK_TEXT.sub(r"\1", raw)
        base = _SLUG_STRIP.sub("", rendered.strip().lower())
        base = re.sub(r"\s", "-", base)
        seen = counts.get(base, 0)
        counts[base] = seen + 1
        slugs.add(base if seen == 0 else f"{base}-{seen}")
    return slugs


def _split_anchor(target: str) -> tuple[str, str | None]:
    path, _, anchor = target.partition("#")
    return path, (anchor or None)


def relative_link_failures(documents: list[Path], repo_root: Path) -> list[str]:
    """Relative targets that are missing or escape the governed repository root."""

    broken: list[str] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for target in extract_links(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path, _ = _split_anchor(target)
            if not path:
                continue
            resolved = (document.parent / path).resolve()
            if not resolved.is_relative_to(repo_root) or not resolved.exists():
                relative = document.relative_to(repo_root).as_posix()
                broken.append(f"{relative} -> {target}")
    return broken


def test_the_walker_sees_the_documentation() -> None:
    documents = published_documents()
    assert len(documents) >= 30, f"expected the docs tree, found {len(documents)}"
    total = sum(
        len(extract_links(path.read_text(encoding="utf-8"))) for path in documents
    )
    assert total >= 100, f"expected many links to check, found {total}"


def test_every_relative_link_resolves() -> None:
    broken = relative_link_failures(published_documents(), REPO_ROOT)
    assert not broken, "unresolved or escaping relative links:\n" + "\n".join(broken)


def test_every_intra_document_anchor_resolves() -> None:
    broken: list[str] = []
    for document in published_documents():
        text = document.read_text(encoding="utf-8")
        slugs = heading_slugs(text)
        for target in extract_links(text):
            if not target.startswith("#"):
                continue
            anchor = target[1:]
            if anchor and anchor not in slugs:
                relative = document.relative_to(REPO_ROOT).as_posix()
                broken.append(f"{relative} -> {target}")
    assert not broken, "unresolved intra-document anchors:\n" + "\n".join(broken)


def test_every_cross_document_anchor_resolves() -> None:
    broken: list[str] = []
    for document in published_documents():
        text = document.read_text(encoding="utf-8")
        for target in extract_links(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path, anchor = _split_anchor(target)
            if not path or anchor is None or not path.endswith(".md"):
                continue
            resolved = (document.parent / path).resolve()
            if not resolved.is_relative_to(REPO_ROOT) or not resolved.is_file():
                continue  # reported by the relative-link test
            if anchor not in heading_slugs(resolved.read_text(encoding="utf-8")):
                relative = document.relative_to(REPO_ROOT).as_posix()
                broken.append(f"{relative} -> {target}")
    assert not broken, "unresolved cross-document anchors:\n" + "\n".join(broken)


def test_external_links_are_well_formed_but_never_fetched() -> None:
    malformed: list[str] = []
    for document in published_documents():
        for target in extract_links(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://")):
                remainder = target.split("//", 1)[1]
                if not remainder or remainder.startswith("/"):
                    malformed.append(f"{document.name} -> {target}")
            elif target.startswith("mailto:") and "@" not in target:
                malformed.append(f"{document.name} -> {target}")
    assert not malformed, "malformed external links:\n" + "\n".join(malformed)


def test_every_thematic_guide_is_indexed() -> None:
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    linked = {
        target.split("#")[0].rsplit("/", 1)[-1]
        for target in extract_links(index)
        if "guides/" in target
    }
    expected = {path.name for path in GUIDES.glob("*.md")}
    assert expected, "expected thematic guides under docs/guides/"
    assert linked == expected, {
        "missing from docs/README.md": sorted(expected - linked),
        "indexed but absent": sorted(linked - expected),
    }


# --- the walker must be able to fail (anti-false-green) ------------------


def test_extract_links_ignores_fenced_code_blocks() -> None:
    text = "[real](./real.md)\n\n```sh\n[fake](./fake.md)\n```\n"
    assert extract_links(text) == ["./real.md"]


def test_heading_slugs_follow_github_rules() -> None:
    text = "# Scope boundaries (out of scope / deferred)\n## A & B\n## A & B\n"
    slugs = heading_slugs(text)
    assert "scope-boundaries-out-of-scope--deferred" in slugs
    assert "a--b" in slugs
    assert "a--b-1" in slugs, "repeated headings must get numbered anchors"


def test_reference_style_links_are_extracted() -> None:
    text = 'Read [the guide][guide].\n\n[guide]: ./guide.md "Guide"\n'
    assert extract_links(text) == ["./guide.md"]


def test_a_broken_relative_link_is_reported_by_the_walker(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    document = root / "page.md"
    document.write_text("[gone](./missing.md)\n", encoding="utf-8")
    assert relative_link_failures([document], root) == ["page.md -> ./missing.md"]


def test_an_existing_link_outside_the_repository_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (tmp_path / "outside.md").write_text("# Outside\n", encoding="utf-8")
    document = docs / "page.md"
    document.write_text("[escape](../../outside.md)\n", encoding="utf-8")
    assert relative_link_failures([document], root) == [
        "docs/page.md -> ../../outside.md"
    ]
