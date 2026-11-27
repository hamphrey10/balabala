# CHANGELOG.md — QUANT DERIV AI

Format : entrées par lot, du plus récent au plus ancien. Pas de métriques de performance inventées.

## [Deriv API] — Connexion WebSocket officielle (DEMO, lecture seule)

### Ajouté

- Package `execution/deriv/` : client WebSocket, credentials env-only, live lock (`is_virtual`), modèles
- CLI `quant deriv` : connect / status / account / disconnect
- Env : `DERIV_APP_ID`, `DERIV_API_TOKEN`, `DERIV_ENDPOINT` (voir `.env.example` + api.deriv.com)
- Tests unitaires mockés (transport injectable)
- Rapport : `docs/DERIV-CONNECTION-REPORT.md`

### Notes

- **Connexion primaire = Deriv API** ; MT5 reste scaffold secondaire/optionnel.
- Endpoint officiel : `wss://ws.derivws.com/websockets/v3?app_id=…`
- Auth : `authorize` ; démo si `is_virtual=1` (fail-closed sinon).
- Aucun `buy` / `sell` / `proposal` d'achat exposé.

## [LOT-002] — Connecteur MetaTrader5 DEMO (lecture seule)

### Ajouté

- Package `execution/mt5/` : client, credentials env-only, live lock, modèles, erreurs
- CLI `quant mt5` : connect / status / account / symbols / positions / disconnect
- Tests unitaires mockés + intégration skippée (BLOCKED sans terminal Windows)
- Rapport : `docs/LOT-002-REPORT.md`

### Notes

- Aucun API d'ordre (`order_send` / place / modify / close) exposé.
- Comptes non-DEMO engagent un verrou permanent (`LiveAccountLock`).
- Sur Linux : package MetaTrader5 non installable — intégration réelle **BLOCKED** (pas un PASS inventé).

## [LOT-001] — Fondation projet Python

### Ajouté

- `pyproject.toml` (Ruff, MyPy, Pytest, entry point `quant`)
- Packages modulaires sous `src/quant_deriv_ai/` (core, config, agents, strategies stub, …)
- Config YAML + validation Pydantic (`config/default.yaml`)
- `.env.example`, `.gitignore`
- CLI : `quant version` / `doctor` / `status` / `config validate`
- Suite Pytest ; rapports `docs/LOT-001-REPORT.md`

### Notes

- Mode trading DEMO-only (`allow_live=false`).
- Aucune stratégie de trading au-delà des stubs vides.
- MetaTrader5 : FAIL attendu sur Linux (wheels Windows only).

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
