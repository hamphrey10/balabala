# ROADMAP.md — QUANT DERIV AI

Feuille de route **haut niveau**. Pas de dates inventées. Pas de résultats de performance inventés.

## LOT-000 — Fondation documentaire (ce lot)

**Objectif :** créer la documentation permanente et les règles Cursor.

**Critère « done » :** tous les fichiers fondation listés existent sur disque, encodent les instructions maîtres, et le rapport de validation LOT-000 est produit (PASS / FAIL / BLOCKED).

**Hors périmètre :** toute implémentation de stratégie de trading ; tout code d'exécution ; toute connexion MT5.

Fichiers attendus :

- `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`
- `RISK_POLICY.md`, `SECURITY.md`, `TESTING.md`, `CHANGELOG.md`
- `STRATEGY_REGISTRY.md`, `MODEL_GOVERNANCE.md`
- `.cursor/rules/project.mdc`, `security.mdc`, `testing.mdc`, `trading.mdc`
- `docs/LOT-000-validation-report.md`

## Lots futurs (indicatif, non daté)

Ordre logique suggéré — à affiner lot par lot selon l'état réel du code :

1. **Scaffold projet Python** — structure de packages, `pyproject.toml` / dépendances vérifiées (Python 3.12 + stack), typage, CLI Typer de base
2. **Connexion MT5 DEMO** — client Deriv MT5 en mode démo uniquement ; refus explicite du live ; gestion sécurisée des credentials hors dépôt
3. **Market data** — découverte dynamique des instruments ; ingestion ; stockage SQLite / DuckDB / Parquet
4. **Observabilité de base** — Loguru, audit trail minimal des décisions
5. **Research toolkit** — pipelines d'analyse, garde-fous anti *look-ahead bias*, métriques d'edge
6. **Risk engine** — politiques de `RISK_POLICY.md` en code ; indépendance ; non-bypass IA
7. **Couche exécution DEMO** — passage obligatoire par le risk engine ; pas d'ordres réels
8. **Stratégies (lots dédiés)** — une stratégie à la fois ; enregistrement dans `STRATEGY_REGISTRY.md` ; tests réels ; abstention sans edge
9. **Gouvernance modèles** — gates d'`MODEL_GOVERNANCE.md` ; évaluation avant promotion
10. **MCP / Cursor tooling** — outils agent pour orchestrer recherche, risque, exécution DEMO

Chaque lot suit la méthodologie de `AGENTS.md` et produit un rapport PASS / FAIL / BLOCKED sans inventer de résultats.
