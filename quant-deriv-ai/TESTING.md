# TESTING.md — QUANT DERIV AI

## Exigences

1. **Tests réels obligatoires** — exécuter réellement la suite (Pytest) avant de conclure.
2. **Aucun résultat inventé** — logs, exit codes et assertions doivent provenir d'une exécution réelle.
3. **Pas de look-ahead bias** dans les backtests et validations d'edge.
4. Couverture alignée sur le périmètre du lot : ce qui est implémenté est testé.
5. Typage et contrats Pydantic validés par des tests unitaires quand applicable.

## Règle PASS / FAIL / BLOCKED

| Verdict | Condition |
| --- | --- |
| **PASS** | Tous les contrôles **obligatoires** du lot ont été **réellement** exécutés et sont verts |
| **FAIL** | Au moins un contrôle obligatoire a été exécuté et a échoué, ou un livrable obligatoire est incorrect |
| **BLOCKED** | Un obstacle externe empêche d'exécuter un contrôle obligatoire (environnement, accès, contrainte plateforme) |

**Ne jamais déclarer PASS** si un test ou contrôle obligatoire n'a pas été réellement exécuté.

## Look-ahead bias

- Les features et labels doivent respecter la causalité temporelle.
- Aucune information future dans les signaux de backtest.
- Les tests de recherche doivent inclure des gardes ou scénarios qui échoueraient en cas de fuite temporelle évidente.

## LOT-000 — contrôles obligatoires

Pour LOT-000 (fondation documentaire, **sans** stratégies) :

1. Tous les fichiers listés existent sur disque
2. Le contenu encode les instructions maîtres dans les fichiers appropriés
3. Aucune implémentation de stratégie de trading
4. Principes DEMO-only / pas d'ordres live encodés

Il n'y a pas de suite Pytest runtime à ce lot ; les contrôles sont des vérifications d'existence et de contenu. Les résultats doivent être factuels (ex. `ls` / lecture de fichiers), jamais inventés.

## LOT-003 — Market Data Engine

Contrôles obligatoires (exécutés réellement) :

1. Pytest : qualité (missing/duplicate/outlier/freshness), intégrité (versions immuables), performance légère, engine mocké
2. Intégration MT5 réelle : **BLOCKED** sans terminal Windows + credentials DEMO (skip honnête, jamais PASS inventé)
3. Ruff + MyPy sur le package
4. CLI `quant data --help` expose download|update|validate|inspect|stats
5. Aucune fabrication silencieuse (`allow_reconstruction=false` ; reconstruction flaguée si activée)

## LOT-004 — Technical Analysis Agent

Contrôles obligatoires (exécutés réellement) :

1. Pytest : indicateurs vs références indépendantes ; anti look-ahead (préfixe / mutation futur) ; engine snapshot ; registry ; CLI
2. Ruff + MyPy sur le package
3. CLI `quant analyze technical` et `quant indicators list|validate`
4. Volumes synthétiques non assumés réels (`volume_is_synthetic=true` par défaut)
5. Aucun API d'ordre / aucune stratégie de trading

## LOT-005 — Quantitative Research Agent

Contrôles obligatoires (exécutés réellement) :

1. Pytest : stats lab ; edge metrics ; causalité (lag>=1, prefix / mutation / signal-bar) ; engine report ; CLI research
2. Ruff + MyPy sur le package
3. CLI `quant research stats|edge|report`
4. Rapports Markdown/JSON sans métriques inventées
5. Aucun API d'ordre / probes ≠ stratégies de trading

## LOT-006 — Strategy Engine

Contrôles obligatoires (exécutés réellement) :

1. Pytest : 12 hypothèses enregistrées ; signaux BUY/SELL/HOLD/EXIT ; anti look-ahead (préfixe / mutation futur) ; CLI strategy ; safety flags
2. Ruff + MyPy sur le package
3. CLI `quant strategy list|inspect|validate`
4. Aucune auto-activation live (`auto_activate=false`, `live_allowed=false`)
5. Aucun API d'ordre ; `edge_demonstrated=false` pour toutes les hypothèses

## Lots futurs

Dès qu'il y a du code :

- Écrire les tests **avant** ou **avec** l'implémentation
- Lancer Pytest réellement ; coller ou référencer la sortie réelle dans le rapport de lot
- Vérifier les régressions
- Mettre à jour ce document si de nouvelles classes de tests deviennent obligatoires
