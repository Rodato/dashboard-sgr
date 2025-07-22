# Dashboard SGR - Sistema General de Regalías

Dashboard interactivo para la visualización de datos del Sistema General de Regalías (SGR) de Colombia, utilizando datos abiertos del gobierno colombiano.

## 🌟 Características

- **Visualización Interactiva**: Mapas departamentales y municipales con datos en tiempo real
- **Filtros Dinámicos**: Filtrado por tipo de fondo, departamento y entidad ejecutora
- **Múltiples Visualizaciones**: 
  - Mapas coropléticos por departamentos
  - Mapas de puntos por municipios
  - Tablas de datos interactivas
- **Exportación**: Descarga de datos filtrados en formato Excel
- **Datos en Tiempo Real**: Conexión directa con la API de datos.gov.co

## 🚀 Instalación y Configuración

### Prerequisitos

- Python 3.7+
- pip (gestor de paquetes de Python)

### Instalación

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/Rodato/dashboard-sgr.git
   cd dashboard-sgr
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

## 🏃‍♂️ Ejecución

### Usando el script de lanzamiento
```bash
./run_dashboard.sh
```

### Usando Streamlit directamente
```bash
streamlit run dashboard_sgr.py
```

### Usando módulo de Python
```bash
python -m streamlit run dashboard_sgr.py
```

El dashboard estará disponible en `http://localhost:8501`

## 📊 Fuentes de Datos

- **API Principal**: [datos.gov.co - Dataset SGR](https://www.datos.gov.co/resource/g4qj-2p2e.json)
- **Datos Geográficos**: 
  - Coordenadas municipales: `divipola.csv`
  - Límites departamentales: GeoJSON de Colombia
- **Actualización**: Los datos se actualizan automáticamente cada hora

## 🗺️ Tipos de Visualización

### Mapa Departamental
- Visualización coroplética que muestra la distribución de recursos por departamento
- Colores más intensos indican mayor asignación de recursos
- Información detallada al hacer hover sobre cada departamento

### Mapa Municipal
- Visualización de puntos que muestra proyectos específicos por municipio
- Tamaño de los puntos proporcional al monto asignado
- Información detallada de cada proyecto en tooltips

## 📈 Métricas Disponibles

- **Valor Asignado**: Monto total de recursos asignados
- **Saldo por Ejecutar**: Recursos pendientes de ejecución
- **Número de Proyectos**: Cantidad de proyectos en el área seleccionada
- **Entidades Ejecutoras**: Número de entidades involucradas

## 🔧 Arquitectura Técnica

### Componentes Principales

1. **Carga de Datos** (`load_data()`): Cliente Socrata API con caché de 1 hora
2. **Procesamiento Geoespacial** (`load_municipios_geo()`): Enriquecimiento con coordenadas
3. **Preparación de Datos**: Agregación y transformación para visualización
4. **Visualización**: Mapas interactivos con pydeck y Streamlit

### Dependencias Clave

- **Streamlit**: Framework de aplicaciones web
- **Pydeck**: Visualizaciones de mapas 3D
- **Pandas**: Manipulación de datos
- **Requests**: Conexión a APIs
- **Plotly**: Gráficos interactivos

## 🎛️ Configuración

### Filtros de Fondos SGR
El dashboard se enfoca en los siguientes tipos de fondos:
- Asignación para la Inversión Local
- Asignación para la Inversión Local - Ambiente y Desarrollo Sostenible
- Asignaciones Directas

### Cache y Rendimiento
- TTL de caché: 1 hora para datos de API
- Optimización de consultas geoespaciales
- Carga lazy de datos geográficos

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama para feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit los cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📞 Contacto

Para preguntas, sugerencias o reportar problemas, por favor abrir un issue en este repositorio.

## 🙏 Reconocimientos

- **Datos.gov.co**: Por proporcionar acceso a los datos abiertos del SGR
- **Streamlit**: Por el excelente framework de desarrollo
- **OpenStreetMap**: Por los datos geográficos base