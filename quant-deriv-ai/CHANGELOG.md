# CHANGELOG.md — QUANT DERIV AI

Format : entrées par lot, du plus récent au plus ancien. Pas de métriques de performance inventées.

## [LOT-000] — Fondation documentaire

### Ajouté

- Documentation permanente du projet :
  - `AGENTS.md`
  - `README.md`
  - `ARCHITECTURE.md`
  - `ROADMAP.md`
  - `RISK_POLICY.md`
  - `SECURITY.md`
  - `TESTING.md`
  - `CHANGELOG.md`
  - `STRATEGY_REGISTRY.md`
  - `MODEL_GOVERNANCE.md`
- Règles Cursor (contraintes agents) — contenu livré sous miroir `dot-cursor/rules/` :
  - `dot-cursor/rules/project.mdc`
  - `dot-cursor/rules/security.mdc`
  - `dot-cursor/rules/testing.mdc`
  - `dot-cursor/rules/trading.mdc`
- Rapport de validation : `docs/LOT-000-validation-report.md`

### Notes

- Aucune stratégie de trading implémentée.
- Aucun connecteur MT5 / code d'exécution livré.
- Phase DEMO-only encodée dans la documentation et les règles.
- **Écart chemin :** le filesystem agent-store refuse le répertoire littéral `.cursor/` ; les règles sont sous `dot-cursor/rules/` (à renommer en `.cursor/rules/` sur un FS/Git normal). Voir rapport LOT-000.
