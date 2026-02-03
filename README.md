# J7-C USB Tester Logger (Modernized)

> **Note**: This repository is a modernized fork of the original J7-C USB Tester script. It has been completely refactored to support **Headless BLE logging** and a **Real-time Web Dashboard** using a modern Python stack (`FastAPI`, `Bleak`, `Typer`, `Rich`).

A modern, headless data logger and web dashboard for the **J7-C / UC96** USB Tester via Bluetooth Low Energy (BLE).

Designed to be robust, lightweight, and easy to deploy on a Raspberry Pi or local machine.

## Features

- **Headless Logging**: Runs in the background, auto-reconnects on signal loss.
- **Web Dashboard**: Real-time charts (Voltage, Current, Power, Temp) using WebSockets.
- **Data Persistence**: Restores chart history on page reload; survives browser disconnects.
- **Zero Configuration**: Auto-discovers the device.

## Installation

This project uses `uv` for dependency management.

```bash
# Clone the repository
git clone https://github.com/yourname/j7-c-usb-meter.git
cd j7-c-usb-meter

# Install dependencies
uv sync
```

## Usage

### 1. Web Dashboard (Recommended)
Starts the background logger and a local web server.

```bash
uv run j7-c-usb-tester web
```
- Open **http://localhost:8000** in your browser.
- Data is auto-saved to `logs/j7c_YYYYMMDD_HHMMSS.csv`.
- Use `--csv <filename>` to specify a custom log file.

### 2. CLI Logger (Headless)
Runs only the logger in the terminal. Useful for minimal environments.

```bash
uv run j7-c-usb-tester run
```
- Use `--quiet` to suppress output (useful for systemd services).
- Use `--verbose` for raw data inspection.

## Project Structure

- `src/j7_c_logger/core/`: Protocol parsing and BLE client logic.
- `src/j7_c_logger/web/`: FastAPI backend and HTML frontend.
- `PROTOCOL.md`: Detailed documentation of the byte-level packet format.

## License

See [LICENSE.txt](LICENSE.txt).
