"""Paquete principal del proyecto AI Support Engine.

Este modulo raiz agrupa las capas de la arquitectura del sistema:
- Capa de Dominio y Contratos (`src/schemas.py`): define los modelos Pydantic y enums
  que garantizan entradas validas y un contrato de salida uniforme.
- Capa de Motores de Clasificacion (`src/engines/`): implementa el Patron Estrategia
  para intercambiar el motor tradicional simbolico y el motor generativo.
- Capa de Servicios (`src/services/`): orquesta la seleccion del motor y aplica
  reglas transversales de negocio y seguridad.
- Capa de Transporte / API (`src/main.py`): expone los endpoints REST con FastAPI.
"""
