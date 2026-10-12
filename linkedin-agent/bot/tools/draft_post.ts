import { defineTool } from "@cursor/bdk/tools";
import { z } from "zod";

type DraftRecord = {
  id: string;
  topic: string;
  audience: string;
  tone: string;
  body: string;
  cta: string;
  updatedAt: string;
  published: false;
};

const DRAFTS_KEY = "linkedin:drafts";

export default defineTool({
  description:
    "Save or update a LinkedIn post draft in durable storage. Never publishes to LinkedIn. Call this when the user wants a post written or refined.",
  effect: "write",
  inputSchema: z.object({
    topic: z.string().min(1).describe("What the post is about"),
    audience: z
      .string()
      .default("professionals on LinkedIn")
      .describe("Who should care"),
    tone: z
      .enum(["professional", "conversational", "bold", "educational"])
      .default("conversational"),
    body: z.string().min(1).describe("Full post text ready to paste"),
    cta: z.string().default("").describe("Optional call to action line"),
    draftId: z
      .string()
      .optional()
      .describe("Reuse to update an existing draft; omit to create"),
  }),
  dryRunResult: ({ topic, draftId }) => ({
    saved: false,
    dryRun: true,
    id: draftId ?? "draft-dry-run",
    topic,
    published: false as const,
  }),
  async execute({ topic, audience, tone, body, cta, draftId }, ctx) {
    const id = draftId?.trim() || `draft-${Date.now()}`;
    const record: DraftRecord = {
      id,
      topic,
      audience,
      tone,
      body,
      cta,
      updatedAt: new Date().toISOString(),
      published: false,
    };

    const existing = (await ctx.host.kv.get(DRAFTS_KEY)) as
      | DraftRecord[]
      | undefined;
    const drafts = Array.isArray(existing) ? existing : [];
    const idx = drafts.findIndex((d) => d.id === id);
    if (idx >= 0) {
      drafts[idx] = record;
    } else {
      drafts.unshift(record);
    }
    await ctx.host.kv.put(DRAFTS_KEY, drafts.slice(0, 50));

    return {
      saved: true,
      id: record.id,
      topic: record.topic,
      tone: record.tone,
      charCount: body.length,
      published: false as const,
      note: "Draft stored locally. Paste into LinkedIn manually — nothing was published.",
    };
  },
});
