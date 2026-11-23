"""Capa de Servicio: orquesta la selección del motor y aplica reglas transversales.

QUÉ hace este módulo:
    Define `SupportAnalyzerService`, responsable de:
    1. Recibir un `AnalyzeRequest` validado por FastAPI/Pydantic.
    2. Seleccionar el motor correcto (`TraditionalEngine` o `GenerativeEngine`)
       según el campo `mode` de la solicitud.
    3. Delegar el análisis al motor elegido (Patrón Estrategia polimórfico).
    4. Aplicar la regla transversal de seguridad: garantizar que todo resultado
       con `category == SECURITY` tenga `requiresHumanReview = True`, sin
       alterar la categoría ni la prioridad que decidió el motor.
    5. Retornar el `AnalyzeResponse` validado a la capa API (`src/main.py`).

POR QUÉ esta capa existe (Arquitectura en Capas):
    La capa de servicio separa la lógica de negocio orquestada (selección de
    motor, reglas transversales) de las preocupaciones de transporte HTTP
    (códigos de error, cabeceras) que maneja `src/main.py`. Esto hace que el
    servicio sea 100% testeable de forma unitaria sin levantar un servidor web.

IMPORTANTE: Este módulo NUNCA modifica `src/schemas.py`, `src/engines/base.py`,
    `src/engines/traditional.py` ni `src/engines/generative.py`.
"""

from src.engines.base import BaseSupportEngine
from src.engines.generative import GenerativeEngine
from src.engines.traditional import TraditionalEngine
from src.schemas import AnalysisMode, AnalyzeRequest, AnalyzeResponse, Category


class SupportAnalyzerService:
    """Servicio de análisis que aplica el Patrón Estrategia para seleccionar motores.

    Responsabilidades:
    - Instanciar `TraditionalEngine` una sola vez al crear el servicio (es ligero
      y seguro; no necesita credenciales externas).
    - Instanciar `GenerativeEngine` de forma perezosa (lazy) solo cuando se
      solicita el modo 'generative', para no bloquear el modo 'traditional'
      si falta GEMINI_API_KEY.
    - Aplicar la salvaguarda transversal SECURITY → requiresHumanReview = True.
    """

    def __init__(self) -> None:
        """Inicializa el motor tradicional en construcción; el generativo es lazy.

        Por qué el tradicional se crea aquí:
            `TraditionalEngine` solo usa regex y listas en memoria; instanciarlo
            al arrancar la aplicación precalienta sus estructuras y es inofensivo
            aunque no exista ninguna clave de API.

        Por qué el generativo NO se crea aquí:
            Siguiendo la recomendación de `docs/FASE_2_MOTOR_GENERATIVO.md` (§9),
            `GenerativeEngine.__init__` no falla aunque falte `GEMINI_API_KEY`,
            pero su uso solo tiene sentido cuando hay una clave real. Instanciarlo
            lazily en `analyze()` hace explícita esa dependencia y permite que
            `mode='traditional'` funcione en cualquier entorno sin configuración
            adicional.
        """
        # Motor tradicional: sin dependencias externas, siempre disponible.
        self._traditional_engine: TraditionalEngine = TraditionalEngine()

        # Motor generativo: se creará la primera vez que se necesite (lazy).
        # El tipo de la anotación es la clase base para mantener el polimorfismo.
        self._generative_engine: GenerativeEngine | None = None

    def _get_engine(self, mode: AnalysisMode) -> BaseSupportEngine:
        """Devuelve el motor apropiado según el modo solicitado (Patrón Estrategia).

        Args:
            mode: `AnalysisMode.TRADITIONAL` o `AnalysisMode.GENERATIVE`.

        Returns:
            BaseSupportEngine: Instancia del motor concreto lista para `analyze()`.
        """
        if mode == AnalysisMode.TRADITIONAL:
            # El motor tradicional ya está listo; lo devolvemos directamente.
            return self._traditional_engine

        # --- Instanciación lazy del motor generativo ---
        # Solo llegamos aquí cuando mode == GENERATIVE.
        # Si la clave falta o es inválida, GenerativeEngine.__init__ no falla
        # ahora; el error surge en GenerativeEngine.analyze() → _resolve_api_key(),
        # que lanza GenerativeEngineConfigError, capturado en src/main.py → 503.
        if self._generative_engine is None:
            self._generative_engine = GenerativeEngine()

        return self._generative_engine

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Analiza una solicitud de soporte y retorna el contrato unificado.

        Flujo:
            1. Selecciona el motor según `request.mode`.
            2. Llama a `engine.analyze(request.message)` de forma polimórfica.
            3. Aplica la regla transversal SECURITY → requiresHumanReview = True.
            4. Retorna el `AnalyzeResponse` validado.

        Args:
            request: Solicitud ya validada por Pydantic con `message` y `mode`.

        Returns:
            AnalyzeResponse: Resultado estructurado con todos los campos del contrato.

        Raises:
            GenerativeEngineConfigError: Propagada sin modificar desde el motor
                generativo cuando falta GEMINI_API_KEY (→ HTTP 503 en main.py).
            GenerativeEngineError: Propagada sin modificar desde el motor
                generativo ante fallos de red, timeout o respuesta inválida
                (→ HTTP 502 en main.py).
        """
        # Paso 1: selección polimórfica del motor (Patrón Estrategia)
        engine: BaseSupportEngine = self._get_engine(request.mode)

        # Paso 2: delegación del análisis al motor concreto.
        # Cualquier excepción de los motores se propaga intacta hacia main.py.
        result: AnalyzeResponse = engine.analyze(request.message)

        # Paso 3: salvaguarda transversal de seguridad.
        # Aunque GenerativeEngine ya aplica esta regla internamente, la capa
        # de servicio la refuerza como medida de defensa en profundidad para
        # cualquier motor actual o futuro que se integre al sistema.
        # NUNCA alteramos `category` ni `priority`; solo ajustamos la bandera.
        if result.category == Category.SECURITY and not result.requiresHumanReview:
            # Reconstruimos el objeto con `model_copy` para no mutar el original
            # (los modelos Pydantic v2 son inmutables por defecto).
            result = result.model_copy(update={"requiresHumanReview": True})

        # Paso 4: retorno del contrato validado a la capa API.
        return result
