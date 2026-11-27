# STRATEGY_REGISTRY.md — QUANT DERIV AI

Registre permanent des stratégies. **Aucune stratégie n'est enregistrée à LOT-000.**

## État actuel

| ID | Nom | Statut | Edge démontré | Risk review | Notes |
| --- | --- | --- | --- | --- | --- |
| — | — | *vide* | — | — | Aucune stratégie enregistrée |

## Template d'enregistrement (lots futurs)

Quand une stratégie est introduite (lot dédié), ajouter une ligne et une section détaillée :

```markdown
### STR-XXX — <nom>

- **Statut :** draft | research | paper/demo | rejected | retired
- **Instruments cibles :** découverte dynamique ; lister ceux validés (pas d'assumptions)
- **Hypothèse d'edge :** …
- **Preuves :** liens vers notebooks/tests/rapports — résultats **réels** uniquement
- **Interdits respectés :** pas de martingale ; pas de recovery agressif ; DEMO only
- **Passage risk engine :** obligatoire ; aucun bypass IA
- **Abstention :** conditions où la stratégie ne trade pas
- **Owner / lot d'introduction :** …
```

## Règles d'inscription

1. Pas d'entrée sans lot et sans tests réellement exécutés.
2. Pas d'activation sans edge statistique démontré → sinon abstention (`RISK_POLICY.md`).
3. Martingale et recovery agressif = rejet immédiat.
4. Toute stratégie active reste soumise au risk engine indépendant.
5. LOT-000 ne remplit **pas** ce registre avec des stratégies fictives.
