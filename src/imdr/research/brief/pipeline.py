"""End-to-end orchestrator for the macro brief pipeline.

Public entry points::

    build_weekly(cfg_path, *, settings=None) -> Path     # writes HTML, returns path
    build_daily(cfg_path,  *, settings=None) -> Path

Both delegate to :class:`BriefPipeline` which exposes the individual
stages (``stage_charts``, ``stage_pdfs``, ``stage_render``, ``stage_link``)
so they can be re-run independently in a notebook or CLI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import json
import re
import shutil

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from imdr.config.settings import Settings, get_settings
from imdr.connectors.mssql import MSSQLConnector

from ._paths import (
    BriefType,
    audit_path,
    bank_pdfs_dir,
    charts_dir,
    output_dir,
    output_path,
    report_links_path,
)
from .charts import build_all_charts, configure_matplotlib
from .config import DailyConfig, WeeklyConfig, load_config
from .data.reports import load_report_refs
from .linking import build_report_links
from .pdf import render_pages

log = structlog.get_logger(__name__)

_MODULE_DIR = Path(__file__).parent
_TEMPLATE_DIR = _MODULE_DIR / "templates"
_ASSETS_DIR = _MODULE_DIR / "assets"


@dataclass
class PipelineResult:
    out_html: Path
    charts: list[Path] = field(default_factory=list)
    pdf_pages: list[Path] = field(default_factory=list)
    report_link_count: int = 0
    audit: dict = field(default_factory=dict)


class BriefPipeline:
    """Drives the full weekly/daily build. Stages run sequentially in
    :meth:`run` but can be invoked individually for debugging."""

    def __init__(
        self,
        cfg: WeeklyConfig | DailyConfig,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.cfg = cfg
        self.brief_type: BriefType = cfg.brief_type
        self.anchor: date = cfg.period_date
        self.settings = settings or get_settings()
        self.out_dir = output_dir(self.brief_type, self.anchor)
        self.charts_dir = charts_dir(self.brief_type, self.anchor)
        self.pdfs_dir = bank_pdfs_dir(self.brief_type, self.anchor)
        self.out_html = output_path(self.brief_type, self.anchor)
        self._charts: list[Path] = []
        self._pdfs: list[Path] = []
        self._report_links: dict[str, dict[str, str]] = {}
        self._pdf_embed_paths: dict[str, list[str]] = {}

    # ------------------------------------------------ collect referenced reports
    def _collect_report_ids(self) -> set[int]:
        """Walk the config and return every report_id we need to link or embed."""
        ids: set[int] = set()
        cfg = self.cfg
        if isinstance(cfg, WeeklyConfig):
            for dd in cfg.deep_dives:
                for vc in dd.vendor_cards:
                    ids.add(vc.report_id)
                for em in dd.pdf_embeds:
                    ids.add(em.report_id)
            for ms in cfg.medium_sections:
                for em in ms.pdf_embeds:
                    ids.add(em.report_id)
            for t in cfg.trades:
                ids.update(t.report_ids)
        else:                                                      # DailyConfig
            for ms in cfg.sections:
                for em in ms.pdf_embeds:
                    ids.add(em.report_id)
            for t in cfg.top_trades:
                ids.update(t.report_ids)
        return ids

    # ----------------------------------------------------------- stages
    def stage_assets(self) -> None:
        """Copy theme.css + logo into the output dir's ``assets/`` so the HTML is portable."""
        dest = self.out_dir / "assets"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ASSETS_DIR / "rv_theme.css", dest / "rv_theme.css")
        shutil.copyfile(_ASSETS_DIR / "RV_Logo_Colour.png", dest / "RV_Logo_Colour.png")

    def stage_links(self, conn: MSSQLConnector) -> None:
        """Resolve every cited report_id → SharePoint URL + metadata."""
        ids = self._collect_report_ids()
        with conn.engine.connect() as cx:
            refs = load_report_refs(cx, ids)
        self._report_links = build_report_links(refs)
        report_links_path(self.brief_type, self.anchor).write_text(
            json.dumps(self._report_links, indent=2), encoding="utf-8"
        )
        log.info("links-resolved", requested=len(ids), found=len(refs))

    def stage_charts(self, conn: MSSQLConnector, *, cpi_consensus_mid: float | None = None) -> None:
        configure_matplotlib()
        with conn.engine.connect() as cx:
            self._charts = build_all_charts(
                cx, self.charts_dir, cpi_consensus_mid=cpi_consensus_mid,
            )
        log.info("charts-built", count=len(self._charts), dir=str(self.charts_dir))

    def stage_pdfs(self, conn: MSSQLConnector) -> None:
        """Render the bank PDF money-pages declared in the config."""
        pages_map: dict[int, list[int]] = {}
        if isinstance(self.cfg, WeeklyConfig):
            iterable = (
                [em for dd in self.cfg.deep_dives for em in dd.pdf_embeds]
                + [em for ms in self.cfg.medium_sections for em in ms.pdf_embeds]
            )
        else:
            iterable = [em for ms in self.cfg.sections for em in ms.pdf_embeds]

        for em in iterable:
            pages_map.setdefault(em.report_id, []).extend(em.pages)
        # de-dup pages per report
        for rid in pages_map:
            pages_map[rid] = sorted(set(pages_map[rid]))

        if not pages_map:
            return
        with conn.engine.connect() as cx:
            refs = load_report_refs(cx, pages_map.keys())
        rendered, skipped = render_pages(refs, pages_map, self.pdfs_dir)
        self._pdfs = [r.path for r in rendered]
        # populate embed paths for templates: rid -> [relative img paths]
        for r in rendered:
            self._pdf_embed_paths.setdefault(str(r.report_id), []).append(
                f"bank_pdfs/{r.path.name}"
            )
        log.info("pdf-pages-rendered", rendered=len(rendered), skipped=len(skipped))
        if skipped:
            log.warning("pdf-skips", details=skipped)

    def stage_render(self, *, extra_context: dict | None = None) -> None:
        """Compose the HTML via Jinja2 and write to :pyattr:`out_html`."""
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template_name = (
            "weekly.html.j2" if isinstance(self.cfg, WeeklyConfig) else "daily.html.j2"
        )
        theme_css = (_ASSETS_DIR / "rv_theme.css").read_text(encoding="utf-8")
        ctx = _base_context(self.cfg, theme_css)
        ctx["cfg"] = self.cfg
        ctx["report_links"] = self._report_links
        ctx["pdf_embed_paths"] = self._pdf_embed_paths
        ctx["build_sources"] = _default_build_sources()
        if extra_context:
            ctx.update(extra_context)

        html = env.get_template(template_name).render(**ctx)
        self.out_html.parent.mkdir(parents=True, exist_ok=True)
        self.out_html.write_text(html, encoding="utf-8")
        log.info("html-rendered", path=str(self.out_html), kb=self.out_html.stat().st_size // 1024)

    def stage_audit(self) -> dict:
        """Run lightweight in-process checks; writes ``_audit.json`` and returns the dict."""
        html = self.out_html.read_text(encoding="utf-8") if self.out_html.exists() else ""
        sp_links = len(re.findall(r'href="https://[^"]*sharepoint\.com[^"]*"', html))
        report_id_mentions = len(re.findall(r'\b\d{4}\b', html))
        audit = {
            "anchor": self.anchor.isoformat(),
            "brief_type": self.brief_type,
            "html_path": str(self.out_html),
            "html_kb": self.out_html.stat().st_size // 1024 if self.out_html.exists() else 0,
            "charts": [p.name for p in self._charts],
            "pdf_pages": [p.name for p in self._pdfs],
            "report_links_resolved": len(self._report_links),
            "sharepoint_href_count": sp_links,
            "report_id_mentions": report_id_mentions,
            "checks": {
                "html_written":     self.out_html.exists(),
                "has_charts":       len(self._charts) > 0,
                "has_links":        sp_links > 0,
            },
        }
        audit_path(self.brief_type, self.anchor).write_text(
            json.dumps(audit, indent=2), encoding="utf-8"
        )
        return audit

    # ----------------------------------------------------------- run
    def run(self, *, cpi_consensus_mid: float | None = None) -> PipelineResult:
        conn = MSSQLConnector(self.settings)
        self.stage_assets()
        self.stage_links(conn)
        self.stage_charts(conn, cpi_consensus_mid=cpi_consensus_mid)
        self.stage_pdfs(conn)
        self.stage_render()
        audit = self.stage_audit()
        return PipelineResult(
            out_html=self.out_html,
            charts=self._charts,
            pdf_pages=self._pdfs,
            report_link_count=len(self._report_links),
            audit=audit,
        )


# ---------------------------------------------------------------- helpers
def _base_context(cfg: WeeklyConfig | DailyConfig, theme_css: str) -> dict:
    nav_items_weekly = [
        ("story", "Story"), ("calendar", "Calendar"), ("snapshot", "Markets"),
        ("uscpi", "US CPI"), ("ecb", "ECB"), ("boc", "BoC"),
        ("japan", "Japan"), ("china", "China"), ("korea", "Korea"),
        ("india", "India"), ("trades", "Trades"), ("risks", "Tail risks"),
    ]
    nav_items_daily = [
        ("today", "Today"), ("prints", "Prints"),
        ("yesterday", "Yesterday"), ("trades", "Trades"),
    ]
    is_weekly = isinstance(cfg, WeeklyConfig)
    section_offset = 3                                                # §0..§2 fixed; deep dives start at §3
    if is_weekly:
        # count deep + medium to compute trade/risks section numbering
        n_deep = len(cfg.deep_dives)
        n_med = len(cfg.medium_sections)
        trades_num = f"§{section_offset + n_deep + n_med}"
        risks_num = f"§{section_offset + n_deep + n_med + 1}"
    else:
        trades_num = "§N"
        risks_num = "§N+1"

    return {
        "page_title": cfg.title,
        "theme_css": theme_css,
        "brand_meta_strong": "Weekly Macro Preview" if is_weekly else "Daily Macro Brief",
        "brand_meta_sub": f"Internal · {cfg.period_date} · IMDR",
        "hero_title": cfg.title,
        "hero_subtitle_html": cfg.subtitle_html,
        "footer_date": cfg.period_date.isoformat(),
        "footer_brand": "IMDR Weekly Macro Preview" if is_weekly else "IMDR Daily Macro Brief",
        "nav_items": nav_items_weekly if is_weekly else nav_items_daily,
        "trades_section_num": trades_num,
        "risks_section_num": risks_num,
        "watch_section_num": "§N+2",
        "cb_section": None,                                           # caller may override
        "cross_asset_charts": [],                                     # caller may override
        "cross_asset_lead": "",
        "chart_captions": {},
        "reaction_captions": {},
        "supporting_chart_files": [],
        "supporting_captions": {},
    }


def _default_build_sources() -> list[str]:
    return [
        "Research: <code>research.dim_report</code> + <code>research.fact_chunk</code>",
        "Cross-asset: <code>fx.fact_fx_rate</code> · <code>econ.fact_indicator</code> · "
        "<code>equities.fact_vix</code> · <code>commodities.fact_spot</code> · "
        "<code>equities.fact_index_level</code>",
        "Bank PDFs sourced from local OneDrive sync of "
        "<code>TradeKnowledgeCore/ResearchData1/IMDR/</code>. PyMuPDF @ 180 DPI.",
        "Build via <code>python -m imdr.research.brief</code>.",
        "All numerical claims tied to source report IDs; bank quotes verbatim from <code>research.fact_chunk</code>.",
    ]


# ----------------------------------------------------------- convenience
def build_weekly(cfg_path: Path | str, *, settings: Settings | None = None) -> PipelineResult:
    cfg = load_config(cfg_path)
    if not isinstance(cfg, WeeklyConfig):
        raise ValueError(f"{cfg_path}: expected brief_type=weekly")
    return BriefPipeline(cfg, settings=settings).run()


def build_daily(cfg_path: Path | str, *, settings: Settings | None = None) -> PipelineResult:
    cfg = load_config(cfg_path)
    if not isinstance(cfg, DailyConfig):
        raise ValueError(f"{cfg_path}: expected brief_type=daily")
    return BriefPipeline(cfg, settings=settings).run()
