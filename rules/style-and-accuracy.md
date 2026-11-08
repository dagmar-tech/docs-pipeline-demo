# Style and accuracy rules

These rules are given to the AI with every drafting prompt, and reviewers use
them to judge every draft. When a mistake gets through, it is added to
`mistakes-log.md` and, if it can recur, becomes a new rule here.

## Accuracy

1. Product facts come only from `product-facts.yml` and the release changes in the
   prompt. If something is missing, ask in "Reviewer questions". Never guess.
2. Write UI labels exactly as they appear in `ui_labels`, in **bold**.
3. State a number or limit only if it is in `limits`. Otherwise do not state one.
4. Never use a term listed under `deprecated_terms`, except in a one-line note
   such as "(formerly Call flows)" in the release that renamed it.
5. Do not describe features, menu positions or steps that are not in the release
   changes or the current page.

## Style

6. Start with what the reader can do, not with what the product is.
7. Steps are numbered, start with a verb and contain one action each. Use five
   steps instead of fifteen when you can.
8. Put prerequisites (roles, plans, settings) before the steps.
9. Use plain words. No marketing language, no "simply", no "just".
10. Link to related pages with relative links, and only to pages that exist.

## Output

11. Return the full page, a change summary and reviewer questions, in that order.
12. Leave `last_verified_release` unchanged. A person updates it after review.
