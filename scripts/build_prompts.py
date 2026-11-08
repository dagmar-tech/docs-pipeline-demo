#!/usr/bin/env python3
"""Build one review-ready prompt per doc that a release touched.

This script does not call any AI. It assembles everything a model needs
(rules, product facts, the release changes, the current page) into a prompt
file. A person runs the prompt in Claude, saves the answer as a draft, and
reviews it with review/weekly-review-checklist.md before anything is published.

Keeping the "draft" step separate from the "publish" step is deliberate: the
model drafts, the checks verify, a person decides.

Usage:
    python scripts/build_prompts.py                 # current release
    python scripts/build_prompts.py --release 2026.11
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from drift_check import load_doc, load_yaml, release_key

PROMPT = """\
# Task: update one help-center page for release {release}

You are drafting an update for a human reviewer. Nothing you write is published
automatically. Follow the rules exactly.

## Rules

{rules}

## Product facts (the only source of truth for names, labels and numbers)

```yaml
{facts}
```

## Release changes that affect this page

{changes}

## Current page

````markdown
{page}
````

## What to return

1. The full updated page in Markdown. Keep the front matter as it is, including
   `last_verified_release` (a person updates that after review).
2. **Change summary:** a short list of what you changed and why, citing change IDs.
3. **Reviewer questions:** every place where the release changes or product facts
   did not give you enough information. Do not guess. Ask.
"""

NEW_DOC_PROMPT = """\
# Task: draft a new help-center page for release {release}

You are drafting a first version for a human reviewer. Nothing you write is
published automatically. Follow the rules exactly.

## Rules

{rules}

## Product facts (the only source of truth for names, labels and numbers)

```yaml
{facts}
```

## What is new

{changes}

## Style reference (an existing page, for tone and structure only)

````markdown
{page}
````

## What to return

1. A new page in Markdown with this front matter: title, slug,
   last_verified_release: "{release}", owner: support.
2. **Change summary:** what the page covers and which change IDs it documents.
3. **Reviewer questions:** everything you could not answer from the facts above.
   Do not invent menu names, steps or limits.
"""


def facts_for_prompt(facts: dict) -> str:
    subset = {key: facts[key] for key in ("ui_labels", "limits", "deprecated_terms") if key in facts}
    return yaml.safe_dump(subset, sort_keys=False).rstrip()


def format_changes(changes: list[dict]) -> str:
    return "\n".join(f"- **{c['id']}** ({c['type']}): {c['summary']}" for c in changes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", default=None, help="Release version, e.g. 2026.11 (default: current_release)")
    parser.add_argument("--docs", default="docs")
    parser.add_argument("--releases", default="releases")
    parser.add_argument("--facts", default="product-facts.yml")
    parser.add_argument("--rules", default="rules/style-and-accuracy.md")
    parser.add_argument("--out", default="drafts")
    args = parser.parse_args()

    facts = load_yaml(Path(args.facts))
    version = str(args.release or facts["current_release"])
    release_file = Path(args.releases) / f"{version}.yml"
    release = load_yaml(release_file)
    rules = Path(args.rules).read_text(encoding="utf-8").strip()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = {}
    for path in sorted(Path(args.docs).glob("*.md")):
        doc = load_doc(path)
        docs[doc.meta.get("slug", path.stem)] = doc

    per_doc: dict[str, list[dict]] = {}
    new_docs: list[dict] = []
    for change in release.get("changes", []):
        for slug in change.get("affects_docs", []):
            doc = docs.get(slug)
            if doc and release_key(str(doc.meta.get("last_verified_release", "0"))) < release_key(version):
                per_doc.setdefault(slug, []).append(change)
        if change.get("needs_new_doc"):
            new_docs.append(change)

    index = [f"# Prompt pack for release {version}", "",
             "Run each prompt in Claude, save the answer as `<name>.draft.md` next to it, "
             "then review it with `review/weekly-review-checklist.md`.", ""]

    for slug, changes in per_doc.items():
        text = PROMPT.format(
            release=version, rules=rules, facts=facts_for_prompt(facts),
            changes=format_changes(changes), page="\n".join(docs[slug].lines))
        target = out_dir / f"{slug}.prompt.md"
        target.write_text(text, encoding="utf-8")
        index.append(f"- [{target.name}]({target.name}): update `{slug}` ({len(changes)} change(s))")

    style_reference = "\n".join(docs["getting-started"].lines) if "getting-started" in docs else ""
    for change in new_docs:
        text = NEW_DOC_PROMPT.format(
            release=version, rules=rules, facts=facts_for_prompt(facts),
            changes=format_changes([change]), page=style_reference)
        target = out_dir / f"new-{change['id'].lower()}.prompt.md"
        target.write_text(text, encoding="utf-8")
        index.append(f"- [{target.name}]({target.name}): new page for {change['id']} ({change['area']})")

    (out_dir / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Wrote {len(per_doc) + len(new_docs)} prompt(s) to {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
