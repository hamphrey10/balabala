# ARCHITECTURE.md — QUANT DERIV AI

## Principes

- Architecture **modulaire**
- **Séparation stricte** des responsabilités (*separation of concerns*)
- Typage Python de bout en bout
- Le *risk engine* est indépendant et non contournable
- Exécution **DEMO uniquement** pour cette phase
- Les stratégies ne sont **pas encore implémentées** (LOT-000 = fondation documentaire)

## Couches modulaires

```
┌─────────────────────────────────────────────────────────┐
│                 Observabilité / Logging                  │
│              (Loguru, métriques, audit trail)            │
└─────────────────────────────────────────────────────────┘
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  MCP / Cursor │  │   Research   │  │   Stratégie (future) │
│  orchestration│  │  edges / ML  │  │  signaux / registry  │
└──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘
       │                 │                     │
       └────────────┬────┴─────────────────────┘
                    ▼
         ┌─────────────────────┐
         │     Risk Engine     │  ← indépendant ; aucun bypass IA
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │  Exécution DEMO MT5 │  ← ordres live interdits
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │   Données marché    │
         │ SQLite/DuckDB/Parquet│
         └─────────────────────┘
```

### 1. Data (données)

- Ingestion et stockage des séries de marché Deriv MT5
- Formats : SQLite, DuckDB, Parquet
- Découverte dynamique des instruments (jamais d'assumptions hardcodées sur disponibilité ou caractéristiques)
- Contrats de données typés (Pydantic)

### 2. Research (recherche)

- Analyse statistique, features, validation d'edges
- Bibliothèques : NumPy, Pandas, SciPy, Scikit-learn, XGBoost
- Interdiction du *look-ahead bias*
- Aucune décision d'ordre directe depuis cette couche

### 3. Strategy (stratégie) — non implémentée à LOT-000

- Production de signaux candidats
- Enregistrement dans `STRATEGY_REGISTRY.md`
- Toute stratégie doit démontrer un edge statistique avant activation
- Martingale et récupération agressive de pertes interdites

### 4. Risk (risque)

- Couche **indépendante** et obligatoire avant toute exécution
- Aucun modèle IA, agent ou stratégie ne peut la contourner
- Abstention obligatoire sans edge démontré
- Préservation du capital prioritaire — voir `RISK_POLICY.md`

### 5. Execution (exécution)

- Connexion MetaTrader 5 / Deriv MT5
- **DEMO only** — refus explicite des comptes / ordres live
- Asyncio pour l'orchestration I/O
- Aucun credential dans le code — voir `SECURITY.md`

### 6. Observability (observabilité)

- Logging structuré (Loguru)
- Traçabilité des décisions (signal → risque → exécution ou abstention)
- Pas de résultats inventés dans les rapports

### 7. MCP / Cursor

- Orchestration depuis Cursor IDE via MCP Python SDK
- CLI / UX agent : Typer, Rich
- Les agents respectent `AGENTS.md` et `.cursor/rules/*.mdc`
- Pas de modification autonome du code de production

## Frontières (separation of concerns)

| Couche | Peut | Ne peut pas |
| --- | --- | --- |
| Data | Lire/écrire séries, métadonnées instruments | Décider d'un trade |
| Research | Évaluer edges, produire métriques | Envoyer des ordres ; contourner le risque |
| Strategy | Émettre des signaux candidats | Exécuter ; bypass risk |
| Risk | Autoriser, réduire, rejeter, forcer l'abstention | Être désactivée par l'IA |
| Execution | Placer ordres DEMO autorisés | Accepter un ordre live ; ignorer le risque |
| Observability | Journaliser et auditer | Altérer les décisions |
| MCP/Cursor | Orchestrer lots et outils | Modifier prod hors process de lot |

## État LOT-000

Seule la documentation et les règles Cursor existent. Aucun module runtime, aucune stratégie, aucun connecteur MT5 n'est livré dans ce lot.
