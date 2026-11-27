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

## État runtime

| Lot | Livré |
| --- | --- |
| LOT-000 | Documentation + règles Cursor |
| LOT-001 | Scaffold Python, config, CLI de base |
| LOT-002 | Connecteur MT5 DEMO lecture seule |
| LOT-003 | Market Data Engine (Parquet / DuckDB / SQLite) |
| LOT-004 | Technical Analysis Agent (indicateurs + structure + MTF) |
| LOT-005 | Quantitative Research Agent (stats lab + edge + reports) |

### Quantitative Research Agent (LOT-005)

- **Stats lab** : returns (log/simple), descriptive stats, rolling mean/std/z, autocorrelation, correlation matrix
- **Edge probes** : momentum sign / RSI threshold vs forward returns (`lag >= 1`) — recherche uniquement, pas des stratégies
- **Causalité** : prefix stability, future mutation (features), indépendance signal-bar pour labels forward
- **ResearchReport** : contrat Pydantic + rendu Markdown/JSON
- **CLI** : `quant research stats|edge|report`
- **Frontière** : couche Research uniquement — **aucun ordre**

### Technical Analysis Agent (LOT-004)

- **Indicateurs vectorisés** : SMA, EMA, RSI, MACD, ATR, ADX, Bollinger, Stochastic, Donchian, ROC, Momentum, CCI, Williams %R, historical volatility
- **Interfaces standardisées** : registre `IndicatorSpec` + `compute_from_ohlc` ; pas de look-ahead (fenêtres causales ; NaN en warmup)
- **Structure de marché** : swings, support/résistance, biais HH/HL vs LH/LL
- **Tendance / breakouts / MTF** : classification MA+ADX+structure ; Donchian breakout (niveau prior) ; consensus multi-timeframes
- **TechnicalSnapshot** : contrat Pydantic unique pour CLI / agents
- **Volumes** : synthétiques / tick volumes **non** traités comme liquidité réelle par défaut
- **CLI** : `quant analyze technical` ; `quant indicators list|validate`
- **Frontière** : couche Research / analyse uniquement — **aucun ordre**

### Market Data Engine (LOT-003)

- **Collecte** : ticks historiques + continus ; candles multi-instruments / multi-timeframes via le connecteur MT5
- **Normalisation** : timestamps UTC ; schémas colonnes stables ; déduplication incrémentale
- **Qualité** : détection missing / duplicate / outlier / freshness / OHLC ; jamais de fabrication silencieuse
- **Reconstruction** : optionnelle, explicitement flaguée (`is_reconstructed`, `reconstruction_method`)
- **Stockage** : Parquet (historique), DuckDB (vues d'analyse), SQLite (métadonnées + versions immuables)
- **Versioning** : snapshots backtest immuables avec hash de contenu ; refus de mutation
- **CLI** : `quant data download|update|validate|inspect|stats`
- **Frontière** : couche Data uniquement — aucune décision d'ordre

## État LOT-000 (historique)

À LOT-000, seule la documentation et les règles Cursor existaient.
