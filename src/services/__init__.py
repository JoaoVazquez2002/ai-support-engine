"""Capa de Servicios / Orquestacion de Negocio.

Esta capa intermedia conecta la capa HTTP (FastAPI) con la capa de motores (`engines`).
Su responsabilidad es seleccionar dinamicamente la estrategia de clasificacion segun
el parametro `mode` solicitado y garantizar reglas transversales obligatorias, como
marcar `requiresHumanReview = True` ante cualquier incidente de seguridad (`SECURITY`).
"""
