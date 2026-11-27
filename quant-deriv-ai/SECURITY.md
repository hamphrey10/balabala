# SECURITY.md — QUANT DERIV AI

## Principes

1. **Aucun secret dans le code source** (mots de passe, tokens, clés API, login MT5, chaînes de connexion).
2. **DEMO uniquement** — pas de trading live / réel dans cette phase.
3. Credentials gérés hors dépôt (variables d'environnement, coffre OS, secrets manager) — jamais commités.
4. Moindre privilège : le runtime n'obtient que les droits nécessaires au compte DEMO.
5. Audit : les tentatives d'accès live ou d'injection de secrets doivent être détectables et refusées.

## Credentials

| Autorisé | Interdit |
| --- | --- |
| Variables d'environnement locales non versionnées | Fichiers `.env` commités avec secrets |
| Coffres / secret stores de l'OS ou de l'équipe | Hardcoding dans Python, Markdown, tests, fixtures |
| Fichiers locaux gitignorés documentés sans valeurs | Coller des secrets dans le chat ou les rapports de lot |
| Comptes **DEMO** Deriv MT5 | Identifiants de compte **réel / live** pour l'exécution |

## Trading live interdit

- Aucun module d'exécution ne doit accepter un mode `live` / `real` / `production trading` dans cette phase.
- La configuration doit échouer clairement si un compte non-DEMO est détecté.
- Les agents ne doivent pas « activer le live pour tester ».

## Code et dépendances

- Vérifier les versions compatibles avant installation (pas de chase du « newest »).
- Pas de modification autonome du code de production hors process de lot (`AGENTS.md`).
- Revues : signaler toute fuite potentielle de secret dans les diffs.

## MCP / Cursor

- Les outils MCP n'exposent pas de secrets en clair dans les logs.
- Les règles `.cursor/rules/security.mdc` renforcent ces contraintes pour tous les agents.

## Incident / fuite

Si un secret apparaît dans le dépôt ou un rapport :

1. Le considérer comme compromis
2. Le révoquer / faire tourner
3. Le retirer de l'historique si nécessaire
4. Documenter l'incident sans republier la valeur
