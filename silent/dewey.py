import json
import sys
import inspect
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime

# Ajouter la racine du projet au sys.path pour permettre les imports depuis src
# On remonte de 2 niveaux car on est dans silent/dewey.py
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

try:
    # Importer les composants nécessaires du projet
    from src.core.orchestrator.generator import SalesforceDocumentationGenerator
    from src.core.history_service import HistoryEntry
    from src.core.customization_metrics import PostureCapabilityConfig
    from src.core.sf_cli_service import SalesforceCliService
except ImportError as e:
    # Si l'import échoue, on essaie d'ajouter le répertoire courant au cas où
    sys.path.insert(0, str(Path.cwd()))
    from src.core.orchestrator.generator import SalesforceDocumentationGenerator
    from src.core.history_service import HistoryEntry
    from src.core.customization_metrics import PostureCapabilityConfig
    from src.core.sf_cli_service import SalesforceCliService

from .dewey_data_mixin import DeweyDataMixin


class Dewey(DeweyDataMixin):
    """
    Objet Dewey permettant d'extraire les chiffres et métriques de l'analyse Salesforce
    sans générer les pages HTML, tout en offrant des capacités d'export.
    """

    def __init__(
        self,
        config: Union[str, Path, Dict[str, Any]],
        source_dir: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        alias: Optional[str] = None,
        verbosity: str = "silent",  # "silent", "steps", "details"
        use_history: bool = True
    ):
        self.verbosity = verbosity.lower()
        self.use_history = use_history
        self.params = {}
        
        # Charger la configuration interne de Dewey
        dewey_json_path = Path(__file__).resolve().parent / "dewey.json"
        with open(dewey_json_path, 'r', encoding='utf-8') as f:
            self.internal_config = json.load(f)

        if isinstance(config, (str, Path)):
            with open(config, 'r', encoding='utf-8') as f:
                self.params = json.load(f)
        elif isinstance(config, dict):
            self.params = config.copy()
            
        if source_dir:
            self.params['source_dir'] = str(source_dir)
        if output_dir:
            self.params['output_dir'] = str(output_dir)
        if alias:
            self.params['alias'] = alias

        # Si l'historique est désactivé, on force certains paramètres
        if not self.use_history:
            self.params['include_comparison'] = False

        # Appliquer le mapping configuré dans dewey.json
        mapping = self.internal_config.get('mapping', {})
        for old_key, new_key in mapping.items():
            if old_key in self.params and new_key not in self.params:
                self.params[new_key] = self.params.pop(old_key)

        if 'source_dir' not in self.params:
            raise ValueError("Le paramètre 'source_dir' (ou 'source_folder') est requis pour l'analyse.")
            
        # Appliquer les paramètres par défaut configurés dans dewey.json
        defaults = self.internal_config.get('defaults', {})
        for key, value in defaults.items():
            self.params.setdefault(key, value)

        # Filtrer les paramètres pour ne passer que ceux acceptés par SalesforceDocumentationGenerator
        sig = inspect.signature(SalesforceDocumentationGenerator.__init__)
        valid_params = [p.name for p in sig.parameters.values() if p.name != 'self']
        
        filtered_params = {k: v for k, v in self.params.items() if k in valid_params}
        
        # Gérer les types spécifiques (tuples pour les seuils)
        for key in ['scoring_thresholds', 'adopt_adapt_thresholds', 'data_model_thresholds', 
                    'profiles_thresholds', 'profiles_ps_ratio_thresholds']:
            if key in filtered_params and isinstance(filtered_params[key], list):
                filtered_params[key] = tuple(filtered_params[key])

        # Gérer posture_config (doit être une liste de PostureCapabilityConfig)
        if 'posture_config' in filtered_params and isinstance(filtered_params['posture_config'], dict):
            capabilities = filtered_params['posture_config'].get('capabilities', [])
            from src.core.customization_metrics import PostureCapabilityConfig, CapabilityLevel
            
            p_configs = []
            for c in capabilities:
                # Convertir le niveau (str) en Enum CapabilityLevel si présent
                if c.get('level'):
                    try:
                        c['level'] = CapabilityLevel(c['level'])
                    except ValueError:
                        # Si la valeur n'est pas reconnue, on laisse l'assesseur décider
                        c['level'] = None
                p_configs.append(PostureCapabilityConfig(**c))
            
            filtered_params['posture_config'] = p_configs

        # Configurer le callback de log en fonction de la verbosité
        filtered_params['log_callback'] = self._log_callback

        # Récupération de la couverture de tests (Apex + Flows) via le CLI Salesforce.
        # Désactivé par défaut : nécessite un org connecté (sf CLI) et un alias/target_org.
        # Voir dewey.json ("calculate_coverage", "run_tests", "target_org").
        self.calculate_coverage = bool(self.params.get('calculate_coverage', False))
        self.run_tests_before_coverage = bool(self.params.get('run_tests', False))
        self.target_org = self.params.get('target_org') or self.params.get('alias')

        if self.calculate_coverage:
            if not self.target_org:
                self._log_callback(
                    "[COUVERTURE] 'calculate_coverage' est actif mais aucun 'target_org' "
                    "(ni 'alias') n'est configure : la couverture de tests est ignoree."
                )
            else:
                cli_service = SalesforceCliService(root_path, log_callback=self._log_callback)
                if self.run_tests_before_coverage:
                    self._log_callback(
                        f"[COUVERTURE] Execution des tests Apex sur '{self.target_org}'..."
                    )
                    cli_service.run_apex_tests(self.target_org)
                self._log_callback(
                    f"[COUVERTURE] Recuperation de la couverture de tests sur '{self.target_org}'..."
                )
                filtered_params['test_coverage_data'] = cli_service.fetch_test_coverage(
                    self.target_org
                )

        self._generator = SalesforceDocumentationGenerator(**filtered_params)
        
        # Désactiver la sauvegarde en base de données si demandé
        if not self.use_history:
            self._generator._save_to_history = lambda *args, **kwargs: None

        self._result = None
        self._data = {}

    def _log_callback(self, message: str):
        """Gère l'affichage des messages en fonction de la verbosité."""
        if self.verbosity == "silent":
            return
            
        # Détection heuristique des étapes majeures
        major_steps = [
            "Debut de l'analyse",
            "Lecture des metadata terminee",
            "Catalogue analyzer",
            "Usage IA",
            "Empreinte data model",
            "Posture Adopt vs Adapt",
            "Generation terminee"
        ]
        
        is_major = any(step in message for step in major_steps)
        
        if self.verbosity == "steps" and is_major:
            print(f"[Dewey] {message}")
        elif self.verbosity == "details":
            print(f"[Dewey] {message}")

    def _run_analysis(self):
        """Exécute l'analyse si ce n'est pas déjà fait."""
        if self._result is not None:
            return
            
        try:
            self._result = self._generator.generate()
            self._collect_data()
        except Exception as e:
            import traceback
            if self.verbosity != "silent":
                print(f"DEBUG: Erreur lors de generate(): {e}")
                traceback.print_exc()
            raise
