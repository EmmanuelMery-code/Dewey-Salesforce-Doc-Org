from __future__ import annotations

from src.analyzer.apex_analyzer_helpers import (
    _count_code_lines,
    _detect_self_recursive_methods,
    _detect_soql_injection,
    _detect_trigger_after_save_recursion,
    _find_hardcoded_ids,
    _has_security_enforcement,
    _strip_comments_and_strings,
)
from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


def analyze_apex_artifact(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    if artifact.kind == "trigger":
        return _analyze_trigger(artifact, catalog)
    return _analyze_class(artifact, catalog)


# ------------------------------------------------------------------ classes


def _analyze_class(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # APEX-SEC-001 : sharing declaration
    if not artifact.is_test and not artifact.is_interface:
        rule = catalog.get("APEX-SEC-001")
        if rule and rule.enabled and not artifact.sharing_declaration:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Aucune declaration 'with sharing' / 'without sharing' / 'inherited sharing' detectee.",
                    details=[
                        "Par defaut la classe herite du contexte appelant, ce qui peut contourner les partages.",
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-SEC-002 : hardcoded Id
    rule = catalog.get("APEX-SEC-002")
    if rule and rule.enabled:
        hardcoded = _find_hardcoded_ids(artifact.body)
        if hardcoded:
            sample = ", ".join(sorted(hardcoded)[:5])
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=f"{len(hardcoded)} identifiant(s) Salesforce ecrit(s) en dur detecte(s).",
                    details=[f"Exemples: {sample}"],
                    source_path=artifact.source_path,
                )
            )

    # APEX-SEC-003 : SOQL injection
    rule = catalog.get("APEX-SEC-003")
    if rule and rule.enabled and not artifact.is_test:
        injection_lines = _detect_soql_injection(artifact.body)
        if injection_lines:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Risque d'injection SOQL detecte dans une requete dynamique.",
                    details=[
                        "L'utilisation de Database.query() avec des variables concatenees sans echappement est risquee.",
                    ],
                    source_path=artifact.source_path,
                    line=injection_lines[0],
                )
            )

    # APEX-SEC-004 : CRUD/FLS enforcement
    rule = catalog.get("APEX-SEC-004")
    if rule and rule.enabled and not artifact.is_test:
        if (artifact.dml_count > 0 or artifact.soql_count > 0) and not _has_security_enforcement(artifact.body):
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Absence de controle CRUD/FLS explicite detectee.",
                    details=[
                        "La classe effectue des operations de donnees sans utiliser WITH USER_MODE, Security.stripInaccessible() ou WITH SECURITY_ENFORCED.",
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-REL-001 : try/catch around DML/SOQL
    rule = catalog.get("APEX-REL-001")
    if rule and rule.enabled and not artifact.is_test:
        if (artifact.dml_count > 0 or artifact.soql_count > 0) and not artifact.has_try_catch:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message="Acces aux donnees sans gestion d'exception (aucun bloc try/catch).",
                    details=[
                        f"SOQL = {artifact.soql_count}, DML = {artifact.dml_count}.",
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-PERF-001 : SOQL in loop
    rule = catalog.get("APEX-PERF-001")
    if rule and rule.enabled and artifact.query_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message="Une requete SOQL apparait potentiellement dans une boucle.",
                source_path=artifact.source_path,
                line=artifact.query_in_loop_line,
            )
        )

    # APEX-PERF-002 : DML in loop
    rule = catalog.get("APEX-PERF-002")
    if rule and rule.enabled and artifact.dml_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message="Un DML apparait potentiellement dans une boucle.",
                source_path=artifact.source_path,
                line=artifact.dml_in_loop_line,
            )
        )

    # APEX-PERF-003 : HTTP callout in loop
    rule = catalog.get("APEX-PERF-003")
    if rule and rule.enabled and artifact.callout_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message="Un callout HTTP (Http/HttpRequest) apparait potentiellement dans une boucle.",
                source_path=artifact.source_path,
                line=artifact.callout_in_loop_line,
            )
        )

    # APEX-REL-002 : method self-recursion without visible guard
    rule = catalog.get("APEX-REL-002")
    if rule and rule.enabled and not artifact.is_test:
        recursive_methods = _detect_self_recursive_methods(artifact.body)
        if recursive_methods:
            sample = ", ".join(sorted(recursive_methods)[:5])
            details = [f"Methode(s) concernee(s) : {sample}."]
            if len(recursive_methods) > 5:
                details.append(
                    f"+ {len(recursive_methods) - 5} autre(s) methode(s) avec auto-appel."
                )
            details.append(
                "Aucune garde de reentrance evidente (Set<Id>/flag static) detectee dans la classe."
            )
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=(
                        f"{len(recursive_methods)} methode(s) s'invoquent elles-memes "
                        "sans mecanisme visible de garde d'arret."
                    ),
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-001 : class length
    rule = catalog.get("APEX-MAINT-001")
    if rule and rule.enabled and artifact.line_count > 500:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=f"Classe de {artifact.line_count} lignes (seuil recommande : 500).",
                source_path=artifact.source_path,
            )
        )

    # APEX-MAINT-002 : comment density
    rule = catalog.get("APEX-MAINT-002")
    if rule and rule.enabled and artifact.line_count > 80:
        ratio = artifact.comment_line_count / max(1, artifact.line_count)
        if ratio < 0.05:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=f"Densite de commentaires = {ratio:.1%} (recommande >= 5%).",
                    details=[
                        f"{artifact.comment_line_count} lignes commentees sur {artifact.line_count}."
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-003 : too many System.debug
    rule = catalog.get("APEX-MAINT-003")
    if rule and rule.enabled and artifact.system_debug_count > 10:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=f"{artifact.system_debug_count} appels 'System.debug' presents dans la classe.",
                source_path=artifact.source_path,
            )
        )

    return findings


# ------------------------------------------------------------------ triggers


def _analyze_trigger(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # TRIG-MAINT-001 : business logic in trigger
    rule = catalog.get("TRIG-MAINT-001")
    if rule and rule.enabled:
        code_lines = _count_code_lines(artifact.body)
        has_dml_or_soql = artifact.dml_count > 0 or artifact.soql_count > 0
        if code_lines > 10 or has_dml_or_soql:
            details = [f"Lignes de code detectees : {code_lines}."]
            if has_dml_or_soql:
                details.append(f"SOQL = {artifact.soql_count}, DML = {artifact.dml_count}.")
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message="Le trigger porte de la logique metier (code substantiel ou operations de donnees).",
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # TRIG-REL-001 : after insert/update trigger rewriting Trigger.new (recursion risk)
    rule = catalog.get("TRIG-REL-001")
    if rule and rule.enabled:
        detection = _detect_trigger_after_save_recursion(artifact.body)
        if detection is not None:
            events, dml_sample = detection
            details = [
                "Evenements declares : " + ", ".join(sorted(events)) + ".",
                "Operation detectee : " + dml_sample + ".",
                "Aucune garde de reentrance (Set<Id> static / classe TriggerHandler) trouvee dans le trigger.",
            ]
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message=(
                        "Le trigger modifie ses propres enregistrements declencheurs "
                        "dans un contexte after-save : risque de boucle infinie."
                    ),
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # TRIG-PERF-001 : SOQL or DML in loop
    rule = catalog.get("TRIG-PERF-001")
    if rule and rule.enabled and (artifact.query_in_loop or artifact.dml_in_loop):
        parts = []
        candidate_lines = []
        if artifact.query_in_loop:
            parts.append("SOQL dans une boucle")
            if artifact.query_in_loop_line is not None:
                candidate_lines.append(artifact.query_in_loop_line)
        if artifact.dml_in_loop:
            parts.append("DML dans une boucle")
            if artifact.dml_in_loop_line is not None:
                candidate_lines.append(artifact.dml_in_loop_line)
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexTrigger",
                target_name=artifact.name,
                message="Operations de donnees potentiellement dans une boucle : " + ", ".join(parts) + ".",
                source_path=artifact.source_path,
                line=min(candidate_lines) if candidate_lines else None,
            )
        )

    return findings
