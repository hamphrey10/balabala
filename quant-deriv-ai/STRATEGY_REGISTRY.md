# STRATEGY_REGISTRY.md — QUANT DERIV AI

Registre permanent des stratégies. **LOT-006** introduit 12 hypothèses expérimentales.
Aucune n'est activée en live / paper. Aucun edge n'est démontré. Aucun ordre.

## État actuel

| ID | Nom | Statut | Edge démontré | Risk review | Notes |
| --- | --- | --- | --- | --- | --- |
| STR-001 | sma_crossover | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-002 | ema_crossover | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-003 | rsi_mean_reversion | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-004 | macd_cross | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-005 | bollinger_reversion | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-006 | donchian_breakout | hypothesis | non | non | LOT-006 ; niveaux prior causaux |
| STR-007 | momentum_follow | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-008 | adx_trend | hypothesis | non | non | LOT-006 ; filtre ADX |
| STR-009 | stochastic_reversion | hypothesis | non | non | LOT-006 ; auto_activate=false |
| STR-010 | atr_breakout | hypothesis | non | non | LOT-006 ; canal ATR causal |
| STR-011 | dual_ma_rsi_filter | hypothesis | non | non | LOT-006 ; filtre RSI |
| STR-012 | williams_r_reversion | hypothesis | non | non | LOT-006 ; auto_activate=false |

## Détail (LOT-006)

Toutes les entrées partagent :

- **Statut :** `hypothesis`
- **Signaux candidats :** `BUY` / `SELL` / `HOLD` / `EXIT`
- **Interdits respectés :** pas de martingale ; pas de recovery agressif ; DEMO only
- **Passage risk engine :** obligatoire avant toute exécution future (hors périmètre LOT-006)
- **Abstention :** sans edge démontré → aucune activation ; `edge_demonstrated=false`
- **Activation auto live :** **interdite** (`auto_activate=false`, `live_allowed=false`)
- **Owner / lot d'introduction :** LOT-006

### STR-001 — sma_crossover

- **Hypothèse d'edge :** croisement SMA rapide/lente capture une persistance de tendance courte
- **Preuves :** aucune (hypothèse) — tests unitaires de signaux / causalité uniquement

### STR-002 — ema_crossover

- **Hypothèse d'edge :** croisement EMA réagit plus vite que SMA
- **Preuves :** aucune (hypothèse)

### STR-003 — rsi_mean_reversion

- **Hypothèse d'edge :** sorties de zones RSI extrêmes mean-revertent
- **Preuves :** aucune (hypothèse)

### STR-004 — macd_cross

- **Hypothèse d'edge :** croisement MACD/signal proxy un changement de régime de momentum
- **Preuves :** aucune (hypothèse)

### STR-005 — bollinger_reversion

- **Hypothèse d'edge :** reclaim après sortie de bande Bollinger mean-revert vers le mid
- **Preuves :** aucune (hypothèse)

### STR-006 — donchian_breakout

- **Hypothèse d'edge :** cassure du canal Donchian **prior** (shift 1) continue
- **Preuves :** aucune (hypothèse) ; niveaux causaux

### STR-007 — momentum_follow

- **Hypothèse d'edge :** momentum signé au-delà d'un seuil persiste brièvement
- **Preuves :** aucune (hypothèse)

### STR-008 — adx_trend

- **Hypothèse d'edge :** croisement +DI/−DI plus informatif si ADX au-dessus d'un plancher
- **Preuves :** aucune (hypothèse)

### STR-009 — stochastic_reversion

- **Hypothèse d'edge :** reclaim %K depuis extrêmes mean-revert
- **Preuves :** aucune (hypothèse)

### STR-010 — atr_breakout

- **Hypothèse d'edge :** close hors close prior ± k·ATR signale expansion de volatilité
- **Preuves :** aucune (hypothèse)

### STR-011 — dual_ma_rsi_filter

- **Hypothèse d'edge :** croisement SMA filtré par bande RSI évite de chasser les extrêmes
- **Preuves :** aucune (hypothèse)

### STR-012 — williams_r_reversion

- **Hypothèse d'edge :** sorties Williams %R depuis extrêmes mean-revertent
- **Preuves :** aucune (hypothèse)

## Règles d'inscription

1. Pas d'entrée sans lot et sans tests réellement exécutés.
2. Pas d'activation sans edge statistique démontré → sinon abstention (`RISK_POLICY.md`).
3. Martingale et recovery agressif = rejet immédiat.
4. Toute stratégie active reste soumise au risk engine indépendant.
5. LOT-006 enregistre des **hypothèses** uniquement — **aucune activation live / paper auto**.
