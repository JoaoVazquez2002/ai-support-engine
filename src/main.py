"""Capa API: punto de entrada HTTP del AI Support Engine (Fase 3 - Mariana).

QUÉ hace este módulo:
    Define la aplicación FastAPI con dos endpoints:
    - GET  /health           → verificación de disponibilidad del servicio.
    - POST /api/analyze      → recibe un ticket de soporte y retorna su análisis.

POR QUÉ esta capa existe (Arquitectura en Capas):
    `src/main.py` es exclusivamente responsable de:
    1. Traducir las peticiones HTTP entrantes a objetos del dominio (AnalyzeRequest).
    2. Delegar el procesamiento a `SupportAnalyzerService` (capa de servicio).
    3. Traducir los resultados del dominio a respuestas HTTP (AnalyzeResponse + JSON).
    4. Capturar excepciones de las capas inferiores y convertirlas en errores HTTP
       seguros (sin stacktraces ni credenciales) con códigos correctos:
       - 422 Unprocessable Entity → validación fallida de Pydantic.
       - 503 Service Unavailable  → falta GEMINI_API_KEY (GenerativeEngineConfigError).
       - 502 Bad Gateway          → fallo del proveedor de IA (GenerativeEngineError).

SEGURIDAD: Ningún mensaje de error expone rutas internas, variables de entorno,
    nombres de módulos ni stacktraces crudos al cliente HTTP.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Importamos las excepciones compartidas definidas por Joao en la capa base.
# Capturarlas aquí (capa API) evita que se acoplen a los detalles del SDK de Gemini.
from src.engines.base import GenerativeEngineConfigError, GenerativeEngineError

# Esquemas de dominio: validados automáticamente por FastAPI gracias a Pydantic.
from src.schemas import AnalyzeRequest, AnalyzeResponse

# Servicio que orquesta la selección de motor y las reglas transversales.
from src.services.analyzer import SupportAnalyzerService

# ---------------------------------------------------------------------------
# Configuración del logger del módulo
# ---------------------------------------------------------------------------
# Usamos el logger estándar de Python para registrar errores en el servidor
# sin filtrarlos a las respuestas HTTP del cliente.
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instancia de FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Support Engine",
    description=(
        "API REST para clasificar tickets de soporte técnico usando motores "
        "tradicional (reglas simbólicas) o generativo (Google Gemini API)."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Instancia única del servicio (stateless, compartida entre peticiones)
# ---------------------------------------------------------------------------
# Por qué una sola instancia:
#   El diseño es stateless (sin BD ni sesiones). Usar una instancia a nivel
#   de módulo permite reutilizar el `TraditionalEngine` precalentado y el
#   `GenerativeEngine` lazy sin reinicializarlos en cada petición HTTP,
#   lo que mejora la latencia sin romper la separación de responsabilidades.
_analyzer_service = SupportAnalyzerService()


# ---------------------------------------------------------------------------
# Manejadores globales de excepción
# ---------------------------------------------------------------------------

@app.exception_handler(GenerativeEngineConfigError)
async def handle_config_error(
    request: Request, exc: GenerativeEngineConfigError
) -> JSONResponse:
    """Convierte errores de configuración del motor generativo en HTTP 503.

    Por qué 503 Service Unavailable:
        La API está operativa, pero el servicio de IA generativa no puede
        atenderse porque falta configuración (GEMINI_API_KEY ausente, vacía
        o de plantilla). El cliente debe reintentar cuando el servidor esté
        configurado correctamente.
    """
    # Registramos el error real en el servidor para depuración interna.
    logger.error("Error de configuración del motor generativo: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "El motor de IA generativa no está disponible: falta configuración "
                "requerida en el servidor. Contacte al administrador del sistema."
            )
        },
    )


@app.exception_handler(GenerativeEngineError)
async def handle_engine_error(
    request: Request, exc: GenerativeEngineError
) -> JSONResponse:
    """Convierte errores operativos del proveedor de IA en HTTP 502.

    Por qué 502 Bad Gateway:
        El servidor de la API recibió la petición correctamente, pero al
        actuar como intermediario (gateway) hacia Google Gemini API recibió
        una respuesta inválida o no obtuvo respuesta alguna (timeout, cuota
        agotada, error 5xx del proveedor o JSON malformado).
    """
    logger.error("Error operativo del motor generativo: %s", exc)
    return JSONResponse(
        status_code=502,
        content={
            "detail": (
                "El proveedor de IA generativa no pudo completar la solicitud. "
                "Puede deberse a un error temporal del servicio externo, límite "
                "de cuota o problema de red. Intente nuevamente más tarde."
            )
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Verificación de disponibilidad",
    tags=["Monitoreo"],
)
async def health_check() -> dict[str, str]:
    """Endpoint de salud: confirma que el servicio está en línea.

    Returns:
        dict: ``{"status": "ok", "service": "ai-support-engine"}``

    Por qué existe:
        Los sistemas de monitoreo (load balancers, Kubernetes liveness probes,
        herramientas CI/CD) necesitan un endpoint HTTP ligero que responda 200
        para confirmar que el proceso está vivo sin ejecutar lógica de negocio.
    """
    return {"status": "ok", "service": "ai-support-engine"}


@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
    summary="Analiza un ticket de soporte",
    tags=["Análisis"],
    status_code=200,
)
async def analyze_ticket(request: AnalyzeRequest) -> AnalyzeResponse:
    """Clasifica un ticket de soporte y retorna categoría, prioridad y respuesta.

    FastAPI valida automáticamente `request` contra `AnalyzeRequest` (Pydantic).
    Si la validación falla (mensaje vacío, solo espacios, mode inválido, etc.),
    FastAPI responde con HTTP 422 Unprocessable Entity SIN llegar a esta función.

    Args:
        request: Cuerpo JSON validado con ``message`` (str) y ``mode``
                 (``"traditional"`` | ``"generative"``).

    Returns:
        AnalyzeResponse: Objeto JSON con ``category``, ``priority``, ``response``,
                         ``requiresHumanReview`` y ``mode``.

    Raises (manejadas por los exception_handlers registrados arriba):
        GenerativeEngineConfigError → HTTP 503 (falta GEMINI_API_KEY).
        GenerativeEngineError       → HTTP 502 (fallo del proveedor de IA).
    """
    # Delegamos completamente al servicio; él selecciona el motor y aplica
    # las reglas transversales (incluida la salvaguarda SECURITY).
    # Las excepciones GenerativeEngineConfigError y GenerativeEngineError
    # se propagan naturalmente y son capturadas por los exception_handlers.
    result: AnalyzeResponse = _analyzer_service.analyze(request)
    return result
