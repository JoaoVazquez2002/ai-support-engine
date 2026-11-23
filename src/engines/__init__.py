"""Capa de Motores de Clasificacion (Patron Estrategia).

Contiene la interfaz abstracta `BaseSupportEngine` y sus implementaciones concretas:
- `TraditionalEngine` (`traditional.py`): motor determinista de IA simbolica basado
  en reglas y expresiones regulares ponderadas (sin modelos generativos).
- `GenerativeEngine` (`generative.py`): motor basado en IA generativa real mediante
  la API de Google Gemini (a implementar en la Fase 2).

Gracias a esta estructura, ambos motores comparten exactamente el mismo contrato
de entrada y salida y pueden intercambiarse sin modificar la capa de API.
"""
