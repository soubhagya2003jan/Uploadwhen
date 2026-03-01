"""Channel upload-consistency analytics."""

from __future__ import annotations
import math
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def _sorted_dates(records: list[dict]) -> list[datetime]:
    """Extract and sort UTC datetimes from records."""
    dates = [r["datetime_utc"] for r in records if r.get("datetime_utc")]
    dates.sort()
    return dates


def _gaps_in_days(dates: list[datetime]) -> list[float]:
    """Compute inter-upload gaps in days."""
    return [(dates[i + 1] - dates[i]).total_seconds() / 86400
            for i in range(len(dates) - 1)]


def _median(values: list[float]) -> float:
    n = len(values)
    s = sorted(values)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _std_dev(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _consistency_score(std: float, mean: float) -> float:
    """0–10 score using 10 / (1 + CV). Smoother curve that never hits zero."""
    if mean == 0:
        return 0.0
    cv = std / mean
    return round(10 / (1 + cv), 1)


def _format_gap(days: float) -> str:
    """Show hours when gap < 1 day, otherwise days."""
    if days < 1:
        hours = days * 24
        return f"{round(hours, 1)} hours"
    return f"{round(days, 2)} days"


def analyze(records: list[dict]) -> dict | None:
    """Compute upload-gap statistics. Returns None if < 2 dated videos."""
    dates = _sorted_dates(records)
    if len(dates) < 2:
        return None

    gaps     = _gaps_in_days(dates)
    avg      = sum(gaps) / len(gaps)
    med      = _median(gaps)
    shortest = min(gaps)
    longest  = max(gaps)
    std      = _std_dev(gaps, avg)
    score    = _consistency_score(std, avg)

    return {
        "channel":           records[0].get("channel", "Unknown"),
        "total_videos":      len(dates),
        "avg_gap":           _format_gap(avg),
        "median_gap":        _format_gap(med),
        "shortest_gap":      _format_gap(shortest),
        "longest_gap":       _format_gap(longest),
        "std_dev":           _format_gap(std),
        "consistency_score": score,
    }


def _score_color(score: float) -> str:
    """Pick a Rich color based on score (0–10)."""
    if score >= 7.5:
        return "green"
    if score >= 4.0:
        return "yellow"
    return "red"


def print_analysis(stats: dict | None) -> None:
    """Render analysis stats as a Rich panel."""
    if stats is None:
        console.print("\n  [yellow]![/yellow] Need at least 2 dated videos for analytics.\n")
        return

    color = _score_color(stats["consistency_score"])

    table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    table.add_column("Metric", style="bold", width=26)
    table.add_column("Value", justify="right")

    table.add_row("Videos analysed",   str(stats["total_videos"]))
    table.add_row("Avg gap",           stats["avg_gap"])
    table.add_row("Median gap",        stats["median_gap"])
    table.add_row("Shortest gap",      stats["shortest_gap"])
    table.add_row("Longest gap",       stats["longest_gap"])
    table.add_row("Std deviation",     stats["std_dev"])
    table.add_row("Consistency score",
                  f"[{color} bold]{stats['consistency_score']} / 10[/{color} bold]")

    console.print()
    console.print(Panel(
        table,
        title=f"[bold]Upload Consistency — {stats['channel']}[/bold]",
        border_style=color,
        expand=False,
    ))
