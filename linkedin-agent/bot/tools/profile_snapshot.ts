import { defineTool } from "@cursor/bdk/tools";
import { z } from "zod";

type ProfileSnapshot = {
  headline: string;
  about: string;
  experienceCount: number;
  hasPhoto: boolean;
  hasBanner: boolean;
  featuredCount: number;
  openToWork: boolean;
  updatedAt: string;
};

const PROFILE_KEY = "linkedin:profile";

const DEFAULT_SNAPSHOT: ProfileSnapshot = {
  headline: "",
  about: "",
  experienceCount: 0,
  hasPhoto: false,
  hasBanner: false,
  featuredCount: 0,
  openToWork: false,
  updatedAt: new Date(0).toISOString(),
};

function gapsFor(snapshot: ProfileSnapshot): string[] {
  const gaps: string[] = [];
  if (!snapshot.headline.trim()) gaps.push("Add a clear headline with role + niche");
  if (snapshot.about.trim().length < 80) gaps.push("Expand About to ~3 short paragraphs");
  if (!snapshot.hasPhoto) gaps.push("Upload a professional profile photo");
  if (!snapshot.hasBanner) gaps.push("Add a banner that signals your domain");
  if (snapshot.experienceCount < 1) gaps.push("Add at least one experience entry");
  if (snapshot.featuredCount < 1) gaps.push("Feature one post, article, or link");
  return gaps;
}

export default defineTool({
  description:
    "Read or refresh the LinkedIn profile checklist snapshot stored for this agent. Use before advising on profile improvements.",
  effect: ({ mode }) => (mode === "update" ? "write" : "read"),
  inputSchema: z.object({
    mode: z.enum(["get", "update"]).default("get"),
    headline: z.string().optional(),
    about: z.string().optional(),
    experienceCount: z.number().int().min(0).optional(),
    hasPhoto: z.boolean().optional(),
    hasBanner: z.boolean().optional(),
    featuredCount: z.number().int().min(0).optional(),
    openToWork: z.boolean().optional(),
  }),
  dryRunResult: () => ({
    mode: "update" as const,
    dryRun: true,
    snapshot: DEFAULT_SNAPSHOT,
    gaps: gapsFor(DEFAULT_SNAPSHOT),
  }),
  async execute(input, ctx) {
    const existing = (await ctx.host.kv.get(PROFILE_KEY)) as
      | ProfileSnapshot
      | undefined;
    const base: ProfileSnapshot = existing ?? { ...DEFAULT_SNAPSHOT };

    if (input.mode === "get") {
      return {
        mode: "get" as const,
        snapshot: base,
        gaps: gapsFor(base),
        note: existing
          ? "Profile snapshot from storage."
          : "No profile saved yet — gaps reflect an empty snapshot. Call again with mode=update after the user shares details.",
      };
    }

    const next: ProfileSnapshot = {
      headline: input.headline ?? base.headline,
      about: input.about ?? base.about,
      experienceCount: input.experienceCount ?? base.experienceCount,
      hasPhoto: input.hasPhoto ?? base.hasPhoto,
      hasBanner: input.hasBanner ?? base.hasBanner,
      featuredCount: input.featuredCount ?? base.featuredCount,
      openToWork: input.openToWork ?? base.openToWork,
      updatedAt: new Date().toISOString(),
    };
    await ctx.host.kv.put(PROFILE_KEY, next);

    return {
      mode: "update" as const,
      snapshot: next,
      gaps: gapsFor(next),
      note: "Profile snapshot updated in durable storage (not LinkedIn itself).",
    };
  },
});
