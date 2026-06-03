# Azmus Cloud Print Agent

Polls the online ERP (Render) every 5 seconds, downloads label PNGs, and prints to a local Windows USB or shared printer (e.g. **XPrinter XP-350B**).

## Setup

1. On Render, set environment variable `PRINT_AGENT_API_KEY` to a long random secret.
2. In ERP **Settings → Printers**, add a printer:
   - **Name:** `XPrinter XP-350B` (must match `PRINTER_NAME` in `.env`)
   - **Brand:** XPrinter
   - **Connection type:** `cloud_agent`
   - **Windows printer name:** exact name from Windows Devices and Printers
   - **Auto print:** enabled
3. Copy `config.example.env` to `.env` and fill values.
4. Install and run:

```powershell
cd print-agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python agent.py
```

## Render env

| Variable | Description |
|----------|-------------|
| `PRINT_AGENT_API_KEY` | Shared secret for agent Bearer auth |
