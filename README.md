![Projet Logo](brain_ops.svg)

# 🧠 BrainOps

## 🚀 Objectif
BrainOps est un projet Python (>3.1) qui automatise l’organisation et l’enrichissement d’un **second cerveau numérique** construit autour d’[Obsidian](https://obsidian.md).  
Le système s’appuie sur une base de données, un moteur IA local (Ollama) et des scripts Python pour transformer des notes brutes (articles web, idées, documents) en archives propres, catégorisées, enrichies de métadonnées et accompagnées de synthèses intelligentes.

---

## 🧰 Stack technique
- **Python 3.11+**
- **Obsidian** (PC Windows, vault partagé sur serveur Unraid)
- **MariaDB** (Docker officiel, hébergé sur VM Ubuntu Server)
- **Ollama** (Docker officiel, multi-GPU avec équilibrage via Nginx reverse proxy)
- **Unraid** (serveur principal : VM + stockage + GPU)
- **Watcher de fichiers** (surveillance en temps réel du vault Obsidian)

---

## ⚙️ Fonctionnalités principales
- **Import automatique** de notes issues d’Obsidian Web Clipper  
- **Détection des doublons** et rangement intelligent dans le vault  
- **Nettoyage et uniformisation** des titres et contenus  
- **Enrichissement avec IA** (via Ollama) :
  - Catégorisation dynamique (création auto si inexistante)
  - Génération d’un entête structuré (title, dates, source, auteur, status, catégorie, tags, résumé)
  - Génération automatique de **tags** et **résumés courts**
- **Archivage & synthèse** :
  - Sauvegarde de l’article original (archive)
  - Découpage en blocs + embeddings (`nomic-embed-text:latest`)
  - Génération d’une **synthèse structurée** avec glossaire et axes d’approfondissement (`llama3.1:8b-instruct-q8_0`)
  - Liens bidirectionnels entre archive et synthèse
- **Mises à jour automatiques** :
  - Synchronisation entre base MariaDB, vault Obsidian et notes
  - Régénération possible via simple changement de status (`regen`, `regen_header`)
  - Déplacement d’une note → mise à jour auto des catégories dans la DB et vault
- **Service permanent** : démarrage automatique sur la VM + script de rattrapage des écarts

---

## 🏗️ Architecture

Obsidian (notes) 
       │
Obsidian Clipper
       │
       ▼
Vault partagé (Unraid)
       │
       ▼
Watcher (Python)
       │
       ▼
MariaDB (Docker) <──> Ollama (Docker multi-GPU via Nginx)
       │
       ▼
Notes enrichies (Archives + Synthèses)
       │
       ▼
Vault Obsidian

---

## 📊 Base de données
- **obsidian_notes** : notes et métadonnées  
- **obsidian_folders** : dossiers du vault  
- **obsidian_categ** : catégories et sous-catégories  
- **obsidian_tags** : tags associés  
- **obsidian_temp_blocs** : blocs envoyés à Ollama  

---

## 📦 Roadmap & améliorations
- 🎙️ Ajout d’imports audio/vidéo + génération de synthèses automatiques  
- 📚 Création de synthèses multi-documents par catégorie  
- 🧑‍💼 Extension de l’IA aux sections *personnal* et *projet* pour l’organisation personnelle  
- 🔗 Connexion avec **ActivOps** pour la gestion des workflows  

---

## Authors

👤 **u2pitchjami**

[![Bluesky](https://img.shields.io/badge/Bluesky-Follow-blue?logo=bluesky)](https://bsky.app/profile/u2pitchjami.bsky.social)
[![Twitter](https://img.shields.io/twitter/follow/u2pitchjami.svg?style=social)](https://twitter.com/u2pitchjami)
![GitHub followers](https://img.shields.io/github/followers/u2pitchjami)
![Reddit User Karma](https://img.shields.io/reddit/user-karma/combined/u2pitchjami)

* Twitter: [@u2pitchjami](https://twitter.com/u2pitchjami)
* Github: [@u2pitchjami](https://github.com/u2pitchjami)
* LinkedIn: [@LinkedIn](https://linkedin.com/in/thierry-beugnet-a7761672)
