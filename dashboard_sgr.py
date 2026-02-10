import pandas as pd
import streamlit as st
from datetime import datetime

from dashboard_sgr.config import (
    API_ROW_LIMIT,
    COLUMNS_TO_EXCLUDE,
    FONDOS_INTERES,
    MONETARY_COLUMNS,
)
from dashboard_sgr.data import (
    load_colombia_geojson,
    load_data,
    load_municipios_geo,
    prepare_map_data,
)
from dashboard_sgr.charts import (
    create_departamento_distribution_chart,
    create_fondo_comparison_chart,
    create_fondo_pie_chart,
    create_kpi_metrics,
    create_treemap_chart,
    create_vigencia_chart,
)
from dashboard_sgr.maps import create_choropleth_map, create_pydeck_map
from dashboard_sgr.utils import convert_df_to_excel, format_currency

# --- Page config ---
st.set_page_config(page_title="Dashboard SGR", page_icon="📊", layout="wide")
st.title("📊 Dashboard SGR - Sistema General de Regalias")
st.markdown("---")

# --- Sidebar controls ---
st.sidebar.header("⚙️ Controles")

if st.sidebar.button("🔄 Actualizar Datos", type="primary"):
    st.cache_data.clear()
    st.rerun()

# --- Load data ---
with st.spinner("Conectando a la API y cargando datos..."):
    result = load_data()

if result is None:
    st.error("❌ No se pudieron cargar los datos. Verifica la conexion a internet y presiona 'Actualizar Datos'.")
    st.stop()

df, rows_fetched = result

if df.empty:
    st.error("❌ No se pudieron cargar los datos. Verifica la conexion a internet y presiona 'Actualizar Datos'.")
    st.stop()

municipios_geo = load_municipios_geo()
colombia_geojson = load_colombia_geojson()

# Data truncation warning
if rows_fetched > 0 and rows_fetched % API_ROW_LIMIT == 0:
    st.sidebar.warning(
        f"Se cargaron {rows_fetched:,} filas. Si existen mas datos, "
        "la API puede haber paginado multiples lotes."
    )

# --- Filter to funds of interest ---
df_base = df[df["nombrefondo"].isin(FONDOS_INTERES)].copy()

# --- Summary metrics ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Registros", f"{len(df_base):,}")
with col2:
    st.metric("Presupuesto Total", format_currency(df_base["presupuestosgrinversion"].sum()))
with col3:
    st.metric("Recursos Aprobados", format_currency(df_base["recursosaprobadosasignadosspgr"].sum()))
with col4:
    st.metric("Saldo Pendiente", format_currency(df_base["SALDO_PENDIENTE"].sum()))

st.markdown("---")

# --- Sidebar filters ---
st.sidebar.subheader("🔍 Filtros")

# Fund filter
fondos_disponibles = ["Todos"] + sorted(df_base["nombrefondo"].unique().tolist())
filtro_fondo = st.sidebar.selectbox("Seleccionar Fondo:", fondos_disponibles)

# Vigencia filter
if "vigencia" in df_base.columns:
    vigencias_disponibles = sorted(df_base["vigencia"].unique().tolist())
    filtro_vigencias = st.sidebar.multiselect("Seleccionar Vigencias:", vigencias_disponibles)
else:
    filtro_vigencias = []

# Department filter
departamentos_disponibles = sorted(df_base["nombredepartamento"].unique().tolist())
filtro_departamentos = st.sidebar.multiselect("Seleccionar Departamentos:", departamentos_disponibles)

# Entity filter (cascading: filtered by selected departments)
if filtro_departamentos:
    entidades_pool = df_base[df_base["nombredepartamento"].isin(filtro_departamentos)]
else:
    entidades_pool = df_base
entidades_disponibles = sorted(entidades_pool["nombreentidad"].unique().tolist())
filtro_entidades = st.sidebar.multiselect("Seleccionar Entidades:", entidades_disponibles)

# Text search
busqueda_texto = st.sidebar.text_input("Buscar entidad por nombre:")

# --- Apply filters ---
df_filtrado = df_base.copy()

if filtro_fondo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["nombrefondo"] == filtro_fondo]

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

# --- Filtered data display ---
st.subheader(f"📋 Datos Filtrados ({len(df_filtrado):,} registros)")

if len(df_filtrado) == 0:
    st.warning("⚠️ No se encontraron datos con los filtros seleccionados.")
    st.info("💡 Intenta ajustar los filtros para ver mas resultados.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📊 Datos y Resumen", "📈 Graficos Interactivos", "🗺️ Mapa Interactivo"])

# ===== TAB 1: Data & Summary =====
with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Presupuesto Filtrado", format_currency(df_filtrado["presupuestosgrinversion"].sum()))
    with col2:
        st.metric("Recursos Filtrados", format_currency(df_filtrado["recursosaprobadosasignadosspgr"].sum()))
    with col3:
        proyectos = pd.to_numeric(df_filtrado["numeroproyectosaprobados"], errors="coerce").fillna(0).sum()
        st.metric("Proyectos Filtrados", f"{int(proyectos):,}")

    st.subheader("📊 Resumen por Tipo de Fondo")
    for i, fondo in enumerate(FONDOS_INTERES):
        datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo]
        if len(datos_fondo) == 0:
            continue
        st.write(f"**{fondo}**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Registros", f"{len(datos_fondo):,}")
        with c2:
            st.metric("Presupuesto", format_currency(datos_fondo["presupuestosgrinversion"].sum()))
        with c3:
            st.metric("Recursos Aprobados", format_currency(datos_fondo["recursosaprobadosasignadosspgr"].sum()))
        with c4:
            st.metric("Saldo Pendiente", format_currency(datos_fondo["SALDO_PENDIENTE"].sum()))
        if i < len(FONDOS_INTERES) - 1:
            st.markdown("---")

    st.markdown("---")

    # Data table
    df_tabla = df_filtrado.drop(
        columns=[c for c in COLUMNS_TO_EXCLUDE if c in df_filtrado.columns]
    )
    df_tabla_fmt = df_tabla.copy()
    for col in MONETARY_COLUMNS:
        if col in df_tabla_fmt.columns:
            df_tabla_fmt[col] = df_tabla_fmt[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else ""
            )
    st.dataframe(df_tabla_fmt, use_container_width=True, height=400)

# ===== TAB 2: Charts =====
with tab2:
    st.header("📈 Analisis Visual de Datos SGR")

    # KPI
    kpi_fig, porcentaje = create_kpi_metrics(df_filtrado)
    if kpi_fig:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(kpi_fig, use_container_width=True)
        with c2:
            st.metric("Eficiencia de Aprobacion", f"{porcentaje:.1f}%")
            if porcentaje >= 80:
                st.success("🎯 Excelente eficiencia de aprobacion!")
            elif porcentaje >= 60:
                st.warning("⚠️ Eficiencia moderada")
            else:
                st.error("⚡ Baja eficiencia de aprobacion")

    st.markdown("---")

    # Fund comparison
    st.subheader("💰 Comparacion por Tipo de Fondo")
    fondo_chart = create_fondo_comparison_chart(df_filtrado, FONDOS_INTERES)
    if fondo_chart:
        st.plotly_chart(fondo_chart, use_container_width=True)

    # Pie + Department bar side by side
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🥧 Distribucion del Presupuesto")
        pie_chart = create_fondo_pie_chart(df_filtrado, FONDOS_INTERES)
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)

    with c2:
        top_n = st.slider("Top N Departamentos", min_value=5, max_value=20, value=10, step=5)
        st.subheader(f"🏛️ Top {top_n} Departamentos")
        dept_chart = create_departamento_distribution_chart(df_filtrado, top_n=top_n)
        if dept_chart:
            st.plotly_chart(dept_chart, use_container_width=True)

    st.markdown("---")

    # Treemap
    st.subheader("🌳 Distribucion Jerarquica")
    treemap_fig = create_treemap_chart(df_filtrado)
    if treemap_fig:
        st.plotly_chart(treemap_fig, use_container_width=True)

    # Vigencia chart (only if multiple vigencias)
    vigencia_fig = create_vigencia_chart(df_filtrado)
    if vigencia_fig:
        st.markdown("---")
        st.subheader("📅 Presupuesto por Vigencia")
        st.plotly_chart(vigencia_fig, use_container_width=True)

# ===== TAB 3: Map =====
with tab3:
    map_type = st.radio(
        "Selecciona el tipo de visualizacion:",
        ["🗺️ Mapa Departamental", "📍 Mapa Municipal"],
        horizontal=True,
    )

    if map_type == "🗺️ Mapa Departamental":
        if colombia_geojson:
            choropleth_result = create_choropleth_map(df_filtrado, colombia_geojson)
            if choropleth_result and choropleth_result[0]:
                deck_map, dept_data = choropleth_result
                st.subheader("🗺️ Mapa Departamental")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Departamentos con Datos", len(dept_data))
                with c2:
                    st.metric("Presupuesto Total", format_currency(dept_data["presupuestosgrinversion"].sum()))
                with c3:
                    st.metric("Presupuesto Promedio", format_currency(dept_data["presupuestosgrinversion"].mean()))

                st.pydeck_chart(deck_map)

                c1, c2 = st.columns([2, 1])
                with c2:
                    st.markdown("**🎨 Leyenda del Mapa:**")
                    st.markdown("🔴 **Rojo**: Mayor presupuesto")
                    st.markdown("🔵 **Azul**: Menor presupuesto")
                    st.markdown("⚫ **Gris**: Sin datos")

                with st.expander("🏆 Top 5 Departamentos por Presupuesto"):
                    top = dept_data.nlargest(5, "presupuestosgrinversion")[
                        ["nombredepartamento", "nombrefondo", "presupuestosgrinversion", "numeroproyectosaprobados"]
                    ].copy()
                    top["presupuestosgrinversion"] = top["presupuestosgrinversion"].apply(lambda x: f"${x:,.0f}")
                    top["numeroproyectosaprobados"] = top["numeroproyectosaprobados"].apply(
                        lambda x: f"{int(x):,}" if pd.notna(x) else "0"
                    )
                    top.columns = ["Departamento", "Fondo(s)", "Presupuesto", "Proyectos"]
                    st.dataframe(top, hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ No se pudo crear el mapa coropletico con los datos actuales.")
        else:
            st.error("❌ No se pudo cargar el GeoJSON de Colombia.")

    else:
        if not municipios_geo.empty:
            map_data, unmatched = prepare_map_data(df_filtrado, municipios_geo)

            if not map_data.empty:
                st.subheader("📍 Mapa Municipal")

                if unmatched > 0:
                    st.info(f"{unmatched} municipios no se pudieron geolocalizar.")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Municipios en el Mapa", len(map_data))
                with c2:
                    st.metric("Departamentos", map_data["nombredepartamento"].nunique())
                with c3:
                    st.metric("Presupuesto Promedio", format_currency(map_data["presupuestosgrinversion"].mean()))

                deck_map = create_pydeck_map(map_data)
                if deck_map:
                    st.pydeck_chart(deck_map)

                    c1, c2 = st.columns([2, 1])
                    with c2:
                        st.markdown("**🎨 Leyenda del Mapa:**")
                        st.markdown("🔴 **Rojo**: Mayor presupuesto")
                        st.markdown("🔵 **Azul**: Menor presupuesto")

                with st.expander("🏆 Top 5 Municipios por Presupuesto"):
                    top_m = map_data.nlargest(5, "presupuestosgrinversion")[
                        ["NOM_MPIO", "NOM_DPTO", "nombrefondo", "presupuestosgrinversion", "numeroproyectosaprobados"]
                    ].copy()
                    top_m["presupuestosgrinversion"] = top_m["presupuestosgrinversion"].apply(lambda x: f"${x:,.0f}")
                    top_m["numeroproyectosaprobados"] = top_m["numeroproyectosaprobados"].apply(
                        lambda x: f"{int(x):,}" if pd.notna(x) else "0"
                    )
                    top_m.columns = ["Municipio", "Departamento", "Fondo(s)", "Presupuesto", "Proyectos"]
                    st.dataframe(top_m, hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ No hay datos geograficos disponibles para los filtros seleccionados.")
        else:
            st.error("❌ No se pudo cargar el archivo de coordenadas geograficas.")

# --- Download button ---
st.markdown("---")
excel_data = convert_df_to_excel(df_filtrado)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button(
    label="📥 Descargar datos filtrados en Excel",
    data=excel_data,
    file_name=f"SGR_datos_filtrados_{timestamp}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

# --- Info expander ---
with st.expander("ℹ️ Informacion sobre los datos"):
    st.write("**Columnas disponibles:**")
    for col in df_filtrado.columns:
        st.write(f"- {col}")
    st.write(f"\n**Ultima actualizacion:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.write(f"**Total filas cargadas:** {rows_fetched:,}")
    st.write("**Fuente:** datos.gov.co - Sistema General de Regalias")

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "Dashboard SGR | Desarrollado con Streamlit | Datos de datos.gov.co"
    "</div>",
    unsafe_allow_html=True,
)
