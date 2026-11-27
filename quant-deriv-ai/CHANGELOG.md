# CHANGELOG.md — QUANT DERIV AI

Format : entrées par lot, du plus récent au plus ancien. Pas de métriques de performance inventées.

## [LOT-005] — Quantitative Research Agent

### Ajouté

- Package `quantitative/` : stats lab, edge probes, garde-fous de causalité, rapports, engine, agent
- CLI `quant research stats|edge|report`
- Config `quantitative:` (forward lag min, horizon, reports_dir, probes RSI/momentum)
- Contrats Pydantic `ResearchReport` / `EdgeMetrics` / `ReturnStats`
- Tests stats / edge / causalité / CLI / engine
- Rapport : `docs/LOT-005-REPORT.md`

### Notes

- Aucun ordre ; DEMO-only ; pas de secrets.
- Les probes d'edge sont des outils de recherche, **pas** des stratégies de trading.
- `forward_lag >= 1` obligatoire (anti look-ahead).

## [LOT-004] — Technical Analysis Agent

### Ajouté

- Package `indicators/` : SMA, EMA, RSI, MACD, ATR, ADX, Bollinger, Stochastic, Donchian, ROC, Momentum, CCI, Williams %R, hist_vol (vectorisé, causal)
- Package `technical/` : engine, agent, structure (swings / S/R), trend, breakouts, MTF, `TechnicalSnapshot`
- CLI `quant analyze technical` et `quant indicators list|validate`
- Config `technical:` (volume synthétique par défaut, swings, breakout lookback, SMA fast/slow)
- Tests vs références indépendantes + gardes anti look-ahead
- Rapport : `docs/LOT-004-REPORT.md`

### Notes

- Aucun ordre ; DEMO-only ; pas de secrets.
- Volumes / tick volumes **non** traités comme liquidité réelle par défaut.

## [LOT-003] — Market Data Engine

### Ajouté

- Package `market_data/` : collector, normalize (UTC), quality, reconstruction contrôlée, engine, agent
- Package `persistence/` : Parquet (historique), DuckDB (analyse), SQLite (métadonnées + versions)
- CLI `quant data` : download / update / validate / inspect / stats
- Timeframes disponibles : M1, M5, M15, M30, H1, H4, D1
- Versioning immuable des datasets de backtest (hash SHA-256)
- Tests qualité / intégrité / performance (mock MT5) ; intégration réelle BLOCKED sans terminal
- Rapport : `docs/LOT-003-REPORT.md`

### Notes

- Aucune fabrication silencieuse de données manquantes (`allow_reconstruction=false` par défaut).
- Aucun ordre ; DEMO-only ; pas de secrets.
- Sur Linux : téléchargement réel MT5 **BLOCKED** (pas un PASS inventé).

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
