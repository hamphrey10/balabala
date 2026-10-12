---
description: Use when drafting LinkedIn posts, triaging inbox replies, or reviewing profile gaps end-to-end.
---

# LinkedIn ops

## Draft a post

1. Clarify topic, audience, and desired tone if missing.
2. Draft in the user's language: hook → insight → proof → CTA.
3. Call `draft_post` with the final body (and optional `draftId` to revise).
4. Return the paste-ready text. Never say it was published.

## Triage inbox

1. Call `list_inbox`.
2. Group by priority: urgent → normal → later.
3. For each urgent/normal item, suggest one short reply the user can send.
4. If `source` is `demo`, label the triage as practice data.

## Profile review

1. Call `profile_snapshot` with `mode=get`.
2. If empty, ask for headline / about / photo / banner / experience count, then `mode=update`.
3. Work the `gaps` list top-down; propose one concrete rewrite for the headline or About.
