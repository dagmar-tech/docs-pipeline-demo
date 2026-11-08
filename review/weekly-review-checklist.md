# Weekly review checklist

Run once a week, and after every release. Target: docs are current within one
week of a release, without anyone having to ask.

## 1. Detect (automatic)

- [ ] `python scripts/drift_check.py` has run (the GitHub Action does this weekly).
- [ ] Read `reports/drift-report.md`. Fix every **stale** and **error** finding first.

## 2. Draft (AI-assisted)

- [ ] `python scripts/build_prompts.py` has been run for the new release.
- [ ] Each prompt was run in Claude and saved as `<name>.draft.md`.

## 3. Review (always a person)

For every draft, whether a person or AI wrote it:

- [ ] Every UI label matches `product-facts.yml`.
- [ ] Every number matches `product-facts.yml`.
- [ ] No deprecated terms.
- [ ] Steps work when followed in the product (open the product and try them).
- [ ] The "Reviewer questions" list is answered, not ignored.
- [ ] Screenshots and in-app tours match the current product (manual in this demo).

## 4. Close the loop

- [ ] Update `last_verified_release` in each doc a person has verified.
- [ ] Log every mistake in `rules/mistakes-log.md`, and add or change a rule if it can recur.
- [ ] Rerun the drift check. The report should show no stale or error findings.
- [ ] Look at `reports/top-topics.md`. Pick the one or two topics to fix next.
