# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Streamlit dashboard for visualizing Colombia's SGR (Sistema General de Regalias) data. Modular application with `dashboard_sgr.py` as the orchestrator and business logic split into the `dashboard_sgr/` package. Fetches budget/project data from the Socrata API at datos.gov.co and renders interactive maps, charts, and data tables.

## Key Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python3 -m streamlit run dashboard_sgr.py
```

## Architecture

### Module Structure

```
dashboard_sgr.py              # Thin orchestrator (~220 lines): page config, sidebar filters, tabs
dashboard_sgr/
├── __init__.py
├── config.py                  # All constants: API settings, fund names, dept mapping, column lists
├── data.py                    # Data loading (Socrata with pagination & retry), DANE code processing, map data prep
├── charts.py                  # Plotly charts: bar, pie, gauge KPI, treemap, vigencia comparison
├── maps.py                    # Pydeck maps: department choropleth, municipality scatter
└── utils.py                   # Helpers: normalize_color_intensity, format_currency, aggregate_sgr_data, excel export
data/
└── colombia.geo.json          # Local copy of department boundaries GeoJSON (fallback to remote URL)
```

### Data Flow

1. **`data.load_data()`** — Fetches from Socrata API (`g4qj-2p2e` dataset) with pagination (loops in batches of 5000) and retry logic (3 attempts with backoff). Normalizes DANE codes using `pd.to_numeric(errors='coerce')`, converts monetary strings to floats, computes `SALDO_PENDIENTE`. Returns `(DataFrame, rows_fetched)`. Cached with 1-hour TTL.
2. **`data.load_municipios_geo()`** — Reads `divipola.csv` for municipality lat/lon coordinates. Cached indefinitely.
3. **`data.load_colombia_geojson()`** — Loads from local `data/colombia.geo.json` first, falls back to remote GitHub gist URL. Cached indefinitely.
4. **Filtering** — Data is first filtered to three specific fund types (`config.FONDOS_INTERES`), then further filtered by sidebar controls: fund, vigencia, department, entity (cascading), and text search.
5. **Visualization** — Three tabs: data/summary tables, Plotly charts (bar, pie, gauge KPI, treemap, vigencia), and pydeck maps (choropleth or scatter).

### Key Data Join

Municipality-level maps depend on joining SGR data to `divipola.csv` via DANE entity codes: `codigodaneentidad` <-> `COD_MPIO_CLEAN`. Department-level choropleths join on normalized department names with `config.DEPT_NAME_MAPPING` to handle accent/naming mismatches with the GeoJSON.

### Fund Types (in config.py)

The dashboard filters to exactly these three fund names (note the double space before "AMBIENTE" -- this matches the source data):
- `'ASIGNACIONES DIRECTAS'`
- `'ASIGNACION PARA LA INVERSION LOCAL'`
- `'ASIGNACION PARA LA INVERSION LOCAL -  AMBIENTE Y DESARROLLO SOSTENIBLE'`

### Sidebar Filters

- **Fondo**: selectbox (single selection)
- **Vigencia**: multiselect (if column exists in data)
- **Departamento**: multiselect (cascading -- updates entity options)
- **Entidad**: multiselect (filtered by selected departments)
- **Busqueda por texto**: text input for entity name search (case-insensitive partial match)

## External Dependencies

- **Socrata API**: `www.datos.gov.co` dataset `g4qj-2p2e` (no API token used -- unauthenticated, rate-limited)
- **GeoJSON**: Local file `data/colombia.geo.json` with remote fallback to `gist.githubusercontent.com/john-guerra/...`
- **Mapbox**: Light-v11 tile style for pydeck maps (requires internet)

## Important Files

- `dashboard_sgr.py` — Main orchestrator
- `dashboard_sgr/config.py` — All configuration constants
- `dashboard_sgr/data.py` — Data loading and transformation
- `dashboard_sgr/charts.py` — Plotly chart creation
- `dashboard_sgr/maps.py` — Pydeck map creation
- `dashboard_sgr/utils.py` — Shared utility functions
- `data/colombia.geo.json` — Local GeoJSON for department boundaries
- `divipola.csv` — Municipality coordinates (DANE codes, lat/lon); tracked in git despite `.gitignore` csv rule
- `requirements.txt` — Python dependencies (streamlit, pandas, sodapy, pydeck, plotly, etc.)
