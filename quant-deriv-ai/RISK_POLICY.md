# RISK_POLICY.md — QUANT DERIV AI

## Priorité absolue

**Préservation du capital > rendements.**

Aucune profitabilité n'est assumée ni garantie. L'absence de trade est toujours préférable à un trade non justifié.

## Interdictions explicites

| Règle | Statut |
| --- | --- |
| Martingale | **Interdite** |
| Stratégies agressives de récupération de pertes (*loss recovery*) | **Interdites** |
| Ordres live / compte réel | **Interdits** (phase DEMO) |
| Contournement du *risk engine* par un humain, un agent ou un modèle IA | **Interdit** |
| Trading sans edge statistique démontré | **Interdit** → abstention obligatoire |

## Indépendance du risk engine

- Le *risk engine* est une couche **indépendante** (voir `ARCHITECTURE.md`).
- Toute intention d'ordre (stratégie, recherche, agent IA, MCP) **doit** passer par le risk engine avant exécution.
- Aucun modèle IA, prompt, outil ou flag ne peut désactiver, court-circuiter ou affaiblir le risk engine.
- Un rejet ou une abstention du risk engine est **définitif** pour ce cycle de décision.

## Abstention obligatoire

Sans edge statistique **démontré** (méthode documentée, tests réels, pas de *look-ahead bias*) :

- le système **s'abstient** ;
- aucun ordre DEMO n'est envoyé ;
- la décision d'abstention est journalisée.

## Dimensionnement et limites (principes)

Les paramètres numériques concrets seront définis et testés dans les lots risk/execution. Principes permanents dès LOT-000 :

- Limiter l'exposition par position et par jour
- Couper les pertes selon des règles préétablies (pas de « recovery » émotionnel ou algorithmique agressif)
- Refuser les séries de scaling type martingale / double-up après perte
- Préférer l'inaction au forçage d'un signal faible

## Mode DEMO

- Compte **DEMO uniquement** pour cette phase
- Toute configuration d'exécution doit refuser explicitement les endpoints / comptes live
- Voir aussi `SECURITY.md`

## Conformité agents

Les agents Cursor doivent encoder et respecter cette politique via `AGENTS.md` et `.cursor/rules/trading.mdc` + `security.mdc`. Toute proposition de stratégie contraire à cette politique est rejetée hors périmètre.
