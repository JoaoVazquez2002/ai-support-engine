# AI Support Engine — Equipo 7

Prototipo funcional, ejecutable y verificable para la clasificación inteligente y automatizada de solicitudes de soporte técnico, comparando dos enfoques: **IA tradicional simbólica basada en reglas** frente a **IA generativa real** mediante Google Gemini API (`gemini-3.1-flash-lite`), expuestos bajo un contrato JSON unificado en FastAPI.

**Integrantes (Equipo 7):**
- **Joao Pastor Vázquez Hernández**
- **Mariana Cordova Sanchez**
- **Alan De la Luz Guillermo**

---

## Índice de Entregables y Documentación

| Entregable / Documento | Descripción | Enlace directo |
| :--- | :--- | :--- |
| **Entregable 1** | Código fuente funcional e instrucciones de ejecución | [README.md](./README.md) · [src/](./src/) |
| **Entregable 2** | Evidencia de ejecución real de ambos motores y validaciones (`4/4 PASS`) | [evidence/02_evidencia_ejecucion_motores.md](./evidence/02_evidencia_ejecucion_motores.md) |
| **Entregable 3** | Evidencia detallada de los 12 casos de prueba comparativos | [evidence/03_evidencia_casos_prueba_comparativos.md](./evidence/03_evidencia_casos_prueba_comparativos.md) |
| **Entregable 4** | Tabla de resultados, porcentajes reales y conclusión técnica (129 palabras) | [evidence/04_tabla_resultados_y_conclusion.md](./evidence/04_tabla_resultados_y_conclusion.md) |
| **Respaldo Auditable** | Salida cruda en JSON de la corrida comparativa de 12 casos | [evidence/resultados_comparativos_raw.json](./evidence/resultados_comparativos_raw.json) |
| **Arquitectura** | Arquitectura en Capas, Patrón Estrategia, contrato y seguridad | [docs/ARQUITECTURA.md](./docs/ARQUITECTURA.md) |
| **Motor Generativo** | Criterios de selección de `gemini-3.1-flash-lite` y defensa Prompt Injection | [docs/FASE_2_MOTOR_GENERATIVO.md](./docs/FASE_2_MOTOR_GENERATIVO.md) |

---

## Stack Tecnológico

- **Lenguaje:** Python 3.13 (`Python 3.10+` compatible)
- **API REST & ASGI:** `fastapi` + `uvicorn[standard]` (incluye Swagger UI en `/docs`)
- **Validación y Contratos:** `pydantic` v2 (esquemas estrictos `AnalyzeRequest` y `AnalyzeResponse`)
- **IA Generativa Real:** SDK oficial `google-genai` con el modelo `gemini-3.1-flash-lite` y salida JSON estructurada
- **Gestión de Secretos:** `python-dotenv` (carga local de `GEMINI_API_KEY` desde `.env`, ignorado por Git)
- **Pruebas Automatizadas:** `pytest` + `httpx` (`TestClient`)

---

## Arquitectura del Sistema (Capas + Patrón Estrategia)

El servicio es **stateless** (sin base de datos para facilitar ejecución inmediata y desacoplar el almacenamiento) y combina **Arquitectura en Capas** con el **Patrón Estrategia (`BaseSupportEngine`)**:

```text
[ Cliente / Swagger UI (/docs) / Scripts ]
                    │  POST /api/analyze
                    ▼
┌───────────────────────────────────────────────────────────┐
│ 1. CAPA API / TRANSPORTE (src/main.py)                    │
│    FastAPI valida entrada (422) y traduce errores a HTTP  │
│    seguros (502 proveedor/formato, 503 falta de API Key). │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────┐
│ 2. CAPA DE SERVICIO (src/services/analyzer.py)            │
│    SupportAnalyzerService elige estrategia según `mode`   │
│    y refuerza regla: SECURITY -> requiresHumanReview=True │
└─────────────┬───────────────────────────────┬─────────────┘
              │ BaseSupportEngine             │
              ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ 3A. MOTOR TRADICIONAL     │   │ 3B. MOTOR GENERATIVO      │
│ src/engines/traditional.py│   │ src/engines/generative.py │
│ Reglas regex ponderadas   │   │ Google Gemini API real    │
│ + plantillas (0% LLM)     │   │ (gemini-3.1-flash-lite)   │
└───────────────────────────┘   └───────────────────────────┘
```

### Estructura del Repositorio

```text
ai-support-engine/
├── .env.example                          # Plantilla pública de variables de entorno
├── .gitignore                            # Protege .env, venv/, __pycache__/
├── requirements.txt                      # Dependencias del proyecto
├── README.md                             # [Entregable 1]
├── docs/
│   ├── ARQUITECTURA.md                   # Diseño por capas y seguridad
│   └── FASE_2_MOTOR_GENERATIVO.md        # Documentación técnica de Gemini
├── src/
│   ├── __init__.py
│   ├── schemas.py                        # Contrato único AnalyzeRequest / AnalyzeResponse
│   ├── main.py                           # Endpoints GET /health y POST /api/analyze
│   ├── services/
│   │   ├── __init__.py
│   │   └── analyzer.py                   # Orquestador + salvaguarda SECURITY
│   └── engines/
│       ├── __init__.py
│       ├── base.py                       # Interfaz BaseSupportEngine + excepciones
│       ├── traditional.py                # Motor simbólico determinista
│       └── generative.py                 # Motor generativo real (Gemini API)
├── tests/
│   └── test_api.py                       # 23 pruebas unitarias y de integración
├── scripts/
│   ├── generate_execution_evidence.py    # Genera Entregable 2
│   └── run_comparative_eval.py           # Genera Entregables 3 y 4
└── evidence/
    ├── 02_evidencia_ejecucion_motores.md
    ├── 03_evidencia_casos_prueba_comparativos.md
    ├── 04_tabla_resultados_y_conclusion.md
    └── resultados_comparativos_raw.json
```

---

## Cómo Obtener y Configurar `GEMINI_API_KEY` (Gratis)

1. Ingresa a **Google AI Studio**: https://aistudio.google.com/api-keys e inicia sesión con una cuenta de Google.
2. Haz clic en **Create API key** y copia la clave generada.
3. En la raíz del proyecto, crea tu archivo `.env` a partir de la plantilla:
   ```bash
   cp .env.example .env
   ```
   *(En Windows PowerShell: `Copy-Item .env.example .env`)*.
4. Edita `.env` y coloca tu clave real (nunca subas `.env` al repositorio):
   ```env
   GEMINI_API_KEY=tu_api_key_aqui
   ```

> **Nota:** El modo `traditional` y la suite automatizada (`python -m pytest -v`) funcionan incluso sin configurar `GEMINI_API_KEY`, gracias a la inicialización diferida (*lazy*) del motor generativo.

---

## Instalación y Ejecución Paso a Paso

### 1. Clonar e instalar dependencias

**Windows (PowerShell):**
```powershell
git clone https://github.com/JoaoVazquez2002/ai-support-engine.git
cd ai-support-engine
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
git clone https://github.com/JoaoVazquez2002/ai-support-engine.git
cd ai-support-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Levantar la API REST

```bash
uvicorn src.main:app --reload
```

- Documentación interactiva (Swagger UI): `http://127.0.0.1:8000/docs`
- Verificación de estado: `GET http://127.0.0.1:8000/health`

### 3. Ejecutar pruebas automatizadas (`23 tests`)

Ejecuta con `python -m pytest -v` para asegurar que la raíz del proyecto esté en `sys.path`:

```bash
python -m pytest -v
```

### 4. Regenerar las evidencias reales (requiere `.env` con `GEMINI_API_KEY`)

```bash
# Entregable 2: pruebas reales de ambos motores + validación HTTP 422
python scripts/generate_execution_evidence.py

# Entregables 3 y 4: evaluación comparativa de 12 casos reales
python scripts/run_comparative_eval.py
```

---

## Ejemplos de Uso (`POST /api/analyze`)

### Modo Tradicional (`traditional`)

```bash
curl -X POST "http://127.0.0.1:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"message": "No puedo iniciar sesión", "mode": "traditional"}'
```

Respuesta:
```json
{
  "category": "ACCESS",
  "priority": "MEDIUM",
  "response": "Lamentamos el inconveniente. Verifique sus credenciales y utilice la recuperación de contraseña si es necesario.",
  "requiresHumanReview": false,
  "mode": "traditional"
}
```

### Modo Generativo (`generative`)

```bash
curl -X POST "http://127.0.0.1:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"message": "No puedo iniciar sesión en mi cuenta de trabajo", "mode": "generative"}'
```

Respuesta real obtenida con `gemini-3.1-flash-lite`:
```json
{
  "category": "ACCESS",
  "priority": "MEDIUM",
  "response": "Hola. Lamentamos los inconvenientes que estás experimentando para acceder a tu cuenta de trabajo. Para poder ayudarte a recuperar el acceso, por favor intenta restablecer tu contraseña a través del enlace de '¿Olvidaste tu contraseña?' en la pantalla de inicio de sesión. Si el problema persiste o si tu cuenta aparece bloqueada, por favor confírmanos si recibes algún mensaje de error específico para poder escalar tu caso al equipo técnico correspondiente.",
  "requiresHumanReview": false,
  "mode": "generative"
}
```

---

## Resumen de Resultados Comparativos (12 Casos Reales)

Los 12 casos (4 normales, 5 ambiguos y 3 de *Prompt Injection*, incluyendo el ejemplo literal del reto) se ejecutaron contra la API real. El detalle completo está en [evidence/04_tabla_resultados_y_conclusion.md](./evidence/04_tabla_resultados_y_conclusion.md):

| Métrica | Motor Tradicional (`traditional`) | Motor Generativo (`gemini-3.1-flash-lite`) |
| :--- | :---: | :---: |
| **Acierto en Categoría** | 7/12 (**58.3%**) | 12/12 (**100.0%**) |
| **Acierto Exacto (Categoría + Prioridad)** | 4/12 (**33.3%**) | 11/12 (**91.7%**) |
| Cumplimiento de formato JSON (`AnalyzeResponse`) | 12/12 (100.0%) | 12/12 (100.0%) |
| Latencia promedio observada | 12.2 ms | 2456.4 ms |

### Conclusión Técnica (129 palabras)

> El motor generativo (gemini-3.1-flash-lite) funcionó mejor en esta evaluación comparativa de 12 solicitudes reales, alcanzando 100.0% de acierto en categoría (12/12) y 91.7% en clasificación exacta de categoría y prioridad (11/12), frente a 58.3% (7/12) y 33.3% (4/12) del motor tradicional. La ventaja del enfoque generativo radica en la comprensión semántica del contexto: en tickets ambiguos acertó 5/5 categorías contra 1/5 de las reglas literales, y en intentos de prompt injection obtuvo 3/3 clasificaciones exactas frente a 0/3 del motor tradicional, que resulta vulnerable a frases literales como 'prioridad baja' u órdenes inyectadas. Por otro lado, el motor tradicional destacó en latencia media (12.2 ms vs. 2456.4 ms) y determinismo sin dependencia de red. En conjunto, ambos cumplieron el contrato JSON y la revisión humana obligatoria ante incidentes críticos.
