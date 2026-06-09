import pandas as pd
import streamlit as st
from datetime import datetime

from dashboard_sgr.config import (
    CATCHALL_NAMES,
    COLUMN_LABELS,
    COLUMNS_TO_EXCLUDE,
    ESTADO_EN_EJECUCION,
    MONETARY_COLUMNS,
)
from dashboard_sgr.data import load_data, load_giros, load_proyectos
from dashboard_sgr.charts import (
    create_benchmark_chart,
    create_bottom_ejecucion_chart,
    create_desaprobado_chart,
    create_entidad_ranking_chart,
    create_fondo_pie_chart,
    create_giros_dept_chart,
    create_giros_flujo_chart,
    create_presupuesto_vs_saldo_chart,
    create_proyectos_ejecucion_chart,
    create_proyectos_estado_chart,
    create_proyectos_sector_donut,
    create_proyectos_top_entidades_chart,
    create_sunburst_chart,
    create_territorio_scatter,
    create_treemap_chart,
    create_vigencia_chart,
    create_zombie_year_chart,
)
from dashboard_sgr.analytics import (
    desaprobado_by_dept,
    national_execution,
    paying_ahead,
    territorialize,
    territorio_join,
    zombies,
    zombies_by_year,
)
from dashboard_sgr.theme import CUSTOM_CSS, PALETTE, kpi_card, section_title
from dashboard_sgr.utils import (
    classify_fondo,
    convert_df_to_excel,
    format_currency,
    format_currency_md,
    norm_dept,
)

# --- Page config ---
st.set_page_config(
    page_title="Dashboard SGR",
    page_icon="○",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- Load data ---
with st.spinner("Conectando a la API y cargando datos..."):
    result = load_data()

if result is None:
    st.error("No se pudieron cargar los datos. Verifica la conexion a internet.")
    st.stop()

df, rows_fetched = result

if df.empty:
    st.error("No se pudieron cargar los datos. Verifica la conexion a internet.")
    st.stop()

df_base = df.copy()

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 1rem 0; border-bottom: 1px solid {PALETTE['border']}; margin-bottom: 1rem;">
            <div style="font-size: 1.1rem; font-weight: 700; color: {PALETTE['primary_dark']}; letter-spacing: -0.01em;">
                Dashboard SGR
            </div>
            <div style="font-size: 0.75rem; color: {PALETTE['text_muted']}; margin-top: 0.15rem;">
                Sistema General de Regalias
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("##### Filtros")

qp = st.query_params


def _qp_list(key):
    raw = qp.get(key, "")
    return [x for x in raw.split("|") if x] if raw else []


def _labeled(base, key, default, singular, plural):
    current = st.session_state.get(key, default)
    n = len(current) if current else 0
    if n == 0:
        return base
    word = singular if n == 1 else plural
    return f"{base} ({n} {word})"


def _clear_filters():
    """Reset every sidebar/proyectos filter and the shareable URL params.

    Used by the "Limpiar filtros" buttons (sidebar + empty-state). Runs as an
    on_click callback, before widgets re-instantiate, so popping the widget keys
    is safe and Streamlit reruns automatically afterwards.
    """
    for k in ("flt_fondos", "flt_deptos", "flt_entidades", "flt_vigencias",
              "flt_sectores", "flt_estados", "det_fondo_sel"):
        st.session_state.pop(k, None)
    st.query_params.clear()


# Fund filter
fondos_disponibles = sorted(df_base["nombrefondo"].unique().tolist())
default_fondos = [f for f in _qp_list("f") if f in fondos_disponibles]
filtro_fondos = st.sidebar.multiselect(
    _labeled("Fondos", "flt_fondos", default_fondos, "seleccionado", "seleccionados"),
    fondos_disponibles, default=default_fondos, key="flt_fondos",
)

# Department filter
departamentos_disponibles = sorted(df_base["nombredepartamento"].unique().tolist())
default_deptos = [d for d in _qp_list("d") if d in departamentos_disponibles]
filtro_departamentos = st.sidebar.multiselect(
    _labeled("Departamentos", "flt_deptos", default_deptos,
             "seleccionado", "seleccionados"),
    departamentos_disponibles, default=default_deptos, key="flt_deptos",
)

# Entity filter (cascading)
if filtro_departamentos:
    entidades_pool = df_base[df_base["nombredepartamento"].isin(filtro_departamentos)]
else:
    entidades_pool = df_base
entidades_disponibles = sorted(entidades_pool["nombreentidad"].unique().tolist())
if "flt_entidades" not in st.session_state:
    st.session_state["flt_entidades"] = [
        e for e in _qp_list("e") if e in entidades_disponibles
    ]
else:
    st.session_state["flt_entidades"] = [
        e for e in st.session_state["flt_entidades"] if e in entidades_disponibles
    ]
filtro_entidades = st.sidebar.multiselect(
    _labeled("Entidades", "flt_entidades",
             st.session_state["flt_entidades"],
             "seleccionada", "seleccionadas"),
    entidades_disponibles, key="flt_entidades",
)

# Vigencia filter — only shown when the data actually spans more than one
# vigencia. The live dataset is a single vigencia ("2025 - 2026"), so the control
# is dead weight; this guard hides it now yet revives it automatically if the
# source ever gains vigencias.
if "vigencia" in df_base.columns and df_base["vigencia"].nunique() > 1:
    vigencias_disponibles = sorted(df_base["vigencia"].unique().tolist())
    vig_strs = {str(v): v for v in vigencias_disponibles}
    default_vigencias = [vig_strs[v] for v in _qp_list("v") if v in vig_strs]
    filtro_vigencias = st.sidebar.multiselect(
        _labeled("Vigencias", "flt_vigencias", default_vigencias,
                 "seleccionada", "seleccionadas"),
        vigencias_disponibles, default=default_vigencias, key="flt_vigencias",
    )
else:
    filtro_vigencias = []

busqueda_texto = st.sidebar.text_input(
    "Buscar entidad", value=qp.get("q", ""), placeholder="Nombre parcial...",
)

with st.sidebar:
    st.markdown(f'<div style="margin-top: 1rem; border-top: 1px solid {PALETTE["border"]}; padding-top: 1rem;"></div>',
                unsafe_allow_html=True)
    if st.button("Actualizar datos", width="stretch"):
        load_data.clear()
        st.rerun()
    st.button("Limpiar filtros", width="stretch",
              on_click=_clear_filters, key="clear_sidebar")

# Sync URL query params
new_qp = {}
if filtro_fondos:
    new_qp["f"] = "|".join(filtro_fondos)
if filtro_vigencias:
    new_qp["v"] = "|".join(str(v) for v in filtro_vigencias)
if filtro_departamentos:
    new_qp["d"] = "|".join(filtro_departamentos)
if filtro_entidades:
    new_qp["e"] = "|".join(filtro_entidades)
if busqueda_texto:
    new_qp["q"] = busqueda_texto
st.query_params.clear()
if new_qp:
    st.query_params.update(new_qp)

# --- Apply filters ---
df_filtrado = df_base.copy()
if filtro_fondos:
    df_filtrado = df_filtrado[df_filtrado["nombrefondo"].isin(filtro_fondos)]
if filtro_vigencias and "vigencia" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["vigencia"].isin(filtro_vigencias)]
if filtro_departamentos:
    df_filtrado = df_filtrado[df_filtrado["nombredepartamento"].isin(filtro_departamentos)]
if filtro_entidades:
    df_filtrado = df_filtrado[df_filtrado["nombreentidad"].isin(filtro_entidades)]
if busqueda_texto:
    df_filtrado = df_filtrado[
        df_filtrado["nombreentidad"].str.contains(busqueda_texto, case=False, na=False)
    ]

# --- Page header ---
st.markdown(
    f"""
    <div class="dsgr-header">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;">
            <div>
                <h1>Dashboard SGR</h1>
                <div class="subtitle">Resumen ejecutivo &middot; Sistema General de Regalias</div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span class="dsgr-pill">{len(df_filtrado):,} registros</span>
                <span class="dsgr-pill">Consultado: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if len(df_filtrado) == 0:
    st.warning(
        "Ningún registro coincide con los filtros actuales. Las vistas de asignaciones "
        "(Resumen, Territorio, Detalles) aparecerán vacías; la pestaña Proyectos sigue "
        "disponible. Ajusta o limpia los filtros en la barra lateral."
    )
    st.button("Limpiar filtros", on_click=_clear_filters, key="clear_inline")

# --- Load proyectos once (shared by Territorio + Proyectos tabs) ---
# st.tabs renders every tab body each rerun, so proyectos loads regardless of
# the active tab anyway; loading here lets both tabs reuse one cached fetch.
with st.spinner("Cargando proyectos SGR..."):
    proyectos_result = load_proyectos()

if proyectos_result is not None and not proyectos_result[0].empty:
    df_proyectos_full, proyectos_rows = proyectos_result
else:
    df_proyectos_full, proyectos_rows = None, 0


def _filter_proyectos_by_side(df):
    """Apply the sidebar department filter to a proyectos frame using the
    normalized department key (accent/alias-aware) so depto names that differ
    between datasets (VALLE DEL CAUCA vs VALLE, etc.) still match."""
    if df is None:
        return None
    if filtro_departamentos and "departamento" in df.columns:
        keys = {norm_dept(d) for d in filtro_departamentos}
        return df[df["departamento"].map(norm_dept).isin(keys)].copy()
    return df.copy()


df_proy_side = _filter_proyectos_by_side(df_proyectos_full)
# Warn when a department selection silently yields zero projects (a join miss).
if filtro_departamentos and df_proy_side is not None and len(df_proy_side) == 0 \
        and df_proyectos_full is not None and not df_proyectos_full.empty:
    st.info("Los departamentos seleccionados no tienen proyectos en el dataset de proyectos.")

# --- Load giros/pagos once (shared by the Flujo de caja tab) ---
with st.spinner("Cargando giros y pagos SGR..."):
    giros_result = load_giros()

if giros_result is not None and not giros_result[0].empty:
    df_giros_full, giros_rows = giros_result
else:
    df_giros_full, giros_rows = None, 0


def _filter_giros_by_side(df):
    """Apply the sidebar fondo / departamento / entidad / búsqueda filters to a
    giros frame. Giros shares g4qj's exact naming (entity names match byte-for-byte
    — suffix and all, verified 100% overlap), so .isin matches across both datasets
    and the entidad filter stays consistent with the rest of the dashboard."""
    if df is None:
        return None
    out = df
    if filtro_fondos:
        out = out[out["nombrefondo"].isin(filtro_fondos)]
    if filtro_departamentos:
        out = out[out["nombredepartamento"].isin(filtro_departamentos)]
    if filtro_entidades:
        out = out[out["nombreentidad"].isin(filtro_entidades)]
    if busqueda_texto:
        out = out[out["nombreentidad"].str.contains(busqueda_texto, case=False, na=False)]
    return out.copy()


df_giros = _filter_giros_by_side(df_giros_full)

tab_resumen, tab_flujo, tab_territorio, tab_detalles, tab_proyectos = st.tabs(
    ["Resumen", "Flujo de caja", "Territorio", "Detalles", "Proyectos"]
)

# ===== TAB 1: RESUMEN EJECUTIVO =====
with tab_resumen:
    # Top KPIs
    presupuesto_total = df_filtrado["presupuestosgrinversion"].sum()
    aprobado_total = df_filtrado["recursosaprobadosasignadosspgr"].sum()
    saldo_total = df_filtrado["SALDO_PENDIENTE"].sum()
    pct_ejecucion = (aprobado_total / presupuesto_total * 100) if presupuesto_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_card("Presupuesto", format_currency(presupuesto_total)),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("Recursos aprobados", format_currency(aprobado_total)),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card("Saldo pendiente", format_currency(saldo_total)),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card("% Ejecucion", f"{pct_ejecucion:.1f}%"),
                    unsafe_allow_html=True)

    # Honest reconciliation: the headline KPIs sum the full frame, but every
    # territorial ranking below drops the OTROS / sin-ubicación catch-all bolsas
    # (~44% of the budget). Make that gap explicit so the numbers reconcile.
    _catchall_mask = (
        df_filtrado["nombredepartamento"].astype(str).str.upper().str.strip()
        .isin(CATCHALL_NAMES)
    )
    terr_pres = df_filtrado.loc[~_catchall_mask, "presupuestosgrinversion"].sum()
    oculto = presupuesto_total - terr_pres
    if oculto > 0 and presupuesto_total > 0:
        st.caption(
            f"Del presupuesto total, **{format_currency_md(terr_pres)}** está "
            f"territorializado (con departamento asignado). Los **{format_currency_md(oculto)}** "
            f"restantes ({oculto / presupuesto_total * 100:.0f}%) están en bolsas "
            f"OTROS / sin ubicación y no aparecen en los rankings por departamento."
        )

    # Hero chart: presupuesto apilado por departamento
    st.markdown(section_title("Presupuesto y saldo pendiente por departamento"),
                unsafe_allow_html=True)
    hero_fig = create_presupuesto_vs_saldo_chart(df_filtrado, top_n=10)
    if hero_fig:
        st.plotly_chart(hero_fig, width="stretch")
    else:
        st.info("No hay datos suficientes para generar el chart.")

    # Secondary row: bottom-5 ejecucion · donut
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.markdown(section_title("Menor ejecucion"), unsafe_allow_html=True)
        bottom_fig = create_bottom_ejecucion_chart(df_filtrado, bottom_n=5)
        if bottom_fig:
            st.plotly_chart(bottom_fig, width="stretch")
        else:
            st.caption("Sin datos.")
    with col_right:
        st.markdown(section_title("Distribucion por fondo"), unsafe_allow_html=True)
        pie_chart = create_fondo_pie_chart(df_filtrado)
        if pie_chart:
            st.plotly_chart(pie_chart, width="stretch")

    # Download CTA
    st.markdown(
        f'<div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid {PALETTE["border"]};"></div>',
        unsafe_allow_html=True,
    )
    excel_data = convert_df_to_excel(df_filtrado)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    c_dl, c_pad = st.columns([1, 2])
    with c_dl:
        st.download_button(
            label="Descargar datos filtrados (Excel)",
            data=excel_data,
            file_name=f"SGR_datos_filtrados_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
        )
    with c_pad:
        st.markdown(
            f'<div style="padding: 0.5rem 0; color: {PALETTE["text_muted"]}; font-size: 0.85rem;">'
            f'Para analisis detallado, tabla completa y mapas, ver la pestana <b>Detalles</b>.'
            f'</div>',
            unsafe_allow_html=True,
        )

# ===== TAB: FLUJO DE CAJA (giros/pagos e624-d9uy) =====
with tab_flujo:
    st.caption(
        "Fuente: giros y pagos SGR (dataset `e624-d9uy`), misma vigencia 2025-26 y mismo "
        "grano (fondo / departamento / entidad) que las asignaciones — el presupuesto "
        "reconcilia con el Resumen. Muestra el **desembolso real**: del presupuesto, cuánto "
        "se recaudó, cuánto se aprobó y cuánto efectivamente se **pagó**; el resto queda en caja."
    )
    if df_giros is None or df_giros.empty:
        st.warning("No hay datos de giros y pagos con los filtros actuales.")
    else:
        presupuesto_g = df_giros["presupuestosgrinversion"].sum()
        recaudo = df_giros["valorrecaudo"].sum()
        aprobado_g = df_giros["recursosaprobadosasignadosspgr"].sum()
        pagado = df_giros["totalpagado"].sum()
        caja = df_giros["saldocaja"].sum()
        pct_pagado = (pagado / recaudo * 100) if recaudo > 0 else 0

        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.markdown(kpi_card("Recaudo", format_currency(recaudo)), unsafe_allow_html=True)
        with g2:
            st.markdown(kpi_card("Aprobado", format_currency(aprobado_g)), unsafe_allow_html=True)
        with g3:
            st.markdown(kpi_card("Pagado", format_currency(pagado)), unsafe_allow_html=True)
        with g4:
            st.markdown(kpi_card("Saldo en caja", format_currency(caja)), unsafe_allow_html=True)

        st.caption(
            f"**Solo el {pct_pagado:.0f}% de lo recaudado se ha pagado.** "
            f"Quedan {format_currency_md(caja)} en caja sin ejecutar."
        )

        # Magnitudes (NOT a funnel): aprobado is accumulated/cross-vigency and can
        # exceed recaudo, so independent bars are honest and filter-robust.
        st.markdown(section_title("Presupuesto, recaudo, aprobado y pago"),
                    unsafe_allow_html=True)
        st.caption(
            "Magnitudes comparadas (el % es respecto al presupuesto). **No es una "
            "cascada estricta**: el *aprobado* es acumulado e incluye compromisos de "
            "vigencias anteriores, por lo que puede superar al recaudo y no es un "
            f"subconjunto de él. La señal sólida: de lo recaudado, **solo el "
            f"{pct_pagado:.0f}%** se ha pagado."
        )
        flujo_fig = create_giros_flujo_chart([
            ("Presupuesto", presupuesto_g), ("Recaudo", recaudo),
            ("Aprobado", aprobado_g), ("Pagado", pagado),
        ])
        if flujo_fig:
            st.plotly_chart(flujo_fig, width="stretch")

        # Honest note: how much of the idle cash sits in national OTROS bolsas.
        cat_g = (df_giros["nombredepartamento"].astype(str).str.upper().str.strip()
                 .isin(CATCHALL_NAMES))
        caja_otros = df_giros.loc[cat_g, "saldocaja"].sum()
        if caja > 0 and caja_otros > 0:
            st.caption(
                f"De los {format_currency_md(caja)} en caja, {format_currency_md(caja_otros)} "
                f"({caja_otros / caja * 100:.0f}%) están en bolsas nacionales OTROS / sin "
                f"territorializar."
            )

        # Where is the cash stuck — by department.
        st.markdown(section_title("¿Dónde está la plata en caja?"), unsafe_allow_html=True)
        st.caption(
            "Top departamentos por saldo en caja: lo **pagado** (azul) y lo que sigue "
            "**en caja** (ámbar), lado a lado. Son cifras reportadas por separado — el "
            "saldo en caja no es exactamente recaudo menos pagado."
        )
        dept_fig = create_giros_dept_chart(df_giros, top_n=10)
        if dept_fig:
            st.plotly_chart(dept_fig, width="stretch")
        else:
            st.caption("Sin departamentos territorializados con saldo en caja en la selección.")

        # Download
        excel_g = convert_df_to_excel(df_giros)
        ts_g = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="Descargar giros y pagos (Excel)",
            data=excel_g,
            file_name=f"SGR_giros_{ts_g}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_giros",
        )
        st.caption(
            f"Total filas cargadas: {giros_rows:,}  ·  "
            f"Fuente: datos.gov.co (giros y pagos SGR, e624-d9uy)"
        )


# ===== TAB: TERRITORIO (cross-dataset value) =====
# Analyst-chosen thresholds (single source of truth for both the logic and the
# captions so they never drift apart).
GAP_PP = 20          # paying-ahead: financiera - física, en puntos porcentuales
ZOMBIE_YEAR = 2020   # zombie: proyectos formulados antes de este año BPIN

with tab_territorio:
    st.caption(
        "Cruce de las dos fuentes: **presupuesto asignado 2025-26** (asignaciones por fondo) "
        "frente a la **cartera de proyectos** que se ejecuta en el territorio (DNP-ProyectosSGR, "
        "histórico). Son horizontes distintos —el presupuesto es la nueva vigencia; los proyectos "
        "son el acumulado—, leelos como *cuánta plata nueva llega vs. qué capacidad de ejecución "
        "tiene ese territorio*."
    )

    if df_proy_side is None or df_proy_side.empty:
        st.warning("No hay datos de proyectos para el cruce territorial con los filtros actuales.")
    else:
        terr = territorio_join(df_filtrado, df_proy_side)
        # Benchmark reference is the TRUE national average (full portfolio,
        # territorialized, project-grain) so it stays fixed under a depto filter.
        nat_fis, nat_fin = national_execution(df_proyectos_full)
        pa = paying_ahead(df_proy_side, gap_pp=GAP_PP)
        zb = zombies(df_proy_side, before_year=ZOMBIE_YEAR)

        if terr.empty:
            st.warning("Sin departamentos con presupuesto y proyectos para cruzar.")
        else:
            # Distinct (project-grain) active set within the territorialized selection.
            act_terr = territorialize(df_proy_side)
            act_terr = act_terr[act_terr["estado"] == ESTADO_EN_EJECUCION].drop_duplicates("codigobpin")
            # Alerts: union of distinct flagged projects (some are both).
            n_alertas = len(pa.index.union(zb.index))

            # --- KPIs ---
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.markdown(kpi_card("Departamentos", f"{len(terr)}"), unsafe_allow_html=True)
            with k2:
                st.markdown(
                    kpi_card("Presup. territorializado", format_currency(terr["presupuesto"].sum())),
                    unsafe_allow_html=True,
                )
            with k3:
                st.markdown(
                    kpi_card("Proyectos activos", f"{len(act_terr):,}"),
                    unsafe_allow_html=True,
                )
            with k4:
                st.markdown(kpi_card("Alertas de auditoría", f"{n_alertas:,}"), unsafe_allow_html=True)

            # --- Honest disclosure of what the cross leaves out ---
            total_pto = df_filtrado["presupuestosgrinversion"].sum()
            terr_pto = terr["presupuesto"].sum()
            pct_excl = ((total_pto - terr_pto) / total_pto * 100) if total_pto else 0
            excl_proy = df_proy_side[~df_proy_side.index.isin(territorialize(df_proy_side).index)]
            n_excl = excl_proy["codigobpin"].nunique()
            v_excl = excl_proy.drop_duplicates("codigobpin")["valortotal"].sum()
            st.caption(
                f"Territorializa **{format_currency_md(terr_pto)}** de {format_currency_md(total_pto)} del "
                f"presupuesto ({pct_excl:.0f}% queda en bolsas no territorializables: OTROS / corporaciones "
                f"/ sin ubicación). Del lado de proyectos se excluyen {n_excl:,} sin departamento "
                f"identificable ({format_currency_md(v_excl)}); sí cuentan en la pestaña Proyectos."
            )

            # --- Hero: money-in vs delivery ---
            st.markdown(section_title("Plata asignada vs. ejecución en el territorio"),
                        unsafe_allow_html=True)
            st.caption(
                "Cada burbuja es un departamento · Eje X: presupuesto 2025-26 · Eje Y: ejecución "
                "financiera promedio de sus proyectos activos · Tamaño: valor acumulado de la cartera "
                "activa (todas las vigencias; proyectos multi-departamento cuentan en cada territorio). "
                "Abajo-derecha (mucha plata nueva, baja ejecución) = vigilar."
            )
            sc = create_territorio_scatter(terr, nat_fin)
            if sc:
                st.plotly_chart(sc, width="stretch")

            # --- Decision table ---
            st.markdown(section_title("Tabla de decisión por departamento"), unsafe_allow_html=True)
            tbl = terr.copy()
            # Nullable Float64 so departments with no active projects render blank
            # (not 'nan') in the execution/delta columns.
            for c in ["ejec_fis", "ejec_fin"]:
                tbl[c] = tbl[c].astype("Float64")
            tbl["delta_nac"] = (tbl["ejec_fin"] - nat_fin).astype("Float64")
            no_active = tbl["n_activos"] == 0
            tbl.loc[no_active, ["ejec_fis", "ejec_fin", "delta_nac"]] = pd.NA
            tbl = tbl[[
                "depto", "presupuesto", "aprobado", "n_proy", "n_activos",
                "valor_activos", "ejec_fis", "ejec_fin", "delta_nac", "n_desaprobados",
            ]]
            st.dataframe(
                tbl, hide_index=True, width="stretch", height=430,
                column_config={
                    "depto": st.column_config.Column("Departamento"),
                    "presupuesto": st.column_config.NumberColumn("Presupuesto 25-26", format="dollar"),
                    "aprobado": st.column_config.NumberColumn("Aprobado", format="dollar"),
                    "n_proy": st.column_config.NumberColumn("Proyectos", format="%d"),
                    "n_activos": st.column_config.NumberColumn("Activos", format="%d"),
                    "valor_activos": st.column_config.NumberColumn("Valor en ejecución", format="dollar"),
                    "ejec_fis": st.column_config.NumberColumn("% Físico", format="%.0f%%"),
                    "ejec_fin": st.column_config.NumberColumn("% Financiero", format="%.0f%%"),
                    "delta_nac": st.column_config.NumberColumn("vs Nacional", format="%+.0f pp",
                        help="Puntos de ejecución financiera (activos) frente al promedio nacional"),
                    "n_desaprobados": st.column_config.NumberColumn("Desaprob.", format="%d"),
                },
            )

            # --- Benchmark vs national ---
            st.markdown(section_title("Ejecución vs. promedio nacional"), unsafe_allow_html=True)
            st.caption(
                f"Promedio simple por proyecto (no ponderado por valor). Referencia nacional: "
                f"{nat_fin:.0f}% financiera · {nat_fis:.0f}% física (proyectos activos)."
            )
            bm = create_benchmark_chart(terr, nat_fin)
            if bm:
                st.plotly_chart(bm, width="stretch")

            # --- Audit red-flag panels ---
            st.markdown(section_title("Alertas de auditoría"), unsafe_allow_html=True)
            st.caption(
                f"Umbrales elegidos por el analista (ajustables): brecha financiera−física > {GAP_PP} pp · "
                f"proyectos formulados antes de {ZOMBIE_YEAR}. Cifras a nivel de proyecto único."
            )

            # 1) Paying ahead of delivery
            st.markdown(
                f'<div style="color:{PALETTE["primary_dark"]}; font-weight:600; margin:0.5rem 0;">'
                f'Se paga por delante de la obra</div>',
                unsafe_allow_html=True,
            )
            if pa.empty:
                st.caption("Sin proyectos con la ejecución financiera muy por delante de la física.")
            else:
                st.caption(
                    f"**{len(pa):,}** proyectos en ejecución con la financiera más de {GAP_PP} pp por encima "
                    f"de la física ({format_currency_md(pa['valortotal'].sum())} en valor total de los proyectos "
                    f"señalados) — candidatos prioritarios de auditoría. Top 20 por valor:"
                )
                pa_cols = [c for c in [
                    "codigobpin", "nombre", "departamento", "valortotal",
                    "ejecucionfisica", "ejecucionfinanciera", "gap",
                ] if c in pa.columns]
                st.dataframe(
                    pa[pa_cols].head(20), hide_index=True, width="stretch", height=360,
                    column_config={
                        "codigobpin": st.column_config.Column("BPIN"),
                        "nombre": st.column_config.Column("Proyecto"),
                        "departamento": st.column_config.Column("Departamento"),
                        "valortotal": st.column_config.NumberColumn("Valor total", format="dollar"),
                        # NumberColumn (not Progress) so values >100% read literally.
                        "ejecucionfisica": st.column_config.NumberColumn("% Físico", format="%.0f%%"),
                        "ejecucionfinanciera": st.column_config.NumberColumn("% Financiero", format="%.0f%%"),
                        "gap": st.column_config.NumberColumn("Brecha", format="%.0f pp"),
                    },
                )

            # 2) Zombie projects (stalled vintages)
            st.markdown(
                f'<div style="color:{PALETTE["primary_dark"]}; font-weight:600; margin:1rem 0 0.5rem 0;">'
                f'Proyectos zombie (formulados antes de {ZOMBIE_YEAR}, aún en ejecución)</div>',
                unsafe_allow_html=True,
            )
            if zb.empty:
                st.caption(f"Sin proyectos en ejecución formulados antes de {ZOMBIE_YEAR}.")
            else:
                st.caption(
                    f"**{len(zb):,}** proyectos formulados antes de {ZOMBIE_YEAR} siguen *en ejecución* "
                    f"({format_currency_md(zb['valortotal'].sum())} comprometidos que no terminan de aterrizar)."
                )
                zby = zombies_by_year(df_proy_side, before_year=ZOMBIE_YEAR, z=zb)
                zfig = create_zombie_year_chart(zby)
                if zfig:
                    st.plotly_chart(zfig, width="stretch")

            # 3) DESAPROBADO concentration
            st.markdown(
                f'<div style="color:{PALETTE["primary_dark"]}; font-weight:600; margin:1rem 0 0.5rem 0;">'
                f'Concentración de proyectos desaprobados</div>',
                unsafe_allow_html=True,
            )
            dby = desaprobado_by_dept(df_proy_side, top_n=10)
            if dby is None or dby.empty:
                st.caption("Sin proyectos desaprobados en la selección.")
            else:
                st.caption(
                    "Departamentos con mayor valor de proyectos desaprobados — señal de dónde falla "
                    "la formulación/aprobación y se necesita fortalecimiento de capacidades."
                )
                dfig = create_desaprobado_chart(dby)
                if dfig:
                    st.plotly_chart(dfig, width="stretch")


# ===== TAB 2: DETALLES =====
with tab_detalles:
    # --- Resumen por fondo (un fondo a la vez para evitar saturacion) ---
    st.markdown(section_title("Resumen por tipo de fondo"), unsafe_allow_html=True)
    fondos_con_datos = sorted(df_filtrado["nombrefondo"].dropna().unique().tolist())
    if not fondos_con_datos:
        st.info(
            "No hay datos en ningún fondo con los filtros actuales. "
            "Ajusta o limpia los filtros en la barra lateral."
        )
    else:
        fondo_sel = st.selectbox(
            "Ver fondo:", fondos_con_datos, key="det_fondo_sel",
            label_visibility="collapsed",
        )
        datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo_sel]
        # Classify up front: ~14 of 31 fondos are national "bolsas"/convocatorias
        # whose presupuesto lives entirely in OTROS. The shape drives both the 4th
        # KPI and the breakdown below.
        fondo_shape, fondo_stats = classify_fondo(datos_fondo)
        st.markdown(
            f'<div style="color: {PALETTE["primary_dark"]}; font-weight: 600; margin: 0.75rem 0 0.5rem 0;">{fondo_sel}</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi_card("Registros", f"{len(datos_fondo):,}"), unsafe_allow_html=True)
        with c2:
            st.markdown(
                kpi_card("Presupuesto", format_currency(datos_fondo["presupuestosgrinversion"].sum())),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                kpi_card("Aprobado",
                         format_currency(datos_fondo["recursosaprobadosasignadosspgr"].sum())),
                unsafe_allow_html=True,
            )
        with c4:
            # For national-pot funds the per-row "Pendiente" (presupuesto-aprobado)
            # is just the un-territorialized OTROS bolsa and would contradict the
            # caption below; show the territorialized approved instead (which is
            # what the breakdown actually sums to).
            if fondo_shape == "territorial":
                st.markdown(
                    kpi_card("Pendiente", format_currency(datos_fondo["SALDO_PENDIENTE"].sum())),
                    unsafe_allow_html=True,
                )
            elif fondo_shape == "pot_approved":
                st.markdown(
                    kpi_card("Aprobado territ.", format_currency(fondo_stats["aprob_terr"])),
                    unsafe_allow_html=True,
                )
            else:  # pot_empty: aprob_terr is 0 by definition; a bare "$0" next to
                # the full "Aprobado" reads as broken, so show the share instead.
                st.markdown(
                    kpi_card("Territorializado", "0%"),
                    unsafe_allow_html=True,
                )

        # Pick the breakdown metric from the fondo shape (classified above). The
        # tree drops catch-alls only for the aprobado path so its total, the
        # ranking and the caption all report the same territorialized universe.
        tree_drop_catchall = False
        if fondo_shape == "territorial":
            rank_col, rank_label = "SALDO_PENDIENTE", "Saldo pendiente"
            tree_col, tree_label = "presupuestosgrinversion", "Presupuesto"
        elif fondo_shape == "pot_approved":
            rank_col, rank_label = "recursosaprobadosasignadosspgr", "Recursos aprobados"
            tree_col, tree_label = "recursosaprobadosasignadosspgr", "Recursos aprobados"
            tree_drop_catchall = True
            gap = fondo_stats["aprob_total"] - fondo_stats["aprob_terr"]
            detalle_aprob = (
                f" ({format_currency_md(fondo_stats['aprob_terr'])} de "
                f"{format_currency_md(fondo_stats['aprob_total'])} aprobados; el resto sigue "
                f"en la bolsa nacional)" if gap > 0 else ""
            )
            st.caption(
                f"Este fondo opera como **bolsa nacional / convocatoria**: su presupuesto "
                f"({format_currency_md(fondo_stats['pres_total'])}) figura sin territorializar "
                f"(bolsa OTROS). El desglose de abajo usa los **recursos aprobados asignados "
                f"por departamento**{detalle_aprob}."
            )
        else:  # pot_empty
            rank_col = rank_label = tree_col = tree_label = None
            st.caption(
                f"Este fondo opera como **bolsa nacional**: tanto el presupuesto "
                f"({format_currency_md(fondo_stats['pres_total'])}) como los recursos aprobados "
                f"figuran sin territorializar (sin departamento). No hay desglose territorial "
                f"para este fondo; ver la tabla de datos abajo."
            )

        if fondo_shape != "pot_empty":
            # --- Ranking de entidades (métrica según la forma del fondo) ---
            r1, r2 = st.columns([3, 1])
            with r1:
                st.markdown(
                    section_title(f"Top entidades por {rank_label.lower()} · {fondo_sel}"),
                    unsafe_allow_html=True,
                )
            with r2:
                top_n = st.selectbox(
                    "Mostrar:", [5, 10, 15, 20], index=1,
                    format_func=lambda n: f"Top {n}",
                    label_visibility="collapsed",
                )
            rank_fig = create_entidad_ranking_chart(
                datos_fondo, rank_col, rank_label, top_n=top_n
            )
            if rank_fig:
                st.plotly_chart(rank_fig, width="stretch")
            else:
                st.caption("Sin entidades territorializadas para rankear en este fondo.")

            # --- Distribución jerárquica (Fondo → Depto → Entidad) ---
            h1, h2 = st.columns([3, 1])
            with h1:
                st.markdown(
                    section_title(
                        f"Distribucion jerarquica ({tree_label.lower()}) · {fondo_sel}"
                    ),
                    unsafe_allow_html=True,
                )
            with h2:
                hierarchy_view = st.radio(
                    "Vista:", ["Treemap", "Sunburst"],
                    horizontal=True, label_visibility="collapsed",
                )
            if hierarchy_view == "Treemap":
                hierarchy_fig = create_treemap_chart(
                    datos_fondo, tree_col, tree_label, drop_catchall=tree_drop_catchall
                )
            else:
                hierarchy_fig = create_sunburst_chart(
                    datos_fondo, tree_col, tree_label, drop_catchall=tree_drop_catchall
                )
            if hierarchy_fig:
                st.plotly_chart(hierarchy_fig, width="stretch")
            else:
                st.caption("Sin desglose territorial para este fondo.")

        # Vigencia (solo si hay mas de una)
        vigencia_fig = create_vigencia_chart(df_filtrado)
        if vigencia_fig:
            st.markdown(section_title("Presupuesto por vigencia"), unsafe_allow_html=True)
            st.plotly_chart(vigencia_fig, width="stretch")

        # --- Tabla: filtrada por fondo seleccionado ---
        st.markdown(section_title(f"Tabla de datos · {fondo_sel}"), unsafe_allow_html=True)
        df_tabla = datos_fondo.drop(
            columns=[c for c in COLUMNS_TO_EXCLUDE if c in datos_fondo.columns]
        )
        column_config = {
            col: st.column_config.NumberColumn(COLUMN_LABELS.get(col, col), format="dollar")
            for col in MONETARY_COLUMNS
            if col in df_tabla.columns
        }
        for col in df_tabla.columns:
            if col not in column_config and col in COLUMN_LABELS:
                column_config[col] = st.column_config.Column(COLUMN_LABELS[col])
        st.dataframe(
            df_tabla, width="stretch", height=420, column_config=column_config,
            hide_index=True,
        )

        # Download del fondo seleccionado
        excel_data_2 = convert_df_to_excel(datos_fondo)
        timestamp_2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        fondo_slug = fondo_sel.replace(" ", "_").replace("-", "").replace("__", "_")[:40]
        st.download_button(
            label=f"Descargar {fondo_sel} (Excel)",
            data=excel_data_2,
            file_name=f"SGR_{fondo_slug}_{timestamp_2}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_tab2",
        )

        with st.expander("Glosario de columnas"):
            glosario = pd.DataFrame(
                [
                    {"Columna": col, "Descripcion": COLUMN_LABELS.get(col, col)}
                    for col in df_filtrado.columns
                ]
            )
            st.dataframe(glosario, hide_index=True, width="stretch")
            st.caption(
                f"Total filas cargadas: {rows_fetched:,}  ·  "
                f"Fuente: datos.gov.co (Sistema General de Regalias)"
            )

# ===== TAB 3: PROYECTOS =====
with tab_proyectos:
    st.caption(
        "Fuente complementaria: DNP-ProyectosSGR (dataset `mzgh-shtp`) — listado "
        "de proyectos aprobados SGR a nivel BPIN. Independiente de las asignaciones "
        "por fondo/vigencia del resto del dashboard."
    )

    if df_proyectos_full is None or df_proyectos_full.empty:
        st.error("No se pudieron cargar los proyectos.")
    else:
        # Reutiliza la carga compartida, ya filtrada por el departamento del sidebar
        # (con coincidencia normalizada de nombres — ver _filter_proyectos_by_side).
        df_proyectos = df_proy_side.copy() if df_proy_side is not None else df_proyectos_full.copy()

        # Filtros locales de proyectos
        fc1, fc2 = st.columns(2)
        with fc1:
            sectores_disp = sorted(
                df_proyectos["sector"].dropna().unique().tolist()
            ) if "sector" in df_proyectos.columns else []
            filtro_sectores = st.multiselect(
                "Sectores", sectores_disp, key="flt_sectores",
            )
        with fc2:
            estados_disp = sorted(
                df_proyectos["estado"].dropna().unique().tolist()
            ) if "estado" in df_proyectos.columns else []
            filtro_estados = st.multiselect(
                "Estados", estados_disp, key="flt_estados",
            )

        if filtro_sectores:
            df_proyectos = df_proyectos[df_proyectos["sector"].isin(filtro_sectores)]
        if filtro_estados:
            df_proyectos = df_proyectos[df_proyectos["estado"].isin(filtro_estados)]

        # KPIs
        total_proyectos = len(df_proyectos)
        valor_total = df_proyectos["valortotal"].sum() if "valortotal" in df_proyectos.columns else 0
        ejec_fis = df_proyectos["ejecucionfisica"].mean() if "ejecucionfisica" in df_proyectos.columns else 0
        ejec_fin = df_proyectos["ejecucionfinanciera"].mean() if "ejecucionfinanciera" in df_proyectos.columns else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(kpi_card("Proyectos", f"{total_proyectos:,}"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi_card("Valor total", format_currency(valor_total)),
                        unsafe_allow_html=True)
        with k3:
            st.markdown(
                kpi_card("Ejec. fisica promedio",
                         f"{ejec_fis:.1f}%" if total_proyectos else "—"),
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                kpi_card("Ejec. financiera promedio",
                         f"{ejec_fin:.1f}%" if total_proyectos else "—"),
                unsafe_allow_html=True,
            )

        if total_proyectos == 0:
            st.warning("No hay proyectos con los filtros seleccionados.")
        else:
            # Flags especiales
            flag_cols = []
            for col, label in [
                ("proyecto_paz", "Proyectos de Paz"),
                ("proyecto_covid", "Proyectos COVID"),
            ]:
                if col in df_proyectos.columns:
                    count = (df_proyectos[col].astype(str).str.upper() == "SI").sum()
                    if count > 0:
                        flag_cols.append((label, count))
            if "proyecto_grupo_etnico" in df_proyectos.columns:
                etnico = df_proyectos["proyecto_grupo_etnico"].astype(str)
                count_etnico = (etnico != "SIN ENFOQUE DIFERENCIAL").sum()
                if count_etnico > 0:
                    flag_cols.append(("Enfoque etnico diferencial", count_etnico))

            if flag_cols:
                st.markdown(
                    f'<div style="margin-top: 1rem; color: {PALETTE["text_muted"]}; font-size: 0.85rem;">'
                    + " · ".join([f"<b>{n:,}</b> {lbl}" for lbl, n in flag_cols])
                    + "</div>",
                    unsafe_allow_html=True,
                )

            # Sector donut + estado bar
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown(section_title("Proyectos por sector"), unsafe_allow_html=True)
                sector_fig = create_proyectos_sector_donut(df_proyectos, top_n=8)
                if sector_fig:
                    st.plotly_chart(sector_fig, width="stretch")
            with c2:
                st.markdown(section_title("Estado"), unsafe_allow_html=True)
                estado_fig = create_proyectos_estado_chart(df_proyectos)
                if estado_fig:
                    st.plotly_chart(estado_fig, width="stretch")

            # Top entidades
            st.markdown(section_title("Top 10 entidades ejecutoras por valor"),
                        unsafe_allow_html=True)
            top_ent_fig = create_proyectos_top_entidades_chart(df_proyectos, top_n=10)
            if top_ent_fig:
                st.plotly_chart(top_ent_fig, width="stretch")

            # Scatter ejecucion
            st.markdown(section_title("Ejecucion fisica vs financiera"),
                        unsafe_allow_html=True)
            exec_fig = create_proyectos_ejecucion_chart(df_proyectos)
            if exec_fig:
                st.plotly_chart(exec_fig, width="stretch")

            # Tabla
            st.markdown(section_title("Proyectos"), unsafe_allow_html=True)
            display_cols = [c for c in [
                "codigobpin", "nombre", "sector", "estado",
                "valortotal", "ejecucionfisica", "ejecucionfinanciera",
                "entidadejecutora", "departamento",
            ] if c in df_proyectos.columns]
            df_tabla_p = df_proyectos[display_cols].copy()
            col_cfg_p = {}
            if "valortotal" in df_tabla_p.columns:
                col_cfg_p["valortotal"] = st.column_config.NumberColumn("Valor total", format="dollar")
            for col, label in [
                ("ejecucionfisica", "Ejec. fisica"),
                ("ejecucionfinanciera", "Ejec. financiera"),
            ]:
                if col in df_tabla_p.columns:
                    # NumberColumn (not ProgressColumn) so executions >100% read
                    # literally instead of being silently clamped to a full bar —
                    # the >100% cases are exactly the audit signal worth seeing.
                    col_cfg_p[col] = st.column_config.NumberColumn(
                        label, format="%.1f%%",
                    )
            pretty = {
                "codigobpin": "BPIN", "nombre": "Proyecto", "sector": "Sector",
                "estado": "Estado", "entidadejecutora": "Entidad ejecutora",
                "departamento": "Departamento",
            }
            for col, label in pretty.items():
                if col in df_tabla_p.columns and col not in col_cfg_p:
                    col_cfg_p[col] = st.column_config.Column(label)
            st.dataframe(
                df_tabla_p, width="stretch", height=420,
                column_config=col_cfg_p, hide_index=True,
            )

            # Descarga
            excel_p = convert_df_to_excel(df_proyectos)
            ts_p = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="Descargar proyectos filtrados (Excel)",
                data=excel_p,
                file_name=f"SGR_proyectos_{ts_p}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_proyectos",
            )

        st.caption(f"Total proyectos cargados: {proyectos_rows:,}  ·  "
                   f"Fuente: datos.gov.co (DNP-ProyectosSGR, dataset mzgh-shtp)")

st.markdown(
    f"""
    <div class="dsgr-footer">
        Dashboard SGR &middot; Datos: <a href="https://datos.gov.co" style="color: {PALETTE['primary']}; text-decoration: none;">datos.gov.co</a>
    </div>
    """,
    unsafe_allow_html=True,
)
