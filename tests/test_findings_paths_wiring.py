"""One generator construction, reached by every entry point.

A generator built without ``findings_history_path`` still produces the
findings workbook, only stripped of the findings of the past runs — a
regression nothing else would catch. These tests pin the helper that carries
the paths, and check that the generator is instantiated in exactly one place
so no entry point can quietly drift from the others.
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

#: The only module allowed to instantiate the generator.
TASK_BUILDER = "src/ui/app_documentation_task_mixin.py"

#: Modules that start a documentation run on behalf of the user. Each must go
#: through the shared builder rather than instantiating its own generator.
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


class TestASingleGeneratorConstruction:
    """The documentation must not depend on which button produced it.

    The generator takes some forty options; as long as several entry points
    build their own, they drift apart and the same org yields different
    reports. So exactly one module may instantiate it.
    """

    def _generator_calls(self, module: str) -> list[ast.Call]:
        tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "SalesforceDocumentationGenerator"
        ]

    def _builder_calls(self, module: str) -> list[ast.Call]:
        tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_build_documentation_task"
        ]

    def test_the_generator_is_built_in_a_single_place(self) -> None:
        building = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "src" / "ui").rglob("*.py")
            if self._generator_calls(path.relative_to(REPO_ROOT).as_posix())
        }

        assert building == {TASK_BUILDER}

    def test_that_single_construction_carries_the_findings_paths(self) -> None:
        calls = self._generator_calls(TASK_BUILDER)
        assert len(calls) == 1

        keywords = {keyword.arg for keyword in calls[0].keywords}
        unpacked = {
            keyword.value.id
            for keyword in calls[0].keywords
            if keyword.arg is None and isinstance(keyword.value, ast.Name)
        }
        wired = "findings_history_path" in keywords or "findings_paths" in unpacked
        assert wired, f"{TASK_BUILDER} construit le generateur sans l'historique"

    def test_every_entry_point_goes_through_the_shared_builder(self) -> None:
        assert {module: bool(self._builder_calls(module)) for module in ENTRY_POINTS} == {
            module: True for module in ENTRY_POINTS
        }
