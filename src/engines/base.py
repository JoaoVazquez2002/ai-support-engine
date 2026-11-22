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
