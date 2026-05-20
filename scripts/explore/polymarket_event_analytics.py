"""Analytic companion for Polymarket event snapshots.

Reads every snapshot under `data/cache/polymarket/snapshots/` and emits three
markdown reports under `data/cache/polymarket/analytics/`:

    (b) move_classification_{YYYY-MM-DD}.md
        Per-event transition classifications (BIG_MOVE / MOVE / DRIFT /
        FLAT / ILLIQUID / NEW / RESOLVED), grouped by theme.

    (c) theme_rollup_{YYYY-MM-DD}.md
        Per-snapshot, per-theme rollup: event count, total volume, mean /
        median modal probability, activity score (Σ|Δ modal|), hottest
        event.

    (a) event_stats.md
        Per-event quantitative behaviour (realised vol, autocorrelation at
        lag 1/2, modal-outcome dwell time, AM→PM intra-day range p90).
        Flagged `insufficient_data` for any event with < 7 observations.

Run:
    python -m scripts.explore.polymarket_event_analytics
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SNAPSHOT_ROOT = Path("data/cache/polymarket/snapshots")
REPORT_ROOT = Path("data/cache/polymarket/analytics")

# Classification thresholds on |Δ modal_yes|
T_BIG_MOVE = 0.10
T_MOVE = 0.05
T_DRIFT = 0.01

# Minimum observations for quantitative stats section
MIN_OBS_STATS = 7


@dataclass
class Observation:
    snapshot_ts: datetime
    snapshot_label: str
    event_id: int
    title: str
    theme: str
    total_volume: float
    market_count: int
    modal_question: str | None
    modal_yes: float | None
    runner_up_yes: float | None
    illiquid_flag: bool
    implied_prob_sum: float | None
    hhi: float | None


def load_panel() -> list[Observation]:
    """Walk all snapshot JSONL files into a flat observation list."""
    panel: list[Observation] = []
    if not SNAPSHOT_ROOT.exists():
        return panel
    for date_dir in sorted(SNAPSHOT_ROOT.iterdir()):
        if not date_dir.is_dir():
            continue
        for f in sorted(date_dir.glob("snapshot_*Z.jsonl")):
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    d = rec.get("derived") or {}
                    try:
                        ts = datetime.fromisoformat(rec["snapshot_ts"])
                    except (KeyError, ValueError):
                        continue
                    panel.append(Observation(
                        snapshot_ts=ts,
                        snapshot_label=rec.get("snapshot_label", ""),
                        event_id=int(rec.get("event_id") or 0),
                        title=rec.get("title") or "",
                        theme=rec.get("theme") or "",
                        total_volume=float(rec.get("total_volume") or 0),
                        market_count=int(rec.get("market_count") or 0),
                        modal_question=d.get("modal_question"),
                        modal_yes=d.get("modal_yes"),
                        runner_up_yes=d.get("runner_up_yes"),
                        illiquid_flag=bool(d.get("illiquid_flag")),
                        implied_prob_sum=d.get("implied_prob_sum"),
                        hhi=d.get("hhi"),
                    ))
    return panel


# ---------------------------------------------------------------------------
# (b) Move classification
# ---------------------------------------------------------------------------

def classify(prev: Observation, curr: Observation) -> tuple[str, float | None]:
    if prev.illiquid_flag or curr.illiquid_flag:
        return ("ILLIQUID", None)
    if prev.modal_yes is None or curr.modal_yes is None:
        return ("ILLIQUID", None)
    delta = curr.modal_yes - prev.modal_yes
    modal_changed = (
        prev.modal_question is not None
        and curr.modal_question is not None
        and prev.modal_question != curr.modal_question
    )
    abs_d = abs(delta)
    if modal_changed or abs_d >= T_BIG_MOVE:
        return ("BIG_MOVE", delta)
    if abs_d >= T_MOVE:
        return ("MOVE", delta)
    if abs_d >= T_DRIFT:
        return ("DRIFT", delta)
    return ("FLAT", delta)


def _trans_cell(t: dict) -> str:
    cls = t["class"]
    if t.get("delta") is None:
        return cls
    return f"{cls}({t['delta']*100:+.1f}pp)"


def write_move_classification(panel: list[Observation], out_dir: Path) -> Path:
    by_event: dict[int, list[Observation]] = defaultdict(list)
    for o in panel:
        by_event[o.event_id].append(o)
    for obs_list in by_event.values():
        obs_list.sort(key=lambda o: o.snapshot_ts)

    all_ts = sorted({o.snapshot_ts for o in panel})
    records: list[dict] = []
    for eid, obs_list in by_event.items():
        transitions: list[dict] = []
        # Classify each consecutive pair
        for i in range(1, len(obs_list)):
            cls, delta = classify(obs_list[i - 1], obs_list[i])
            transitions.append({
                "from_ts": obs_list[i - 1].snapshot_ts,
                "to_ts": obs_list[i].snapshot_ts,
                "class": cls,
                "delta": delta,
                "prev_yes": obs_list[i - 1].modal_yes,
                "curr_yes": obs_list[i].modal_yes,
            })
        # NEW if first observation isn't the earliest panel snapshot
        if all_ts and obs_list[0].snapshot_ts != all_ts[0]:
            transitions.insert(0, {
                "from_ts": None, "to_ts": obs_list[0].snapshot_ts,
                "class": "NEW", "delta": None,
                "prev_yes": None, "curr_yes": obs_list[0].modal_yes,
            })
        # RESOLVED if last observation isn't the latest panel snapshot
        if all_ts and obs_list[-1].snapshot_ts != all_ts[-1]:
            transitions.append({
                "from_ts": obs_list[-1].snapshot_ts, "to_ts": None,
                "class": "RESOLVED", "delta": None,
                "prev_yes": obs_list[-1].modal_yes, "curr_yes": None,
            })

        counts: dict[str, int] = defaultdict(int)
        for t in transitions:
            counts[t["class"]] += 1
        real_deltas = [t["delta"] for t in transitions if t.get("delta") is not None]
        max_abs = max((abs(d) for d in real_deltas), default=0.0)
        records.append({
            "event_id": eid,
            "title": obs_list[-1].title,
            "theme": obs_list[-1].theme,
            "total_volume": obs_list[-1].total_volume,
            "transitions": transitions,
            "counts": dict(counts),
            "max_abs_delta": max_abs,
            "n_snapshots": len(obs_list),
        })

    now = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"move_classification_{now.strftime('%Y-%m-%d')}.md"

    lines: list[str] = []
    lines.append("# Polymarket Event Move Classification")
    lines.append(
        f"_Generated {now.isoformat(timespec='seconds')} · "
        f"panel={len(all_ts)} snapshots · {len(records)} events_\n"
    )
    if all_ts:
        lines.append(
            f"**Snapshot window:** `{all_ts[0].isoformat()}` → `{all_ts[-1].isoformat()}`\n"
        )
    lines.append(
        f"**Thresholds:** BIG_MOVE ≥ {T_BIG_MOVE*100:.0f}pp · "
        f"MOVE ≥ {T_MOVE*100:.0f}pp · DRIFT ≥ {T_DRIFT*100:.0f}pp · "
        f"FLAT < {T_DRIFT*100:.0f}pp · ILLIQUID when spread > 20pp on modal market\n"
    )

    total_counts: dict[str, int] = defaultdict(int)
    for r in records:
        for k, v in r["counts"].items():
            total_counts[k] += v
    lines.append("## Overall transition counts")
    for cls in ("BIG_MOVE", "MOVE", "DRIFT", "FLAT", "ILLIQUID", "NEW", "RESOLVED"):
        lines.append(f"- **{cls}**: {total_counts.get(cls, 0)}")
    lines.append("")

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_theme[r["theme"]].append(r)
    theme_order = sorted(
        by_theme.keys(),
        key=lambda t: (
            -sum(r["counts"].get("BIG_MOVE", 0) for r in by_theme[t]),
            -sum(r["counts"].get("MOVE", 0) for r in by_theme[t]),
        ),
    )

    for theme in theme_order:
        items = sorted(
            by_theme[theme],
            key=lambda r: (
                -r["counts"].get("BIG_MOVE", 0),
                -r["counts"].get("MOVE", 0),
                -r["max_abs_delta"],
                -r["total_volume"],
            ),
        )
        lines.append(f"## Theme: {theme}  _(n={len(items)})_\n")
        lines.append(
            "| event_id | title | transitions | max \\|Δ\\| | n_snap | counts |"
        )
        lines.append("|--:|---|---|--:|--:|---|")
        for r in items:
            title = r["title"][:70].replace("|", "\\|")
            trans_s = " → ".join(_trans_cell(t) for t in r["transitions"])
            counts_s = ", ".join(f"{k}={v}" for k, v in sorted(r["counts"].items()))
            max_abs_s = f"{r['max_abs_delta']*100:.1f}pp"
            lines.append(
                f"| {r['event_id']} | {title} | {trans_s} | {max_abs_s} "
                f"| {r['n_snapshots']} | {counts_s} |"
            )
        lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


# ---------------------------------------------------------------------------
# (c) Theme rollup
# ---------------------------------------------------------------------------

def write_theme_rollup(panel: list[Observation], out_dir: Path) -> Path:
    by_ts_theme: dict[tuple[datetime, str], list[Observation]] = defaultdict(list)
    for o in panel:
        by_ts_theme[(o.snapshot_ts, o.theme)].append(o)
    by_event_ts: dict[tuple[int, datetime], Observation] = {
        (o.event_id, o.snapshot_ts): o for o in panel
    }
    all_ts = sorted({o.snapshot_ts for o in panel})

    now = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"theme_rollup_{now.strftime('%Y-%m-%d')}.md"

    lines: list[str] = []
    lines.append("# Polymarket Theme Rollup")
    lines.append(
        f"_Generated {now.isoformat(timespec='seconds')} · panel={len(all_ts)} snapshots_\n"
    )

    for idx, ts in enumerate(all_ts):
        prev_ts = all_ts[idx - 1] if idx > 0 else None
        lines.append(f"## Snapshot `{ts.isoformat()}`")
        if prev_ts is not None:
            lines.append(f"_previous: `{prev_ts.isoformat()}`_\n")
        else:
            lines.append("_first snapshot — activity column omitted_\n")
        lines.append(
            "| theme | events | total_volume | mean_modal | median_modal | "
            "activity (Σ\\|Δ\\|) | hottest event |"
        )
        lines.append("|---|--:|--:|--:|--:|--:|---|")
        themes_here = sorted({t for (t_ts, t) in by_ts_theme.keys() if t_ts == ts})
        for theme in themes_here:
            items = by_ts_theme[(ts, theme)]
            modals = [o.modal_yes for o in items if o.modal_yes is not None]
            total_vol = sum(o.total_volume for o in items)
            mean_m = mean(modals) if modals else None
            median_m = median(modals) if modals else None

            activity = 0.0
            hottest = None
            hottest_mag = 0.0
            if prev_ts is not None:
                for o in items:
                    prev = by_event_ts.get((o.event_id, prev_ts))
                    if prev is None or prev.modal_yes is None or o.modal_yes is None:
                        continue
                    d = abs(o.modal_yes - prev.modal_yes)
                    activity += d
                    if d > hottest_mag:
                        hottest_mag = d
                        hottest = (o.title, o.modal_yes - prev.modal_yes)

            mean_s = f"{mean_m:.3f}" if mean_m is not None else "-"
            median_s = f"{median_m:.3f}" if median_m is not None else "-"
            act_s = f"{activity*100:.1f}pp" if prev_ts is not None else "-"
            if hottest is not None:
                h_title = hottest[0][:40].replace("|", "\\|")
                hottest_s = f"{h_title} ({hottest[1]*100:+.1f}pp)"
            else:
                hottest_s = "-"
            lines.append(
                f"| {theme} | {len(items)} | ${total_vol:,.0f} | {mean_s} | {median_s} "
                f"| {act_s} | {hottest_s} |"
            )
        lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


# ---------------------------------------------------------------------------
# (a) Event statistics
# ---------------------------------------------------------------------------

def _autocorr(series: list[float], lag: int) -> float | None:
    if len(series) <= lag + 1:
        return None
    m = mean(series)
    num = sum((series[i] - m) * (series[i - lag] - m) for i in range(lag, len(series)))
    den = sum((x - m) ** 2 for x in series)
    return num / den if den > 0 else None


def write_event_stats(panel: list[Observation], out_dir: Path) -> Path:
    by_event: dict[int, list[Observation]] = defaultdict(list)
    for o in panel:
        by_event[o.event_id].append(o)
    for obs_list in by_event.values():
        obs_list.sort(key=lambda o: o.snapshot_ts)

    now = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "event_stats.md"

    lines: list[str] = []
    lines.append("# Polymarket Event Statistics")
    lines.append(f"_Generated {now.isoformat(timespec='seconds')}_\n")
    lines.append(
        f"Stats require ≥{MIN_OBS_STATS} snapshots per event to be meaningful. "
        f"Events with fewer observations are marked `insufficient_data`.\n"
    )
    lines.append(
        "| event_id | title | theme | n_obs | realised_vol | ac1 | ac2 "
        "| modal_dwell | am_pm_range_p90 | status |"
    )
    lines.append("|--:|---|---|--:|--:|--:|--:|--:|--:|---|")

    events_sorted = sorted(
        by_event.items(), key=lambda kv: (-len(kv[1]), kv[0])
    )
    for eid, obs_list in events_sorted:
        n = len(obs_list)
        title = obs_list[-1].title[:60].replace("|", "\\|")
        theme = obs_list[-1].theme
        modal_series = [o.modal_yes for o in obs_list if o.modal_yes is not None]

        if n < MIN_OBS_STATS or len(modal_series) < 3:
            lines.append(
                f"| {eid} | {title} | {theme} | {n} | - | - | - | - | - "
                f"| insufficient_data |"
            )
            continue

        diffs = [modal_series[i] - modal_series[i - 1] for i in range(1, len(modal_series))]
        vol = pstdev(diffs) if len(diffs) >= 2 else None
        ac1 = _autocorr(modal_series, 1)
        ac2 = _autocorr(modal_series, 2)

        questions = [o.modal_question for o in obs_list]
        dwell = 0
        if questions and questions[-1] is not None:
            dwell = 1
            for i in range(len(questions) - 2, -1, -1):
                if questions[i] == questions[-1]:
                    dwell += 1
                else:
                    break

        by_date: dict[str, dict[str, float]] = defaultdict(dict)
        for o in obs_list:
            if o.modal_yes is None:
                continue
            d = o.snapshot_ts.date().isoformat()
            by_date[d][o.snapshot_label] = o.modal_yes
        ranges = sorted(
            abs(v["PM"] - v["AM"]) for v in by_date.values()
            if "AM" in v and "PM" in v
        )
        p90 = ranges[int(0.9 * (len(ranges) - 1))] if ranges else None

        def fmt(x: float | None) -> str:
            return f"{x:.4f}" if x is not None else "-"

        lines.append(
            f"| {eid} | {title} | {theme} | {n} | {fmt(vol)} | {fmt(ac1)} "
            f"| {fmt(ac2)} | {dwell} | {fmt(p90)} | ok |"
        )

    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    panel = load_panel()
    print(f"Loaded {len(panel)} observations from {SNAPSHOT_ROOT}")
    if not panel:
        print("  No snapshots found — run polymarket_event_snapshot first.")
        return
    all_ts = sorted({o.snapshot_ts for o in panel})
    all_events = {o.event_id for o in panel}
    print(f"  {len(all_ts)} snapshot timestamps")
    print(f"  {len(all_events)} distinct events")
    print(f"  Window: {all_ts[0].isoformat()} → {all_ts[-1].isoformat()}")

    move_file = write_move_classification(panel, REPORT_ROOT)
    print(f"  wrote  {move_file}")
    rollup_file = write_theme_rollup(panel, REPORT_ROOT)
    print(f"  wrote  {rollup_file}")
    stats_file = write_event_stats(panel, REPORT_ROOT)
    print(f"  wrote  {stats_file}")


if __name__ == "__main__":
    main()
