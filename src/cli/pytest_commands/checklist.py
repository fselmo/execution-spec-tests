"""CLI entry point for the `checklist` pytest-based command."""

import click

from .fill import FillCommand


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    default="./checklists",
    help="Directory to output the generated checklists (default: ./checklists)",
)
@click.option(
    "--eip",
    "-e",
    type=int,
    multiple=True,
    help="Generate checklist only for specific EIP(s)",
)
def checklist(output: str, eip: tuple, **kwargs) -> None:
    """
    Generate EIP test checklists based on pytest.mark.eip_checklist markers.

    This command scans test files for eip_checklist markers and generates
    filled checklists showing which checklist items have been implemented.

    Examples:
        # Generate checklists for all EIPs
        uv run checklist

        # Generate checklist for specific EIP
        uv run checklist --eip 7702

        # Generate checklists for specific test path
        uv run checklist tests/prague/eip7702*

        # Specify output directory
        uv run checklist --output ./my-checklists

    """
    # Add output directory to pytest args
    args = ["--checklist-output", output]

    # Add EIP filter if specified
    for eip_num in eip:
        args.extend(["--checklist-eip", str(eip_num)])

    command = FillCommand(
        plugins=["pytest_plugins.filler.eip_checklist"],
    )
    command.execute(args)


if __name__ == "__main__":
    checklist()
