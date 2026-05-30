"""Service to manage generation history in a SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class HistoryEntry:
    """A single generation history record."""
    id: int | None = None
    alias: str = ""
    source_dir: str = ""
    output_dir: str = ""
    score: int = 0
    score_no_code: int = 0
    score_low_code: int = 0
    score_pro_code: int = 0
    adopt_adapt_score: int = 0
    adopt_adapt_score_no_code: int = 0
    adopt_adapt_score_low_code: int = 0
    adopt_adapt_score_pro_code: int = 0
    custom_objects: int = 0
    standard_objects: int = 0
    custom_fields: int = 0
    standard_fields: int = 0
    flows: int = 0
    record_types: int = 0
    validation_rules: int = 0
    page_layouts: int = 0
    custom_tabs: int = 0
    custom_apps: int = 0
    total_custom_components: int = 0
    total_standard_components: int = 0
    adopt_ootb_count: int = 0
    adopt_decl_count: int = 0
    adapt_low_count: int = 0
    adapt_high_count: int = 0
    apex_classes_triggers: int = 0
    omni_components: int = 0
    agents: int = 0
    gen_ai_prompts: int = 0
    einstein_predictions: int = 0
    findings_total: int = 0
    findings_critical: int = 0
    findings_major: int = 0
    findings_minor: int = 0
    findings_info: int = 0
    ai_usage_pct: float = 0.0
    data_model_custom_pct: float = 0.0
    data_model_standard_pct: float = 0.0
    adoption_pct: float = 0.0
    adaptation_pct: float = 0.0
    timestamp: str = ""
    generation_number: int = 0


@dataclass(slots=True)
class GeneratedReport:
    """A report generated from the history screen."""
    id: int | None = None
    alias: str = ""
    type: str = ""  # 'dashboard' or 'comparison'
    path: str = ""
    timestamp: str = ""
    label: str = ""


class HistoryService:
    """Service to handle SQLite operations for generation history."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the database and create tables if they don't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT,
                    source_dir TEXT,
                    output_dir TEXT,
                    score INTEGER,
                    score_no_code INTEGER,
                    score_low_code INTEGER,
                    score_pro_code INTEGER,
                    adopt_adapt_score INTEGER,
                    adopt_adapt_score_no_code INTEGER,
                    adopt_adapt_score_low_code INTEGER,
                    adopt_adapt_score_pro_code INTEGER,
                    custom_objects INTEGER,
                    standard_objects INTEGER,
                    custom_fields INTEGER,
                    standard_fields INTEGER,
                    flows INTEGER,
                    record_types INTEGER,
                    validation_rules INTEGER,
                    page_layouts INTEGER,
                    custom_tabs INTEGER,
                    custom_apps INTEGER,
                    total_custom_components INTEGER,
                    total_standard_components INTEGER,
                    adopt_ootb_count INTEGER,
                    adopt_decl_count INTEGER,
                    adapt_low_count INTEGER,
                    adapt_high_count INTEGER,
                    apex_classes_triggers INTEGER,
                    omni_components INTEGER,
                    agents INTEGER,
                    gen_ai_prompts INTEGER,
                    einstein_predictions INTEGER,
                    findings_total INTEGER,
                    findings_critical INTEGER,
                    findings_major INTEGER,
                    findings_minor INTEGER,
                    findings_info INTEGER,
                    ai_usage_pct REAL,
                    data_model_custom_pct REAL,
                    data_model_standard_pct REAL,
                    adoption_pct REAL,
                    adaptation_pct REAL,
                    timestamp TEXT,
                    generation_number INTEGER
                )
            """)
            
            # Migration: add missing columns if they don't exist
            cursor = conn.execute("PRAGMA table_info(history)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            new_cols = [
                ("agents", "INTEGER DEFAULT 0"),
                ("gen_ai_prompts", "INTEGER DEFAULT 0"),
                ("einstein_predictions", "INTEGER DEFAULT 0"),
                ("standard_objects", "INTEGER DEFAULT 0"),
                ("standard_fields", "INTEGER DEFAULT 0"),
                ("score_no_code", "INTEGER DEFAULT 0"),
                ("score_low_code", "INTEGER DEFAULT 0"),
                ("score_pro_code", "INTEGER DEFAULT 0"),
                ("adopt_adapt_score_no_code", "INTEGER DEFAULT 0"),
                ("adopt_adapt_score_low_code", "INTEGER DEFAULT 0"),
                ("adopt_adapt_score_pro_code", "INTEGER DEFAULT 0"),
                ("record_types", "INTEGER DEFAULT 0"),
                ("validation_rules", "INTEGER DEFAULT 0"),
                ("page_layouts", "INTEGER DEFAULT 0"),
                ("custom_tabs", "INTEGER DEFAULT 0"),
                ("custom_apps", "INTEGER DEFAULT 0"),
                ("total_custom_components", "INTEGER DEFAULT 0"),
                ("total_standard_components", "INTEGER DEFAULT 0"),
                ("adopt_ootb_count", "INTEGER DEFAULT 0"),
                ("adopt_decl_count", "INTEGER DEFAULT 0"),
                ("adapt_low_count", "INTEGER DEFAULT 0"),
                ("adapt_high_count", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_type in new_cols:
                if col_name not in existing_columns:
                    conn.execute(f"ALTER TABLE history ADD COLUMN {col_name} {col_type}")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS generated_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT,
                    type TEXT,
                    path TEXT,
                    timestamp TEXT,
                    label TEXT
                )
            """)
            conn.commit()

    def add_entry(self, entry: HistoryEntry) -> int:
        """Add a new history entry and return its ID."""
        # Calculate generation number for this alias
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(generation_number) FROM history WHERE alias = ?",
                (entry.alias,)
            )
            max_num = cursor.fetchone()[0]
            entry.generation_number = (max_num or 0) + 1
            entry.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor = conn.execute("""
                INSERT INTO history (
                    alias, source_dir, output_dir, score, 
                    score_no_code, score_low_code, score_pro_code,
                    adopt_adapt_score, 
                    adopt_adapt_score_no_code, adopt_adapt_score_low_code, adopt_adapt_score_pro_code,
                    custom_objects, standard_objects, custom_fields, standard_fields, 
                    flows, record_types, validation_rules, page_layouts, custom_tabs, custom_apps,
                    total_custom_components, total_standard_components,
                    adopt_ootb_count, adopt_decl_count, adapt_low_count, adapt_high_count,
                    apex_classes_triggers,
                    omni_components, agents, gen_ai_prompts, einstein_predictions, findings_total, findings_critical,
                    findings_major, findings_minor, findings_info,
                    ai_usage_pct, data_model_custom_pct, data_model_standard_pct,
                    adoption_pct, adaptation_pct, timestamp, generation_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.alias, entry.source_dir, entry.output_dir, entry.score,
                entry.score_no_code, entry.score_low_code, entry.score_pro_code,
                entry.adopt_adapt_score,
                entry.adopt_adapt_score_no_code, entry.adopt_adapt_score_low_code, entry.adopt_adapt_score_pro_code,
                entry.custom_objects, entry.standard_objects,
                entry.custom_fields, entry.standard_fields,
                entry.flows, entry.record_types, entry.validation_rules, entry.page_layouts, entry.custom_tabs, entry.custom_apps,
                entry.total_custom_components, entry.total_standard_components,
                entry.adopt_ootb_count, entry.adopt_decl_count, entry.adapt_low_count, entry.adapt_high_count,
                entry.apex_classes_triggers, entry.omni_components,
                entry.agents, entry.gen_ai_prompts, entry.einstein_predictions,
                entry.findings_total, entry.findings_critical, entry.findings_major,
                entry.findings_minor, entry.findings_info, entry.ai_usage_pct,
                entry.data_model_custom_pct, entry.data_model_standard_pct,
                entry.adoption_pct, entry.adaptation_pct, entry.timestamp,
                entry.generation_number
            ))
            conn.commit()
            return cursor.lastrowid

    def add_report(self, report: GeneratedReport) -> int:
        """Add a new generated report and return its ID."""
        report.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO generated_reports (alias, type, path, timestamp, label)
                VALUES (?, ?, ?, ?, ?)
            """, (report.alias, report.type, report.path, report.timestamp, report.label))
            conn.commit()
            return cursor.lastrowid

    def list_reports_for_alias(self, alias: str) -> list[GeneratedReport]:
        """Return all generated reports for a given alias."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM generated_reports WHERE alias = ? ORDER BY timestamp DESC",
                (alias,)
            )
            return [
                GeneratedReport(
                    id=row["id"],
                    alias=row["alias"],
                    type=row["type"],
                    path=row["path"],
                    timestamp=row["timestamp"],
                    label=row["label"]
                )
                for row in cursor.fetchall()
            ]

    def delete_report(self, report_id: int) -> None:
        """Delete a generated report entry from the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM generated_reports WHERE id = ?", (report_id,))
            conn.commit()

    def list_aliases(self) -> list[str]:
        """Return a sorted list of all unique aliases in history."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT alias FROM history ORDER BY alias ASC")
            return [row[0] for row in cursor.fetchall()]

    def list_entries_for_alias(self, alias: str) -> list[HistoryEntry]:
        """Return all history entries for a given alias, sorted by generation number."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM history WHERE alias = ? ORDER BY generation_number DESC",
                (alias,)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_first_entry_for_alias(self, alias: str) -> HistoryEntry | None:
        """Return the very first generation entry for an alias."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM history WHERE alias = ? ORDER BY generation_number ASC LIMIT 1",
                (alias,)
            )
            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None

    def delete_entry(self, entry_id: int) -> None:
        """Delete a history entry by its ID."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()

    def delete_alias(self, alias: str) -> None:
        """Delete all history entries and reports for a given alias."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM history WHERE alias = ?", (alias,))
            conn.execute("DELETE FROM generated_reports WHERE alias = ?", (alias,))
            conn.commit()

    def update_entry(self, entry: HistoryEntry) -> None:
        """Update an existing history entry."""
        if entry.id is None:
            return
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE history SET
                    alias = ?, source_dir = ?, output_dir = ?, score = ?,
                    score_no_code = ?, score_low_code = ?, score_pro_code = ?,
                    adopt_adapt_score = ?, 
                    adopt_adapt_score_no_code = ?, adopt_adapt_score_low_code = ?, adopt_adapt_score_pro_code = ?,
                    custom_objects = ?, standard_objects = ?,
                    custom_fields = ?, standard_fields = ?,
                    flows = ?, record_types = ?, validation_rules = ?, page_layouts = ?, custom_tabs = ?, custom_apps = ?,
                    total_custom_components = ?, total_standard_components = ?,
                    adopt_ootb_count = ?, adopt_decl_count = ?, adapt_low_count = ?, adapt_high_count = ?,
                    apex_classes_triggers = ?, omni_components = ?,
                    agents = ?, gen_ai_prompts = ?, einstein_predictions = ?,
                    findings_total = ?, findings_critical = ?, findings_major = ?,
                    findings_minor = ?, findings_info = ?, ai_usage_pct = ?,
                    data_model_custom_pct = ?, data_model_standard_pct = ?,
                    adoption_pct = ?, adaptation_pct = ?, timestamp = ?,
                    generation_number = ?
                WHERE id = ?
            """, (
                entry.alias, entry.source_dir, entry.output_dir, entry.score,
                entry.score_no_code, entry.score_low_code, entry.score_pro_code,
                entry.adopt_adapt_score,
                entry.adopt_adapt_score_no_code, entry.adopt_adapt_score_low_code, entry.adopt_adapt_score_pro_code,
                entry.custom_objects, entry.standard_objects,
                entry.custom_fields, entry.standard_fields,
                entry.flows, entry.record_types, entry.validation_rules, entry.page_layouts, entry.custom_tabs, entry.custom_apps,
                entry.total_custom_components, entry.total_standard_components,
                entry.adopt_ootb_count, entry.adopt_decl_count, entry.adapt_low_count, entry.adapt_high_count,
                entry.apex_classes_triggers, entry.omni_components,
                entry.agents, entry.gen_ai_prompts, entry.einstein_predictions,
                entry.findings_total, entry.findings_critical, entry.findings_major,
                entry.findings_minor, entry.findings_info, entry.ai_usage_pct,
                entry.data_model_custom_pct, entry.data_model_standard_pct,
                entry.adoption_pct, entry.adaptation_pct, entry.timestamp,
                entry.generation_number, entry.id
            ))
            conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> HistoryEntry:
        """Convert a database row to a HistoryEntry object using column names."""
        
        def get_val(name: str, default: Any = 0) -> Any:
            try:
                return row[name]
            except (IndexError, KeyError):
                return default

        return HistoryEntry(
            id=get_val("id", None),
            alias=get_val("alias", ""),
            source_dir=get_val("source_dir", ""),
            output_dir=get_val("output_dir", ""),
            score=get_val("score"),
            score_no_code=get_val("score_no_code"),
            score_low_code=get_val("score_low_code"),
            score_pro_code=get_val("score_pro_code"),
            adopt_adapt_score=get_val("adopt_adapt_score"),
            adopt_adapt_score_no_code=get_val("adopt_adapt_score_no_code"),
            adopt_adapt_score_low_code=get_val("adopt_adapt_score_low_code"),
            adopt_adapt_score_pro_code=get_val("adopt_adapt_score_pro_code"),
            custom_objects=get_val("custom_objects"),
            standard_objects=get_val("standard_objects"),
            custom_fields=get_val("custom_fields"),
            standard_fields=get_val("standard_fields"),
            flows=get_val("flows"),
            record_types=get_val("record_types"),
            validation_rules=get_val("validation_rules"),
            page_layouts=get_val("page_layouts"),
            custom_tabs=get_val("custom_tabs"),
            custom_apps=get_val("custom_apps"),
            total_custom_components=get_val("total_custom_components"),
            total_standard_components=get_val("total_standard_components"),
            adopt_ootb_count=get_val("adopt_ootb_count"),
            adopt_decl_count=get_val("adopt_decl_count"),
            adapt_low_count=get_val("adapt_low_count"),
            adapt_high_count=get_val("adapt_high_count"),
            apex_classes_triggers=get_val("apex_classes_triggers"),
            omni_components=get_val("omni_components"),
            agents=get_val("agents"),
            gen_ai_prompts=get_val("gen_ai_prompts"),
            einstein_predictions=get_val("einstein_predictions"),
            findings_total=get_val("findings_total"),
            findings_critical=get_val("findings_critical"),
            findings_major=get_val("findings_major"),
            findings_minor=get_val("findings_minor"),
            findings_info=get_val("findings_info"),
            ai_usage_pct=get_val("ai_usage_pct", 0.0),
            data_model_custom_pct=get_val("data_model_custom_pct", 0.0),
            data_model_standard_pct=get_val("data_model_standard_pct", 0.0),
            adoption_pct=get_val("adoption_pct", 0.0),
            adaptation_pct=get_val("adaptation_pct", 0.0),
            timestamp=get_val("timestamp", ""),
            generation_number=get_val("generation_number", 0)
        )
