"""Thin CLI shell over `lseg_extractor.client` — no data logic lives here."""

from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

load_dotenv()

from lseg_extractor.config import get_settings
from lseg_extractor.session import session_scope

app = typer.Typer(
    name="lseg-extract",
    help="Extract data from the LSEG Data Platform (Workspace or LDPv2 auth).",
    no_args_is_help=True,
)


def _parse_list(value: str) -> list[str]:
    """Accept `A,B,C` or `@file.txt` (one entry per line)."""
    value = value.strip()
    if value.startswith("@"):
        path = Path(value[1:])
        if not path.exists():
            raise typer.BadParameter(f"file not found: {path}")
        items = [line.strip() for line in path.read_text().splitlines()]
        return [i for i in items if i and not i.startswith("#")]
    return [i.strip() for i in value.split(",") if i.strip()]


def _write_output(df, output: str | None, fmt: str, index: bool = True) -> None:
    import pandas as pd

    assert isinstance(df, pd.DataFrame)
    if not output:
        typer.echo(df.to_string())
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(path, index=index)
    elif fmt == "parquet":
        df.to_parquet(path, index=index)
    else:
        raise typer.BadParameter("--format must be csv or parquet")
    typer.echo(f"Wrote {len(df)} rows x {len(df.columns)} cols → {path}")


@app.command()
def snapshot(
    universe: Annotated[str, typer.Option(help="RICs, comma-separated or @file.txt")],
    fields: Annotated[str, typer.Option(help="Fields, e.g. 'BID,ASK,TR.Revenue'")],
    output: Annotated[str | None, typer.Option(help="Output file (else stdout)")] = None,
    format: Annotated[str, typer.Option(help="csv or parquet")] = "csv",
) -> None:
    """Pricing snapshot: ld.get_data(universe, fields)."""
    from lseg_extractor.client import get_snapshot

    settings = get_settings()
    try:
        with session_scope(settings):
            df = get_snapshot(_parse_list(universe), _parse_list(fields))
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, output, format)


@app.command()
def history(
    universe: Annotated[str, typer.Option(help="RICs, comma-separated or @file.txt")],
    interval: Annotated[str, typer.Option(help="e.g. 1D, 1W, 1M, PT1M")] = "1D",
    start: Annotated[str | None, typer.Option(help="ISO start, e.g. 2024-01-01")] = None,
    end: Annotated[str | None, typer.Option(help="ISO end")] = None,
    count: Annotated[int | None, typer.Option(help="Max points")] = None,
    output: Annotated[str | None, typer.Option()] = None,
    format: Annotated[str, typer.Option()] = "csv",
) -> None:
    """Historical series: ld.get_history(...)."""
    from lseg_extractor.client import get_history

    settings = get_settings()
    try:
        with session_scope(settings):
            df = get_history(
                _parse_list(universe),
                interval=interval,
                start=start,
                end=end,
                count=count,
            )
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, output, format)


@app.command()
def fundamentals(
    universe: Annotated[str, typer.Option(help="RICs, comma-separated or @file.txt")],
    fields: Annotated[str, typer.Option(help="e.g. 'TR.Revenue,TR.GrossProfit'")],
    output: Annotated[str | None, typer.Option()] = None,
    format: Annotated[str, typer.Option()] = "csv",
) -> None:
    """Fundamentals & reference data."""
    from lseg_extractor.client import get_fundamentals

    settings = get_settings()
    try:
        with session_scope(settings):
            df = get_fundamentals(_parse_list(universe), _parse_list(fields))
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, output, format)


@app.command()
def news(
    query: Annotated[str, typer.Option(help="RQL query, e.g. 'IBM.N AND Language:EN'")],
    count: Annotated[int, typer.Option()] = 10,
    output: Annotated[str | None, typer.Option()] = None,
    format: Annotated[str, typer.Option()] = "csv",
) -> None:
    """News headlines for a query."""
    from lseg_extractor.client import get_news_headlines

    settings = get_settings()
    try:
        with session_scope(settings):
            df = get_news_headlines(query, count=count)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, output, format)


@app.command()
def search(
    query: Annotated[str, typer.Option(help="Free-text search, e.g. 'Apple'")],
    top: Annotated[int, typer.Option()] = 10,
) -> None:
    """Discovery search → RICs and metadata (prints to stdout)."""
    from lseg_extractor.client import search_instruments

    settings = get_settings()
    try:
        with session_scope(settings):
            df = search_instruments(query, top=top)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, None, "csv")


@app.command()
def goodwill(
    preset: Annotated[str, typer.Option(help="French preset: cac40 or sbf120")] = "cac40",
    universe: Annotated[
        str | None, typer.Option(help="Override RICs, comma-separated or @file.txt")
    ] = None,
    years: Annotated[int, typer.Option(help="Annual fiscal periods (Frq=FY)")] = 5,
    fields: Annotated[
        str | None, typer.Option(help="Override TR fields, e.g. 'TR.Goodwill'")
    ] = None,
    currency: Annotated[str, typer.Option(help="Curn conversion target")] = "EUR",
    output: Annotated[str | None, typer.Option()] = None,
    format: Annotated[str, typer.Option()] = "csv",
) -> None:
    """Goodwill history for French companies (tidy long form)."""
    from lseg_extractor.goodwill import GOODWILL_FIELD, get_goodwill_history

    settings = get_settings()
    try:
        with session_scope(settings):
            df = get_goodwill_history(
                universe or preset,
                years=years,
                fields=_parse_list(fields) if fields else [GOODWILL_FIELD],
                currency=currency,
            )
    except (RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_output(df, output, format, index=False)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
