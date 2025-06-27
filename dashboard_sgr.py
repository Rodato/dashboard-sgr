import streamlit as st
import pandas as pd
import requests
from sodapy import Socrata
import io
from datetime import datetime
import numpy as np
import pydeck as pdk

# Configuración de la página
st.set_page_config(
    page_title="Dashboard SGR",
    page_icon="📊",
    layout="wide"
)

# Función para cargar datos desde la API
@st.cache_data(ttl=3600)  # Cache por 1 hora
def load_data():
    """Carga datos desde la API de datos abiertos de Colombia"""
    try:
        with st.spinner('Conectando a la API y cargando datos...'):
            client = Socrata("www.datos.gov.co", None)
            results = client.get("g4qj-2p2e", limit=5000)
            results_df = pd.DataFrame.from_records(results)
            
            # Procesamiento de datos (igual que en tu script)
            results_df['codigodanedepartamento'] = pd.to_numeric(results_df['codigodanedepartamento'], errors='coerce').fillna('COR01')
            results_df['codigodanedepartamento'] = results_df['codigodanedepartamento'].apply(lambda x: int(x) / 1000 if x != 'COR01' else x)
            
            results_df['codigodaneentidad'] = results_df['codigodaneentidad'].str.strip().astype(int)
            results_df['codigodaneentidad'] = results_df['codigodaneentidad'].apply(lambda x: x // 1000 if isinstance(x, int) and x % 1000 == 0 else x)
            
            results_df['presupuestosgrinversion'] = results_df['presupuestosgrinversion'].str.strip().astype(float)
            results_df['recursosaprobadosasignadosspgr'] = results_df['recursosaprobadosasignadosspgr'].str.strip().astype(float)
            results_df['SALDO_PENDIENTE'] = results_df['presupuestosgrinversion'] - results_df['recursosaprobadosasignadosspgr']
            results_df['SALDO_PENDIENTE'] = results_df['SALDO_PENDIENTE'].apply(lambda x: 0 if x < 0 else x)
            
            return results_df
            
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return pd.DataFrame()

# Función para cargar datos de municipios geolocalizados
@st.cache_data
def load_municipios_geo():
    """Carga datos de municipios con coordenadas geográficas"""
    try:
        # Leer el archivo CSV de municipios
        municipios_df = pd.read_csv('divipola.csv')
        
        # Limpiar el código de municipio para hacer el join
        municipios_df['COD_MPIO_CLEAN'] = municipios_df['COD_MPIO'].astype(str).str.replace(',', '').astype(int)
        
        return municipios_df
        
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de municipios: {str(e)}")
        return pd.DataFrame()

# Función para cargar datos geográficos de Colombia
@st.cache_data
def load_colombia_geojson():
    """Carga datos geográficos de Colombia desde una fuente online"""
    try:
        # URL del GeoJSON de departamentos de Colombia
        url_departamentos = "https://gist.githubusercontent.com/john-guerra/43c7656821069d00dcbc/raw/be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/Colombia.geo.json"
        
        response = requests.get(url_departamentos)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning("No se pudo cargar el GeoJSON de Colombia")
            return None
            
    except Exception as e:
        st.warning(f"Error al cargar GeoJSON: {str(e)}")
        return None

# Función para preparar datos para el mapa
def prepare_map_data(df_filtrado, municipios_df):
    """Prepara los datos para mostrar en el mapa"""
    if municipios_df.empty:
        return pd.DataFrame()
    
    try:
        # Agrupar datos SGR por entidad, incluyendo el nombre del fondo
        df_agrupado = df_filtrado.groupby(['codigodaneentidad', 'nombreentidad', 'nombredepartamento']).agg({
            'presupuestosgrinversion': 'sum',
            'recursosaprobadosasignadosspgr': 'sum',
            'SALDO_PENDIENTE': 'sum',
            'numeroproyectosaprobados': 'sum',
            'nombrefondo': lambda x: ', '.join(x.unique())  # Concatenar fondos únicos
        }).reset_index()
        
        # Hacer join con las coordenadas geográficas
        map_data = pd.merge(
            df_agrupado,
            municipios_df[['COD_MPIO_CLEAN', 'NOM_MPIO', 'NOM_DPTO', 'LATITUD', 'LONGITUD']],
            left_on='codigodaneentidad',
            right_on='COD_MPIO_CLEAN',
            how='inner'
        )
        
        if len(map_data) > 0:
            # Normalizar presupuesto para el color (0-255)
            min_presupuesto = map_data['presupuestosgrinversion'].min()
            max_presupuesto = map_data['presupuestosgrinversion'].max()
            
            if max_presupuesto > min_presupuesto:
                map_data['color_intensity'] = ((map_data['presupuestosgrinversion'] - min_presupuesto) / 
                                             (max_presupuesto - min_presupuesto) * 255).astype(int)
            else:
                map_data['color_intensity'] = 128
            
            # Crear colores RGB (gradiente de azul a rojo)
            map_data['color_r'] = map_data['color_intensity']
            map_data['color_g'] = 100
            map_data['color_b'] = 255 - map_data['color_intensity']
            map_data['color_a'] = 200  # Alpha (transparencia)
            
            # Crear tooltip text
            map_data['tooltip'] = map_data.apply(lambda row: 
                f"🏛️ {row['NOM_MPIO']}\n" +
                f"📍 {row['NOM_DPTO']}\n" +
                f"💰 Presupuesto: ${row['presupuestosgrinversion']:,.0f}\n" +
                f"🏦 Fondo: {row['nombrefondo']}\n" +
                f"📊 Proyectos: {int(pd.to_numeric(row['numeroproyectosaprobados'], errors='coerce'))}", axis=1
            )
        
        return map_data
        
    except Exception as e:
        st.warning(f"Error al preparar datos del mapa: {str(e)}")
        return pd.DataFrame()

# Función para preparar datos para mapa coroplético
def prepare_choropleth_data(df_filtrado):
    """Prepara datos agregados por departamento para el mapa coroplético"""
    try:
        # Agrupar por departamento
        dept_data = df_filtrado.groupby(['nombredepartamento']).agg({
            'presupuestosgrinversion': 'sum',
            'recursosaprobadosasignadosspgr': 'sum',
            'SALDO_PENDIENTE': 'sum',
            'numeroproyectosaprobados': 'sum',
            'nombrefondo': lambda x: ', '.join(x.unique())
        }).reset_index()
        
        # Normalizar nombres de departamentos para el join
        dept_data['dept_normalized'] = dept_data['nombredepartamento'].str.upper().str.strip()
        
        # Mapeo de nombres de departamentos (algunos pueden diferir)
        dept_mapping = {
            'BOGOTÁ D.C.': 'BOGOTÁ',
            'ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA': 'SAN ANDRÉS Y PROVIDENCIA',
            'VALLE DEL CAUCA': 'VALLE DEL CAUCA'
        }
        
        for old_name, new_name in dept_mapping.items():
            dept_data.loc[dept_data['dept_normalized'] == old_name, 'dept_normalized'] = new_name
        
        return dept_data
        
    except Exception as e:
        st.warning(f"Error al preparar datos coropléticos: {str(e)}")
        return pd.DataFrame()

# Función para crear mapa combinado (departamentos + municipios)
def create_combined_choropleth_map(df_filtrado, geojson_data, municipios_geo):
    """Crea un mapa que combina departamentos coropléticos y círculos de municipios"""
    if not geojson_data:
        return None
        
    try:
        # Preparar datos por departamento
        dept_data = prepare_choropleth_data(df_filtrado)
        
        # Preparar datos de municipios
        muni_data = prepare_map_data(df_filtrado, municipios_geo) if not municipios_geo.empty else pd.DataFrame()
        
        if dept_data.empty and muni_data.empty:
            return None
        
        layers = []
        
        # Layer 1: Departamentos coropléticos (fondo)
        if not dept_data.empty:
            # Normalizar presupuesto departamental para colores
            min_budget = dept_data['presupuestosgrinversion'].min()
            max_budget = dept_data['presupuestosgrinversion'].max()
            
            if max_budget > min_budget:
                dept_data['color_intensity'] = ((dept_data['presupuestosgrinversion'] - min_budget) / 
                                             (max_budget - min_budget) * 255).astype(int)
            else:
                dept_data['color_intensity'] = 128
            
            # Crear diccionario de colores por departamento
            color_dict = {}
            tooltip_dict = {}
            
            for _, row in dept_data.iterrows():
                dept_name = row['dept_normalized']
                intensity = row['color_intensity']
                
                # Color RGB suave para departamentos (más transparente)
                color_dict[dept_name] = [intensity//2 + 100, 150, 255 - intensity//2, 120]  # Más transparente
                
                # Tooltip departamental
                tooltip_dict[dept_name] = (
                    f"🏛️ DEPARTAMENTO: {row['nombredepartamento']}\n"
                    f"💰 Presupuesto Dept: ${row['presupuestosgrinversion']:,.0f}\n"
                    f"🏦 Fondos: {row['nombrefondo']}\n"
                    f"📊 Proyectos Dept: {int(pd.to_numeric(row['numeroproyectosaprobados'], errors='coerce'))}"
                )
            
            # Agregar propiedades al GeoJSON
            for feature in geojson_data['features']:
                dept_name = feature['properties'].get('NOMBRE_DPT', '').upper().strip()
                
                if dept_name in color_dict:
                    feature['properties']['fill_color'] = color_dict[dept_name]
                    feature['properties']['tooltip'] = tooltip_dict[dept_name]
                else:
                    feature['properties']['fill_color'] = [240, 240, 240, 80]  # Gris muy claro
                    feature['properties']['tooltip'] = f"🏛️ {dept_name}\n❌ Sin datos disponibles"
            
            # Layer de departamentos
            choropleth_layer = pdk.Layer(
                'GeoJsonLayer',
                data=geojson_data,
                get_fill_color='properties.fill_color',
                get_line_color=[100, 100, 100, 150],  # Bordes grises suaves
                get_line_width=1,
                pickable=True,
                auto_highlight=True,
                opacity=0.6
            )
            layers.append(choropleth_layer)
        
        # Layer 2: Municipios como círculos (encima)
        if not muni_data.empty:
            # Normalizar presupuesto municipal para colores más intensos
            min_muni_budget = muni_data['presupuestosgrinversion'].min()
            max_muni_budget = muni_data['presupuestosgrinversion'].max()
            
            if max_muni_budget > min_muni_budget:
                muni_data['color_intensity'] = ((muni_data['presupuestosgrinversion'] - min_muni_budget) / 
                                              (max_muni_budget - min_muni_budget) * 255).astype(int)
            else:
                muni_data['color_intensity'] = 128
            
            # Colores más intensos para municipios
            muni_data['color_r'] = muni_data['color_intensity']
            muni_data['color_g'] = 80
            muni_data['color_b'] = 255 - muni_data['color_intensity']
            muni_data['color_a'] = 200  # Más opaco que departamentos
            
            # Tooltip municipal más detallado
            muni_data['tooltip_muni'] = muni_data.apply(lambda row: 
                f"🏘️ MUNICIPIO: {row['NOM_MPIO']}\n" +
                f"📍 Departamento: {row['NOM_DPTO']}\n" +
                f"💰 Presupuesto Mpio: ${row['presupuestosgrinversion']:,.0f}\n" +
                f"🏦 Fondo: {row['nombrefondo']}\n" +
                f"📊 Proyectos Mpio: {int(pd.to_numeric(row['numeroproyectosaprobados'], errors='coerce'))}\n" +
                f"💸 Recursos: ${row['recursosaprobadosasignadosspgr']:,.0f}", axis=1
            )
            
            # Layer de municipios (círculos)
            municipios_layer = pdk.Layer(
                'ScatterplotLayer',
                data=muni_data,
                get_position=['LONGITUD', 'LATITUD'],
                get_color=['color_r', 'color_g', 'color_b', 'color_a'],
                get_radius=6000,  # Radio fijo
                radius_scale=1,
                radius_min_pixels=6,
                radius_max_pixels=25,
                pickable=True,
                auto_highlight=True,
                stroked=True,
                get_line_color=[255, 255, 255, 200],  # Borde blanco
                get_line_width=1
            )
            layers.append(municipios_layer)
        
        # Vista inicial centrada en Colombia
        view_state = pdk.ViewState(
            latitude=4.5709,
            longitude=-74.2973,
            zoom=5.2,
            pitch=0,
            bearing=0
        )
        
        # Tooltip combinado
        tooltip = {
            "html": "<div style='background: white; color: black; padding: 12px; border-radius: 8px; border: 1px solid #ccc; box-shadow: 0 2px 10px rgba(0,0,0,0.1);'><b>{tooltip}</b><b>{tooltip_muni}</b></div>",
            "style": {
                "fontSize": "13px",
                "fontFamily": "Arial, sans-serif",
                "whiteSpace": "pre-line",
                "maxWidth": "320px"
            }
        }
        
        # Crear deck con fondo blanco
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style='mapbox://styles/mapbox/light-v11'  # Fondo blanco/claro
        )
        
        return deck, dept_data, muni_data
        
    except Exception as e:
        st.error(f"Error al crear mapa combinado: {str(e)}")
        return None, pd.DataFrame(), pd.DataFrame()

# Función para crear el mapa con pydeck
def create_pydeck_map(map_data):
    """Crea un mapa interactivo con pydeck"""
    if map_data.empty:
        return None
    
    # Calcular centro del mapa
    center_lat = map_data['LATITUD'].mean()
    center_lon = map_data['LONGITUD'].mean()
    
    # Crear layer de círculos coloreados
    circle_layer = pdk.Layer(
        'ScatterplotLayer',
        data=map_data,
        get_position=['LONGITUD', 'LATITUD'],
        get_color=['color_r', 'color_g', 'color_b', 'color_a'],
        get_radius=8000,  # Radio en metros
        radius_scale=1,
        radius_min_pixels=8,
        radius_max_pixels=50,
        pickable=True,
        auto_highlight=True
    )
    
    # Configurar vista inicial
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=5.5,
        pitch=0,
        bearing=0
    )
    
    # Crear tooltip
    tooltip = {
        "html": "<b>{tooltip}</b>",
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "padding": "10px",
            "border-radius": "5px",
            "font-family": "Arial",
            "font-size": "12px",
            "white-space": "pre-line",
            "border": "1px solid #ccc"
        }
    }
    
    # Crear el deck
    deck = pdk.Deck(
        layers=[circle_layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/light-v11'
    )
    
    return deck

# Función para convertir DataFrame a Excel
def convert_df_to_excel(df):
    """Convierte el DataFrame a Excel para descarga"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos_SGR', float_format="%.2f")
    processed_data = output.getvalue()
    return processed_data

# Título de la aplicación
st.title("📊 Dashboard SGR - Sistema General de Regalías")
st.markdown("---")

# Sidebar para controles
st.sidebar.header("⚙️ Controles")

# Botón para actualizar datos
if st.sidebar.button("🔄 Actualizar Datos", type="primary"):
    st.cache_data.clear()
    st.rerun()

# Cargar datos
df = load_data()
municipios_geo = load_municipios_geo()
colombia_geojson = load_colombia_geojson()

if not df.empty:
    # Definir fondos de interés
    fondos_interes = [
        'ASIGNACION PARA LA INVERSION LOCAL',
        'ASIGNACION PARA LA INVERSION LOCAL - AMBIENTE Y DESARROLLO SOSTENIBLE',
        'ASIGNACIONES DIRECTAS'
    ]
    
    # Primero filtrar el DataFrame base por los fondos de interés
    df_base_filtrado = df[df['nombrefondo'].isin(fondos_interes)].copy()
    
    # Mostrar información básica (solo de los fondos de interés)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Registros", len(df_base_filtrado))
    
    with col2:
        total_presupuesto = df_base_filtrado['presupuestosgrinversion'].sum()
        st.metric("Presupuesto Total", f"${total_presupuesto:,.0f}")
    
    with col3:
        total_recursos = df_base_filtrado['recursosaprobadosasignadosspgr'].sum()
        st.metric("Recursos Aprobados", f"${total_recursos:,.0f}")
    
    with col4:
        total_saldo = df_base_filtrado['SALDO_PENDIENTE'].sum()
        st.metric("Saldo Pendiente", f"${total_saldo:,.0f}")
    
    st.markdown("---")
    
    # Filtros en el sidebar
    st.sidebar.subheader("🔍 Filtros")
    
    # Filtro por Fondo - Solo mostrar los fondos específicos
    fondos_disponibles = ['Todos'] + sorted(df_base_filtrado['nombrefondo'].unique().tolist())
    filtro_fondo = st.sidebar.selectbox(
        "Seleccionar Fondo:",
        fondos_disponibles
    )
    
    # Filtro por Departamento - basado en datos filtrados
    departamentos_disponibles = ['Todos'] + sorted(df_base_filtrado['nombredepartamento'].unique().tolist())
    filtro_departamento = st.sidebar.selectbox(
        "Seleccionar Departamento:",
        departamentos_disponibles
    )
    
    # Filtro por Entidad - basado en datos filtrados
    entidades_disponibles = ['Todos'] + sorted(df_base_filtrado['nombreentidad'].unique().tolist())
    filtro_entidad = st.sidebar.selectbox(
        "Seleccionar Entidad:",
        entidades_disponibles
    )
    
    # Aplicar filtros paso a paso
    df_filtrado = df_base_filtrado.copy()
    
    # Aplicar filtro de fondo
    if filtro_fondo != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombrefondo'] == filtro_fondo]
    
    # Aplicar filtro de departamento
    if filtro_departamento != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombredepartamento'] == filtro_departamento]
        
    # Aplicar filtro de entidad
    if filtro_entidad != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombreentidad'] == filtro_entidad]
    
    # Mostrar información de los datos filtrados
    st.subheader(f"📋 Datos Filtrados ({len(df_filtrado)} registros)")
    
    if len(df_filtrado) > 0:
        # Crear tabs para organizar el contenido
        tab1, tab2 = st.tabs(["📊 Tabla de Datos", "🗺️ Mapa Interactivo"])
        
        with tab1:
            # Mostrar métricas de los datos filtrados
            col1, col2, col3 = st.columns(3)
            
            with col1:
                presupuesto_filtrado = df_filtrado['presupuestosgrinversion'].sum()
                st.metric("Presupuesto Filtrado", f"${presupuesto_filtrado:,.0f}")
            
            with col2:
                recursos_filtrado = df_filtrado['recursosaprobadosasignadosspgr'].sum()
                st.metric("Recursos Filtrados", f"${recursos_filtrado:,.0f}")
            
            with col3:
                proyectos_filtrado = pd.to_numeric(df_filtrado['numeroproyectosaprobados'], errors='coerce').fillna(0).sum()
                st.metric("Proyectos Filtrados", f"{int(proyectos_filtrado):,}")
            
            # Mostrar tabla
            st.dataframe(
                df_filtrado,
                use_container_width=True,
                height=400
            )
        
        with tab2:
            # Selector de tipo de mapa
            map_type = st.radio(
                "Selecciona el tipo de visualización:",
                ["🗺️ Mapa Combinado (Departamentos + Municipios)", "📍 Mapa de Puntos (Solo Municipios)"],
                horizontal=True
            )
            
            if map_type == "🗺️ Mapa Combinado (Departamentos + Municipios)":
                # Mapa combinado: departamentos coropléticos + círculos municipales
                if colombia_geojson and not municipios_geo.empty:
                    combined_result = create_combined_choropleth_map(df_filtrado, colombia_geojson, municipios_geo)
                    
                    if combined_result and combined_result[0]:
                        deck_map, dept_data, muni_data = combined_result
                        
                        st.subheader("🗺️ Mapa Combinado: Departamentos y Municipios")
                        
                        # Métricas combinadas
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Departamentos", len(dept_data) if not dept_data.empty else 0)
                        with col2:
                            st.metric("Municipios", len(muni_data) if not muni_data.empty else 0)
                        with col3:
                            total_budget = (dept_data['presupuestosgrinversion'].sum() if not dept_data.empty else 0)
                            st.metric("Presupuesto Total", f"${total_budget:,.0f}")
                        with col4:
                            total_projects = (pd.to_numeric(dept_data['numeroproyectosaprobados'], errors='coerce').fillna(0).sum() if not dept_data.empty else 0)
                            st.metric("Proyectos Total", f"{int(total_projects):,}")
                        
                        # Mostrar mapa
                        st.pydeck_chart(deck_map)
                        
                        # Leyenda mejorada
                        col1, col2 = st.columns([2, 1])
                        with col2:
                            st.markdown("**🎨 Leyenda del Mapa:**")
                            st.markdown("**Departamentos (Fondo):**")
                            st.markdown("🟦 **Azul claro**: Menor presupuesto")
                            st.markdown("🟥 **Rojo claro**: Mayor presupuesto")
                            st.markdown("**Municipios (Círculos):**")
                            st.markdown("🔵 **Azul intenso**: Menor presupuesto")
                            st.markdown("🔴 **Rojo intenso**: Mayor presupuesto")
                            st.markdown("💡 **Tip**: Haz clic en departamentos o municipios")
                        
                        # Información en pestañas expandibles
                        tab_dept, tab_muni = st.tabs(["🏛️ Top Departamentos", "🏘️ Top Municipios"])
                        
                        with tab_dept:
                            if not dept_data.empty:
                                st.write("**🏆 Top 5 Departamentos por Presupuesto:**")
                                top_depts = dept_data.nlargest(5, 'presupuestosgrinversion')[
                                    ['nombredepartamento', 'nombrefondo', 'presupuestosgrinversion', 'numeroproyectosaprobados']
                                ].copy()
                                top_depts['presupuestosgrinversion'] = top_depts['presupuestosgrinversion'].apply(lambda x: f"${x:,.0f}")
                                top_depts['numeroproyectosaprobados'] = pd.to_numeric(top_depts['numeroproyectosaprobados'], errors='coerce').fillna(0).round().apply(lambda x: f"{int(x):,}")
                                top_depts.columns = ['Departamento', 'Fondo(s)', 'Presupuesto', 'Proyectos']
                                st.dataframe(top_depts, hide_index=True, use_container_width=True)
                            else:
                                st.info("No hay datos de departamentos disponibles")
                        
                        with tab_muni:
                            if not muni_data.empty:
                                st.write("**🏆 Top 5 Municipios por Presupuesto:**")
                                top_municipios = muni_data.nlargest(5, 'presupuestosgrinversion')[
                                    ['NOM_MPIO', 'NOM_DPTO', 'nombrefondo', 'presupuestosgrinversion', 'numeroproyectosaprobados']
                                ].copy()
                                top_municipios['presupuestosgrinversion'] = top_municipios['presupuestosgrinversion'].apply(lambda x: f"${x:,.0f}")
                                top_municipios['numeroproyectosaprobados'] = pd.to_numeric(top_municipios['numeroproyectosaprobados'], errors='coerce').fillna(0).round().apply(lambda x: f"{int(x):,}")
                                top_municipios.columns = ['Municipio', 'Departamento', 'Fondo(s)', 'Presupuesto', 'Proyectos']
                                st.dataframe(top_municipios, hide_index=True, use_container_width=True)
                            else:
                                st.info("No hay datos de municipios disponibles")
                    
                    else:
                        st.warning("⚠️ No se pudo crear el mapa combinado con los datos actuales.")
                        st.info("💡 Verifica que haya datos disponibles para los filtros seleccionados.")
                
                else:
                    st.error("❌ No se pudieron cargar los datos geográficos necesarios.")
                    st.info("🌐 Verificando conexión para cargar mapas base y archivo divipola.csv...")
            
            else:
                # Mapa de puntos (código existente)
                if not municipios_geo.empty:
                    map_data = prepare_map_data(df_filtrado, municipios_geo)
                    
                    if not map_data.empty:
                        st.subheader("📍 Mapa de Puntos por Municipios")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Municipios en el Mapa", len(map_data))
                        with col2:
                            st.metric("Departamentos", map_data['nombredepartamento'].nunique())
                        with col3:
                            avg_presupuesto = map_data['presupuestosgrinversion'].mean()
                            st.metric("Presupuesto Promedio", f"${avg_presupuesto:,.0f}")
                        
                        # Crear y mostrar el mapa de puntos
                        deck_map = create_pydeck_map(map_data)
                        if deck_map:
                            st.pydeck_chart(deck_map)
                            
                            # Leyenda del mapa
                            col1, col2 = st.columns([2, 1])
                            with col2:
                                st.markdown("**🎨 Leyenda del Mapa:**")
                                st.markdown("🔴 **Rojo**: Mayor presupuesto")
                                st.markdown("🔵 **Azul**: Menor presupuesto")
                                st.markdown("💡 **Tip**: Pasa el mouse sobre los círculos")
                        
                        # Top 5 municipios
                        with st.expander("🏆 Top 5 Municipios por Presupuesto"):
                            top_municipios = map_data.nlargest(5, 'presupuestosgrinversion')[
                                ['NOM_MPIO', 'NOM_DPTO', 'nombrefondo', 'presupuestosgrinversion', 'numeroproyectosaprobados']
                            ].copy()
                            top_municipios['presupuestosgrinversion'] = top_municipios['presupuestosgrinversion'].apply(lambda x: f"${x:,.0f}")
                            top_municipios['numeroproyectosaprobados'] = pd.to_numeric(top_municipios['numeroproyectosaprobados'], errors='coerce').fillna(0).round().apply(lambda x: f"{int(x):,}")
                            top_municipios.columns = ['Municipio', 'Departamento', 'Fondo(s)', 'Presupuesto', 'Proyectos']
                            st.dataframe(top_municipios, hide_index=True, use_container_width=True)
                    
                    else:
                        st.warning("⚠️ No hay datos geográficos disponibles para los filtros seleccionados.")
                        st.info("💡 Intenta ajustar los filtros o verifica que los códigos de entidad coincidan.")
                
                else:
                    st.error("❌ No se pudo cargar el archivo de coordenadas geográficas.")
                    st.info("📁 Asegúrate de que el archivo 'divipola.csv' esté en el directorio del proyecto.")
        
        # Botón de descarga (fuera de los tabs)
        st.markdown("---")
        excel_data = convert_df_to_excel(df_filtrado)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SGR_datos_filtrados_{timestamp}.xlsx"
        
        st.download_button(
            label="📥 Descargar datos filtrados en Excel",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
        # Información adicional
        with st.expander("ℹ️ Información sobre los datos"):
            st.write("**Columnas disponibles:**")
            for col in df_filtrado.columns:
                st.write(f"- {col}")
            
            st.write(f"\n**Última actualización:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.write("**Fuente:** datos.gov.co - Sistema General de Regalías")
    
    else:
        st.warning("⚠️ No se encontraron datos con los filtros seleccionados.")
        st.info("💡 Intenta ajustar los filtros para ver más resultados.")

else:
    st.error("❌ No se pudieron cargar los datos. Verifica la conexión a internet y presiona 'Actualizar Datos'.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Dashboard SGR | Desarrollado con Streamlit | Datos de datos.gov.co
    </div>
    """, 
    unsafe_allow_html=True
)