# AutoDiag

*[Versão em português](README.md)*

[![PyPI](https://img.shields.io/pypi/v/autodiag)](https://pypi.org/project/autodiag/)
[![CI](https://github.com/lucianoon/autodiag/actions/workflows/ci.yml/badge.svg)](https://github.com/lucianoon/autodiag/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An OBD2 diagnostics tool in Python for 2015+ vehicles, using **ELM327** adapters
(USB, Bluetooth serial or Wi-Fi). It reads diagnostic trouble codes (DTCs),
polls live PIDs, identifies the vehicle by VIN, keeps history in SQLite and
serves a local web interface that streams the scan in real time.

No adapter on hand? `autodiag scan --demo` runs the whole flow against a
simulated vehicle — no hardware at all.

## Reproducible demo

![AutoDiag running a simulated OBD2 scan with DTCs and live PIDs](docs/assets/autodiag-demo.jpg)

This screenshot was produced by the application itself with the deterministic
P0171/P0300 scenario. To reproduce the same flow locally:

```bash
pip install autodiag
autodiag serve
```

Open `http://localhost:8000`, select **Scan**, check **Modo demo** and
**Sem análise IA**, then click **Iniciar Scan**. No adapter, API key, or
external access is required.

> **Note on language:** the bundled DTC database stores its descriptions and
> probable causes in Portuguese, and severity levels are the literal strings
> `critico` / `atencao` / `informativo`. The CLI and the web UI render those
> values as-is.

## What it does today

- **DTC reading** (mode 03) over ELM327, decoding P/C/B/U codes and looking
  them up in a local database of **566 codes** — 65 hand-curated + 501
  generated from the standardized SAE J2012 families (description, severity,
  affected system and probable causes, in Portuguese).
- **DTC clearing** (mode 04), with confirmation.
- **Readiness monitors** with **recent-code-clearing detection**: incomplete
  monitors + zero DTCs + low distance since last clear (PIDs 01/30/31)
  produce an auditable verdict — the classic signature of a scan wiped right
  before a used-car inspection. In demo mode, clear the DTCs and scan again
  to see the detection fire.
- **Inspection verdict** on the HTML report: a standardized four-level call
  (Approved / Approved with caveats / Re-inspection required / Failed)
  consolidating urgency, DTCs and the code-clearing check — built for
  used-car evaluation reports.
- **Live PIDs** (mode 01): RPM, speed, engine and intake temperature, throttle
  position, MAF, short/long fuel trim bank 1, O2 sensor B1S1 voltage and fuel
  level.
- **Vehicle identification**: VIN read (mode 09 02), local decoding (WMI +
  model year) and optional enrichment through NHTSA's public vPIC API.
- **Urgency heuristic** (`critico` / `atencao` / `informativo` — critical /
  warning / informational) derived from the DTCs found and from PID thresholds
  (overheating, high fuel trim, low MAF).
- **Demo mode** (`--demo` on the CLI, a checkbox on the web UI): a simulated
  adapter running a realistic lean-mixture + misfire scenario (P0171/P0300), so
  the entire tool can be exercised without hardware.
- **Optional AI analysis, with any model** — native Anthropic (streaming +
  adaptive thinking) or any OpenAI-compatible endpoint (OpenAI, OpenRouter,
  Groq, Together, vLLM, Ollama, LM Studio). Selected by environment variable,
  no code edits; `--no-ai` turns it off.
- **Local history** in SQLite (`~/.autodiag/history.db`) with listing and a
  statistical summary (total scans, criticals, most frequent DTCs).
- **Web interface** (FastAPI + uvicorn): a single page streaming the scan over
  Server-Sent Events, plus a JSON API for history and DTC lookup.

## Architecture

```
src/autodiag/
├── cli.py              # CLI (argparse): scan, history, summary, dtc, clear, serve
├── core/
│   ├── dtc.py          # Local DTC database (DTCInfo, lookup, severity)
│   └── vehicle.py      # VIN decoding (local + NHTSA API)
├── elm327/
│   ├── __init__.py     # OBDReader protocol + create_reader factory (real/simulated)
│   ├── reader.py       # ELM327 communication (serial/Wi-Fi), DTC and PID decoding
│   └── sim.py          # Simulated adapter behind demo mode
├── agents/
│   ├── provider.py     # Single LLM port (Anthropic + OpenAI-compatible)
│   └── diagnostic.py   # Automotive diagnostic prompt
├── db/
│   └── history.py      # Diagnostic history in SQLite
├── ui/
│   └── display.py      # Terminal output (rich): tables, panels, status
└── web/
    ├── server.py       # FastAPI: web page, JSON API and SSE scan stream
    └── static/         # index.html for the web interface
```

## Installation

Straight from [PyPI](https://pypi.org/project/autodiag/) (Python 3.11+):

```bash
pip install autodiag
autodiag scan --demo   # try it without hardware
```

For development, use [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/lucianoon/autodiag.git
cd autodiag
uv sync
```

To enable the optional AI analysis, copy `.env.example` to `.env` and
configure a model (also read from `~/.autodiag/.env`). See
[Choosing the model](#choosing-the-model) — it works with Anthropic, OpenAI,
OpenRouter, Groq, or a local server such as Ollama.

## Usage

With an ELM327 adapter connected to the vehicle:

```bash
# Full diagnostic (auto-detects the port on macOS/Linux)
uv run autodiag scan

# Specific port, or a Wi-Fi adapter
uv run autodiag scan --port /dev/cu.usbserial-1410
uv run autodiag scan --wifi 192.168.0.10

# Without AI analysis
uv run autodiag scan --no-ai

# Clear the vehicle's DTCs (asks for confirmation)
uv run autodiag clear
```

Without hardware, these still work:

```bash
# Full diagnostic flow against a simulated vehicle (P0171 + P0300)
uv run autodiag scan --demo

# Look up a code in the local database
uv run autodiag dtc P0171

# History and statistics for saved diagnostics
uv run autodiag history --limit 20
uv run autodiag summary

# Web interface at http://localhost:8000
uv run autodiag serve --open
```

Port auto-detection works on Windows, Linux and macOS: system serial ports are
enumerated through pyserial and filtered by identifiers typical of ELM327
adapters (CH340/CP210x/FTDI/PL2303 chipsets and "OBDII" names). If your adapter
is not recognized, pass the port explicitly with `--port` (`COM3` on Windows,
`/dev/ttyUSB0` on Linux).

## Choosing the model

LLM access goes through a single port (`agents/provider.py`) with two backends
behind one interface, selected by environment variable:

| Variable | Values |
|---|---|
| `AUTODIAG_LLM_BACKEND` | `auto` (default), `anthropic`, `openai` |
| `AUTODIAG_MODEL` | model id; defaults to `claude-opus-5` or `gpt-4.1-mini` |
| `AUTODIAG_BASE_URL` | OpenAI-compatible endpoint (also accepts `OPENAI_BASE_URL`) |
| `AUTODIAG_API_KEY` | credential; falls back to `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` |

In `auto` mode: an Anthropic key ⇒ the `anthropic` backend; otherwise a base URL
or an OpenAI key ⇒ the `openai` backend; with neither, AI analysis is skipped.

```bash
# Anthropic (native backend: streaming + adaptive thinking)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# OpenRouter, Groq, Together, DeepInfra, Fireworks…
export AUTODIAG_BASE_URL=https://openrouter.ai/api/v1
export AUTODIAG_API_KEY=sk-or-v1-...
export AUTODIAG_MODEL=meta-llama/llama-3.3-70b-instruct

# Local Ollama or LM Studio — no credential at all
export AUTODIAG_BASE_URL=http://localhost:11434/v1
export AUTODIAG_MODEL=llama3.1
```

The OpenAI-compatible backend needs an optional extra:

```bash
pip install 'autodiag[openai]'
```

For a one-off scan, `--model` overrides the environment:

```bash
uv run autodiag scan --model claude-sonnet-5
```

Local servers usually need no credential; when a base URL is set and no key is,
the client sends a placeholder that the server ignores.

## Tests

The tests cover pure logic — DTC and PID decoding against a fake reader, VIN
handling, the urgency heuristic and history against a temporary database — and
require neither hardware nor API keys:

```bash
uv sync
uv run pytest
```

Code quality is checked with [ruff](https://docs.astral.sh/ruff/) (lint) and
[mypy](https://mypy-lang.org/) (types):

```bash
uv run ruff check .
uv run mypy
```

Tests, lint and type-check run in CI (GitHub Actions, Ubuntu, Python 3.12) on
every push and pull request.

The OIDC-based versioning and publishing process is documented in
[`RELEASING.md`](RELEASING.md).

## License

[MIT](LICENSE) — © 2026 Luciano de Oliveira Nunes.
