# QUANT DERIV AI

Système de trading algorithmique autonome professionnel, connecté à **Deriv** via **MetaTrader 5**, opéré depuis **Cursor IDE**.

## Objectif

- Analyser les marchés
- Rechercher des edges statistiques
- Tester des stratégies
- Gérer le risque de façon indépendante
- Exécuter des ordres **uniquement en DEMO**

**Préservation du capital > rendements.** Aucune profitabilité n'est assumée ni garantie.

## Avertissement DEMO uniquement

> **COMPTE DEMO UNIQUEMENT.** Les ordres live / réels sont interdits pour cette phase du projet. Aucun credential de compte réel ne doit être utilisé pour l'exécution. Voir `SECURITY.md` et `RISK_POLICY.md`.

## Stack cible

| Domaine | Technologies |
| --- | --- |
| OS / IDE | Windows 11, Cursor IDE |
| Langage | Python 3.12 (vérifier la compatibilité) |
| Broker / plateforme | MetaTrader 5, Deriv MT5 |
| Données | SQLite, DuckDB, Parquet |
| Quant / ML | NumPy, Pandas, SciPy, Scikit-learn, XGBoost |
| App | Pydantic, Asyncio, Loguru, Rich, Typer |
| Tests / outillage | Pytest, MCP Python SDK, Git |

**Règle dépendances :** vérifier les versions compatibles avant installation. Ne pas choisir une dépendance uniquement parce qu'elle est la plus récente.

## Instruments à étudier

Volatility Indices, Boom/Crash, Jump, Step, Range Break, Forex, et tout autre instrument disponible sur le compte Deriv MT5.

Les instruments doivent être **découverts dynamiquement**. Ne jamais assumer leurs caractéristiques ni leur disponibilité.

## Navigation de la documentation

| Fichier | Contenu |
| --- | --- |
| `AGENTS.md` | Rôle agent, non-négociables, méthodologie LOT |
| `ARCHITECTURE.md` | Couches modulaires et séparation des responsabilités |
| `ROADMAP.md` | LOT-000 et lots futurs (haut niveau) |
| `RISK_POLICY.md` | Capital, martingale, abstention, indépendance du risque |
| `SECURITY.md` | Secrets, DEMO-only, credentials |
| `TESTING.md` | Tests réels, pas de résultats inventés, règle PASS |
| `CHANGELOG.md` | Historique des lots |
| `STRATEGY_REGISTRY.md` | Registre des stratégies (vide à LOT-000) |
| `MODEL_GOVERNANCE.md` | Cycle de vie des modèles et gates d'évaluation |
| `.cursor/rules/` (cible) / `dot-cursor/rules/` (LOT-000 miroir) | Règles Cursor (projet, sécurité, tests, trading). Sur l'agent-store, `.cursor/` est bloqué — contenu sous `dot-cursor/rules/`. |

## État actuel (LOT-000)

Fondation documentaire et règles Cursor uniquement. **Aucune stratégie de trading n'est implémentée.** Aucun code d'exécution live. Voir `ROADMAP.md` pour la suite.
