# Bureau de signaux (Or & Argent)

Petit outil local d’aide à la décision pour **XAUUSD** et **XAGUSD**, en français. Il lit la structure des prix en **swing H4** (horizon verrouillé pour les deux symboles) et propose entrée, stop et objectifs. **Vous exécutez chaque signal manuellement** — pas de connexion courtier ni d’envoi d’ordres.

Les setups dont le rapport gain/risque vers le premier take profit est **strictement inférieur à 2** ne sont pas publiés ; la raison s’affiche en une phrase.

## Prérequis

- Python 3.10+
- Accès réseau (téléchargement des cours via Yahoo Finance)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer l’application

Depuis la racine du dépôt :

```bash
source .venv/bin/activate
uvicorn signal_desk.main:app --reload --host 127.0.0.1 --port 8000
```

Ouvrir [http://127.0.0.1:8000](http://127.0.0.1:8000).

API JSON (optionnel) : [http://127.0.0.1:8000/api/signals](http://127.0.0.1:8000/api/signals)

## Alertes signal actif (Telegram)

Quand `signal_active` passe de **false** à **true** pour XAUUSD ou XAGUSD, le bureau :

1. écrit l’alerte en français dans `alerte-active.md` (écrasé à chaque nouvelle alerte) ;
2. ajoute une ligne dans `alerte-log.txt` (empreinte `fp=…` — **pas de renvoi** du même plan) ;
3. envoie **un message Telegram** si les variables ci-dessous sont définies.

Dossier par défaut : `/cursor/stores/self/docs/` (variable `SIGNAL_DESK_ALERT_DIR` pour le changer).

### Variables d’environnement Telegram

| Variable | Rôle |
|----------|------|
| `TELEGRAM_BOT_TOKEN` | Token du bot [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Identifiant du chat ou du canal de destination |

Ne commitez **jamais** ces valeurs. Sans elles, l’alerte est quand même écrite dans `alerte-active.md` avec la mention *envoi en attente*.

### Lancer une vérification

```bash
source .venv/bin/activate
export TELEGRAM_BOT_TOKEN="…"
export TELEGRAM_CHAT_ID="…"
python3 -m signal_desk.alerts
```

Même logique via HTTP si le serveur tourne : [http://127.0.0.1:8000/api/alerts/check](http://127.0.0.1:8000/api/alerts/check)

## Données de marché

Les cours proviennent de **Yahoo Finance** :

| Symbole affiché | Ticker Yahoo | Note |
|-----------------|--------------|------|
| XAUUSD | `GC=F` | Future COMEX or — **proxy**, pas le spot de votre courtier |
| XAGUSD | `SI=F` | Future COMEX argent — **proxy**, pas le spot de votre courtier |

Les bougies **H4** sont obtenues par regroupement des barres horaires (`1h → 4h`). Les niveaux sont indicatifs ; comparez toujours avec votre plateforme avant de passer un ordre.

## Structure du projet

```
signal_desk/
  main.py       # Serveur FastAPI + page d’accueil
  data.py       # Téléchargement et préparation H4
  analysis.py   # Biais, niveaux, filtre R/R ≥ 2
  alerts.py     # Alerte false→true, fichier alerte-active.md
  templates/    # Interface HTML (français)
  static/       # Styles
```
