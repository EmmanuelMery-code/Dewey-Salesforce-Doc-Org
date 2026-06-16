"""Service to generate a professional audit summary in RTF format."""

from __future__ import annotations

from pathlib import Path
from src.core.models import MetadataSnapshot, CustomizationMetrics
from src.core.utils import write_text

def generate_audit_summary_rtf(
    snapshot: MetadataSnapshot,
    metrics: CustomizationMetrics,
    output_path: Path,
) -> None:
    """Generate a professional audit summary in RTF format."""
    
    # RTF Header
    rtf = r"{\rtf1\ansi\deff0"
    rtf += r"{\fonttbl{\f0\fswiss\fcharset0 Segoe UI;}{\f1\fswiss\fcharset0 Arial;}}"
    rtf += r"{\colortbl;\red0\green0\blue0;\red29\green78\blue216;\red100\green116\blue139;}"
    
    from datetime import datetime
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Title
    rtf += r"\viewkind4\uc1\pard\cf1\f0\fs36\b Audit de Synthese Salesforce\b0\fs24\par"
    rtf += rf"\cf3\fs20 Genere le {now} \line\par"
    
    # Executive Summary
    rtf += r"\cf1\fs28\b 1. Resume Executif\b0\fs24\par"
    rtf += f"L'organisation Salesforce analysee presente un score de customisation de {metrics.score}."
    rtf += r"\par\par"
    
    # Key Metrics
    rtf += r"\b 2. Metriques Cles\b0\par"
    rtf += r"\pard\li360"
    rtf += f"- Objets personnalises : {metrics.custom_objects}\\line"
    rtf += f"- Champs personnalises : {metrics.custom_fields}\\line"
    rtf += f"- Classes Apex : {metrics.apex_classes}\\line"
    rtf += f"- Triggers Apex : {metrics.apex_triggers}\\line"
    rtf += f"- Flux (Flows) : {metrics.flows}\\line"
    rtf += r"\pard\par"
    
    # Security
    rtf += r"\b 3. Securite et Gouvernance\b0\par"
    rtf += f"- Profils personnalises : {metrics.custom_profiles_count}\\line"
    rtf += f"- Permission Sets : {metrics.permission_sets_count}\\line"
    rtf += r"\par"
    
    # Findings
    rtf += r"\b 4. Points d'attention (Analyse Statique)\b0\par"
    # Add summary of findings here
    rtf += r"\par"
    
    # Conclusion
    rtf += r"\b 5. Conclusion et Recommandations\b0\par"
    rtf += "L'org est globalement saine." # Placeholder
    rtf += r"\par"
    
    rtf += "}"
    
    write_text(output_path, rtf)


def generate_ai_summary_rtf(
    ai_text: str,
    output_path: Path,
) -> None:
    """Save an AI-generated summary text as a professional RTF document."""
    
    # RTF Header
    rtf = r"{\rtf1\ansi\ansicpg1252\deff0"
    rtf += r"{\fonttbl{\f0\fswiss\fcharset0 Segoe UI;}{\f1\fswiss\fcharset0 Arial;}}"
    rtf += r"{\colortbl;\red0\green0\blue0;\red29\green78\blue216;\red100\green116\blue139;}"
    
    from datetime import datetime
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Title
    rtf += r"\viewkind4\uc1\pard\cf1\f0\fs36\b Resume de l'Organisation par l'IA\b0\fs24\par"
    rtf += rf"\cf3\fs20 Genere le {now} \line\par"
    rtf += r"\par"
    
    # Process AI text: convert newlines to \par and handle bold/lists
    # Handle RTF escaping and encoding for accents
    def rtf_escape(text: str) -> str:
        # Basic RTF escaping
        text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        # Encode non-ASCII characters for RTF (CP1252)
        result = []
        for char in text:
            cp = ord(char)
            if cp < 128:
                result.append(char)
            else:
                # Use RTF hex escape \'xx
                try:
                    # Try to encode as cp1252
                    h = char.encode("cp1252").hex()
                    result.append(f"\\'{h}")
                except UnicodeEncodeError:
                    # Fallback to unicode escape \uN?
                    result.append(f"\\u{cp}?")
        return "".join(result)

    processed_text = rtf_escape(ai_text)
    
    # Convert markdown-style bold **text** to RTF \b text \b0
    import re
    processed_text = re.sub(r"\*\*(.*?)\*\*", r"\\b \1 \\b0", processed_text)
    
    # Convert newlines to RTF paragraphs
    processed_text = processed_text.replace("\n", "\\par\n")
    
    rtf += r"\cf1\f0\fs24 " + processed_text
    rtf += r"\par}"
    
    write_text(output_path, rtf)
