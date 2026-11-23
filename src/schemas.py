"""Contratos de datos y validaciones estrictas del dominio (Capa de Dominio).

Este modulo implementa los esquemas Pydantic que garantizan el cumplimiento de:
- Requerimiento 3 (API funcional): define el contrato JSON exacto que deben devolver
  ambos motores (`category`, `priority`, `response`, `requiresHumanReview`, `mode`) y
  restringe los modos permitidos a `traditional` y `generative`.
- Requerimiento 4 (Validacion y seguridad): valida todas las solicitudes entrantes
  (evitando mensajes vacios, solo espacios o fuera de rango) y valida la estructura
  de salida antes de responder al cliente.
"""

from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    """Categorias oficiales permitidas para clasificar solicitudes de soporte.

    Heredar de `(str, Enum)` permite que Pydantic serialice y valide los valores
    directamente como cadenas JSON legibles (por ejemplo, `"ACCESS"`).
    """

    ACCESS = "ACCESS"
    BUG = "BUG"
    FEATURE = "FEATURE"
    SECURITY = "SECURITY"


class Priority(str, Enum):
    """Niveles de prioridad asignables a cada solicitud de soporte."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnalysisMode(str, Enum):
    """Modos de ejecucion soportados por el endpoint `POST /api/analyze`."""

    TRADITIONAL = "traditional"
    GENERATIVE = "generative"


class AnalyzeRequest(BaseModel):
    """Esquema de entrada para las peticiones enviadas a `POST /api/analyze`.

    FastAPI utiliza este modelo para rechazar automaticamente con codigo HTTP 422
    cualquier solicitud malformada, con campos faltantes, `mode` invalido o un
    mensaje demasiado corto, demasiado largo o compuesto solo por espacios.
    """

    message: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Texto de la solicitud de soporte enviada por el usuario.",
        examples=["No puedo iniciar sesión"],
    )
    mode: AnalysisMode = Field(
        ...,
        description="Motor de analisis a utilizar: 'traditional' o 'generative'.",
        examples=["traditional"],
    )

    @field_validator("message")
    @classmethod
    def validate_non_blank_message(cls, value: str) -> str:
        """Limpia espacios extremos y rechaza mensajes vacios o triviales.

        Por que existe este validador: `min_length=3` por si solo aceptaria `"   "`
        (tres espacios). Al hacer `.strip()` primero, nos aseguramos de que existan
        al menos 3 caracteres reales visibles antes de pasar el texto a los motores.
        """
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError(
                "El campo 'message' no puede estar vacio ni contener solo espacios; "
                "debe tener al menos 3 caracteres visibles."
            )
        return cleaned


class AnalyzeResponse(BaseModel):
    """Contrato unificado de respuesta para ambos motores (Tradicional y Generativo).

    Tanto `TraditionalEngine` como `GenerativeEngine` estan obligados a devolver una
    instancia valida de este modelo, garantizando que el cliente consuma exactamente
    la misma estructura sin importar el motor elegido.
    """

    category: Category = Field(
        ...,
        description="Categoria asignada: ACCESS, BUG, FEATURE o SECURITY.",
    )
    priority: Priority = Field(
        ...,
        description="Prioridad asignada: LOW, MEDIUM, HIGH o CRITICAL.",
    )
    response: str = Field(
        ...,
        min_length=1,
        description="Respuesta sugerida para atender al usuario.",
    )
    requiresHumanReview: bool = Field(
        ...,
        description=(
            "Indica si el ticket requiere revision obligatoria por un humano "
            "(siempre true cuando la categoria es SECURITY)."
        ),
    )
    mode: AnalysisMode = Field(
        ...,
        description="Modo con el que se proceso la solicitud.",
    )
