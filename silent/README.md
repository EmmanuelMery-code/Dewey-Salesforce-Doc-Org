# Manuel Utilisateur - Module Dewey

L'objet `Dewey` est un extracteur de métriques et de données Salesforce conçu pour fonctionner de manière "silencieuse". Contrairement au générateur principal, il ne produit pas de rapports HTML ou Word par défaut, mais collecte l'intégralité des informations nécessaires pour les exposer via une API Python ou les exporter en JSON/CSV.

## 1. Dépendances

Le module `Dewey` est intégré au projet et dépend des modules coeurs suivants :

*   **`src.core.orchestrator.generator`** : Utilise la classe `SalesforceDocumentationGenerator` pour orchestrer l'analyse des métadonnées.
*   **`src.core.history_service`** : Gère l'accès à la base de données SQLite (`history.db`) pour le stockage et la récupération de l'historique des analyses.
*   **`src.core.customization_metrics`** : Utilisé pour les calculs de posture "Adopt vs Adapt" et les configurations de capacités.
*   **`src.analyzer`** : Moteur d'analyse statique pour la détection des findings.

## 2. Configuration (`dewey.json`)

Dewey utilise son propre fichier de configuration interne nommé `dewey.json`, situé dans le même répertoire que `dewey.py`. Ce fichier définit deux aspects critiques :

### `defaults`
Ce sont les paramètres appliqués par défaut à chaque analyse pour garantir un fonctionnement silencieux et performant :
*   `generate_html`, `generate_word`, `generate_excels` : Positionnés à `false` pour éviter la création de fichiers lourds.
*   `include_comparison` : Activé par défaut pour permettre le calcul des régressions.
*   `pmd_enabled` : Activé par défaut pour l'analyse de qualité du code.
*   `use_history` : Activé par défaut (`true`).

### `mapping`
Permet de faire le pont entre les clés utilisées dans les fichiers de configuration externes (comme `app_settings.json`) et les noms de paramètres attendus par le moteur interne :
*   Exemple : `source_folder` est automatiquement converti en `source_dir`.
*   `comparison_target` est mappé pour cibler une génération spécifique.

## 3. Utilisation de l'Objet Dewey

### Initialisation
```python
from silent.dewey import Dewey

# Configuration via un dictionnaire ou un chemin vers un fichier JSON
config = {
    "source_dir": "chemin/vers/metadata",
    "alias": "MonProjet"
}

# Paramètres optionnels :
# - verbosity : 
#     * "silent" (défaut) : Aucun log.
#     * "steps" : Affiche les grandes étapes (début, lecture metadata, fin, etc.).
#     * "details" : Affiche le détail technique de chaque opération.
# - use_history : 
#     * True (défaut) : Utilise history.db pour stocker les résultats et comparer.
#     * False : Mode totalement éphémère, aucune écriture en base, comparaison désactivée.

dewey = Dewey(config, verbosity="steps", use_history=True)
```

### Accès aux données
L'analyse est déclenchée automatiquement lors du premier accès à une propriété. Dewey expose des données **détaillées** et non plus seulement des chiffres agrégés :

```python
# Récupérer l'intégralité des données (dictionnaire géant)
data = dewey.chiffres

# 1. Scoring et Posture
print(data["index"]["Scoring"]["score"])
print(data["index"]["Scoring"]["adopt_vs_adapt_niveau"])

# 2. Détails des composants (Description)
# Contient les listes d'objets, LWC, Aura, etc.
objets = data["index"]["Description"]["details"]["objects"]
for obj in objets[:5]:
    print(f"Objet: {obj['api_name']} (Custom: {obj['custom']})")

# 3. Qualité et Findings
# Contient la liste complète des violations détectées
findings = data["findings_report"]["findings"]
for f in findings[:3]:
    print(f"Violation: {f['rule']['title']} sur {f['target_name']}")

# 4. IA et Innovation
# Détails des agents, prompts et tags IA détectés
print(data["ai_usage"]["stats"]["with_tag_count"])
print(data["index"]["IA"]["details"]["prompts"])
```

### Exportation
```python
# Export JSON complet (contient TOUS les détails techniques)
dewey.export(format="json", path="mon_export_complet.json")

# Export CSV résumé (contient les métriques clés sous forme de tableau)
dewey.export(format="csv", path="mon_export_resume.csv")
```

## 4. Fonctionnement des Comparaisons

La comparaison dans Dewey s'appuie sur l'**historique** stocké dans la base `history.db`.

1.  **L'Alias est la clé** : Dewey utilise l'attribut `alias` pour regrouper les analyses.
2.  **Mécanisme** :
    *   Lors d'une analyse, Dewey recherche dans la base de données la dernière entrée enregistrée pour le même `alias`.
    *   Il compare les métriques actuelles avec celles de cette entrée précédente.
    *   Les régressions (baisse de couverture, augmentation des findings critiques, etc.) sont calculées.
3.  **Données de comparaison** :
    *   `regressions_count` : Nombre de régressions détectées.
    *   `regressions` : Liste détaillée des indicateurs en baisse.
    *   `source_precedente` : Chemin du dossier "retrieve" utilisé lors de la génération précédente.
4.  **Cible spécifique** : Utilisez `comparison_target` dans la config pour comparer avec une génération précise (ex: `"1"`).

> **Note importante** : Si `use_history=False` est utilisé, aucune donnée n'est lue ou écrite en base, et la section `comparaison` sera vide.
