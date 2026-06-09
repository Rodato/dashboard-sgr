# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Executive dashboard in Streamlit for Colombia's Sistema General de Regalías (SGR). Consumes **three** open datasets from `datos.gov.co` via Socrata and renders a single-scroll, **five-tab** executive UX:

1. **Resumen ejecutivo** — KPIs + hero chart + supporting visuals + Excel download. A reconciliation caption discloses the ~44% of budget that lives in non-territorial OTROS bolsas (so the headline and the catch-all-stripped rankings reconcile on screen).
2. **Flujo de caja** — real disbursement, on the giros/pagos dataset (`e624-d9uy`): presupuesto → recaudo → aprobado → pagado → saldo en caja. **Magnitude bars (NOT a funnel — see the funnel trap below)** + a per-department "where is the cash stuck" chart. Headline insight: only ~36% of collected money has been paid out.
3. **Territorio** — cross-dataset join (asignaciones budget vs proyectos delivery): money-in-vs-delivery scatter, national benchmark, and audit red-flag panels (paying-ahead, zombies, desaprobados). Built on `analytics.py`.
4. **Detalles** — per-fondo drill-down (rankings, hierarchical breakdown, full table). **Adapts to the fondo's shape** (territorial vs national-pot) via `classify_fondo`.
5. **Proyectos** — project-level DNP-ProyectosSGR dataset (sector/estado/ejecución física y financiera).

`dashboard_sgr.py` is the orchestrator; business logic is split into the `dashboard_sgr/` package.

## Key Commands

```bash
# Install dependencies. Use a Python 3.11+ venv (Homebrew), not the system 3.9.
pip install -r requirements.txt

# Run the dashboard
python3 -m streamlit run dashboard_sgr.py

# Local dev with auto-reload (does NOT drop the browser session on file edits):
#   .venv/bin/python -m streamlit run dashboard_sgr.py --server.runOnSave true
```

## Architecture

### Module Structure

```
dashboard_sgr.py              # Orchestrator (~1,050 lines): header, sidebar, 5 tabs
dashboard_sgr/
├── __init__.py
├── config.py                 # Constants: 3 Socrata IDs, DEPT_ALIAS, NON_TERRITORIAL, CATCHALL_NAMES, column labels
├── data.py                   # load_data (g4qj-2p2e), load_proyectos (mzgh-shtp), load_giros (e624-d9uy); DANE/map prep
├── analytics.py              # Cross-dataset joins + audit signals for Territorio (territorio_join, national_execution, paying_ahead, zombies, desaprobado_by_dept)
├── charts.py                 # All Plotly charts, shared LAYOUT_DEFAULTS, _currency_ticks / _drop_catchall helpers
├── maps.py                   # Pydeck choropleth + scatter (defined but NOT called from the UI)
├── theme.py                  # PALETTE, CHART_SCALE_*, CSS injection, kpi_card / section_title helpers
└── utils.py                  # format_currency(+_md), classify_fondo, norm_dept, aggregate_sgr_data, strip_accents, short_fondo_name, cached Excel export
data/
└── colombia.geo.json         # Department boundaries (used only by maps.py; the UI does not render maps)
```

### Data Flow

1. **`data.load_data()`** — Paginated Socrata fetch of `g4qj-2p2e` (asignaciones SGR). No `where` filter; **all 31 fondos**, single vigencia "2025 - 2026". DANE codes + monetary columns coerced with `pd.to_numeric(errors="coerce")` (never `.str.strip().astype(float)` — one stray cell would crash the whole load). Computes `SALDO_PENDIENTE = max(0, presupuesto - aprobado)`. 1-hour cache.
2. **`data.load_proyectos()`** — `mzgh-shtp` (DNP-ProyectosSGR, ~35k). Grain is (project × depto × OCAD); `drop_duplicates(["codigobpin","departamento"])` collapses multi-OCAD dupes. Project-grain audit/national metrics in `analytics.py` further dedup on `codigobpin`.
3. **`data.load_giros()`** — `e624-d9uy` (giros/pagos, 5,264 rows). Same grain & naming as g4qj (presupuesto reconciles at ~$57.4T; entity names match 100% byte-for-byte). Adds `valorrecaudo`, `totalpagado`, `saldocaja`. 1-hour cache.
4. **Filtering** — Sidebar multiselects (fondos / deptos / entidades / vigencias) + text search, persisted to `st.query_params` (`f/d/e/v/q`) for shareable URLs. A **"Limpiar filtros"** button + `_clear_filters()` (on_click) resets everything. The empty-result guard shows a banner **without `st.stop()`** (which would blank every tab, including the independent ones).
5. **Per-fondo scoping in Detalles** — local `st.selectbox`; `classify_fondo(datos_fondo)` routes the breakdown metric (see Key Helpers).
6. **Cross-tab frames** — `load_giros` / `load_proyectos` load once and are filtered to each tab via `_filter_giros_by_side` (exact `.isin` — names match g4qj) and `_filter_proyectos_by_side` (`norm_dept` — proyectos spells depts differently).

### Key Helpers

- **`utils.classify_fondo(datos_fondo) -> (shape, stats)`** — `"territorial"` / `"pot_approved"` / `"pot_empty"` from `terr_share = pres_terr/pres_total >= 0.5`. **~14 of 31 fondos are national "bolsas"/convocatorias with presupuesto 100% in OTROS** (no department), so Detalles breaks those down on **recursos aprobados** (the metric that IS distributed) instead of presupuesto, with the 4th KPI swapped to "Aprobado territ." / "Territorializado 0%". `stats` carries pres_total, pres_terr, aprob_total, aprob_terr for the captions.
- **`utils.format_currency(v)`** → abbreviated `$1.5T`. **`utils.format_currency_md(v)`** → same but escapes `\$` for **Markdown** contexts (`st.caption`/`st.markdown`). Streamlit's KaTeX reads `$…$` as inline math, so two money strings in one caption render as italic math — use `_md` in Markdown text, but keep raw `format_currency` in HTML `kpi_card` and Plotly text (where `$` must stay literal).
- **`utils.norm_dept(name)`** — upper + strip accents + `DEPT_ALIAS` for cross-dataset depto joins ("VALLE DEL CAUCA" ↔ "VALLE", "ARCHIPIÉLAGO…" ↔ "SAN ANDRES").
- **`charts._currency_ticks(max_val)`** — clean tick arrays (`$500B`, `$1T`) instead of the Plotly SI default (`1.2G`).
- **`charts._drop_catchall(df, cols)`** — strips `OTROS` / `SIN UBICACION` / `SIN UBICACIÓN` rows.
- **`charts._build_hierarchy_records(df, value_col, value_label)`** — treemap/sunburst records, **parameterized by metric** so it serves both presupuesto and recursos-aprobados breakdowns. Groups by original `nombrefondo`, labels with `short_fondo_name`, collapses the entity level when entity name duplicates the department.
- **`charts.create_entidad_ranking_chart(df, value_col, value_label, top_n)`** — generic entity ranking; `create_saldo_pendiente_chart` is now a thin wrapper.
- **`theme.kpi_card` / `theme.section_title`** — the design system. Do **not** swap `kpi_card` for `st.metric`, and avoid `st.subheader`/`st.header` (visual consistency).

### Chart Conventions

- All Plotly charts go through `_apply_theme(fig, **overrides)` (Inter font, transparent bg, grid in `PALETTE['border']`, no title).
- Currency axes use `_currency_ticks` + explicit `tickvals/ticktext` (never `tickformat: "$,.2s"`).
- Use **`width="stretch"`** on `st.plotly_chart`/`st.dataframe`/buttons — the old `use_container_width` is deprecated.
- Long titles go in `section_title()` markdown outside the figure (avoids the "undefined" placeholder bug).
- **No funnels for the giros magnitudes.** `recursosaprobadosasignadosspgr` (aprobado) is an **accumulated cross-vigency stock**: aprobado > recaudo in 30/32 departments, so a `go.Funnel` visually inverts under a depto filter and its %-of-initial labels read as false leakage. `create_giros_flujo_chart` uses independent horizontal bars and the caption discloses aprobado is acumulado. Likewise `pagado + saldocaja ≠ recaudo` (saldocaja is a standalone reported balance) — never stack them as a whole; `create_giros_dept_chart` uses grouped bars.

### Catch-alls & national-pot funds

Source rows where `nombredepartamento`/`nombreentidad` = `OTROS` / `SIN UBICACIÓN` (`CATCHALL_NAMES`) hold **~44% of the budget** and would swamp any ranking, so ranking/top-N charts call `_drop_catchall` first. The **Resumen reconciliation caption** makes that gap explicit. Beyond catch-all rows, **14 of 31 fondos** keep their entire presupuesto in OTROS (national pots) — handled per-fondo by `classify_fondo` (see Key Helpers). `analytics.territorialize` / `NON_TERRITORIAL` drop these from the cross-dataset Territorio view.

### >100% execution is real — don't clamp it

`recursosaprobadosasignadosspgr` is the **accumulated** approved amount (may include prior-vigency commitments), while `presupuestosgrinversion` is the current-vigency budget, so ratios above 100% are normal (median ~117% on proyectos). These are **not** clamped: the Proyectos table uses `NumberColumn` (not `ProgressColumn`) and the execution scatter uses `rangemode="tozero"` (not a fixed `[0,105]`) so >100% reads literally. The Resumen hero shows the currency total on each bar and keeps the % in the hover only.

### Sidebar Filters

| Filter | Type | Notes |
|---|---|---|
| Fondos | multiselect (all fondos) | Empty = all; URL `?f=` |
| Departamentos | multiselect | cascades to entities; URL `?d=` |
| Entidades | multiselect | pool narrows by depto; session_state purged on cascade narrowing; URL `?e=` |
| Vigencias | multiselect | **only shown when `nunique() > 1`** (data is single-vigencia, so currently hidden); URL `?v=` |
| Búsqueda | text input | case-insensitive partial match on `nombreentidad`; URL `?q=` |

Multiselects show selection counters via `_labeled()`. **"Limpiar filtros"** resets all via `_clear_filters` (on_click). The same fondo/depto/búsqueda filters apply to the giros and proyectos frames.

## External Dependencies

- **Socrata** — `www.datos.gov.co`, datasets `g4qj-2p2e` (asignaciones), `mzgh-shtp` (DNP-ProyectosSGR), `e624-d9uy` (giros/pagos). Unauthenticated (rate-limited); add a token via `st.secrets` if needed.
- **No Mapbox / no maps in the UI** — `maps.py` and `data/colombia.geo.json` (with remote gist fallback) remain in case maps are reintroduced, but the UI renders none.

## Important Files

- `dashboard_sgr.py` — orchestrator (5 tabs)
- `dashboard_sgr/config.py` — constants (3 dataset IDs, DEPT_ALIAS, NON_TERRITORIAL, CATCHALL_NAMES, column labels)
- `dashboard_sgr/data.py` — Socrata loaders (load_data / load_proyectos / load_giros)
- `dashboard_sgr/analytics.py` — cross-dataset joins + audit signals (Territorio)
- `dashboard_sgr/charts.py` — all Plotly figures
- `dashboard_sgr/utils.py` — format_currency(+_md), classify_fondo, norm_dept, helpers
- `dashboard_sgr/theme.py` — palette + CSS
- `.streamlit/config.toml` — theme primaryColor, backgroundColor, font
- `requirements.txt` — `streamlit>=1.30` required for `st.query_params`
