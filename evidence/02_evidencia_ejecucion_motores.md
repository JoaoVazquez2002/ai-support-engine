# Evidencia de Ejecución de Motores — AI Support Engine

**Proyecto:** AI Support Engine — Equipo 7  
**Responsable de generación:** Joao Pastor Vázquez Hernández (Fase 4)  
**Script:** `scripts/generate_execution_evidence.py`  
**Fecha de ejecución:** 2026-11-23 03:04:57 UTC  
**Modelo generativo configurado:** `gemini-3.1-flash-lite`  

> **Nota metodológica:** Todas las peticiones se ejecutaron usando  
> `TestClient` de FastAPI contra la aplicación real (sin mocks ni  
> servidores externos). Los casos del motor generativo requieren  
> `GEMINI_API_KEY` válida en `.env` para obtener respuestas reales de Gemini.

---

## Caso 1: Motor Tradicional — Problema de acceso

**Descripción:** Ticket de acceso clásico ('No puedo iniciar sesión'). El motor tradicional clasifica mediante expresiones regulares sin consumir ninguna API externa.  
**Timestamp:** `2026-11-23T03:04:52Z`  
**Estado:** ✅ PASS  
**HTTP obtenido:** `200` (esperado: `200`)  
**Latencia:** `60 ms`  

### Petición enviada

```json
{
  "message": "No puedo iniciar sesión en mi cuenta de trabajo",
  "mode": "traditional"
}
```

### Respuesta recibida

```json
{
  "category": "ACCESS",
  "priority": "MEDIUM",
  "response": "Lamentamos el inconveniente. Verifique sus credenciales y utilice la recuperación de contraseña si es necesario.",
  "requiresHumanReview": false,
  "mode": "traditional"
}
```

---

## Caso 2: Motor Generativo — Problema de acceso

**Descripción:** El mismo ticket de acceso procesado por Google Gemini API ('gemini-3.1-flash-lite'). Requiere GEMINI_API_KEY válida en .env. Si la clave no está configurada, el sistema responde 503.  
**Timestamp:** `2026-11-23T03:04:52Z`  
**Estado:** ✅ PASS  
**HTTP obtenido:** `200` (esperado: `200`)  
**Latencia:** `3359 ms`  

### Petición enviada

```json
{
  "message": "No puedo iniciar sesión en mi cuenta de trabajo",
  "mode": "generative"
}
```

### Respuesta recibida

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

## Caso 3: Motor Generativo — Incidente de seguridad real

**Descripción:** Incidente de seguridad crítico enviado al motor generativo. Se espera category=SECURITY, requiresHumanReview=True y una respuesta contextualizada en español generada por Gemini.  
**Timestamp:** `2026-11-23T03:04:56Z`  
**Estado:** ✅ PASS  
**HTTP obtenido:** `200` (esperado: `200`)  
**Latencia:** `1259 ms`  

### Petición enviada

```json
{
  "message": "Detecté que nuestras credenciales de base de datos están expuestas en el repositorio público de GitHub. Hay un token de acceso real y contraseñas en texto plano en el archivo de configuración.",
  "mode": "generative"
}
```

### Respuesta recibida

```json
{
  "category": "SECURITY",
  "priority": "CRITICAL",
  "response": "Hemos recibido su reporte sobre la exposición de credenciales en un repositorio público. Dada la gravedad de esta situación, hemos escalado su caso de manera prioritaria a nuestro equipo de seguridad. Por favor, proceda a revocar inmediatamente las credenciales expuestas y a rotar todas las contraseñas y tokens afectados. Un especialista se pondrá en contacto con usted a la brevedad para asegurar que el incidente sea contenido correctamente.",
  "requiresHumanReview": true,
  "mode": "generative"
}
```

---

## Caso 4: Validación de entrada — Mensaje vacío (esperado: HTTP 422)

**Descripción:** Petición con mensaje vacío. FastAPI + Pydantic deben rechazarla automáticamente con HTTP 422 Unprocessable Entity, sin llegar a ejecutar ningún motor.  
**Timestamp:** `2026-11-23T03:04:57Z`  
**Estado:** ✅ PASS  
**HTTP obtenido:** `422` (esperado: `422`)  
**Latencia:** `15 ms`  

### Petición enviada

```json
{
  "message": "",
  "mode": "traditional"
}
```

### Respuesta recibida

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "message"
      ],
      "msg": "String should have at least 3 characters",
      "input": "",
      "ctx": {
        "min_length": 3
      }
    }
  ]
}
```

---

## Resumen de Ejecución

| Métrica | Valor |
|---------|-------|
| Total de casos ejecutados | 4 |
| Casos PASS (✅) | 4 |
| Casos con advertencia (⚠️) | 0 |
| Casos FAIL (❌) | 0 |

> Los casos ⚠️ son resultados esperados cuando se ejecuta sin  
> `GEMINI_API_KEY` real. Al ejecutar con credenciales válidas,  
> todos los casos deben mostrar ✅ PASS.
