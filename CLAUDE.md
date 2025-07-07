# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit dashboard for visualizing SGR (Sistema General de Regalías) data from Colombia's open data platform. The dashboard provides interactive maps and data tables for analyzing budget allocations, approved resources, and project distributions across Colombian departments and municipalities.

## Key Commands

### Running the Application
```bash
# Using the provided shell script
./run_dashboard.sh

# Or directly with streamlit
streamlit run dashboard_sgr.py

# Or using Python module
python -m streamlit run dashboard_sgr.py
```

### Dependency Management
```bash
# Install dependencies
pip install -r requirements.txt

# The application expects a virtual environment at .venv/
source .venv/bin/activate
```

## Architecture

### Main Application (`dashboard_sgr.py`)
- **Data Loading**: Uses Socrata API client to fetch SGR data from datos.gov.co
- **Geospatial Data**: Loads municipality coordinates from `divipola.csv` and Colombia GeoJSON from external URL
- **Visualization**: Two main map types:
  - Choropleth maps (department-level aggregation)
  - Scatter plot maps (municipality-level points)
- **Filtering**: Multi-level filtering by fund type, department, and entity
- **Export**: Excel download functionality for filtered data

### Data Processing Pipeline
1. **API Data Fetch**: `load_data()` - Fetches from Socrata API with 1-hour cache
2. **Geographic Enrichment**: `load_municipios_geo()` - Loads municipality coordinates
3. **Data Preparation**: `prepare_map_data()` and `prepare_choropleth_data()` - Aggregates and joins data
4. **Visualization**: `create_pydeck_map()` and `create_choropleth_map()` - Creates interactive maps

### Key Data Transformations
- DANE codes normalization for proper joins
- Budget calculations including pending balances
- Color intensity mapping for visualizations
- Tooltip generation for interactive elements

## Important Files

- `dashboard_sgr.py`: Main Streamlit application
- `requirements.txt`: Python dependencies
- `divipola.csv`: Municipality geographic coordinates (required for point maps)
- `run_dashboard.sh`: Shell script for launching the application

## Configuration Notes

- The application filters data to focus on specific SGR funds:
  - 'ASIGNACION PARA LA INVERSION LOCAL'
  - 'ASIGNACION PARA LA INVERSION LOCAL - AMBIENTE Y DESARROLLO SOSTENIBLE'
  - 'ASIGNACIONES DIRECTAS'
- Default cache TTL is 1 hour for API data
- Maps use Mapbox light style (requires internet connection)
- The shell script expects the virtual environment at `/Users/daniel/Desktop/OctopusDash/.venv/`

## External Dependencies

- **API**: datos.gov.co Socrata API (dataset: g4qj-2p2e)
- **GeoJSON**: Colombia department boundaries from GitHub gist
- **Mapbox**: Map tiles for pydeck visualizations