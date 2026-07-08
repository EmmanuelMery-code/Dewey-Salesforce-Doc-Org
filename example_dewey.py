from silent.dewey import Dewey
import json
import os

def run_example():
    # 1. Configuration de l'exemple
    # On peut charger les paramètres depuis app_settings.json s'il existe
    settings_path = "app_settings.json"
    
    if os.path.exists(settings_path):
        print(f"--- Chargement de la configuration depuis {settings_path} ---")
        with open(settings_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # On force la désactivation de la génération HTML/Word pour cet exemple
        config["generate_html"] = False
        config["generate_word"] = False
        config["pmd_enabled"] = False
    else:
        print("--- Utilisation d'une configuration manuelle ---")
        config = {
            "source_dir": "C:/Users/emery/Desktop/Dewey/org/mh recette/20260706/retrieve",
            "output_dir": "output_silent",
            "alias": "Exemple Dewey",
            "generate_html": False,
            "pmd_enabled": True
        }

    try:
        # 2. Initialisation de l'objet Dewey
        print("Initialisation de l'analyse (mode 'steps')...")
        # L'objet Dewey gère lui-même le mapping des clés depuis le JSON
        # On peut choisir entre "silent", "steps", "details"
        dewey = Dewey(config, verbosity="steps")

        # 3. Accès aux chiffres (déclenche l'analyse au premier appel)
        print("\n--- RÉSULTATS DE L'ANALYSE ---")
        
        # Section Scoring
        scoring = dewey.index["Scoring"]
        print(f"Score Total : {scoring['score']}")
        print(f"Niveau de customisation : {scoring['niveau']}")
        print(f"Posture Adopt vs Adapt : {scoring['adopt_vs_adapt_niveau']}")

        # Section IA
        ia = dewey.index["IA"]
        print(f"\n--- IA & Innovation ---")
        print(f"Nombre d'Agents : {ia['agents']}")
        print(f"Nombre de Prompts : {ia['prompts']}")
        
        # Section Métriques
        metriques = dewey.index["Métriques"]
        print(f"\n--- Qualité ---")
        print(f"Nombre de Findings : {metriques['findings_total']}")
        
        # Accès aux détails des findings
        findings_report = dewey.findings_report
        if findings_report['findings']:
            print(f"\nExemple de Finding (le premier) :")
            f = findings_report['findings'][0]
            rule = f.get('rule', {})
            print(f"  - [{rule.get('severity')}] {rule.get('title')}")
            desc = rule.get('description') or ""
            print(f"    {desc[:100]}...")

        print(f"\nCouverture de tests : {metriques['test_coverage']}%")

        # Accès aux détails des objets
        objects_details = dewey.index["Description"]["details"]["objects"]
        print(f"\n--- Détails des Objets ---")
        print(f"Nombre total d'objets analysés : {len(objects_details)}")
        if objects_details:
            print("Quelques objets : " + ", ".join([o['api_name'] for o in objects_details[:5]]) + "...")

        # 4. Exportation
        print("\n--- EXPORTATION ---")
        
        # Export JSON
        json_path = "export_dewey_example.json"
        dewey.export(format="json", path=json_path)
        print(f"Données complètes exportées dans : {json_path}")
        
        # Export CSV
        csv_path = "export_dewey_example.csv"
        dewey.export(format="csv", path=csv_path)
        print(f"Métriques clés exportées dans : {csv_path}")

    except Exception as e:
        print(f"Erreur lors de l'exécution : {e}")
        print("\nNote: Assurez-vous que le chemin 'source_dir' dans app_settings.json est accessible.")
        print('')

if __name__ == "__main__":
    run_example()
