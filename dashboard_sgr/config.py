# Socrata API
SOCRATA_DOMAIN = "www.datos.gov.co"
DATASET_ID = "g4qj-2p2e"
API_ROW_LIMIT = 5000
API_MAX_RETRIES = 3
API_RETRY_BACKOFF = 2  # seconds

# Cache
CACHE_TTL = 3600  # 1 hour in seconds

# Fund types of interest (note: double space before "AMBIENTE" matches source data)
FONDOS_INTERES = [
    "ASIGNACIONES DIRECTAS",
    "ASIGNACION PARA LA INVERSION LOCAL",
    "ASIGNACION PARA LA INVERSION LOCAL -  AMBIENTE Y DESARROLLO SOSTENIBLE",
]

# Department name mapping: SGR names -> GeoJSON names
DEPT_NAME_MAPPING = {
    "ARCHIPIÉLAGO DE SAN ANDRÉS": "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA",
    "ATLÁNTICO": "ATLANTICO",
    "BOGOTÁ D.C.": "SANTAFE DE BOGOTA D.C",
    "BOLÍVAR": "BOLIVAR",
    "BOYACÁ": "BOYACA",
    "CAQUETÁ": "CAQUETA",
    "CHOCÓ": "CHOCO",
    "CÓRDOBA": "CORDOBA",
    "GUAINÍA": "GUAINIA",
    "QUINDÍO": "QUINDIO",
    "VAUPÉS": "VAUPES",
}

# Columns to exclude from data table display
COLUMNS_TO_EXCLUDE = [
    "codigofondo",
    "codigodanedepartamento",
    "codigodaneentidad",
    "nombrebolsaregional",
]

# Monetary columns for formatting
MONETARY_COLUMNS = [
    "presupuestosgrinversion",
    "recursosaprobadosasignadosspgr",
    "SALDO_PENDIENTE",
]

# GeoJSON
GEOJSON_LOCAL_PATH = "data/colombia.geo.json"
GEOJSON_URL = (
    "https://gist.githubusercontent.com/john-guerra/"
    "43c7656821069d00dcbc/raw/be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/"
    "Colombia.geo.json"
)

# Map defaults
MAP_CENTER_LAT = 4.5709
MAP_CENTER_LON = -74.2973
DEFAULT_ZOOM = 5
MAP_STYLE = "mapbox://styles/mapbox/light-v11"
