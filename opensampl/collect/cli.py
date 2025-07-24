"""Consolidated CLI entry point for opensampl.collect tools."""

import click

from opensampl.collect.microchip.twst.generate_twst_files import collect_files as collect_twst_files


@click.group()
def cli():
    """OpenSAMPL data collection tools."""
    pass


@cli.group()
def microchip():
    """Microchip device collection tools."""
    pass


@microchip.command()
@click.option("--ip", required=True, help="IP address of the modem")
@click.option("--control-port", required=False, default=1700, help="Control port of the modem (default: 1700)")
@click.option("--status-port", required=False, default=1900, help="Status port of the modem (default: 1900)")
@click.option("--dump-interval", default=300, help="Duration between file dumps in seconds (default: 300 = 5 minutes)")
@click.option(
    "--total-duration", default=None, type=int, help="Total duration to run in seconds (default: run indefinitely)"
)
@click.option("--output-dir", default="./output", help="Output directory for CSV files (default: ./output)")
def twst(ip: str, control_port: int, status_port: int, dump_interval: int, total_duration: int, output_dir: str):
    """
    Collect data from Microchip TWST modems.

    This command connects to TWST modems via IP address to collect measurement data including
    offset and EBNO tracking values, along with contextual information. Data is saved to
    CSV files with YAML metadata headers for comprehensive data logging.

    Examples:
        opensampl-collect microchip twst --ip 192.168.1.100
        opensampl-collect microchip twst --ip 192.168.1.100 --dump-interval 600 --total-duration 3600

    """
    collect_twst_files(
        host=ip,
        control_port=control_port,
        status_port=status_port,
        dump_interval=dump_interval,
        total_duration=total_duration,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    cli()
