# 📘 TUTORIEL : Méthodologie pour les règles JSON de classification

## 🌟 Objectif

Utiliser un fichier JSON pour classifier automatiquement des scrobbles ("écoutes") par type : `music`, `video`, `podcast`, etc., de manière simple, claire et évolutive.

---

## 🔺 Structure de base d’une règle

```json
{
  "field": "client",
  "pattern": "vlc",
  "match": "contains",
  "scrobble_type": "video"
}
```

✅ Le champ `client` contient "vlc" → scrobble classé comme `video`

---

## 📊 Plusieurs patterns (logique OR ou AND interne)

```json
{
  "field": "client",
  "pattern": ["vlc", "plex", "kodi"],
  "match": "contains",
  "logic": "or",
  "scrobble_type": "video"
}
```

* `logic: "or"` : au moins un mot doit être présent
* `logic: "and"` : tous les mots doivent être présents

---

## 🔗 Plusieurs conditions (logique entre champs)

```json
{
  "conditions": [
    { "field": "client", "pattern": "firefox", "match": "contains" },
    { "field": "title", "pattern": "podcast", "match": "contains" }
  ],
  "scrobble_type": "podcast"
}
```

* Les conditions sont évaluées avec un **ET logique (AND)**
* **La première règle qui match est appliquée**, les suivantes sont ignorées

---

## 🧹 Cas spéciaux

### Champ non vide :

```json
{ "field": "title", "match": "not_null", "scrobble_type": "music" }
```

### Champ vide :

```json
{ "field": "album", "match": "is_null", "scrobble_type": "unknown" }
```

---

## 🚦 Activation / désactivation des règles

Tu peux désactiver une règle temporairement avec :

```json
{
  "field": "client",
  "pattern": ["vlc", "plex"],
  "match": "contains",
  "logic": "or",
  "scrobble_type": "video",
  "active": false,
  "note": "Test désactivé temporairement"
}
```

* Si `active` est `false`, la règle est ignorée
* Si `active` est `true` ou absent → la règle est active par défaut

---

## 🗂️ Organisation recommandée

* Classer les règles **de la plus spécifique à la plus générale**
* Ajouter un champ `note` si besoin :

```json
{
  "field": "client",
  "pattern": "youtube",
  "match": "contains",
  "scrobble_type": "video",
  "note": "Cas de YouTube via web scrobbler"
}
```

* Tester avec `--dry-run` avant application
* Versionner le fichier JSON avec Git

---

## 📋 Récapitulatif des clés

| Clé             | Type               | Description                                                          |
| --------------- | ------------------ | -------------------------------------------------------------------- |
| `field`         | `str`              | Champ à analyser (`client`, `title`, etc.)                           |
| `pattern`       | `str` ou `[str]`   | Mot(s) à chercher                                                    |
| `match`         | `str`              | `contains`, `startswith`, `endswith`, `exact`, `is_null`, `not_null` |
| `logic`         | `str`              | `or` ou `and` entre plusieurs `pattern`                              |
| `conditions`    | `[dict]`           | Plusieurs conditions liées par `AND`                                 |
| `scrobble_type` | `str`              | Catégorie à affecter                                                 |
| `note`          | `str` (optionnel)  | Commentaire pour humain                                              |
| `active`        | `bool` (optionnel) | Activer ou désactiver une règle                                      |

---

## ✅ Bonnes pratiques

* Toujours tester avec `--dry-run`
* Ne pas multiplier les doublons
* Priorité par ordre dans le fichier (pas de `priority` pour rester simple)
* Conserver une structure lisible et commentée

---

Tu peux copier-coller ce fichier dans Obsidian dans ton dossier `docs` ou `dev_notes`
\#tuto #jsonrules #methodologie
