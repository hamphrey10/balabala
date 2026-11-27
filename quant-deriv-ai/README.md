# QUANT DERIV AI

Système de trading algorithmique autonome professionnel, connecté à **Deriv** via l'**API WebSocket officielle Deriv**, opéré depuis **Cursor IDE**.

## Objectif

- Analyser les marchés
- Rechercher des edges statistiques
- Tester des stratégies
- Gérer le risque de façon indépendante
- Exécuter des ordres **uniquement en DEMO**

**Préservation du capital > rendements.** Aucune profitabilité n'est assumée ni garantie.

## Avertissement DEMO uniquement

> **COMPTE DEMO UNIQUEMENT.** Les ordres live / réels sont interdits pour cette phase du projet. Aucun credential de compte réel ne doit être utilisé pour l'exécution. Voir `SECURITY.md` et `RISK_POLICY.md`.

## Connexion broker (priorité)

| Priorité | Canal | Statut |
| --- | --- | --- |
| **Primaire** | **Deriv WebSocket API** (`wss://ws.derivws.com/websockets/v3?app_id=…`) | Connecteur DEMO lecture seule (`quant deriv …`) |
| Secondaire / optionnel | MetaTrader 5 (terminal Windows) | Scaffold LOT-002 — non requis pour la connexion Deriv |

Enregistrement app + tokens : [api.deriv.com](https://api.deriv.com). Auth officielle : message `{"authorize":"<token>"}`. Compte démo si `authorize.is_virtual == 1` (fail-closed sinon).

## Stack cible

| Domaine | Technologies |
| --- | --- |
| OS / IDE | Windows 11 / Linux (agent), Cursor IDE |
| Langage | Python 3.12 (vérifier la compatibilité) |
| Broker / plateforme | **Deriv API (WebSocket)** ; MT5 optionnel |
| Données | SQLite, DuckDB, Parquet |
| Quant / ML | NumPy, Pandas, SciPy, Scikit-learn, XGBoost |
| App | Pydantic, Asyncio, Loguru, Rich, Typer, websockets |
| Tests / outillage | Pytest, MCP Python SDK, Git |

**Règle dépendances :** vérifier les versions compatibles avant installation. Ne pas choisir une dépendance uniquement parce qu'elle est la plus récente.

## Instruments à étudier

Volatility Indices, Boom/Crash, Jump, Step, Range Break, Forex, et tout autre instrument disponible sur le compte Deriv (découverte dynamique via l'API).

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
| `docs/DERIV-CONNECTION-REPORT.md` | Rapport connexion Deriv API |

## Package Python

Racine runtime : ce répertoire (`pyproject.toml`, `src/`, `tests/`, `config/`).

### Prérequis

- Python 3.12
- Accès Deriv API (app_id + token DEMO) via [api.deriv.com](https://api.deriv.com)
- Optionnel : package MetaTrader5 (**wheels Windows uniquement**)

### Setup

```bash
cd quant-deriv-ai
python3.12 -m venv --copies .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
# Sur Windows uniquement, quand MT5 optionnel est nécessaire :
# pip install -e ".[dev,mt5]"
cp .env.example .env
# Remplir DERIV_APP_ID et DERIV_API_TOKEN (compte DEMO / virtual)
```

### CLI

Point d'entrée : `quant`

```bash
quant version
quant doctor
quant status
quant config validate

# Primaire — Deriv WebSocket API (DEMO, lecture seule)
quant deriv connect
quant deriv status
quant deriv account
quant deriv disconnect

# Optionnel — MT5 (Windows + terminal + creds DEMO)
quant mt5 connect
quant mt5 status
quant mt5 account
quant mt5 symbols
quant mt5 positions
quant mt5 disconnect
```

**Credentials Deriv** (`.env`) : `DERIV_APP_ID`, `DERIV_API_TOKEN`, optionnel `DERIV_ENDPOINT`.  
Ne jamais committer de secrets. Ne jamais logger le token. Comptes réels (`is_virtual=0`) rejetés et verrouillés. **Aucun placement d'ordre.**

## État actuel

Fondation documentaire (LOT-000), scaffold Python (LOT-001), connecteur MT5 optionnel (LOT-002), **connecteur Deriv API DEMO lecture seule (primaire)**. **Aucune stratégie de trading n'est implémentée.** Aucun ordre placé. Voir `ROADMAP.md` pour la suite.
