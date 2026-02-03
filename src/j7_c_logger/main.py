import typer
import asyncio
import csv
import uvicorn
import logging
import os
from rich.console import Console
from .core.client import J7CBLEClient

# Configure logging
logging.basicConfig(level=logging.ERROR)

app = typer.Typer(help="J7-C USB Tester Logger & Web Dashboard")
console = Console()

@app.command()
def run(
    csv_file: str = typer.Option(None, "--csv", help="Path to save CSV data"),
    quiet: bool = typer.Option(False, "--quiet", help="Run in background with minimal output"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed log output")
):
    """
    Start data collection (CLI Mode).
    Automatically reconnects if device is lost.
    """
    csv_handler = None
    csv_writer = None

    if csv_file:
        f = open(csv_file, 'w', newline='')
        csv_handler = f

    def on_measurement(m):
        nonlocal csv_writer
        if csv_handler:
            if not csv_writer:
                csv_writer = csv.DictWriter(csv_handler, fieldnames=m.to_dict().keys())
                csv_writer.writeheader()
            csv_writer.writerow(m.to_dict())
            csv_handler.flush()

        if not quiet:
            if verbose:
                console.log(f"V:{m.voltage:<5.2f} A:{m.current:<5.2f} W:{m.power:<5.2f} T:{m.temperature} [{m.duration}]")
            else:
                status_msg = f"OK"
                if m.voltage < m.lvp or m.current > m.ocp:
                    status_msg = "PROTECTION?"
                print(f"{m.timestamp.split('T')[1][:8]} | {m.voltage:5.2f} V | {m.current:5.2f} A | {m.power:5.2f} W | {m.temperature}C | {status_msg}")

    async def main_async():
        client = J7CBLEClient(on_measurement=on_measurement)
        
        while True:
            device = None
            if not quiet:
                with console.status("[bold green]Scanning for J7-C/UC96...[/bold green]"):
                    device = await client.find_device()
            else:
                device = await client.find_device()

            if not device:
                if not quiet:
                    console.print("[red]Device not found. Retrying in 5s...[/red]")
                await asyncio.sleep(5)
                continue

            if not quiet:
                console.print(f"[green]Connected to {device.name} ({device.address})[/green]")
                console.print("[dim]Press Ctrl+C to stop logging...[/dim]")
                if not verbose:
                    print(f"{ 'Time':<8} | {'Volts':<7} | {'Amps':<7} | {'Watts':<7} | {'Temp':<4} | {'Status'}")
                    print("-" * 55)

            try:
                await client.run(device.address)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if not quiet:
                    console.print(f"[red]Connection Lost: {e}. Reconnecting...[/red]")
                await asyncio.sleep(2)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user.[/yellow]")
    finally:
        if csv_handler:
            csv_handler.close()

@app.command()
def web(
    csv_file: str = typer.Option("web_log.csv", "--csv", help="Path to save CSV data"),
    port: int = typer.Option(8000, help="Web server port"),
    host: str = typer.Option("0.0.0.0", help="Web server host")
):
    """
    Start Web Dashboard (and background logging).
    """
    console.print(f"[green]Starting Web Dashboard at http://{host}:{port}[/green]")
    console.print(f"[dim]Logging to: {csv_file}[/dim]")
    console.print("[dim]Background logging active. Press Ctrl+C to stop server.[/dim]")
    
    # Pass CSV path via environment variable to the worker
    os.environ["J7C_CSV_PATH"] = csv_file
    
    # Run Uvicorn Programmatically
    uvicorn.run("j7_c_logger.web.server:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    app()
