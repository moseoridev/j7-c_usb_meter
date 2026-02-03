import typer
import asyncio
import csv
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console
from rich import box
from .core.client import J7CBLEClient

app = typer.Typer(help="J7-C USB Tester Modernized Logger")
console = Console()

class Dashboard:
    def __init__(self):
        self.last_m = None
        self.history = []

    def update(self, m):
        self.last_m = m
        self.history.append(m)
        if len(self.history) > 15:
            self.history.pop(0)

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=11), # Increased size for extra row
            Layout(name="footer")
        )

        # Header
        title_text = f"J7-C USB Tester Live Dashboard"
        if self.last_m:
             title_text += f" | Duration: {self.last_m.duration}"
        layout["header"].update(Panel(title_text, style="bold cyan"))

        # Main metrics
        metrics_table = Table(show_header=False, box=box.SIMPLE, expand=True)
        metrics_table.add_column("Label", style="dim")
        metrics_table.add_column("Value", style="bold yellow", justify="right")
        metrics_table.add_column("Unit", style="dim")
        
        if self.last_m:
            metrics_table.add_row("Voltage", f"{self.last_m.voltage:6.2f}", "V")
            metrics_table.add_row("Current", f"{self.last_m.current:6.2f}", "A")
            metrics_table.add_row("Power", f"{self.last_m.power:6.2f}", "W")
            metrics_table.add_row("Resistance", f"{self.last_m.resistance:6.1f}", "Ω")
            metrics_table.add_row("Temp", f"{self.last_m.temperature}", "C")
            metrics_table.add_row("LVP (Low V)", f"<{self.last_m.lvp:.2f}", "V")
            metrics_table.add_row("OCP (High A)", f">{self.last_m.ocp:.2f}", "A")
        else:
            metrics_table.add_row("Status", "Waiting for data...", "")

        layout["main"].update(Panel(metrics_table, title="Real-time Metrics", border_style="green"))

        # History Table
        history_table = Table(title="Recent Logs (Live)", box=box.MINIMAL, expand=True)
        history_table.add_column("Time")
        history_table.add_column("V", justify="right")
        history_table.add_column("A", justify="right")
        history_table.add_column("W", justify="right")
        history_table.add_column("Temp", justify="right")

        for h in reversed(self.history):
            history_table.add_row(
                h.timestamp.split('T')[1].split('.')[0],
                f"{h.voltage:.2f}",
                f"{h.current:.2f}",
                f"{h.power:.2f}",
                f"{h.temperature}C"
            )
        layout["footer"].update(history_table)
        
        return layout

@app.command()
def run(
    csv_file: str = typer.Option(None, "--csv", help="Path to save CSV data"),
    quiet: bool = typer.Option(False, "--quiet", help="Run in background without UI")
):
    """Start data collection and logging."""
    dashboard = Dashboard()
    csv_handler = None
    csv_writer = None

    if csv_file:
        f = open(csv_file, 'w', newline='')
        csv_handler = f

    def on_measurement(m):
        nonlocal csv_writer
        if quiet:
            if not csv_writer:
                print(f"Logging started to {csv_file}...")
        else:
            dashboard.update(m)
            
        if csv_handler:
            if not csv_writer:
                csv_writer = csv.DictWriter(csv_handler, fieldnames=m.to_dict().keys())
                csv_writer.writeheader()
            csv_writer.writerow(m.to_dict())
            csv_handler.flush()

    async def main_async():
        client = J7CBLEClient(on_measurement=on_measurement)
        
        device = None
        with console.status("[bold green]Scanning for J7-C/UC96...[/bold green]", spinner="dots"):
            try:
                device = await client.find_device()
            except Exception as e:
                console.print(f"[red]Scan failed: {e}[/red]")
                return

        if not device:
            console.print("[red]Device not found. Please check Bluetooth.[/red]")
            return

        console.print(f"[green]Found {device.name} ({device.address})! Connecting...[/green]")
        
        if quiet:
            await client.run(device.address)
        else:
            with Live(dashboard.generate_layout(), refresh_per_second=4, screen=True) as live:
                task = asyncio.create_task(client.run(device.address))
                try:
                    while not task.done():
                        live.update(dashboard.generate_layout())
                        await asyncio.sleep(0.2)
                except asyncio.CancelledError:
                    client.stop()
                    await task
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
    finally:
        if csv_handler:
            csv_handler.close()

if __name__ == "__main__":
    app()
