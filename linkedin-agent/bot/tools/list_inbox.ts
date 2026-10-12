import { defineTool } from "@cursor/bdk/tools";
import { z } from "zod";

type InboxItem = {
  id: string;
  kind: "message" | "comment" | "connection" | "mention";
  from: string;
  preview: string;
  priority: "urgent" | "normal" | "later";
  receivedAt: string;
};

const INBOX_KEY = "linkedin:inbox";

const DEMO_INBOX: InboxItem[] = [
  {
    id: "in-1",
    kind: "message",
    from: "Alex Martin",
    preview: "Loved your last post — open to a quick intro call next week?",
    priority: "urgent",
    receivedAt: "2026-04-10T09:15:00.000Z",
  },
  {
    id: "in-2",
    kind: "comment",
    from: "Priya Shah",
    preview: "Curious how you measured the retention lift you mentioned.",
    priority: "normal",
    receivedAt: "2026-04-10T14:40:00.000Z",
  },
  {
    id: "in-3",
    kind: "connection",
    from: "Jordan Lee",
    preview: "Wants to connect · Product lead at Northwind",
    priority: "later",
    receivedAt: "2026-04-09T18:05:00.000Z",
  },
];

export default defineTool({
  description:
    "List pending LinkedIn inbox items (messages, comments, connections, mentions) for triage. Uses stored or demo data until a LinkedIn API is wired.",
  effect: "read",
  inputSchema: z.object({
    limit: z.number().int().min(1).max(50).default(20),
    seedDemoIfEmpty: z
      .boolean()
      .default(true)
      .describe("If no inbox is stored, return demo items so triage can be practiced"),
  }),
  async execute({ limit, seedDemoIfEmpty }, ctx) {
    const stored = (await ctx.host.kv.get(INBOX_KEY)) as InboxItem[] | undefined;
    let items = Array.isArray(stored) ? stored : [];
    let source: "stored" | "demo" | "empty" = "stored";

    if (items.length === 0) {
      if (seedDemoIfEmpty) {
        items = DEMO_INBOX;
        source = "demo";
      } else {
        source = "empty";
      }
    }

    const sliced = items.slice(0, limit);
    return {
      source,
      count: sliced.length,
      items: sliced,
      note:
        source === "demo"
          ? "Demo inbox — not live LinkedIn data. Connect an API later to replace this."
          : source === "empty"
            ? "No inbox items stored."
            : "Inbox loaded from durable storage.",
    };
  },
});
