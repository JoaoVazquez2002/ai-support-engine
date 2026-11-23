# Arquitectura de Software — AI Support Engine (Equipo 7)

**Integrantes del Equipo 7:**
- **Joao Pastor Vázquez Hernández**
- **Mariana Cordova Sanchez**
- **Alan De la Luz Guillermo**

---

## 1. Visión General y Decisión *Stateless* (Sin Base de Datos)

`AI Support Engine` está diseñado como un **microservicio *stateless* (sin estado)** especializado en clasificar solicitudes de soporte en tiempo real a través de `POST /api/analyze`.

**¿Por qué no usamos base de datos?**
- El alcance del reto exige un prototipo funcional, ejecutable y verificable donde el evaluador pueda clonar el repositorio, configurar `GEMINI_API_KEY` y ejecutar el endpoint sin levantar motores externos (PostgreSQL, MongoDB o Docker).
- Al separar responsabilidades mediante una **Arquitectura en Capas**, el sistema permanece desacoplado: si en una versión futura se requiriera persistir el historial de tickets o métricas, bastaría con incorporar una capa de Repositorio debajo de `SupportAnalyzerService` sin modificar los motores de clasificación ni el contrato HTTP.

---

## 2. Arquitectura en Capas + Patrón Estrategia y Carpetado Oficial

El proyecto combina **Arquitectura en Capas (Layered Architecture)** con el **Patrón Estrategia (Strategy Pattern)**:

```text
[ Cliente / Swagger UI (/docs) / Scripts de Evaluación ]
                          │
                          │ HTTP POST /api/analyze
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 1: TRANSPORTE / API (src/main.py)                      │
│  FastAPI expone /health y /api/analyze, valida entrada con   │
│  Pydantic (422) y traduce errores internos a 502 / 503.      │
└─────────────────────────┬────────────────────────────────────┘
                          │ AnalyzeRequest
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 2: SERVICIO / ORQUESTACIÓN (src/services/analyzer.py)  │
│  SupportAnalyzerService selecciona el motor según `mode`,    │
│  valida contrato y refuerza regla SECURITY -> revisión humana│
└────────────┬────────────────────────────────────┬────────────┘
             │                                    │
             │ Patrón Estrategia:                 │
             │ BaseSupportEngine.analyze(message) │
             ▼                                    ▼
┌───────────────────────────┐    ┌─────────────────────────────┐
│ CAPA 3A: MOTOR TRADICIONAL│    │ CAPA 3B: MOTOR GENERATIVO   │
│ src/engines/traditional.py│    │ src/engines/generative.py   │
│ IA simbólica con regex y  │    │ Integración real con Gemini │
│ reglas ponderadas (0% LLM)│    │ (gemini-3.1-flash-lite)+JSON│
└───────────────────────────┘    └─────────────────────────────┘
                          ▲
                          │ Contratos compartidos
             ┌────────────┴────────────┐
             │ DOMINIO (src/schemas.py)│
             │ Enums + AnalyzeRequest  │
             │ + AnalyzeResponse       │
             └─────────────────────────┘
```

### Estructura Oficial de Carpetas
```text
ai-support-engine/
├── .env                         # Secreto local (IGNORADO por Git)
├── .env.example                 # Plantilla sin secretos
├── .gitignore                   # Ignora .env, venv/, __pycache__/, .pytest_cache/
├── requirements.txt             # Dependencias exactas
├── README.md                    # [Entregable 1] Documentación reproducible e índice
├── docs/
│   ├── ARQUITECTURA.md          # Arquitectura en capas, Patrón Estrategia y seguridad
│   └── FASE_2_MOTOR_GENERATIVO.md # Detalle técnico del motor Gemini (gemini-3.1-flash-lite)
├── src/
│   ├── __init__.py
│   ├── schemas.py               # [Capa Dominio] Enums y modelos Pydantic (contrato único)
│   ├── main.py                  # [Capa API] FastAPI (GET /health, POST /api/analyze)
│   ├── services/
│   │   ├── __init__.py
│   │   └── analyzer.py          # [Capa Servicio] Orquestador + regla SECURITY
│   └── engines/
│       ├── __init__.py
│       ├── base.py              # [Interfaz Estrategia] BaseSupportEngine + excepciones
│       ├── traditional.py       # [Estrategia 1] Motor simbólico por reglas (0% LLM)
│       └── generative.py        # [Estrategia 2] Motor real Gemini (`gemini-3.1-flash-lite`)
├── tests/
│   └── test_api.py              # Pruebas automatizadas (normal, límites, fallos 422/502/503)
├── scripts/
│   ├── generate_execution_evidence.py  # Genera Entregable 2 (ejecución real)
│   └── run_comparative_eval.py         # Genera Entregables 3 y 4 (12 casos reales)
└── evidence/
    ├── 02_evidencia_ejecucion_motores.md         # [Entregable 2]
    ├── 03_evidencia_casos_prueba_comparativos.md # [Entregable 3]
    ├── 04_tabla_resultados_y_conclusion.md       # [Entregable 4] (<= 150 palabras)
    └── resultados_comparativos_raw.json          # Respaldo auditable crudo
```

### Ventajas de esta arquitectura
1. **Intercambiabilidad total:** `TraditionalEngine` y `GenerativeEngine` implementan la clase abstracta `BaseSupportEngine` (`src/engines/base.py`), por lo que devuelven exactamente el mismo tipo `AnalyzeResponse`. El detalle de implementación de Gemini (`gemini-3.1-flash-lite`, defensa contra *Prompt Injection* y validación de esquema) se documenta en [FASE_2_MOTOR_GENERATIVO.md](./FASE_2_MOTOR_GENERATIVO.md).
2. **Desacoplamiento entre transporte e IA:** `main.py` no conoce expresiones regulares ni el SDK `google-genai`; solo delega al servicio y maneja códigos de estado HTTP.
3. **Comparabilidad justa:** Ninguno de los motores altera la lógica del otro; la evaluación comparativa mide ambos enfoques en igualdad de condiciones.

---

## 3. Contrato Unificado de Datos (`src/schemas.py`)

Tanto el modo `traditional` como el modo `generative` comparten exactamente el mismo contrato JSON definido con Pydantic:

- **Entrada (`AnalyzeRequest`):**
  ```json
  {
    "message": "No puedo iniciar sesión",
    "mode": "traditional"
  }
  ```
  - `message`: cadena obligatoria entre `3` y `2000` caracteres visibles (se rechazan cadenas vacías o compuestas únicamente de espacios mediante `validate_non_blank_message`).
  - `mode`: Enum estricto (`"traditional"` o `"generative"`).

- **Salida (`AnalyzeResponse`):**
  ```json
  {
    "category": "ACCESS",
    "priority": "MEDIUM",
    "response": "Lamentamos el inconveniente. Verifique sus credenciales y utilice la recuperación de contraseña si es necesario.",
    "requiresHumanReview": false,
    "mode": "traditional"
  }
  ```
  - `category`: `ACCESS | BUG | FEATURE | SECURITY`
  - `priority`: `LOW | MEDIUM | HIGH | CRITICAL`
  - `response`: respuesta sugerida no vacía
  - `requiresHumanReview`: booleano (`true` obligatorio ante incidentes de seguridad)
  - `mode`: `traditional | generative`

---

## 4. Estrategia de Seguridad, Validación y Manejo de Errores

1. **Validación estricta de entradas (`HTTP 422`):** Pydantic bloquea mensajes vacíos, espacios en blanco, longitudes fuera de rango o modos no soportados antes de invocar cualquier motor.
2. **Validación de formato generativo y errores del proveedor (`src/engines/base.py`):**
   - `GenerativeEngineConfigError` $\to$ la API responde `503 Service Unavailable` cuando falta `GEMINI_API_KEY` o la configuración es inválida, sin revelar variables de entorno.
   - `GenerativeEngineError` $\to$ la API responde `502 Bad Gateway` ante errores de red, límites de cuota (`429`), fallos del proveedor o respuestas con formato JSON inválido/incompleto que no cumplen el contrato `AnalyzeResponse`, sin exponer stacktraces crudos.
3. **Protección de secretos:** La clave `GEMINI_API_KEY` se carga localmente desde `.env` (ignorado en `.gitignore`) usando `.env.example` como plantilla pública.
4. **Regla obligatoria de seguridad (`SECURITY`):** Tanto `TraditionalEngine`, `GenerativeEngine` como el post-procesamiento en `SupportAnalyzerService` garantizan que toda solicitud clasificada como `SECURITY` marque `requiresHumanReview = True`, sin sobrescribir la categoría ni la prioridad emitidas por el motor.

---

## 5. División Modular para Trabajo Paralelo en Equipo (Equipo 7)

La estructura de módulos permite que **Joao, Mariana y Alan** desarrollen sus entregables sin editar los mismos archivos ni generar conflictos de fusión:

| Orden | Integrante | Fase | Archivos asignados | Rama de trabajo |
| :---: | :--- | :--- | :--- | :--- |
| **1°** | **Joao Pastor Vázquez Hernández** | Fase 1 (Base y Motor Tradicional) | `requirements.txt`, `.env.example`, `.gitignore`, `src/schemas.py`, `src/engines/base.py`, `src/engines/traditional.py`, stub `src/engines/generative.py`, `docs/ARQUITECTURA.md` | `pruebas` |
| **2° (Paralelo)** | **Alan De la Luz Guillermo** | Fase 2 (Motor Generativo Real) | `src/engines/generative.py` | `feat/alan-motor-generativo` |
| **2° (Paralelo)** | **Mariana Cordova Sanchez** | Fase 3 (API, Seguridad y Tests) | `src/services/analyzer.py`, `src/main.py`, `tests/test_api.py`, `scripts/generate_execution_evidence.py` | `feat/mariana-api-seguridad` |
| **3° y 4°** | **Joao Pastor Vázquez Hernández** | Integración + Fase 4 (Evaluación y Cierre) | `scripts/run_comparative_eval.py`, `evidence/*`, `README.md` | `feat/joao-evaluacion-final` $\to$ `pruebas` $\to$ `main` |

### Flujo de integración en Git
- **Prohibido hacer `git push` directo a `main`.**
- Todas las ramas `feat/*` se integran primero en `pruebas` mediante Pull Request.
- Una vez integradas y verificadas las 4 fases en `pruebas`, se abre un único Pull Request limpio de `pruebas` $\to$ `main`.
