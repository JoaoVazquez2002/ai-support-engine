"""Script de generación de evidencia de ejecución real (Entregable 2).

QUÉ hace este script:
    Ejecuta una batería de peticiones reales contra la app FastAPI usando
    `TestClient` (sin servidor uvicorn externo, sin mocks) y guarda un reporte
    completo en `evidence/02_evidencia_ejecucion_motores.md`.

    Los casos cubiertos son:
    1. POST /api/analyze — modo 'traditional' — "No puedo iniciar sesión"
    2. POST /api/analyze — modo 'generative'  — "No puedo iniciar sesión"
       (requiere GEMINI_API_KEY real; si falta, registra el error 503/502)
    3. POST /api/analyze — modo 'generative'  — incidente de seguridad real
    4. POST /api/analyze — entrada inválida   — mensaje vacío (esperado: 422)

QUIÉN ejecuta este script:
    Joao (Fase 4), con su `.env` real que contiene `GEMINI_API_KEY`, para que
    los casos 2 y 3 llamen realmente a Google Gemini API y la evidencia incluya
    respuestas generativas auténticas.

CÓMO ejecutar:
    Desde la raíz del proyecto (con el venv activado):
        python scripts/generate_execution_evidence.py

    La evidencia se guarda en:
        evidence/02_evidencia_ejecucion_motores.md
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Ajuste del sys.path para importar src.* cuando se corre desde la raíz
# ---------------------------------------------------------------------------
# Por qué: Python resuelve importaciones absolutas desde el primer elemento
# de sys.path. Al correr `python scripts/generate_evidence.py` desde la raíz,
# el directorio de trabajo ya está en sys.path en la mayoría de entornos, pero
# lo añadimos explícitamente para garantizar la portabilidad del script.
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402  (import después del sys.path)

from src.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Configuración del directorio de evidencia
# ---------------------------------------------------------------------------

# Garantizamos que el directorio exista; `parents=True` crea subdirectorios
# intermedios si fuera necesario, `exist_ok=True` evita error si ya existe.
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

EVIDENCE_FILE = EVIDENCE_DIR / "02_evidencia_ejecucion_motores.md"

# ---------------------------------------------------------------------------
# Casos de prueba a ejecutar
# ---------------------------------------------------------------------------

CASOS = [
    {
        "id": 1,
        "titulo": "Motor Tradicional — Problema de acceso",
        "descripcion": (
            "Ticket de acceso clásico ('No puedo iniciar sesión'). "
            "El motor tradicional clasifica mediante expresiones regulares "
            "sin consumir ninguna API externa."
        ),
        "payload": {"message": "No puedo iniciar sesión en mi cuenta de trabajo", "mode": "traditional"},
        "http_esperado": 200,
    },
    {
        "id": 2,
        "titulo": "Motor Generativo — Problema de acceso",
        "descripcion": (
            "El mismo ticket de acceso procesado por Google Gemini API "
            "('gemini-3.1-flash-lite'). Requiere GEMINI_API_KEY válida en .env. "
            "Si la clave no está configurada, el sistema responde 503."
        ),
        "payload": {"message": "No puedo iniciar sesión en mi cuenta de trabajo", "mode": "generative"},
        "http_esperado": 200,
    },
    {
        "id": 3,
        "titulo": "Motor Generativo — Incidente de seguridad real",
        "descripcion": (
            "Incidente de seguridad crítico enviado al motor generativo. "
            "Se espera category=SECURITY, requiresHumanReview=True y "
            "una respuesta contextualizada en español generada por Gemini."
        ),
        "payload": {
            "message": (
                "Detecté que nuestras credenciales de base de datos están expuestas "
                "en el repositorio público de GitHub. Hay un token de acceso real "
                "y contraseñas en texto plano en el archivo de configuración."
            ),
            "mode": "generative",
        },
        "http_esperado": 200,
    },
    {
        "id": 4,
        "titulo": "Validación de entrada — Mensaje vacío (esperado: HTTP 422)",
        "descripcion": (
            "Petición con mensaje vacío. FastAPI + Pydantic deben rechazarla "
            "automáticamente con HTTP 422 Unprocessable Entity, sin llegar "
            "a ejecutar ningún motor."
        ),
        "payload": {"message": "", "mode": "traditional"},
        "http_esperado": 422,
    },
]


# ---------------------------------------------------------------------------
# Función auxiliar: ejecutar una petición y registrar el resultado
# ---------------------------------------------------------------------------

def ejecutar_caso(client: TestClient, caso: dict) -> dict:
    """Ejecuta un caso de prueba y retorna un dict con los resultados.

    Args:
        client: TestClient configurado con la app FastAPI real.
        caso: Diccionario con id, titulo, descripcion, payload y http_esperado.

    Returns:
        dict con timestamp, payload, http_real, http_esperado, json_respuesta
        y estado (PASS / FAIL / ERROR_ESPERADO).
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inicio = time.perf_counter()

    try:
        response = client.post("/api/analyze", json=caso["payload"])
        duracion_ms = int((time.perf_counter() - inicio) * 1000)

        # Intentamos parsear como JSON; si falla, usamos el texto crudo.
        try:
            respuesta_json = response.json()
        except Exception:
            respuesta_json = {"_raw_text": response.text}

        http_real = response.status_code

        # Determinamos el estado del caso:
        # - PASS: código coincide con el esperado (incluye 422 que son correctos).
        # - ERROR_ESPERADO: 503 o 502 en casos generativos sin API Key real.
        # - FAIL: cualquier otro resultado inesperado.
        if http_real == caso["http_esperado"]:
            estado = "✅ PASS"
        elif caso["modo_es_generativo"] and http_real in (502, 503):
            estado = f"⚠️  ERROR_ESPERADO (sin GEMINI_API_KEY real) — HTTP {http_real}"
        else:
            estado = f"❌ FAIL (esperado {caso['http_esperado']}, obtenido {http_real})"

    except Exception as exc:
        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        http_real = None
        respuesta_json = {"_excepcion": str(exc)}
        estado = f"❌ EXCEPCIÓN: {type(exc).__name__}"

    return {
        "timestamp": timestamp,
        "duracion_ms": duracion_ms,
        "payload": caso["payload"],
        "http_real": http_real,
        "http_esperado": caso["http_esperado"],
        "respuesta_json": respuesta_json,
        "estado": estado,
    }


# ---------------------------------------------------------------------------
# Función principal: genera el reporte Markdown
# ---------------------------------------------------------------------------

def generar_evidencia() -> None:
    """Ejecuta todos los casos y escribe el reporte de evidencia en Markdown."""

    print(f"\n{'='*60}")
    print("  AI Support Engine — Generación de Evidencia de Ejecución")
    print(f"{'='*60}\n")

    # Enriquecemos los casos con metadato de modo para la lógica de estado.
    for caso in CASOS:
        caso["modo_es_generativo"] = caso["payload"].get("mode") == "generative"

    # Instanciamos el TestClient con la app real (sin mocks, sin servidor uvicorn).
    client = TestClient(app, raise_server_exceptions=False)

    resultados = []
    for caso in CASOS:
        print(f"▶ Caso {caso['id']}: {caso['titulo']}")
        resultado = ejecutar_caso(client, caso)
        resultado["id"] = caso["id"]
        resultado["titulo"] = caso["titulo"]
        resultado["descripcion"] = caso["descripcion"]
        resultados.append(resultado)
        print(f"  Estado : {resultado['estado']}")
        print(f"  HTTP   : {resultado['http_real']} (esperado: {resultado['http_esperado']})")
        print(f"  Tiempo : {resultado['duracion_ms']} ms\n")

    # -----------------------------------------------------------------------
    # Construcción del reporte Markdown
    # -----------------------------------------------------------------------
    fecha_reporte = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lineas = [
        "# Evidencia de Ejecución de Motores — AI Support Engine",
        "",
        f"**Proyecto:** AI Support Engine — Equipo 7  ",
        f"**Responsable de generación:** Joao Pastor Vázquez Hernández (Fase 4)  ",
        f"**Script:** `scripts/generate_execution_evidence.py`  ",
        f"**Fecha de ejecución:** {fecha_reporte}  ",
        f"**Modelo generativo configurado:** `gemini-3.1-flash-lite`  ",
        "",
        "> **Nota metodológica:** Todas las peticiones se ejecutaron usando  ",
        "> `TestClient` de FastAPI contra la aplicación real (sin mocks ni  ",
        "> servidores externos). Los casos del motor generativo requieren  ",
        "> `GEMINI_API_KEY` válida en `.env` para obtener respuestas reales de Gemini.",
        "",
        "---",
        "",
    ]

    for r in resultados:
        lineas += [
            f"## Caso {r['id']}: {r['titulo']}",
            "",
            f"**Descripción:** {r['descripcion']}  ",
            f"**Timestamp:** `{r['timestamp']}`  ",
            f"**Estado:** {r['estado']}  ",
            f"**HTTP obtenido:** `{r['http_real']}` (esperado: `{r['http_esperado']}`)  ",
            f"**Latencia:** `{r['duracion_ms']} ms`  ",
            "",
            "### Petición enviada",
            "",
            "```json",
            json.dumps(r["payload"], ensure_ascii=False, indent=2),
            "```",
            "",
            "### Respuesta recibida",
            "",
            "```json",
            json.dumps(r["respuesta_json"], ensure_ascii=False, indent=2),
            "```",
            "",
            "---",
            "",
        ]

    # Resumen final
    total = len(resultados)
    passes = sum(1 for r in resultados if r["estado"].startswith("✅"))
    lineas += [
        "## Resumen de Ejecución",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Total de casos ejecutados | {total} |",
        f"| Casos PASS (✅) | {passes} |",
        f"| Casos con advertencia (⚠️) | {sum(1 for r in resultados if r['estado'].startswith('⚠️'))} |",
        f"| Casos FAIL (❌) | {sum(1 for r in resultados if r['estado'].startswith('❌'))} |",
        "",
        "> Los casos ⚠️ son resultados esperados cuando se ejecuta sin  ",
        "> `GEMINI_API_KEY` real. Al ejecutar con credenciales válidas,  ",
        "> todos los casos deben mostrar ✅ PASS.",
        "",
    ]

    # Escritura del archivo de evidencia
    contenido = "\n".join(lineas)
    EVIDENCE_FILE.write_text(contenido, encoding="utf-8")

    print(f"{'='*60}")
    print(f"  Evidencia guardada en: {EVIDENCE_FILE}")
    print(f"  Casos PASS: {passes}/{total}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    generar_evidencia()
