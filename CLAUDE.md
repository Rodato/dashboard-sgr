# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Executive dashboard in Streamlit for Colombia's Sistema General de Regalías (SGR). Consumes two open datasets from `datos.gov.co` via Socrata and renders a two-stage UX:

1. **Resumen ejecutivo** — single-scroll executive view (KPIs + hero chart + supporting visuals + Excel download).
2. **Detalles** — per-fondo drill-down (rankings, hierarchical breakdown, full table).
3. **Proyectos** — complementary view built on the project-level DNP-ProyectosSGR dataset (sector/estado/ejecución física y financiera).

`dashboard_sgr.py` is the orchestrator; business logic is split into the `dashboard_sgr/` package.

## Key Commands

```bash
# Install dependencies (Python 3.9+)
pip install -r requirements.txt

# Run the dashboard
python3 -m streamlit run dashboard_sgr.py
```

## Architecture

### Module Structure

```
dashboard_sgr.py              # Orchestrator (~450 lines): header, sidebar, 3 tabs
dashboard_sgr/
├── __init__.py
├── config.py                 # Constants: Socrata IDs, DANE mapping, catch-all names, column labels
├── data.py                   # load_data (g4qj-2p2e), load_proyectos (mzgh-shtp), DANE processing, map prep
├── charts.py                 # All Plotly charts, shared LAYOUT_DEFAULTS, _currency_ticks helper
├── maps.py                   # Pydeck choropleth + scatter (defined but not called from the UI)
├── theme.py                  # PALETTE, CHART_SCALE_*, CSS injection, kpi_card / section_title helpers
└── utils.py                  # format_currency, aggregate_sgr_data, strip_accents, short_fondo_name, Excel export
data/
└── colombia.geo.json         # Department boundaries (used only by maps.py; UI currently does not render maps)
```

### Data Flow

1. **`data.load_data()`** — Paginated Socrata fetch of `g4qj-2p2e` (asignaciones SGR). No `where` filter; brings **all fondos** (~30+). DANE codes coerced with `pd.to_numeric(errors='coerce')`, monetary strings → floats, computes `SALDO_PENDIENTE = max(0, presupuesto - aprobado)`. 1-hour cache.
2. **`data.load_proyectos()`** — Paginated Socrata fetch of `mzgh-shtp` (DNP-ProyectosSGR, ~35k projects). Coerces `valortotal`, `ejecucionfisica`, `ejecucionfinanciera` to numeric. 1-hour cache.
3. **Filtering** — Sidebar multiselects (fondos / deptos / entidades / vigencias) + text search. Filters persist to `st.query_params` with short keys (`f`, `d`, `e`, `v`, `q`) for shareable URLs. Entity filter cascades from department selection (session_state is purged when options narrow to avoid Streamlit errors).
4. **Per-fondo scoping in Detalles** — A local `st.selectbox` picks one fondo; the per-fondo KPIs, saldo-pendiente ranking, hierarchical chart, table and download all use `datos_fondo = df_filtrado[nombrefondo == fondo_sel]`.
5. **Tabs render** —
   - **Resumen** hero chart `create_presupuesto_vs_saldo_chart` (stacked bar: aprobado + saldo pendiente per depto), callout `create_bottom_ejecucion_chart` (bottom 5 by % ejecución), donut `create_fondo_pie_chart` (top 8 + Otros).
   - **Detalles** per-fondo KPIs, saldo ranking, treemap/sunburst toggle, vigencia chart (if >1 vigencia), data table with `st.column_config.NumberColumn(format="dollar")`.
   - **Proyectos** independent pipeline; filters by depto from sidebar + local sector/estado multiselects; sector donut, estado bar, top entidades ejecutoras, scatter física vs financiera, project table with `st.column_config.ProgressColumn` for execution %.

### Key Helpers

- **`charts._currency_ticks(max_val)`** — returns clean tick arrays (`$500B`, `$1T`) instead of the ugly Plotly SI default (`1.2G`). Use for every monetary axis.
- **`charts._drop_catchall(df, cols)`** — strips rows where dept/entity is `OTROS`, `SIN UBICACION`, or `SIN UBICACIÓN` (source-data catch-alls that swamp rankings).
- **`charts._build_hierarchy_records(df)`** — builds `(ids, labels, parents, values, texts, hovers)` for treemap/sunburst. Groups by **original** `nombrefondo` (not short name — avoids collisions from truncation) and labels with `short_fondo_name`. Collapses the entity level when entity name duplicates the department.
- **`utils.short_fondo_name(name, max_len=40)`** — shortens long SGR fund names with known abbreviations (`INVERSION LOCAL`, `CTeI`, etc.) and `…` truncation.
- **`utils.strip_accents(text)`** — used for dept name matching against GeoJSON and for future fuzzy joins.
- **`theme.kpi_card(label, value, delta=None)`** — HTML string for a consistent KPI card.
- **`theme.section_title(text)`** — inline heading with brand underline; avoid `st.subheader`/`st.header` for visual consistency.

### Chart Conventions

- All Plotly charts go through `_apply_theme(fig, **overrides)` which merges `LAYOUT_DEFAULTS` (Inter font, transparent bg, grid in `PALETTE['border']`, no title).
- Currency axes use `_currency_ticks` + explicit `tickvals/ticktext` (never `tickformat: "$,.2s"`).
- Bar charts: `width=0.5-0.55`, `cliponaxis=False` when text overflows.
- Long chart titles go in `section_title()` markdown outside the figure, not in `layout.title` (avoids "undefined" placeholder bug).

### Catch-alls in Source Data

The SGR dataset contains placeholder rows where `nombredepartamento = "OTROS"` and `nombreentidad = "OTROS"` (or `SIN UBICACIÓN`). These have large budget values and would swamp any ranking. All ranking/top-N charts call `_drop_catchall` first. `CATCHALL_NAMES` lives in `config.py`.

### Sidebar Filters

| Filter | Type | Notes |
|---|---|---|
| Fondos | multiselect (all fondos) | Empty = all; persisted to URL as `?f=` |
| Departamentos | multiselect | Cascades to entities; URL `?d=` |
| Entidades | multiselect | Pool narrows by depto; session_state purged on cascade narrowing; URL `?e=` |
| Vigencias | multiselect | Only if column exists; URL `?v=` |
| Búsqueda | text input | Case-insensitive partial match on `nombreentidad`; URL `?q=` |

Sidebar multiselects show selection counters in the label (`Departamentos (3 seleccionados)`) via the `_labeled()` helper.

### UX note: "% ejecución" can exceed 100%

In the source data, `recursosaprobadosasignadosspgr` is the **accumulated** approved amount (may include prior-vigency commitments still executing), while `presupuestosgrinversion` is the current-vigency investment budget. Ratios above 100% are possible and visible via the hero chart's tooltip. The **anotación visible** on each bar shows only the currency total, not the %, to avoid confusion. The % lives in the hover only.

## External Dependencies

- **Socrata** — `www.datos.gov.co`, datasets `g4qj-2p2e` (asignaciones) and `mzgh-shtp` (DNP-ProyectosSGR). Unauthenticated (rate-limited); add token via `st.secrets` if needed.
- **No Mapbox token** — `MAP_STYLE = "light"` maps to pydeck's built-in Carto Positron tiles. The `mapbox://` styles require a token and left the map blank when we tried them.
- **GeoJSON** — `data/colombia.geo.json` with remote gist fallback. Currently unused by the UI (maps were removed because they were unreliable); `maps.py` and the geojson remain in case we reintroduce them.

## Important Files

- `dashboard_sgr.py` — orchestrator
- `dashboard_sgr/config.py` — constants
- `dashboard_sgr/data.py` — Socrata loaders
- `dashboard_sgr/charts.py` — all Plotly figures (including the proyectos charts)
- `dashboard_sgr/theme.py` — palette + CSS
- `dashboard_sgr/utils.py` — helpers
- `.streamlit/config.toml` — theme primaryColor, backgroundColor, font
- `requirements.txt` — `streamlit>=1.30` required for `st.query_params`
