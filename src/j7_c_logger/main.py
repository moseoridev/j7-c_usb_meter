import typer
import asyncio
import csv
from rich.console import Console
from rich.table import Table
from rich.live import Live
from .core.client import J7CBLEClient

app = typer.Typer(help="J7-C USB Tester Headless Logger")
console = Console()

@app.command()
def run(
    csv_file: str = typer.Option(None, "--csv", help="Path to save CSV data"),
    quiet: bool = typer.Option(False, "--quiet", help="Run in background with minimal output"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed log output")
):
    """
    Start data collection.
    
    Default behavior: Connects to device and prints measurements to stdout in a simple table.
    Use --quiet for headless/background execution.
    """
    csv_handler = None
    csv_writer = None

    if csv_file:
        f = open(csv_file, 'w', newline='')
        csv_handler = f

    # Prepare a simple live table for standard output
    table = Table(box=None, show_header=True, header_style="bold cyan")
    table.add_column("Time")
    table.add_column("Voltage", justify="right", style="yellow")
    table.add_column("Current", justify="right", style="cyan")
    table.add_column("Power", justify="right", style="red")
    table.add_column("Temp", justify="right")
    table.add_column("Status", style="dim")

    def on_measurement(m):
        nonlocal csv_writer
        
        # 1. Save to CSV
        if csv_handler:
            if not csv_writer:
                csv_writer = csv.DictWriter(csv_handler, fieldnames=m.to_dict().keys())
                csv_writer.writeheader()
            csv_writer.writerow(m.to_dict())
            csv_handler.flush()

        # 2. Output to Console (if not quiet)
        if not quiet:
            if verbose:
                # Detailed log style
                console.log(f"V:{m.voltage:<5.2f} A:{m.current:<5.2f} W:{m.power:<5.2f} T:{m.temperature} [{m.duration}]")
            else:
                # Live single-row update (Clean & Simple)
                # We reuse the same table object but clear rows to simulate a static header
                # Actually, standard print is better for simple logging, 
                # but Live Table looks nicer if we want a static status bar.
                # Let's just do a clean one-line print that overwrites itself using carriage return,
                # or just standard logging. 
                # User said "Headless mostly", so standard scrolling log is safer/simpler than TUI.
                # Let's stick to a clean, formatted print.
                
                status_msg = "OK"
                if m.voltage < m.lvp or m.current > m.ocp:
                    status_msg = "PROTECTION?"

                # Print clean columns
                print(f"{m.timestamp.split('T')[1][:8]} | "
                      f"{m.voltage:5.2f} V | "
                      f"{m.current:5.2f} A | "
                      f"{m.power:5.2f} W | "
                      f"{m.temperature}C | "
                      f"{status_msg}")

    async def main_async():
        client = J7CBLEClient(on_measurement=on_measurement)
        
        device = None
        # Simple status spinner during scan
        with console.status("[bold green]Scanning for J7-C/UC96...[/bold green]"):
            try:
                device = await client.find_device()
            except Exception as e:
                console.print(f"[red]Scan failed: {e}[/red]")
                return

        if not device:
            console.print("[red]Device not found.[/red]")
            return

        console.print(f"[green]Connected to {device.name} ({device.address})[/green]")
        console.print("[dim]Press Ctrl+C to stop logging...[/dim]")
        
        # Print Header for text output
        if not quiet and not verbose:
             print(f"{ 'Time':<8} | { 'Volts':<7} | { 'Amps':<7} | { 'Watts':<7} | { 'Temp':<4} | {'Status'}")
             print("-" * 55)

        await client.run(device.address)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    finally:
        if csv_handler:
            csv_handler.close()

if __name__ == "__main__":
    app()