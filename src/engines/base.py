"""Interfaz base del Patron Estrategia para los motores de clasificacion.

Por que usamos el Patron Estrategia (Strategy Pattern):
El reto exige comparar dos enfoques distintos (IA tradicional basada en reglas e IA
generativa) bajo una misma API y un mismo contrato de respuesta. Al definir una clase
abstracta comun (`BaseSupportEngine`), la capa de servicios (`SupportAnalyzerService`)
puede invocar `engine.analyze(message)` de forma polimorfica sin acoplarse a los
detalles internos de expresiones regulares ni al SDK de Gemini.
"""

from abc import ABC, abstractmethod

from src.schemas import AnalyzeResponse


class GenerativeEngineConfigError(Exception):
    """Error de configuracion en el motor generativo (por ejemplo, falta GEMINI_API_KEY).

    Por que vive aqui y no en `generative.py`:
    Al definir esta excepcion compartida en la interfaz base, la capa API (`src/main.py`,
    desarrollada por Mariana) puede capturarla y traducirla a HTTP 503 Service Unavailable
    sin acoplarse a la implementacion interna del SDK de Gemini (desarrollada por Alan),
    evitando ademas filtrar secretos o credenciales en las respuestas HTTP.
    """


class GenerativeEngineError(Exception):
    """Error operativo al comunicarse con el proveedor de IA o validar su salida JSON.

    Se lanza ante fallos de red, timeouts, limites de cuota (HTTP 429) o respuestas
    malformadas del modelo. La capa API la traduce de forma segura a HTTP 502 Bad Gateway
    sin exponer stacktraces crudos ni llaves privadas al cliente.
    """


class BaseSupportEngine(ABC):
    """Contrato abstracto que todo motor de analisis de soporte debe implementar."""

    @abstractmethod
    def analyze(self, message: str) -> AnalyzeResponse:
        """Analiza una solicitud de soporte y devuelve una respuesta estructurada.

        Args:
            message: Texto de la solicitud previamente validado.

        Returns:
            AnalyzeResponse: Resultado normalizado con categoria, prioridad,
                respuesta sugerida, bandera de revision humana y modo.
        """
        raise NotImplementedError
