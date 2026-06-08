"""Pydantic models for the YAML config that drives each brief.

The config is the *only file you edit each cycle* — events, vendor report
IDs, trade ideas, tail risks. Everything else (template, palette,
chart logic) stays static. Loaded via :func:`load_config`.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- shared atoms ----------

Tier = Literal[1, 2, 3]                       # 1 = market-moving, 3 = low
TradeKind = Literal["rates", "fx", "equity", "credit", "commodity", "macro"]


class Event(BaseModel):
    """One row in the §1 calendar table."""
    model_config = ConfigDict(extra="forbid")

    day: str                                  # "Mon" / "Tue 9 Jun" — free-form
    time_utc: str                             # "20:30" / "TBC"
    name: str                                 # "US May CPI"
    consensus: str = ""
    prior: str = ""
    vendor_lean: str = ""
    tier: Tier = 3
    deep_dive: bool = False                   # promotes to its own §


class ReactionScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str                                # "Soft / dovish"
    prob: int                                 # 5..100
    trigger: str                              # "Core ≤ 0.20 m/m"
    cells: dict[str, str]                     # column_id -> body cell text


class ReactionMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[str]                        # column headers (≥ 3 typical)
    bull: ReactionScenario | None = None
    base: ReactionScenario
    bear: ReactionScenario | None = None


class VendorQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str                                 # verbatim from research.fact_chunk
    chunk_ref: str | None = None              # "ch.0" / "chunk_id 12345"


class VendorCard(BaseModel):
    """One per-bank thesis block in a deep-dive section."""
    model_config = ConfigDict(extra="forbid")

    bank: str                                 # display label "BNP Paribas"
    report_id: int                            # research.dim_report.id — link source
    thesis: str                               # italic one-liner
    forecast: str = ""                        # numeric line "Hd 0.56 / Core 0.29"
    quotes: list[VendorQuote] = Field(default_factory=list)
    trade: str | None = None                  # explicit trade levels if any
    risk: str | None = None


class PdfEmbed(BaseModel):
    """A bank PDF page rendered + embedded as augmentation."""
    model_config = ConfigDict(extra="forbid")

    report_id: int
    pages: list[int] = Field(default_factory=lambda: [1])     # 1-indexed
    eyebrow: str = ""                                          # "BNP · Hot-tail forecast"
    look_at: str | None = None                                 # the pa-note guidance


class DeepDive(BaseModel):
    """A full deep-dive section (e.g. US CPI, ECB).

    Renders to: lead paragraph -> consensus banner -> vendor forecast
    table -> vendor cards -> component drivers -> reaction matrix ->
    PDF embeds.
    """
    model_config = ConfigDict(extra="forbid")

    section_id: str                           # "uscpi" (used as HTML anchor)
    section_num: str                          # "§3"
    title: str                                # "US May CPI — Wed 10 Jun 20:30 UTC"
    label: str = "DEEP DIVE"                  # appears as suffix in header
    lead: str                                 # narrative paragraph
    consensus_number: str                     # "0.22" / "10/10"
    consensus_text: str                       # banner text
    forecast_table_headers: list[str] = Field(default_factory=list)
    forecast_table_rows: list[list[str]] = Field(default_factory=list)
    vendor_cards: list[VendorCard] = Field(default_factory=list)
    component_drivers: list[list[str]] = Field(default_factory=list)
    reaction_matrix: ReactionMatrix | None = None
    pdf_embeds: list[PdfEmbed] = Field(default_factory=list)


class MediumSection(BaseModel):
    """Lighter section — narrative + table + 1 PDF embed."""
    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_num: str
    title: str
    callout: str | None = None                # e.g. KRW alert callout
    callout_kind: Literal["default", "warn", "alert"] = "default"
    lead: str
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    pdf_embeds: list[PdfEmbed] = Field(default_factory=list)
    chart_files: list[str] = Field(default_factory=list)       # filename in charts/


class Trade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idx: int
    name: str
    kind: TradeKind
    thesis: str
    risk: str
    owners: str                                                # "JPM, Goldman, Nomura"
    report_ids: list[int] = Field(default_factory=list)        # link in owners


class TailRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str                                                  # may include <strong>


class KpiCell(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str                                                 # "EUR/USD"
    value: str                                                 # "1.1510"
    change: str = ""                                           # "−1.13%"
    change_sign: Literal["pos", "neg", "flat"] = "flat"
    context: str = ""                                          # "into ECB"


# ---------- top-level configs ----------


class _BriefBase(BaseModel):
    """Shared across weekly and daily."""
    model_config = ConfigDict(extra="forbid")

    period_date: date                                          # anchor date
    title: str                                                 # hero h1
    subtitle_html: str                                         # hero p (may include <strong>)
    story_callout: str
    kpis: list[KpiCell] = Field(default_factory=list)          # mini-table
    events: list[Event] = Field(default_factory=list)
    appendix: dict[str, str] = Field(default_factory=dict)     # {topic: "vendor 4694 · ..."}


class WeeklyConfig(_BriefBase):
    model_config = ConfigDict(extra="forbid")
    brief_type: Literal["weekly"] = "weekly"
    deep_dives: list[DeepDive] = Field(default_factory=list)
    medium_sections: list[MediumSection] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)
    tail_risks: list[TailRisk] = Field(default_factory=list)


class DailyConfig(_BriefBase):
    model_config = ConfigDict(extra="forbid")
    brief_type: Literal["daily"] = "daily"
    # Daily uses lighter MediumSection blocks for each Tier-1 event today
    sections: list[MediumSection] = Field(default_factory=list)
    yesterday_recap: str = ""                                  # narrative + a small table
    yesterday_table: list[list[str]] = Field(default_factory=list)
    top_trades: list[Trade] = Field(default_factory=list)      # 2-3 max
    watch_list: list[TailRisk] = Field(default_factory=list)   # "watch for" bullets


BriefConfig = Annotated[
    WeeklyConfig | DailyConfig,
    Field(discriminator="brief_type"),
]


# ---------- IO ----------

def load_config(path: Path | str) -> WeeklyConfig | DailyConfig:
    """Read a YAML file and resolve into the correct config model.

    ``brief_type`` field in the YAML selects weekly vs daily. Raises
    ``ValueError`` if the type is missing or unknown.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} is not a YAML mapping")
    bt = raw.get("brief_type")
    if bt == "weekly":
        return WeeklyConfig.model_validate(raw)
    if bt == "daily":
        return DailyConfig.model_validate(raw)
    raise ValueError(f"{path}: brief_type must be 'weekly' or 'daily', got {bt!r}")
