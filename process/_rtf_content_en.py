"""English content for the Lucie usage guide RTF."""
from __future__ import annotations

from _rtf_helpers import (
    bullets,
    build_document,
    code_block,
    h1,
    h2,
    numbered,
    page_break,
    paragraph,
    placeholder,
    quote,
)


def english_document() -> str:
    parts: list[str] = []

    parts.append(h1("Dewey : Doc Org - Salesforce"))
    parts.append(h1("Usage guide for Squads, Tech Leads and the Design Review"))
    parts.append(
        paragraph(
            "This document explains step-by-step how Squads, Tech Leads and "
            "the Design Review use Lucie to produce, share and leverage a "
            "high-quality Salesforce documentation. It emphasises the "
            "benefits brought by the tool and the collaborative aspect "
            "across the team."
        )
    )
    parts.append(page_break())

    parts.append(h1("1. Overview"))
    parts.append(
        paragraph(
            "Lucie is an internal tool that analyses a Salesforce org and "
            "produces: a complete HTML documentation (objects, Apex, Flows, "
            "OmniStudio, permissions), detailed Excel workbooks (data "
            "dictionary, profiles, permission sets, inventory, PMD "
            "violations) and two Word documents (a data dictionary and a "
            "summary holding prioritised advice)."
        )
    )
    parts.append(paragraph("Three audiences use Lucie:"))
    parts.append(
        bullets(
            [
                "Squads: to quickly explore the metadata, prepare a story or "
                "validate the impact of a delivery.",
                "Tech Leads: to drive technical quality, follow the org "
                "evolution sprint after sprint and feed cross-cutting "
                "reviews.",
                "Design Review: to rely on a standardised support to arbitrate "
                "and prioritise the actions to take.",
            ]
        )
    )
    parts.append(
        paragraph(
            "The generated documentation is centralised in a shared folder "
            "so everyone works on the same body of knowledge."
        )
    )

    parts.append(h1("2. Key benefits"))
    parts.append(
        bullets(
            [
                "Automated, standardised documentation: no more manual "
                "maintenance of the data dictionary, the Apex/Flow pages or "
                "the permission set list.",
                "Prioritised advice: the Word summary lists actions sorted by "
                "severity then by occurrence count. The most impactful items "
                "appear first.",
                "Adopt vs Adapt score: a synthetic indicator to compare the "
                "level of customisation across orgs or over time.",
                "Anti-pattern detection: static analysis rules inspired by "
                "PMD, the Salesforce Well-Architected Framework and the "
                "Architect Decision Guides.",
                "Multilingual: generation in French or English depending on "
                "the UI language.",
                "Built-in AI assistant: discuss the analysed org with Claude "
                "or Gemini.",
                "Native collaboration: shareable configuration (weights, "
                "rules, exclusions), shared output folder, format suited to "
                "meeting minutes.",
            ]
        )
    )

    parts.append(h1("3. Setup and shared configuration"))
    parts.append(
        paragraph(
            "Before rolling Lucie out to the Squads, the technical owner "
            "sets up a shared reference configuration."
        )
    )

    parts.append(h2("3.1 Installation"))
    parts.append(
        numbered(
            [
                "Clone the repository.",
                "Install dependencies: pip install -r requirements.txt.",
                "(Optional) Install Salesforce CLI (sf) and PMD for the "
                "built-in features.",
                "Run the application: python app.py.",
            ]
        )
    )

    parts.append(h2("3.2 Shared configuration"))
    parts.append(paragraph("In the configuration screen, the team agrees on:"))
    parts.append(
        bullets(
            [
                "The shared output folder (network share, OneDrive or "
                "SharePoint accessible to every Squad).",
                "The exclusion file (exclusion.xlsx), versioned and used by "
                "every Squad to homogenise results.",
                "The PMD ruleset (optional), versioned in the same shared "
                "repository.",
                "The static analysis rules (rules.xml): validate the enabled "
                "rules through the \"Analysis rules\" tab.",
                "Scoring weights and Adopt vs Adapt weights: standardised, "
                "otherwise scores stop being comparable across Squads.",
                "The interface language (FR or EN), which drives the language "
                "of the generated Word documents.",
                "The \"Generate the Data Dictionary Word document\" and "
                "\"Generate the summary Word document\" toggles: ticked by "
                "default, leave them on so Design Review has its inputs.",
                "AI API keys (Claude, Gemini): personal, kept in each user's "
                "individual configuration.",
            ]
        )
    )
    parts.append(
        quote(
            "Tip: versioning exclusion.xlsx, rules.xml and the PMD ruleset "
            "in a shared Git repository ensures consistent analyses across "
            "all Squads."
        )
    )

    parts.append(page_break())

    parts.append(h1("4. How Squads use the tool"))
    parts.append(
        paragraph(
            "Each Squad uses Lucie for everyday needs: exploring the org, "
            "preparing a story, auditing before a release."
        )
    )

    parts.append(h2("4.1 Standard run"))
    parts.append(
        numbered(
            [
                "Open Lucie via python app.py.",
                "Pick the source folder (Salesforce retrieve output or clone "
                "of the Squad repo).",
                "Pick the shared output folder, in a Squad-specific dated "
                "subfolder (e.g. \\\\share\\dewey\\squad-alpha\\2026-04-25).",
                "Load the Salesforce org: either via Web login + alias then "
                "Generate manifest and Run retrieve, or directly via the "
                "Manifest + Retrieve + Doc button which chains everything.",
                "Click Generate documentation.",
                "Open the HTML index and explore the generated docs.",
            ]
        )
    )

    parts.append(h2("4.2 Recommended use cases"))
    parts.append(
        bullets(
            [
                "Onboarding a new joiner: the HTML documentation provides an "
                "instant map of the org (objects, flows, Apex classes, "
                "permissions).",
                "Preparing a story: open the data dictionary Word document or "
                "the page of the impacted object to identify existing fields, "
                "record types and rules.",
                "Pre-release audit: generate the docs before delivery and "
                "compare the Word summary with the previous run to spot new "
                "findings.",
                "Quick check: ask the AI assistant (Discussion tab) about the "
                "org instead of digging through code.",
            ]
        )
    )

    parts.append(h2("4.3 Squad guidelines"))
    parts.append(
        bullets(
            [
                "Run the generation before each sprint review to have a "
                "stable baseline.",
                "Store the documentation in the shared folder: other Squads "
                "and Design Review will rely on it.",
                "React quickly to the Critical and Major findings of the "
                "Word summary; they are the first to surface in Design "
                "Review.",
            ]
        )
    )

    placeholder1 = (
        "[DIAGRAM PLACEHOLDER 1: Squad workflow - "
        "insert here the PNG or PDF export of squad_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder1))

    parts.append(page_break())

    parts.append(h1("5. How Tech Leads use the tool"))
    parts.append(
        paragraph(
            "The Tech Lead drives the technical quality of their Squad and "
            "feeds the cross-cutting reviews led by the manager."
        )
    )

    parts.append(h2("5.1 Tooling responsibilities"))
    parts.append(
        bullets(
            [
                "Maintain the shared configuration (analysis rules, exclusion "
                "file, scoring weights).",
                "Make sure the Squad generates the documentation at least "
                "once per sprint.",
                "Review the findings raised and organise their treatment "
                "with the Squad.",
                "Surface to the manager the topics that go beyond the Squad "
                "boundaries and deserve a Design Review.",
            ]
        )
    )

    parts.append(h2("5.2 Typical sprint workflow"))
    parts.append(
        numbered(
            [
                "Beginning of sprint: pull the latest generation stored in "
                "the shared folder as a reference baseline.",
                "During the sprint: launch an intermediate analysis on a "
                "major refactor (new object, Apex refactor, Flow migration).",
                "End of sprint: generate the full documentation and archive "
                "it in the shared folder (dated subfolder).",
                "Prepare the retrospective / sprint review: pull the 3 to 5 "
                "highest-priority actions from the Word summary.",
                "Prepare the Design Review: surface to the manager the "
                "cross-cutting findings and arbitration topics.",
            ]
        )
    )

    parts.append(h2("5.3 Indicators to watch"))
    parts.append(
        bullets(
            [
                "Customisation score evolution sprint after sprint.",
                "Adopt vs Adapt score evolution.",
                "Findings volume per severity (Critical, Major, Minor, Info).",
                "Top 5 triggered rules, visible in the Advice chapter of the "
                "Word summary.",
                "Number of objects and fields actually documented (data "
                "dictionary).",
            ]
        )
    )

    parts.append(page_break())

    parts.append(h1("6. Use in Design Review"))
    parts.append(
        paragraph(
            "The Design Review combines outputs produced by every Squad to "
            "take coordinated architecture decisions. This is where the "
            "Word summary and its Advice chapter shine."
        )
    )

    parts.append(h2("6.1 Before the meeting"))
    parts.append(
        numbered(
            [
                "The manager (Design Review host) gathers from the shared "
                "folder the summary.docx of every Squad, the matching "
                "data_dictionary.docx and the HTML index for technical "
                "details.",
                "Preliminary read of the Advice chapter of every summary.",
                "Selection of actions to debate, prioritising Critical and "
                "Major ones.",
                "Building the agenda from that selection.",
            ]
        )
    )

    parts.append(h2("6.2 During the meeting"))
    parts.append(
        numbered(
            [
                "Walk through the Word summary: cover page, overview, "
                "customisation metrics, then Advice chapter.",
                "For each priority action, discuss the finding with the "
                "concerned Squad.",
                "Decide the action: fix now, documented exception or "
                "deferred with deadline.",
                "Assign the responsible Squad and action owner.",
                "If needed, open the data dictionary Word document or HTML "
                "documentation to double-check a technical detail.",
                "Capture each decision in the meeting minutes by quoting the "
                "rule identifier (for example APEX-SEC-001).",
            ]
        )
    )

    parts.append(h2("6.3 After the meeting"))
    parts.append(
        bullets(
            [
                "Store the meeting minutes next to the analysed documentation "
                "in the shared folder.",
                "Minutes refer to findings from the Word summary, which makes "
                "decisions replayable.",
                "At the next Design Review, verify the decrease in occurrence "
                "count for every treated finding and acknowledge the Squads "
                "that progressed.",
            ]
        )
    )

    placeholder2 = (
        "[DIAGRAM PLACEHOLDER 2: Design Review workflow - "
        "insert here the PNG or PDF export of design_review_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder2))

    parts.append(page_break())

    parts.append(h1("7. Collaborative aspect and shared folder"))
    parts.append(
        paragraph(
            "The tool delivers its full value when shared and when every "
            "actor works from the same reference folder."
        )
    )

    parts.append(h2("7.1 Suggested layout"))
    parts.append(
        code_block(
            [
                "\\\\share\\dewey\\",
                "+-- _config\\",
                "|   +-- exclusion.xlsx",
                "|   +-- rules.xml",
                "|   +-- pmd_ruleset.xml",
                "+-- squad-alpha\\",
                "|   +-- 2026-04-11\\",
                "|   |   +-- index.html",
                "|   |   +-- excel\\...",
                "|   |   +-- word\\data_dictionary.docx",
                "|   |   +-- word\\summary.docx",
                "|   +-- 2026-04-25\\",
                "+-- squad-beta\\",
                "+-- design-review\\",
                "    +-- 2026-04-15-minutes.docx",
                "    +-- 2026-04-29-minutes.docx",
            ]
        )
    )

    parts.append(h2("7.2 Collaborative benefits"))
    parts.append(
        bullets(
            [
                "Single view: everyone reads the same data and the same "
                "rules.",
                "Capitalisation: the generation history works as the "
                "collective memory of the org.",
                "Comparison: Tech Leads can compare their Squad with others "
                "on the same basis.",
                "Traceable decisions: Design Review minutes refer to rule "
                "identifiers, making arbitrations replayable.",
                "Easier communication: the Word documents can be shared with "
                "non-technical stakeholders (Product Owners, Architects, "
                "Sponsors).",
            ]
        )
    )

    placeholder3 = (
        "[DIAGRAM PLACEHOLDER 3: Collaborative view - "
        "insert here the PNG or PDF export of collaboration_overview.drawio.]"
    )
    parts.append(placeholder(placeholder3))

    parts.append(h1("8. Best practices"))
    parts.append(
        bullets(
            [
                "Refresh the docs after each major change (new module, "
                "object refactor, important batch).",
                "Version the shared configuration (exclusion.xlsx, "
                "rules.xml, pmd_ruleset.xml).",
                "Name the generation subfolders with an ISO date YYYY-MM-DD "
                "to ease sorting.",
                "Limit the use of the exclusion file: it must reflect "
                "architecture decisions, not hide problems.",
                "Agree on scoring weights upfront: a score is only "
                "meaningful against a shared reference.",
                "Store Design Review minutes alongside the analysed "
                "documentation for traceability.",
                "Run a full cycle (generation + Design Review + fix) at "
                "least once per release.",
            ]
        )
    )

    parts.append(h1("9. Appendices - associated diagrams"))
    parts.append(
        paragraph(
            "Three drawio diagrams ship in this folder. Insert them where "
            "the PLACEHOLDER blocks appear above:"
        )
    )
    parts.append(
        bullets(
            [
                "squad_workflow.drawio: Squad workflow over a sprint.",
                "design_review_workflow.drawio: Design Review flow.",
                "collaboration_overview.drawio: high-level view of the "
                "collaboration between Squads, Tech Leads and Design Review.",
            ]
        )
    )
    parts.append(
        paragraph(
            "How to open them: use https://app.diagrams.net or the "
            "Draw.io Integration extension for Visual Studio Code. Export "
            "as PNG or PDF and replace the PLACEHOLDER blocks with the "
            "matching image."
        )
    )

    return build_document(parts)
