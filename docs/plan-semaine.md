# Plan semaine — Deriv MT5 (XAUUSD & XAGUSD, swing H4)

**Exécution :** Deriv + **MT5**, manuel. **Aucune promesse de gain.**

**Budget risque au stop :** **50 USD** (phase actuelle).

**Prix proxy (Yahoo → H4) :** tirage **2026-11-01 22:37 UTC** (rechargez le bureau avant ordre).

**Specs Deriv :** [Trading specifications | Deriv MT5](https://trade.deriv.com/trading-specifications) — **XAUUSD** 100 XAU/lot, **XAGUSD** 5 000 XAG/lot, **min & pas 0,01 lot**. Échelle 4 TP = **0,04 lot** (4 clôtures de **0,01**).

---

## XAUUSD (or) — ordre Deriv MT5

**Sell limit** · cours proxy **3 898,90**

| | |
|--|--|
| **Entrée** | **Sell limit 3 989,10** |
| **Volume** | **0,04 lot** (4 × **0,01**) |
| **Stop loss** | **4 001,13** |
| **Risque au stop** | **~48,12 USD** (≤ 50 USD) |

### Quatre take profits (0,01 lot chacun)

| TP | Prix | USD ~ | Action |
|----|------|-------|--------|
| **TP1** (~1R) | **3 977,07** | **~12,03** | Clôturer **0,01** ; stop du **0,03** restant → **3 989,10** |
| **TP2** | **3 935,25** | **~53,85** | Clôturer **0,01** |
| **TP3** | **3 893,43** | **~95,67** | Clôturer **0,01** |
| **TP4** | **3 851,61** | **~137,49** | Clôturer **0,01** |

**Cumul si les 4 TP sont touchés :** **~299,04 USD** (arithmétique seulement).

**Avant TP1 :** perte possible **~48,12 USD** au stop sur **0,04 lot**.

---

## XAGUSD (argent)

**Hors phase 50 USD** : **0,04 lot** → **~60,95 USD** au stop (> 50 USD). **Pas d’ordre argent** à ce budget sur Deriv MT5.

---

## Rappel

Pas d’ordre au marché hors zone de retest H4. Vérifiez *Spécification* du symbole dans MT5 avant envoi.
