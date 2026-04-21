import pandas as pd
import streamlit as st
from datetime import datetime

from dashboard_sgr.config import (
    COLUMN_LABELS,
    COLUMNS_TO_EXCLUDE,
    FONDOS_INTERES,
    MONETARY_COLUMNS,
)
from dashboard_sgr.data import load_data
from dashboard_sgr.charts import (
    create_bottom_ejecucion_chart,
    create_fondo_pie_chart,
    create_presupuesto_vs_saldo_chart,
    create_saldo_pendiente_chart,
    create_sunburst_chart,
    create_treemap_chart,
    create_vigencia_chart,
)
from dashboard_sgr.theme import CUSTOM_CSS, PALETTE, kpi_card, section_title
from dashboard_sgr.utils import convert_df_to_excel, format_currency

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

# Vigencia filter
if "vigencia" in df_base.columns:
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
    if st.button("Actualizar datos", use_container_width=True):
        load_data.clear()
        st.rerun()

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
                <span class="dsgr-pill">Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if len(df_filtrado) == 0:
    st.warning("No se encontraron datos con los filtros seleccionados. Ajusta los filtros en la barra lateral.")
    st.stop()

tab_resumen, tab_detalles = st.tabs(["Resumen", "Detalles"])

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

    # Hero chart: presupuesto apilado por departamento
    st.markdown(section_title("Presupuesto y saldo pendiente por departamento"),
                unsafe_allow_html=True)
    hero_fig = create_presupuesto_vs_saldo_chart(df_filtrado, top_n=10)
    if hero_fig:
        st.plotly_chart(hero_fig, use_container_width=True)
    else:
        st.info("No hay datos suficientes para generar el chart.")

    # Secondary row: bottom-5 ejecucion · donut
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.markdown(section_title("Menor ejecucion"), unsafe_allow_html=True)
        bottom_fig = create_bottom_ejecucion_chart(df_filtrado, bottom_n=5)
        if bottom_fig:
            st.plotly_chart(bottom_fig, use_container_width=True)
        else:
            st.caption("Sin datos.")
    with col_right:
        st.markdown(section_title("Distribucion por fondo"), unsafe_allow_html=True)
        pie_chart = create_fondo_pie_chart(df_filtrado, FONDOS_INTERES)
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)

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
            use_container_width=True,
        )
    with c_pad:
        st.markdown(
            f'<div style="padding: 0.5rem 0; color: {PALETTE["text_muted"]}; font-size: 0.85rem;">'
            f'Para analisis detallado, tabla completa y mapas, ver la pestana <b>Detalles</b>.'
            f'</div>',
            unsafe_allow_html=True,
        )

# ===== TAB 2: DETALLES =====
with tab_detalles:
    # --- Resumen por fondo (un fondo a la vez para evitar saturacion) ---
    st.markdown(section_title("Resumen por tipo de fondo"), unsafe_allow_html=True)
    fondos_con_datos = [
        f for f in FONDOS_INTERES
        if len(df_filtrado[df_filtrado["nombrefondo"] == f]) > 0
    ]
    if fondos_con_datos:
        fondo_sel = st.selectbox(
            "Ver fondo:", fondos_con_datos, key="det_fondo_sel",
            label_visibility="collapsed",
        )
        datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo_sel]
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
            st.markdown(
                kpi_card("Pendiente", format_currency(datos_fondo["SALDO_PENDIENTE"].sum())),
                unsafe_allow_html=True,
            )
    else:
        st.info("No hay datos en ningun fondo con los filtros actuales.")
        st.stop()

    # --- Top entidades por saldo pendiente ---
    r1, r2 = st.columns([3, 1])
    with r1:
        st.markdown(section_title("Entidades con mayor saldo pendiente"),
                    unsafe_allow_html=True)
    with r2:
        top_n = st.selectbox(
            "Mostrar:", [5, 10, 15, 20], index=1,
            format_func=lambda n: f"Top {n}",
            label_visibility="collapsed",
        )
    saldo_fig = create_saldo_pendiente_chart(df_filtrado, top_n=top_n)
    if saldo_fig:
        st.plotly_chart(saldo_fig, use_container_width=True)

    # Jerarquico: filtrado por fondo seleccionado
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(section_title(f"Distribucion jerarquica · {fondo_sel}"),
                    unsafe_allow_html=True)
    with h2:
        hierarchy_view = st.radio(
            "Vista:", ["Treemap", "Sunburst"],
            horizontal=True, label_visibility="collapsed",
        )
    if hierarchy_view == "Treemap":
        hierarchy_fig = create_treemap_chart(datos_fondo)
    else:
        hierarchy_fig = create_sunburst_chart(datos_fondo)
    if hierarchy_fig:
        st.plotly_chart(hierarchy_fig, use_container_width=True)

    # Vigencia (solo si hay mas de una)
    vigencia_fig = create_vigencia_chart(df_filtrado)
    if vigencia_fig:
        st.markdown(section_title("Presupuesto por vigencia"), unsafe_allow_html=True)
        st.plotly_chart(vigencia_fig, use_container_width=True)

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
        df_tabla, use_container_width=True, height=420, column_config=column_config,
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
        st.dataframe(glosario, hide_index=True, use_container_width=True)
        st.caption(
            f"Total filas cargadas: {rows_fetched:,}  ·  "
            f"Fuente: datos.gov.co (Sistema General de Regalias)"
        )

st.markdown(
    f"""
    <div class="dsgr-footer">
        Dashboard SGR &middot; Datos: <a href="https://datos.gov.co" style="color: {PALETTE['primary']}; text-decoration: none;">datos.gov.co</a>
    </div>
    """,
    unsafe_allow_html=True,
)
