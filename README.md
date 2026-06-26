# Dewey : Doc Org - Salesforce

Application Python avec interface `Tkinter` pour :
- se connecter a une org Salesforce via Salesforce CLI
- lister les orgs disponibles
- generer un manifest
- lancer un retrieve
- generer une documentation HTML et Excel a partir d'un retrieve Salesforce

## Prerequis

- Windows
- Python 3.12 ou plus recent recommande
- Salesforce CLI (`sf`) installe et accessible

## Installation

1. Creer un environnement virtuel :

```bash
python -m venv .venv
```

2. Activer l'environnement virtuel :

```bash
.venv\Scripts\activate
```

3. Installer les dependances Python :

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

## Fonctions principales

- Connexion web Salesforce avec alias
- Choix d'environnement `Production` / `Sandbox` / `Custom`
- Choix du fichier de regles d'analyse (`src/analyzer/rules.xml` par defaut)
- Memorisation de la langue de l'interface (`Francais` ou `English`)
- Ouverture rapide des dossiers source et sortie dans l'explorateur Windows
- Pipeline complet :
  - generation du manifest
  - retrieve
  - generation de la documentation
- Assistant IA (Claude, Gemini ou Gateway) pour discuter de l'org documentee

## Sorties generees

Dans le dossier de sortie, l'application genere notamment :

- `excel/permission_sets.xlsx`
- `excel/profiles.xlsx`
- `html/objects/*.html`
- `html/apex/*.html`
- `html/flows/*.html`
- `html/index.html`
- `word/data_dictionary.docx`
- `word/summary.docx`

## Notes

- `Tkinter` fait partie de la bibliotheque standard Python sur Windows.
- Les preferences de l'application sont stockees dans `app_settings.json`.
