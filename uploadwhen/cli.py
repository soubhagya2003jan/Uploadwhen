"""CLI interface for uploadwhen."""

import sys
import json
import csv
import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from uploadwhen import __version__
from uploadwhen.fetcher import fetch_video, fetch_channel_videos, _is_channel_url
from uploadwhen.analyzer import analyze, print_analysis

console = Console()

# Banner
BANNER = """[bold cyan]
  ██╗   ██╗██████╗ ██╗      ██████╗  █████╗ ██████╗ ██╗    ██╗██╗  ██╗███████╗███╗   ██╗
  ██║   ██║██╔══██╗██║     ██╔═══██╗██╔══██╗██╔══██╗██║    ██║██║  ██║██╔════╝████╗  ██║
  ██║   ██║██████╔╝██║     ██║   ██║███████║██║  ██║██║ █╗ ██║███████║█████╗  ██╔██╗ ██║
  ██║   ██║██╔═══╝ ██║     ██║   ██║██╔══██║██║  ██║██║███╗██║██╔══██║██╔══╝  ██║╚██╗██║
  ╚██████╔╝██║     ███████╗╚██████╔╝██║  ██║██████╔╝╚███╔███╔╝██║  ██║███████╗██║ ╚████║
   ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝
[/bold cyan][dim]  Find out exactly when any YouTube video was uploaded.
  v""" + __version__ + "[/dim]"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uploadwhen",
        description=(
            "uploadwhen — Find out exactly when a YouTube video was uploaded.\n"
            "Supports video URLs and channel-level upload consistency analysis.\n"
            "Times shown in IST, US/ET, AU/AEST, JP/JST, and UTC."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            '  uploadwhen "https://www.youtube.com/watch?v=dQw4w9WgXcQ"\n'
            "\n"
            "Tip: Wrap URLs in quotes so your shell doesn't break on & characters."
        ),
    )

    parser.add_argument("url", nargs="?", metavar="URL",
                        help="A YouTube video or channel URL.")
    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", dest="export_json",
                        help="Export results to uploadwhen_results.json")
    parser.add_argument("--csv", action="store_true", dest="export_csv",
                        help="Export results to uploadwhen_results.csv")
    parser.add_argument("--analyze", action="store_true",
                        help="Fetch recent uploads from the channel and show consistency stats.")
    parser.add_argument("-n", "--count", type=int, default=10, metavar="N",
                        help="Number of uploads to analyze (default: 10).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show detailed yt-dlp output.")
    return parser


# Display —————————————————————————————————————————————————————————————————

def _print_video(rec: dict) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1),
                  expand=False, show_edge=False)
    table.add_column("Key", style="bold", width=14)
    table.add_column("Value")

    table.add_row("Channel",       rec["channel"])
    table.add_row("Date",          rec["date"])
    table.add_row("Time (IST)",    f"[green]{rec['time_ist']}[/green]  [dim]India[/dim]")
    table.add_row("Time (ET)",     f"{rec['time_us']}   [dim]US / New York[/dim]")
    table.add_row("Time (AEST)",   f"{rec['time_au']}  [dim]Australia / Sydney[/dim]")
    table.add_row("Time (JST)",    f"{rec['time_jp']}   [dim]Japan / Tokyo[/dim]")
    table.add_row("Time (UTC)",    f"[dim]{rec['time_utc']}[/dim]")
    table.add_row("Duration",      rec["duration"])
    table.add_row("URL",           f"[dim]{rec['video_url']}[/dim]")

    console.print(Panel(table, title=f"[bold]{rec['title']}[/bold]",
                        border_style="cyan", expand=False))


def _print_channel_videos(records: list[dict]) -> None:
    """Render a compact table of channel uploads."""
    table = Table(title="Recent Uploads", box=box.ROUNDED,
                  border_style="cyan", header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Date", width=20)
    table.add_column("Time (IST)", style="green", width=14)
    table.add_column("Title", max_width=55, no_wrap=True)

    for i, rec in enumerate(records, start=1):
        table.add_row(str(i), rec["date"], rec["time_ist"],
                      Text(rec["title"], overflow="ellipsis"))

    console.print(table)


# Export ——————————————————————————————————————————————————————————————————

EXPORT_FIELDS = ["title", "channel", "date", "time_ist", "time_us",
                 "time_au", "time_jp", "time_utc", "duration",
                 "video_url", "video_id"]


def _export_json(records: list[dict], path: Path) -> None:
    clean = [{k: r[k] for k in EXPORT_FIELDS} for r in records]
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\n  [green]✓[/green] JSON saved → [bold]{path}[/bold]")


def _export_csv(records: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r[k] for k in EXPORT_FIELDS})
    console.print(f"\n  [green]✓[/green] CSV  saved → [bold]{path}[/bold]")


# Entry point —————————————————————————————————————————————————————————————

def main(argv: list[str] | None = None) -> None:
    try:
        _run(argv)
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted.[/dim]")
        sys.exit(0)


def _run(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.url:
        console.print(BANNER)
        parser.print_help()
        sys.exit(0)

    console.print(BANNER)
    url = args.url.strip()
    is_channel = _is_channel_url(url)

    # Channel URL path
    if is_channel:
        if not args.analyze:
            console.print(
                f"\n  [yellow]![/yellow] That looks like a channel URL. "
                f"Add [bold]--analyze[/bold] to see upload consistency stats.\n"
            )
            sys.exit(0)

        console.print(f"\n  [cyan]⟳[/cyan] Fetching last [bold]{args.count}[/bold] uploads from channel…\n")
        records = fetch_channel_videos(url, count=args.count, verbose=args.verbose)

        if not records:
            console.print("  [red]✗[/red] Could not retrieve videos from this channel.")
            sys.exit(1)

        _print_channel_videos(records)
        print_analysis(analyze(records))

        if args.export_json:
            _export_json(records, Path.cwd() / "uploadwhen_results.json")
        if args.export_csv:
            _export_csv(records, Path.cwd() / "uploadwhen_results.csv")

        console.print()
        return

    # Single video URL path
    console.print(f"\n  [cyan]⟳[/cyan] Fetching video info…\n")
    video = fetch_video(url, verbose=args.verbose)

    if not video:
        console.print("  [red]✗[/red] Could not retrieve video info. Check the URL.")
        sys.exit(1)

    _print_video(video)

    if args.export_json:
        _export_json([video], Path.cwd() / "uploadwhen_results.json")
    if args.export_csv:
        _export_csv([video], Path.cwd() / "uploadwhen_results.csv")

    # Auto-detect channel and run analysis
    if args.analyze:
        channel_url = video.get("channel_url")
        if not channel_url:
            console.print("\n  [yellow]![/yellow] Could not determine channel URL from this video.\n")
        else:
            channel = video.get("channel", "this channel")
            console.print(
                f"\n  [cyan]⟳[/cyan] Fetching last [bold]{args.count}[/bold] uploads "
                f"from [bold]{channel}[/bold]…\n"
            )
            records = fetch_channel_videos(channel_url, count=args.count, verbose=args.verbose)

            if not records:
                console.print("  [red]✗[/red] Could not retrieve channel videos.")
            else:
                _print_channel_videos(records)
                print_analysis(analyze(records))

    console.print()
