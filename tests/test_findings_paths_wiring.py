"""The findings stores must reach the generator from every entry point.

A generator built without ``findings_history_path`` still produces the
findings workbook, only stripped of the findings of the past runs — a
regression nothing else would catch. These tests pin the helper that carries
the paths and check that every UI entry point actually uses it.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

from src.core.findings_cache import findings_cache_path
from src.core.findings_qualification import STORE_FILENAME
from src.core.orchestrator import SalesforceDocumentationGenerator
from src.ui.app_generation_mixin import AppGenerationMixin

#: Modules that build a generator on behalf of the user.
ENTRY_POINTS = (
    "src/ui/app_generation_mixin.py",
    "src/ui/app_sf_cli_mixin.py",
    "src/ui/app_cli_actions_mixin.py",
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class _Application(AppGenerationMixin):
    """Only what :meth:`_findings_paths` and :meth:`_run_alias` read."""

    def __init__(self, app_dir: Path, alias: str) -> None:
        self.app_dir = app_dir
        self.alias_var = SimpleNamespace(get=lambda: alias)


class TestFindingsPaths:
    def test_both_stores_are_carried(self, tmp_path: Path) -> None:
        paths = _Application(tmp_path, "mh recette")._findings_paths("mh recette")

        assert paths == {
            "findings_qualifications_path": tmp_path / STORE_FILENAME,
            "findings_history_path": findings_cache_path(tmp_path, "mh recette"),
        }

    def test_the_generator_accepts_exactly_those_keywords(self, tmp_path: Path) -> None:
        parameters = inspect.signature(SalesforceDocumentationGenerator).parameters
        paths = _Application(tmp_path, "MHINT")._findings_paths("MHINT")

        assert set(paths) <= set(parameters)

    def test_the_history_follows_the_alias_of_the_run(self, tmp_path: Path) -> None:
        """The alias field wins, and an empty one falls back to the org ref,
        exactly like the alias the generator is given."""
        with_alias = _Application(tmp_path, "mh recette")
        without_alias = _Application(tmp_path, "  ")

        assert with_alias._run_alias("mh_recette_org") == "mh recette"
        assert without_alias._run_alias("mh_recette_org") == "mh_recette_org"
        assert without_alias._findings_paths(
            without_alias._run_alias("mh_recette_org")
        )["findings_history_path"] == findings_cache_path(tmp_path, "mh_recette_org")


class TestEveryEntryPointIsWired:
    def _generator_calls(self, module: str) -> list[ast.Call]:
        tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "SalesforceDocumentationGenerator"
        ]

    def test_every_entry_point_builds_one_generator(self) -> None:
        assert {module: len(self._generator_calls(module)) for module in ENTRY_POINTS} == {
            module: 1 for module in ENTRY_POINTS
        }

    def test_no_entry_point_forgets_the_findings_paths(self) -> None:
        for module in ENTRY_POINTS:
            call = self._generator_calls(module)[0]
            keywords = {keyword.arg for keyword in call.keywords}
            unpacked = {
                keyword.value.id
                for keyword in call.keywords
                if keyword.arg is None and isinstance(keyword.value, ast.Name)
            }
            wired = "findings_history_path" in keywords or "findings_paths" in unpacked
            assert wired, f"{module} construit le generateur sans l'historique"
