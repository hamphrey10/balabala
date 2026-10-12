import { defineEval, includes } from "@cursor/bdk/evals";

export default defineEval({
  tags: ["smoke"],
  cases: [
    {
      id: "draft-post",
      description: "Saves a LinkedIn post draft via draft_post.",
      async test(t) {
        await t.send(
          "Rédige un post LinkedIn court sur l'importance du feedback async en remote, ton conversationnel, et sauvegarde le brouillon."
        );
        t.succeeded();
        t.calledTool("draft_post");
        t.notCalledTool("list_inbox");
        t.check(t.reply, includes(/feedback|async|remote|brouillon|draft/i));
      },
    },
    {
      id: "inbox-triage",
      description: "Triages inbox with list_inbox.",
      async test(t) {
        await t.send(
          "Fais le triage de mon inbox LinkedIn et propose une réponse pour les urgents."
        );
        t.succeeded();
        t.calledTool("list_inbox");
        t.check(t.reply, includes(/urgent|Alex|priorit/i));
      },
    },
  ],
});
