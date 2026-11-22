"""Cascaron (stub) del motor de IA Generativa para desbloqueo paralelo del equipo.

Que hace este archivo actualmente:
Define la estructura minima de la clase `GenerativeEngine` heredando de
`BaseSupportEngine` para que la capa de servicios (`src/services/analyzer.py`)
pueda importarla desde ya sin errores de importacion.

Por que existe este stub en Fase 1:
Permite que el equipo trabaje en paralelo sin conflictos de Git:
- Mariana (`feat/mariana-api-seguridad`) puede importar `GenerativeEngine` en el servicio
  orquestador y validar los flujos de error 502/503 en `tests/test_api.py` usando
  `monkeypatch`.
- Alan (`feat/alan-motor-generativo`) reemplazara este archivo en la Fase 2 con la
  integracion real de Google Gemini (`gemini-2.5-flash`) y salida JSON estructurada.
"""

from src.engines.base import BaseSupportEngine
from src.schemas import AnalyzeResponse


class GenerativeEngine(BaseSupportEngine):
    """Motor de clasificacion basado en IA Generativa (pendiente de implementacion)."""

    def analyze(self, message: str) -> AnalyzeResponse:
        """Lanza NotImplementedError hasta que Alan complete la Fase 2.

        Args:
            message: Texto de la solicitud de soporte previamente validado.

        Raises:
            NotImplementedError: Indica que la implementacion real corresponde a Fase 2.
        """
        raise NotImplementedError("Pendiente de implementación por Alan en Fase 2")
