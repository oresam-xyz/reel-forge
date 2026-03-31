"""ReelForge CLI — main commands using Typer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="reelforge", help="AI-powered faceless short-form video generator.")
brand_app = typer.Typer(help="Brand identity management.")
app.add_typer(brand_app, name="brand")

console = Console()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _resolve_dirs(config_path: Path) -> tuple:
    """Load config and resolve brands/projects directories."""
    from reelforge.config import load_config
    config = load_config(config_path)
    brands_dir = Path(config.brands_dir).resolve()
    projects_dir = Path(config.projects_dir).resolve()
    brands_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    return config, brands_dir, projects_dir


def _auto_approve_review(project, brand, providers) -> None:
    """Non-interactive review — just approve the plan."""
    plan = project.load_plan()
    plan.approved = True
    project.save_plan(plan)
    console.print("[green]Plan auto-approved.[/]")


@app.command()
def new(
    topic: str = typer.Option(..., "--topic", "-t", help="The video topic"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name to use"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Auto-approve the plan without interactive review"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Create a new video project and run the pipeline."""
    _setup_logging(verbose)

    from reelforge.agent.brand import BrandIdentity
    from reelforge.agent.project import Project
    from reelforge.agent.runner import instantiate_providers, run_pipeline

    app_config, brands_dir, projects_dir = _resolve_dirs(config)

    # Load brand
    try:
        brand_identity = BrandIdentity.load(brands_dir, brand)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    # Create project
    project = Project.create(projects_dir, brand, topic)
    console.print(f"[green]Created project:[/] {project.state.project_id}")
    console.print(f"  Topic: {topic}")
    console.print(f"  Brand: {brand}")
    console.print(f"  Path: {project.project_dir}")
    console.print()

    # Instantiate providers and run
    try:
        providers = instantiate_providers(app_config)
    except (ValueError, ImportError) as e:
        console.print(f"[red]Provider error:[/] {e}")
        raise typer.Exit(1)

    phase_overrides = {"review": _auto_approve_review} if auto_approve else None

    try:
        run_pipeline(project, brand_identity, providers, phase_overrides=phase_overrides)
        console.print(f"\n[bold green]Pipeline complete![/] Output: {project.output_path}")
    except Exception as e:
        console.print(f"\n[red]Pipeline failed at phase '{project.get_current_phase()}':[/] {e}")
        console.print("[yellow]Fix the issue and run 'reelforge resume' to continue.[/]")
        raise typer.Exit(1)
    finally:
        if hasattr(providers.llm, "close"):
            providers.llm.close()


@app.command()
def resume(
    project: str = typer.Option(..., "--project", "-p", help="Project ID or directory path"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Auto-approve the plan without interactive review"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Resume an existing project from where it left off."""
    _setup_logging(verbose)

    from reelforge.agent.brand import BrandIdentity
    from reelforge.agent.project import Project
    from reelforge.agent.runner import instantiate_providers, run_pipeline

    app_config, brands_dir, projects_dir = _resolve_dirs(config)

    # Resolve project path
    project_dir = Path(project)
    if not project_dir.is_absolute():
        project_dir = projects_dir / project

    try:
        proj = Project.load(project_dir)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    console.print(f"[green]Resuming project:[/] {proj.state.project_id}")
    console.print(f"  Current phase: {proj.get_current_phase()}")

    # Load brand
    try:
        brand_identity = BrandIdentity.load(brands_dir, proj.state.brand)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    # Instantiate providers and run
    try:
        providers = instantiate_providers(app_config)
    except (ValueError, ImportError) as e:
        console.print(f"[red]Provider error:[/] {e}")
        raise typer.Exit(1)

    phase_overrides = {"review": _auto_approve_review} if auto_approve else None

    try:
        run_pipeline(proj, brand_identity, providers, phase_overrides=phase_overrides)
        console.print(f"\n[bold green]Pipeline complete![/] Output: {proj.output_path}")
    except Exception as e:
        console.print(f"\n[red]Pipeline failed at phase '{proj.get_current_phase()}':[/] {e}")
        console.print("[yellow]Fix the issue and run 'reelforge resume' again.[/]")
        raise typer.Exit(1)
    finally:
        if hasattr(providers.llm, "close"):
            providers.llm.close()


@app.command()
def status(
    project: str = typer.Option(..., "--project", "-p", help="Project ID or directory path"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    """Show the status of a project's phases."""
    from reelforge.agent.project import Project
    from reelforge.config import load_config

    app_config = load_config(config)
    projects_dir = Path(app_config.projects_dir).resolve()

    project_dir = Path(project)
    if not project_dir.is_absolute():
        project_dir = projects_dir / project

    try:
        proj = Project.load(project_dir)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Project:[/] {proj.state.project_id}")
    console.print(f"[bold]Topic:[/] {proj.state.topic}")
    console.print(f"[bold]Brand:[/] {proj.state.brand}")
    console.print(f"[bold]Created:[/] {proj.state.created_at}")
    console.print()

    table = Table(title="Phase Status")
    table.add_column("Phase", style="bold")
    table.add_column("Status")
    table.add_column("Completed At")
    table.add_column("Error")

    status_styles = {
        "pending": "dim",
        "complete": "green",
        "failed": "red",
    }

    for phase_name, info in proj.state.phases.items():
        style = status_styles.get(info.status.value, "")
        table.add_row(
            phase_name,
            f"[{style}]{info.status.value}[/]",
            info.completed_at or "",
            info.error or "",
        )

    console.print(table)


@brand_app.command("create")
def brand_create(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    """Create a new brand identity using the interactive wizard."""
    from reelforge.cli.brand_wizard import run_wizard
    from reelforge.config import load_config

    app_config = load_config(config)
    brands_dir = Path(app_config.brands_dir).resolve()
    brands_dir.mkdir(parents=True, exist_ok=True)

    run_wizard(brands_dir)


@brand_app.command("list")
def brand_list(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    """List all available brands."""
    from reelforge.agent.brand import BrandIdentity
    from reelforge.config import load_config

    app_config = load_config(config)
    brands_dir = Path(app_config.brands_dir).resolve()

    brands = BrandIdentity.list_brands(brands_dir)
    if not brands:
        console.print("[yellow]No brands found.[/] Run 'reelforge brand create' to make one.")
        return

    table = Table(title="Brands")
    table.add_column("Name", style="bold")
    table.add_column("Character")

    for name, character in brands:
        table.add_row(name, character)

    console.print(table)


@app.command()
def split(
    project: str = typer.Option("", "--project", "-p", help="Project ID — splits that project's output.mp4"),
    file: Path = typer.Option(None, "--file", "-f", help="Path to any video file to split"),
    max_size: float = typer.Option(10.0, "--max-size", "-s", help="Max file size per part in MB"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    """Split a video into parts for WhatsApp or other size-limited platforms."""
    from reelforge.providers.renderer.split import split_video

    if file:
        video_path = str(file)
    elif project:
        _, _, projects_dir = _resolve_dirs(config)
        video_path = str(projects_dir / project / "output.mp4")
    else:
        console.print("[red]Error:[/] Provide --project or --file")
        raise typer.Exit(1)

    if not Path(video_path).exists():
        console.print(f"[red]Error:[/] Video not found: {video_path}")
        raise typer.Exit(1)

    parts = split_video(video_path, max_size_mb=max_size)

    if len(parts) == 1:
        console.print(f"[green]Video is already under {max_size:.0f} MB — no split needed.[/]")
    else:
        console.print(f"[green]Split into {len(parts)} parts:[/]")
        for p in parts:
            size_mb = Path(p).stat().st_size / (1024 * 1024)
            console.print(f"  {p} ({size_mb:.1f} MB)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
