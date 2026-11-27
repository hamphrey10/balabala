# MODEL_GOVERNANCE.md — QUANT DERIV AI

Gouvernance du cycle de vie des modèles IA / ML utilisés pour la recherche ou l'aide à la décision.

## Principes

1. Un modèle **ne peut pas contourner** le *risk engine* (non-négociable #15).
2. Un modèle **ne place pas** d'ordres directement — il propose au plus des scores / signaux candidats.
3. Sans edge démontré et sans validation, **abstention** (non-négociable #16).
4. Aucun résultat d'évaluation inventé (`TESTING.md`).
5. Pas de *look-ahead bias* dans l'entraînement ou la validation.
6. DEMO only pour toute boucle liée à l'exécution.

## Cycle de vie

```
idéation → dataset versionné → train → évaluation hors échantillon
    → gate de promotion → staging DEMO (signaux seulement)
    → revue risk → (éventuelle) utilisation sous risk engine
    → monitoring → retirement
```

## Gates d'évaluation (promotion)

Avant qu'un modèle influence des signaux en DEMO :

| Gate | Exigence |
| --- | --- |
| Données | Pas de fuite temporelle ; instruments découverts/validés dynamiquement |
| Métriques | Rapport d'évaluation issu d'une exécution réelle |
| Robustesse | Contrôles de stabilité documentés (lots research) |
| Risk | Mapping explicite : sortie modèle → entrée risk engine ; aucun chemin de bypass |
| Sécurité | Pas de secrets dans artefacts ; conformité `SECURITY.md` |
| Registre | Entrée documentée (lien depuis ce fichier ou annexe lot) |

Échec d'un gate ⇒ **pas de promotion** ; abstention / rejet.

## Interdits modèles

- Désactiver, mocker ou short-circuiter le risk engine en production DEMO
- Optimiser explicitement une politique martingale / recovery agressif
- Cibler l'exécution live
- Modifier le code de production de façon autonome

## LOT-000

Aucun modèle n'est entraîné ni déployé. Ce document fixe les règles avant les lots research / ML.
