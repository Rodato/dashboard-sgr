import streamlit as st
import pandas as pd
import requests
from sodapy import Socrata
import io
from datetime import datetime

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

if not df.empty:
    # Mostrar información básica
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Registros", len(df))
    
    with col2:
        total_presupuesto = df['presupuestosgrinversion'].sum()
        st.metric("Presupuesto Total", f"${total_presupuesto:,.0f}")
    
    with col3:
        total_recursos = df['recursosaprobadosasignadosspgr'].sum()
        st.metric("Recursos Aprobados", f"${total_recursos:,.0f}")
    
    with col4:
        total_saldo = df['SALDO_PENDIENTE'].sum()
        st.metric("Saldo Pendiente", f"${total_saldo:,.0f}")
    
    st.markdown("---")
    
    # Filtros en el sidebar
    st.sidebar.subheader("🔍 Filtros")
    
    # Filtro por Fondo
    fondos_disponibles = ['Todos'] + sorted(df['nombrefondo'].unique().tolist())
    filtro_fondo = st.sidebar.selectbox(
        "Seleccionar Fondo:",
        fondos_disponibles
    )
    
    # Filtro por Departamento
    departamentos_disponibles = ['Todos'] + sorted(df['nombredepartamento'].unique().tolist())
    filtro_departamento = st.sidebar.selectbox(
        "Seleccionar Departamento:",
        departamentos_disponibles
    )
    
    # Filtro por Entidad
    entidades_disponibles = ['Todos'] + sorted(df['nombreentidad'].unique().tolist())
    filtro_entidad = st.sidebar.selectbox(
        "Seleccionar Entidad:",
        entidades_disponibles
    )
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if filtro_fondo != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombrefondo'] == filtro_fondo]
    
    if filtro_departamento != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombredepartamento'] == filtro_departamento]
    
    if filtro_entidad != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['nombreentidad'] == filtro_entidad]
    
    # Mostrar información de los datos filtrados
    st.subheader(f"📋 Datos Filtrados ({len(df_filtrado)} registros)")
    
    if len(df_filtrado) > 0:
        # Mostrar métricas de los datos filtrados
        col1, col2, col3 = st.columns(3)
        
        with col1:
            presupuesto_filtrado = df_filtrado['presupuestosgrinversion'].sum()
            st.metric("Presupuesto Filtrado", f"${presupuesto_filtrado:,.0f}")
        
        with col2:
            recursos_filtrado = df_filtrado['recursosaprobadosasignadosspgr'].sum()
            st.metric("Recursos Filtrados", f"${recursos_filtrado:,.0f}")
        
        with col3:
            proyectos_filtrado = df_filtrado['numeroproyectosaprobados'].astype(int).sum()
            st.metric("Proyectos Filtrados", f"{proyectos_filtrado:,}")
        
        # Mostrar tabla
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            height=400
        )
        
        # Botón de descarga
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