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
| `.cursor/rules/` | Règles Cursor (projet, sécurité, tests, trading) |
| `docs/LOT-000-validation-report.md` | Rapport LOT-000 |
| `docs/LOT-001-REPORT.md` | Rapport LOT-001 (fondation Python) |
| `docs/LOT-002-REPORT.md` | Rapport LOT-002 (connecteur MT5 DEMO lecture seule) |
| `docs/LOT-003-REPORT.md` | Rapport LOT-003 (Market Data Engine) |
| `docs/LOT-004-REPORT.md` | Rapport LOT-004 (Technical Analysis Agent) |

## Package Python (LOT-001 … LOT-004)

Racine runtime : ce répertoire (`pyproject.toml`, `src/`, `tests/`, `config/`).

### Prérequis

- Python 3.12
- Optionnel : package MetaTrader5 (**wheels Windows uniquement** ; typiquement non importable sur Linux)

### Setup

```bash
cd quant-deriv-ai
python3.12 -m venv --copies .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
# Sur Windows uniquement, quand MT5 est nécessaire :
# pip install -e ".[dev,mt5]"
cp .env.example .env
```

### CLI

Point d'entrée : `quant`

```bash
quant version
quant doctor
quant status
quant config validate

# LOT-002 — connecteur MT5 DEMO (lecture seule ; Windows + terminal + creds DEMO)
quant mt5 connect
quant mt5 status
quant mt5 account
quant mt5 symbols
quant mt5 positions
quant mt5 disconnect

# LOT-003 — market data engine (Parquet / DuckDB / SQLite)
quant data download -s EURUSD -t M1 -t H1 --from 2024-01-01T00:00:00Z
quant data update -s EURUSD -t M1
quant data validate -s EURUSD -k candles -t M1
quant data inspect -s EURUSD -k candles -t M1
quant data stats

# LOT-004 — technical analysis (local candles; no orders)
quant indicators list
quant indicators validate rsi --param period=14
quant analyze technical -s EURUSD -t H1 --mtf H4 --mtf D1
```

Credentials via `.env` (`MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` / optionnel `MT5_PATH`). Ne jamais committer de secrets. Les comptes live/réels sont rejetés et verrouillés par le connecteur. **Aucun placement d'ordre.**

Données locales sous `data/` (gitignoré) : Parquet + DuckDB + `metadata.sqlite`. Timeframes : M1, M5, M15, M30, H1, H4, D1. Pas de fabrication silencieuse de barres manquantes.

Analyse technique (LOT-004) : indicateurs vectorisés + structure/tendance/breakouts/MTF → `TechnicalSnapshot`. Volumes synthétiques non assumés réels.

## État actuel (LOT-001 … LOT-004)

Fondation documentaire (LOT-000), scaffold Python (LOT-001), connecteur MT5 DEMO lecture seule (LOT-002), Market Data Engine (LOT-003), Technical Analysis Agent (LOT-004). **Aucune stratégie de trading n'est implémentée.** Aucun ordre placé. Voir `ROADMAP.md` pour la suite.
