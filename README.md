# Dashboard SGR

Dashboard ejecutivo para el Sistema General de Regalías (SGR) de Colombia. Consume el dataset abierto `g4qj-2p2e` de datos.gov.co y presenta una vista consolidada de presupuesto asignado, recursos aprobados y saldo pendiente por departamento, fondo y entidad ejecutora.

## Alcance

El tablero restringe la información a tres tipos de fondo del SGR:

- Asignaciones Directas
- Asignación para la Inversión Local
- Asignación para la Inversión Local — Ambiente y Desarrollo Sostenible

Para cada uno se expone presupuesto total, recursos aprobados y saldo pendiente, con la posibilidad de filtrar por departamento, entidad, vigencia y texto libre.

## Estructura del producto

El dashboard se organiza en dos pestañas:

**Resumen** — vista ejecutiva de un solo scroll.
- Cuatro tarjetas KPI: presupuesto, recursos aprobados, saldo pendiente y porcentaje de ejecución.
- Gráfico principal: top 10 departamentos con presupuesto apilado (aprobado vs. saldo pendiente) y porcentaje de ejecución por departamento.
- Callout: cinco departamentos con menor ejecución.
- Distribución del presupuesto por fondo (donut con total central).
- Botón de descarga del dataset filtrado en Excel.

**Detalles** — drill-down por fondo.
- Selector de fondo único; el resto de secciones se recalcula según la selección.
- Top N entidades con mayor saldo pendiente.
- Distribución jerárquica (Treemap / Sunburst intercambiables).
- Tabla completa con formato monetario nativo.
- Descarga del fondo seleccionado en Excel.
- Glosario de columnas.

Los filtros del sidebar (fondos, departamentos, entidades, vigencias, búsqueda) afectan ambas pestañas y se sincronizan con la URL para compartir vistas específicas.

## Arquitectura

```
dashboard_sgr.py              # Orquestador: header, sidebar, tabs
dashboard_sgr/
├── config.py                 # Constantes: API, fondos, etiquetas de columnas
├── data.py                   # Carga Socrata (paginación + retry), DANE, prep mapas
├── charts.py                 # Gráficos Plotly con paleta unificada
├── maps.py                   # Capas pydeck (disponibles, no activas)
├── theme.py                  # Paleta, CSS inyectable, helpers de layout
└── utils.py                  # Helpers de agregación, formato, exportación
data/
└── colombia.geo.json         # Límites departamentales (fallback remoto)
divipola.csv                  # Coordenadas municipales
```

- `data.load_data()` consulta la API de Socrata con cláusula `where` para traer únicamente los tres fondos de interés. Cache de 1 h vía `st.cache_data`.
- `charts.*` usa la paleta definida en `theme.PALETTE` y el helper `_currency_ticks` para que todos los ejes monetarios tengan formato consistente (`$500B`, `$1T`).
- Los filtros del sidebar se persisten en `st.query_params` (claves cortas `f`, `d`, `e`, `v`, `q`) y en `st.session_state` para permitir URLs compartibles y filtros en cascada.

## Instalación

Requiere Python 3.9 o superior.

```bash
git clone https://github.com/Rodato/dashboard-sgr.git
cd dashboard-sgr
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
python3 -m streamlit run dashboard_sgr.py
```

El dashboard queda disponible en `http://localhost:8501`. El archivo `run_dashboard.sh` ofrece el mismo arranque como script.

## Fuentes de datos

- **API**: `https://www.datos.gov.co/resource/g4qj-2p2e.json` (Socrata).
- **Límites departamentales**: `data/colombia.geo.json` local con fallback remoto a un gist público.
- **Coordenadas municipales**: `divipola.csv` (códigos DANE → lat/lon).

## Licencia

MIT. Ver el archivo `LICENSE`.
