# linkedin-agent

BDK agent that helps manage LinkedIn: draft posts, triage inbox, and review profile gaps.

## Quick start

```bash
cd linkedin-agent
npm install
npx bdk validate --dir .
npx bdk serve --dir . --mode single --dev
# open http://127.0.0.1:3000/playground
```

Model turns need a Cursor credential (`CURSOR_API_KEY` or `npx bdk login`).

## Tools

| Tool | Role |
| --- | --- |
| `draft_post` | Save paste-ready post drafts (does not publish) |
| `list_inbox` | List inbox items (demo data until API is wired) |
| `profile_snapshot` | Read/update a profile checklist snapshot |

## Next

- Wire a LinkedIn API / MCP connection for live inbox and publish gates
- Add Slack or schedule channel if you want digests
- Hillclimb with real fixtures after a few playground turns
