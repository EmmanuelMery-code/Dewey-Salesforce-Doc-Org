"""Renderer for the methodology explanation page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    CAPABILITY_LEVEL_ORDER,
    CapabilityLevel,
    PostureCapabilityConfig,
)
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import (
    href_relative,
    index_back_link,
    render_page,
)


from src.core.models import (
    DEFAULT_DATA_MODEL_THRESHOLDS,
    DEFAULT_PROFILES_THRESHOLDS,
)


LogCallback = Callable[[str], None]


# ---------------------------------------------------------------------------
# Règles de calcul Auto (détection) par capability_id builtin
# ---------------------------------------------------------------------------

_CAPABILITY_RULES_STATIC: dict[str, str] = {
    "automation": (
        "Adopt (OOTB) si aucun flow ni trigger Apex ; "
        "Adapt (déclaratif) si seuls des flows sont présents ; "
        "Adapt (code) si des triggers Apex sont détectés."
    ),
    "validation": (
        "Adopt (OOTB) si aucune validation rule ni trigger de validation ; "
        "Adapt (déclaratif) si validation rules standards ; "
        "Adapt (code) si <code>addError</code> est utilisé dans un trigger."
    ),
    "ui_layout": (
        "Adopt (OOTB) si layouts standards uniquement ; "
        "Adapt (déclaratif) si des FlexiPages sont présents ; "
        "Adapt (code) si des composants LWC sont détectés."
    ),
    "integration": (
        "Adopt (OOTB) si aucun callout Apex détecté ; "
        "Adapt (code) si des appels HTTP, callouts ou traitements asynchrones "
        "Apex sont présents."
    ),
    "reporting": (
        "Adopt (OOTB) si aucun report ni dashboard custom ; "
        "Adapt (déclaratif) si des reports custom sont détectés ; "
        "Adapt (code) si des dashboards custom sont présents."
    ),
    "notifications": (
        "Adopt (OOTB) si aucune notification Apex/email alert ; "
        "Adapt (déclaratif) si des email alerts ou templates custom existent ; "
        "Adapt (code) si <code>Messaging.sendEmail</code> est utilisé en Apex."
    ),
    "omnistudio": (
        "Adopt (OOTB) si pas de composant OmniStudio ; "
        "Adapt (déclaratif) si DataRaptors/FlexCards uniquement ; "
        "Adapt (code) si des OmniScripts ou Integration Procedures sont présents."
    ),
}


def _data_model_rule(low: int, medium: int, high: int) -> str:
    return (
        f"Basé sur le nombre d'objets custom et les seuils configurés — "
        f"Adopt (OOTB) si &lt;&nbsp;{low} ; "
        f"Adopt déclaratif si {low}–{medium - 1} ; "
        f"Adapt (déclaratif) si {medium}–{high - 1} ; "
        f"Adapt (code) si ≥&nbsp;{high}."
    )


def _profiles_rule(low: int, medium: int, high: int) -> str:
    return (
        f"Basé sur le nombre de profils custom et les seuils configurés — "
        f"Adopt (OOTB) si &lt;&nbsp;{low} profil(s) custom ; "
        f"Adopt déclaratif si {low}–{medium - 1} ; "
        f"Adapt (déclaratif) si {medium}–{high - 1} ; "
        f"Adapt (code) si ≥&nbsp;{high}."
    )


def _build_capability_rules(
    data_model_thresholds: tuple[int, int, int],
    profiles_thresholds: tuple[int, int, int],
) -> dict[str, str]:
    rules = dict(_CAPABILITY_RULES_STATIC)
    rules["data_model"] = _data_model_rule(*data_model_thresholds)
    rules["security"] = _profiles_rule(*profiles_thresholds)
    return rules


def _capability_rule_html(
    entry: PostureCapabilityConfig,
    capability_rules: dict[str, str],
) -> str:
    """Return the HTML content for the 'Règle de calcul' cell of ``entry``."""
    if entry.custom:
        if entry.metadata_key:
            rule = f"Compteur automatique : nombre de <em>{html_value(entry.metadata_key)}</em>."
        else:
            rule = "Capacité personnalisée — aucune détection automatique."
    else:
        rule = capability_rules.get(
            entry.capability_id,
            "Détection automatique par analyse des métadonnées.",
        )

    if entry.level is not None:
        rule = f"{rule} <strong>Valeur forcée :</strong> {html_value(entry.level.value)}"

    return rule


def render_methodology_page(
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    posture_config: list[PostureCapabilityConfig] | None = None,
    data_model_thresholds: tuple[int, int, int] = DEFAULT_DATA_MODEL_THRESHOLDS,
    profiles_thresholds: tuple[int, int, int] = DEFAULT_PROFILES_THRESHOLDS,
) -> str:
    """Render the methodology explanation page."""

    back_link = index_back_link(current_path, output_dir)

    capability_rules = _build_capability_rules(data_model_thresholds, profiles_thresholds)

    # Section IA
    ia_section = """
    <div class="section">
        <h2>Usage IA</h2>
        <p>L'indicateur <strong>Usage IA</strong> mesure la proportion d'éléments de métadonnées qui ont été annotés avec des tags spécifiques (par défaut <code>@IAgenerated</code>, <code>@IAassisted</code>). Cela permet de suivre l'adoption des outils d'intelligence artificielle dans le cycle de développement.</p>
        <ul>
            <li><strong>Périmètre de scan :</strong> L'outil parcourt les descriptions des objets, champs, record types, règles de validation, flows, profils et permission sets. Pour le code Apex (classes et triggers), il analyse les commentaires source.</li>
            <li><strong>Calcul :</strong> Le pourcentage est calculé sur l'univers de personnalisation (objets/champs customs, Apex, Flows, etc.). Un élément est considéré comme "IA" s'il contient au moins un des tags configurés.</li>
        </ul>
    </div>
    """

    # Section Data Model
    dm_section = """
    <div class="section">
        <h2>Empreinte data model</h2>
        <p>Cette mesure quantifie l'extension du modèle de données standard de Salesforce.</p>
        <ul>
            <li><strong>Objets :</strong> Compare le nombre d'objets personnalisés (finissant par <code>__c</code>) au nombre d'objets standards présents dans le périmètre d'analyse.</li>
            <li><strong>Champs :</strong> Compare le nombre de champs personnalisés (sur tous les objets) au nombre de champs standards.</li>
            <li><strong>Ratio Global :</strong> Chaque objet et chaque champ compte pour une "unité". Le ratio global est la somme des éléments customs divisée par le total des éléments analysés.</li>
        </ul>
    </div>
    """

    # Section Posture Adopt vs Adapt
    posture_intro = """
    <div class="section">
        <h2>Posture Adopt vs Adapt</h2>
        <p>Cette analyse évalue si l'organisation privilégie l'utilisation des fonctionnalités natives (<strong>Adopt</strong>) ou si elle a fortement personnalisé la plateforme (<strong>Adapt</strong>).</p>
        
        <h3>Mécanisme de calcul</h3>
        <p>L'analyse repose sur un catalogue de capacités (Modèle de données, Sécurité, Automatisation, etc.). Pour chaque capacité :</p>
        <ol>
            <li>Un <strong>Niveau</strong> est déterminé (soit par détection automatique, soit forcé manuellement).</li>
            <li>Un <strong>Poids</strong> est appliqué (par défaut de 1 à 3 selon l'importance architecturale).</li>
            <li>Le score final est le ratio du poids des capacités classées en <em>Adoption</em> sur le poids total.</li>
        </ol>
        
        <h4>Signification des Niveaux</h4>
        <table>
            <thead>
                <tr><th>Niveau</th><th>Catégorie</th><th>Description</th></tr>
            </thead>
            <tbody>
                <tr><td><strong>Adopt (OOTB)</strong></td><td>Adoption</td><td>Utilisation telle quelle des fonctions standards.</td></tr>
                <tr><td><strong>Adopt déclaratif</strong></td><td>Adoption</td><td>Utilisation de fonctions standards via les outils de configuration.</td></tr>
                <tr><td><strong>Adapt (déclaratif)</strong></td><td>Adaptation</td><td>Extension via des outils sans code (Flows, VR, etc.).</td></tr>
                <tr><td><strong>Adapt (code)</strong></td><td>Adaptation</td><td>Extension lourde via du code (Apex, LWC, OmniStudio).</td></tr>
            </tbody>
        </table>
    </div>
    """

    # Current Configuration Table
    config_rows = []
    if posture_config:
        for entry in posture_config:
            level_str = entry.level.value if entry.level else "Auto (détection)"
            rule_html = _capability_rule_html(entry, capability_rules)
            config_rows.append(
                f"<tr>"
                f"<td>{html_value(entry.label)}</td>"
                f"<td>{entry.weight}</td>"
                f"<td>{html_value(level_str)}</td>"
                f"<td>{'Oui' if entry.custom else 'Non'}</td>"
                f"<td>{rule_html}</td>"
                f"</tr>"
            )
    else:
        # Fallback to defaults if no config provided
        for definition in CAPABILITY_CATALOG:
            rule = capability_rules.get(
                definition.capability_id,
                "Détection automatique par analyse des métadonnées.",
            )
            config_rows.append(
                f"<tr>"
                f"<td>{html_value(definition.label)}</td>"
                f"<td>{definition.weight}</td>"
                f"<td>Auto (détection)</td>"
                f"<td>Non</td>"
                f"<td>{rule}</td>"
                f"</tr>"
            )

    config_table = f"""
    <div class="section">
        <h3>Paramètres appliqués pour cette génération</h3>
        <table>
            <thead>
                <tr><th>Capacité</th><th>Poids</th><th>Niveau configuré</th><th>Personnalisée</th><th>Règle de calcul</th></tr>
            </thead>
            <tbody>
                {''.join(config_rows)}
            </tbody>
        </table>
    </div>
    """

    body = f"""
    {back_link}
    <h1>Méthodologie de calcul</h1>
    <p>Cette page détaille les règles et les paramètres utilisés pour produire les indicateurs de synthèse de cette documentation.</p>
    {ia_section}
    {dm_section}
    {posture_intro}
    {config_table}
    """

    return render_page("Méthodologie", body, current_path, assets_dir, include_mermaid=False)


def write_methodology_page(
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    posture_config: list[PostureCapabilityConfig] | None = None,
    data_model_thresholds: tuple[int, int, int] = DEFAULT_DATA_MODEL_THRESHOLDS,
    profiles_thresholds: tuple[int, int, int] = DEFAULT_PROFILES_THRESHOLDS,
) -> Path:
    """Write methodology.html and return its path."""
    path = output_dir / "methodology.html"
    write_text(
        path,
        render_methodology_page(
            path,
            output_dir,
            assets_dir,
            posture_config,
            data_model_thresholds=data_model_thresholds,
            profiles_thresholds=profiles_thresholds,
        ),
    )
    log(f"Page Méthodologie générée : {path}")
    return path
