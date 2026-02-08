"""Demo command - run a pre-canned session to show sift in action.

This command demonstrates the full sift lifecycle without requiring an API key.
It uses pre-generated extraction data to bypass AI, giving new users an
immediate "aha moment".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from sift.error_handler import handle_errors
from sift.ui import console, format_next_step, section_divider, step_header, success_panel

if TYPE_CHECKING:
    from sift.models import Session

app = typer.Typer(no_args_is_help=False)

# ── Pre-canned demo data ──

DEMO_SESSION_NAME = "demo-session"

DEMO_TEXT_PHASE_1 = (
    "We are building a customer onboarding system. The main steps are:\n"
    "1. Customer fills out an intake form on the website\n"
    "2. Sales team reviews the form and schedules a discovery call\n"
    "3. After the call, an account manager creates their workspace\n"
    "4. The customer gets an email with login credentials and a welcome guide\n\n"
    "The biggest pain point is step 3 - it takes 2-3 days because the account\n"
    "manager has to manually configure each workspace. We want to automate this."
)

DEMO_TEXT_PHASE_2 = (
    "After reviewing the initial description, a few things to add:\n"
    "- The intake form also collects billing preferences\n"
    "- Step 2 should include a needs assessment, not just scheduling\n"
    "- We should consider a self-service option for smaller customers\n"
    "- The welcome guide should be personalized based on the discovery call"
)

DEMO_EXTRACTION_PHASE_1 = {
    "key_points": [
        "Customer onboarding has 4 main steps: intake form, discovery call, workspace creation, credentials email",
        "Manual workspace configuration is the bottleneck (2-3 days)",
        "Goal is to automate workspace creation",
        "Current process requires account manager involvement for every customer",
    ],
    "summary": (
        "A customer onboarding system with a manual workspace creation bottleneck "
        "that needs automation to reduce the 2-3 day delay."
    ),
}

DEMO_EXTRACTION_PHASE_2 = {
    "additions": [
        "Intake form also collects billing preferences",
        "Discovery call should include needs assessment",
        "Self-service option needed for smaller customers",
        "Welcome guide should be personalized",
    ],
    "overall_impression": (
        "The onboarding process has clear automation opportunities, especially "
        "around workspace provisioning and personalized onboarding content."
    ),
}


@app.callback(invoke_without_command=True)
@handle_errors
def demo(
    keep: bool = typer.Option(False, "--keep", help="Keep the demo session after completion"),
) -> None:
    """Run a guided demo of sift with sample data (no API key needed)."""
    import shutil

    from sift.core.build_service import BuildService
    from sift.core.session_service import SessionService
    from sift.models import SESSIONS_DIR, Session

    console.print()
    console.print(
        "[bold cyan]Welcome to the sift demo![/bold cyan]\n"
        "[dim]This walks through a complete session lifecycle with sample data.\n"
        "No API key is needed - extraction data is pre-generated.[/dim]\n"
    )

    # Step 1: Create session
    step_header(1, 5, "Create Session", "Using the hello-world template")

    svc = SessionService()

    # Clean up any existing demo session
    demo_dir = SESSIONS_DIR / DEMO_SESSION_NAME
    if demo_dir.exists():
        shutil.rmtree(demo_dir)

    try:
        detail = svc.create_session("hello-world", DEMO_SESSION_NAME)
    except Exception:
        console.print(
            "[red]Could not find hello-world template. "
            "Run 'sift template list' to check available templates.[/red]"
        )
        raise typer.Exit(1)

    console.print(
        f"  Created session [bold cyan]{detail.name}[/bold cyan] with {detail.total_phases} phases"
    )

    # Step 2: Capture text for phase 1
    section_divider()
    step_header(2, 5, "Capture Phase 1: Describe", "Feeding in sample text")

    session = Session.load(DEMO_SESSION_NAME)
    _write_transcript(session, "describe", DEMO_TEXT_PHASE_1)
    console.print(f"  Captured {len(DEMO_TEXT_PHASE_1)} characters of sample text")

    # Step 3: Extract phase 1 (pre-generated)
    section_divider()
    step_header(3, 5, "Extract Phase 1", "AI extraction (pre-generated for demo)")

    _write_extraction(session, "describe", DEMO_EXTRACTION_PHASE_1)

    console.print("  Extracted fields:")
    for key, value in DEMO_EXTRACTION_PHASE_1.items():
        if isinstance(value, list):
            console.print(f"    [cyan]{key}[/cyan]: {len(value)} items")
        else:
            preview = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            console.print(f"    [cyan]{key}[/cyan]: {preview}")

    # Step 4: Capture + extract phase 2
    section_divider()
    step_header(4, 5, "Phase 2: Reflect and Add", "Capture + extract in one step")

    _write_transcript(session, "reflect", DEMO_TEXT_PHASE_2)
    _write_extraction(session, "reflect", DEMO_EXTRACTION_PHASE_2)

    console.print(f"  Captured {len(DEMO_TEXT_PHASE_2)} characters")
    console.print(f"  Extracted {len(DEMO_EXTRACTION_PHASE_2)} fields")

    # Step 5: Build outputs
    section_divider()
    step_header(5, 5, "Build Outputs", "Generating YAML config and markdown summary")

    build_svc = BuildService()
    build_result = build_svc.generate_outputs(DEMO_SESSION_NAME, "all")

    console.print("  Generated files:")
    for label, path in build_result.generated_files:
        console.print(f"    [green]{label}[/green]: {path}")

    # Summary
    section_divider()
    success_panel(
        "Demo Complete!",
        f"Session [bold]{DEMO_SESSION_NAME}[/bold] ran through the full sift lifecycle:\n"
        "  1. Created from hello-world template\n"
        "  2. Captured text content for 2 phases\n"
        "  3. Extracted structured data from each phase\n"
        "  4. Generated YAML and Markdown outputs\n\n"
        "[bold]This is what sift does:[/bold] turns unstructured content into\n"
        "structured, reusable data through guided multi-phase sessions.",
    )

    # Next steps
    console.print("\n[bold]Ready to try it for real?[/bold]")
    format_next_step("sift init                              # Set up your API key")
    format_next_step("sift new hello-world --name my-first    # Create your own session")
    format_next_step("sift new discovery-call --name my-call   # Try a real template")

    # Cleanup
    if not keep:
        console.print("\n[dim]Cleaning up demo session...[/dim]")
        shutil.rmtree(demo_dir, ignore_errors=True)
    else:
        console.print(f"\n[dim]Demo session kept at: {demo_dir}[/dim]")


def _write_transcript(session: Session, phase_id: str, text: str) -> None:
    """Write transcript text directly for a phase and update state."""
    from datetime import datetime

    phase_dir = session.phase_dir(phase_id)
    transcript_path = phase_dir / "transcript.txt"
    transcript_path.write_text(text)

    ps = session.phases[phase_id]
    ps.status = "transcribed"
    ps.transcript_file = "transcript.txt"
    ps.captured_at = datetime.now().isoformat()
    ps.transcribed_at = datetime.now().isoformat()
    session.save()


def _write_extraction(session: Session, phase_id: str, data: dict) -> None:
    """Write extraction data directly for a phase and update state."""
    from datetime import datetime

    import yaml as _yaml

    phase_dir = session.phase_dir(phase_id)
    extracted_path = phase_dir / "extracted.yaml"
    with open(extracted_path, "w") as f:
        _yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    ps = session.phases[phase_id]
    ps.status = "extracted"
    ps.extracted_file = "extracted.yaml"
    ps.extracted_at = datetime.now().isoformat()
    session.save()
