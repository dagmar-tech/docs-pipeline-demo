#!/usr/bin/env python3
"""Drift check: compare docs against product facts and release notes.

Deterministic on purpose: no AI is involved. The checks only report what they
can prove (a renamed term still in use, a number that no longer matches, a
broken link, a doc that a release touched but nobody has re-verified).
A person decides what to do about each finding.

Usage:
    python scripts/drift_check.py
    python scripts/drift_check.py --report reports/drift-report.md --fail-on stale,error
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRED_FRONT_MATTER = ("title", "slug", "last_verified_release", "owner")
SEVERITIES = ("error", "stale", "review")  # most to least serious


@dataclass
class Finding:
    severity: str
    doc: str
    line: int | None
    check: str
    message: str


@dataclass
class Doc:
    path: Path
    meta: dict
    lines: list[str]
    body_start: int  # index of the first line after the front matter


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def release_key(version: str) -> tuple[int, ...]:
    """'2026.11' -> (2026, 11) so releases compare correctly."""
    return tuple(int(part) for part in str(version).split("."))


def load_doc(path: Path) -> Doc:
    lines = path.read_text(encoding="utf-8").splitlines()
    meta: dict = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                meta = yaml.safe_load("\n".join(lines[1:index])) or {}
                body_start = index + 1
                break
    return Doc(path=path, meta=meta, lines=lines, body_start=body_start)


def check_front_matter(doc: Doc) -> list[Finding]:
    missing = [key for key in REQUIRED_FRONT_MATTER if key not in doc.meta]
    if not missing:
        return []
    return [
        Finding("error", doc.path.name, 1, "front-matter",
                f"Missing front matter field(s): {', '.join(missing)}.")
    ]


def check_deprecated_terms(doc: Doc, facts: dict) -> list[Finding]:
    findings = []
    for entry in facts.get("deprecated_terms", []):
        term = entry["term"]
        for number, line in enumerate(doc.lines[doc.body_start:], start=doc.body_start + 1):
            if term in line:
                # The rules allow a one-line "(formerly <term>)" note in the release that renamed it.
                if re.search(rf"formerly\s+\**{re.escape(term)}", line, re.IGNORECASE):
                    continue
                findings.append(Finding(
                    "stale", doc.path.name, number, "deprecated-term",
                    f"'{term}' was renamed to '{entry['replaced_by']}' in release "
                    f"{entry['since']}."))
    return findings


def check_values(doc: Doc, facts: dict) -> list[Finding]:
    findings = []
    for check in facts.get("value_checks", []):
        pattern = re.compile(check["regex"], re.IGNORECASE)
        for number, line in enumerate(doc.lines[doc.body_start:], start=doc.body_start + 1):
            match = pattern.search(line)
            if match and int(match.group(1)) != int(check["expected"]):
                findings.append(Finding(
                    "stale", doc.path.name, number, "value-mismatch",
                    f"{check['description']}: doc says {match.group(1)}, "
                    f"product facts say {check['expected']}."))
    return findings


def check_links(doc: Doc, docs_dir: Path) -> list[Finding]:
    findings = []
    link = re.compile(r"\]\(([^)#\s]+\.md)")
    for number, line in enumerate(doc.lines[doc.body_start:], start=doc.body_start + 1):
        for target in link.findall(line):
            if not (docs_dir / target).exists():
                findings.append(Finding(
                    "error", doc.path.name, number, "broken-link",
                    f"Link target '{target}' does not exist."))
    return findings


def check_releases(docs: dict[str, Doc], releases: list[dict]) -> list[Finding]:
    """Flag docs that a release touched but that were not re-verified since."""
    findings = []
    for release in releases:
        version = str(release["release"])
        for change in release.get("changes", []):
            for slug in change.get("affects_docs", []):
                doc = docs.get(slug)
                if doc is None:
                    findings.append(Finding(
                        "error", f"(slug: {slug})", None, "missing-doc",
                        f"{change['id']} in {version} points to a doc that does not exist."))
                    continue
                verified = str(doc.meta.get("last_verified_release", "0"))
                if release_key(verified) < release_key(version):
                    findings.append(Finding(
                        "review", doc.path.name, None, "release-impact",
                        f"{change['id']} ({change['type']}, release {version}): "
                        f"{change['summary']} Last verified against {verified}."))
            if change.get("needs_new_doc") and change.get("new_doc_slug") not in docs:
                findings.append(Finding(
                    "review", "(new doc)", None, "new-doc-needed",
                    f"{change['id']} ({change['area']}) introduces something new that "
                    f"needs its own page: {change['summary']}"))
    return findings


def write_report(findings: list[Finding], docs: dict[str, Doc], facts: dict, path: Path) -> None:
    ordered = sorted(findings, key=lambda f: (SEVERITIES.index(f.severity), f.doc, f.line or 0))
    counts = {severity: sum(1 for f in findings if f.severity == severity) for severity in SEVERITIES}
    lines = [
        "# Docs drift report",
        "",
        f"Product: {facts.get('product', 'unknown')} | current release: {facts.get('current_release', '?')} "
        f"| docs checked: {len(docs)}",
        "",
        f"**{counts['stale']} stale** (provably wrong) | **{counts['error']} errors** (broken structure) "
        f"| **{counts['review']} need review** (a release touched them)",
        "",
        "| Severity | Doc | Line | Check | Finding |",
        "|---|---|---|---|---|",
    ]
    for finding in ordered:
        line = finding.line if finding.line else "-"
        lines.append(f"| {finding.severity} | {finding.doc} | {line} | {finding.check} | {finding.message} |")
    if not findings:
        lines.append("| - | - | - | - | No findings. |")
    lines += [
        "",
        "## How to clear a finding",
        "",
        "- **stale / error:** fix the doc (or the product facts, if the facts are wrong) and rerun.",
        "- **review:** a person reads the doc against the release and updates "
        "`last_verified_release` in its front matter. Nothing is cleared automatically.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", default="docs")
    parser.add_argument("--releases", default="releases")
    parser.add_argument("--facts", default="product-facts.yml")
    parser.add_argument("--report", default="reports/drift-report.md")
    parser.add_argument("--fail-on", default="stale,error",
                        help="Comma-separated severities that make the exit code 1.")
    args = parser.parse_args()

    docs_dir = Path(args.docs)
    facts = load_yaml(Path(args.facts))
    releases = [load_yaml(path) for path in sorted(Path(args.releases).glob("*.yml"))]
    loaded = [load_doc(path) for path in sorted(docs_dir.glob("*.md"))]
    docs = {doc.meta.get("slug", doc.path.stem): doc for doc in loaded}

    findings: list[Finding] = []
    for doc in loaded:
        findings += check_front_matter(doc)
        findings += check_deprecated_terms(doc, facts)
        findings += check_values(doc, facts)
        findings += check_links(doc, docs_dir)
    findings += check_releases(docs, releases)

    write_report(findings, docs, facts, Path(args.report))
    fail_on = {item.strip() for item in args.fail_on.split(",") if item.strip()}
    blocking = [f for f in findings if f.severity in fail_on]
    print(f"{len(findings)} findings ({len(blocking)} blocking). Report: {args.report}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
