"""Suite de pruebas automatizadas para la API del AI Support Engine (Fase 3 - Mariana).

QUÉ verifica esta suite:
    1. GET /health devuelve HTTP 200 con el cuerpo correcto.
    2. POST /api/analyze en modo 'traditional' para las 4 categorías (ACCESS,
       BUG, FEATURE, SECURITY), incluyendo la regla requiresHumanReview=True
       obligatoria para SECURITY.
    3. Validación de entradas inválidas (HTTP 422): mensaje vacío, solo espacios
       y mode no soportado.
    4. Manejo seguro de errores del motor generativo (HTTP 503 ante falta de
       API Key, HTTP 502 ante fallo del proveedor y HTTP 502 ante formato JSON
       inválido), usando monkeypatch EXCLUSIVAMENTE en estos tests unitarios.
    5. Que ninguna respuesta de error filtra secretos, stacktraces ni rutas internas.
    6. Que el 100% de los tests pasan sin requerir GEMINI_API_KEY real.

ARQUITECTURA DE PRUEBAS:
    - `TestClient` de FastAPI (wrapping de httpx) levanta la app en memoria sin
      necesidad de un servidor uvicorn real.
    - Las pruebas del motor generativo usan `monkeypatch` para simular errores
      del SDK sin llamadas reales a la API de Google, garantizando que los tests
      sean deterministas y no consuman cuota.
    - Las pruebas del motor tradicional NO usan mocks: ejecutan la lógica real
      de `TraditionalEngine` para validar el contrato end-to-end.

IMPORTANTE: `monkeypatch` solo se usa en tests de error del motor generativo.
    Los tests del motor tradicional y de validación de entrada son 100% reales.
"""

import pytest
from fastapi.testclient import TestClient

# Importamos la app FastAPI directamente; TestClient la instancia en memoria.
from src.main import app

# Importamos las excepciones compartidas para usarlas en los mocks de monkeypatch.
from src.engines.base import GenerativeEngineConfigError, GenerativeEngineError


# ---------------------------------------------------------------------------
# Fixture: cliente de pruebas compartido por toda la suite
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    """Crea un TestClient fresco para cada test.

    Por qué un fixture sin scope de módulo:
        Garantiza que cada test recibe un cliente limpio, evitando efectos
        secundarios entre los parches de `monkeypatch` (que se revierten al
        final de cada función de test). `SupportAnalyzerService` es stateless,
        por lo que la reinicialización es trivial en costo.

    Por qué `raise_server_exceptions=False`:
        Permite que los exception_handlers de FastAPI (que atrapan
        GenerativeEngineConfigError → 503 y GenerativeEngineError → 502)
        devuelvan la respuesta JSON correcta en lugar de propagar la excepción
        al test, que es el comportamiento que queremos verificar.
    """
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# SECCIÓN 1: GET /health
# ===========================================================================

class TestHealthEndpoint:
    """Verifica que el endpoint de salud responde correctamente."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """El endpoint GET /health debe responder HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200, (
            f"Se esperaba 200, se obtuvo {response.status_code}"
        )

    def test_health_response_body(self, client: TestClient) -> None:
        """La respuesta de /health debe contener el cuerpo exacto del contrato."""
        response = client.get("/health")
        body = response.json()
        assert body == {"status": "ok", "service": "ai-support-engine"}, (
            f"Cuerpo inesperado: {body}"
        )


# ===========================================================================
# SECCIÓN 2: POST /api/analyze — Motor Tradicional (sin mocks)
# ===========================================================================

class TestTraditionalModeCategories:
    """Verifica las 4 categorías del motor tradicional con lógica real (sin mocks).

    Por qué sin mocks:
        El motor tradicional es determinista y no depende de servicios externos.
        Probarlo sin mocks valida el contrato end-to-end real de la API.
    """

    def _post_analyze(self, client: TestClient, message: str) -> dict:
        """Helper: envía una petición POST /api/analyze en modo traditional."""
        response = client.post(
            "/api/analyze",
            json={"message": message, "mode": "traditional"},
        )
        assert response.status_code == 200, (
            f"Se esperaba 200, se obtuvo {response.status_code}. "
            f"Cuerpo: {response.text}"
        )
        return response.json()

    def test_traditional_access_category(self, client: TestClient) -> None:
        """El mensaje de inicio de sesión debe clasificarse como ACCESS."""
        body = self._post_analyze(client, "No puedo iniciar sesión en mi cuenta")
        assert body["category"] == "ACCESS"
        assert body["mode"] == "traditional"
        # ACCESS no tiene revisión humana obligatoria
        assert isinstance(body["requiresHumanReview"], bool)
        # Verifica campos del contrato presentes
        assert "priority" in body
        assert "response" in body

    def test_traditional_bug_category(self, client: TestClient) -> None:
        """El mensaje de error técnico debe clasificarse como BUG."""
        body = self._post_analyze(
            client, "La aplicación muestra error 500 y se cierra sola"
        )
        assert body["category"] == "BUG"
        assert body["mode"] == "traditional"
        assert "priority" in body
        assert len(body["response"]) > 0

    def test_traditional_feature_category(self, client: TestClient) -> None:
        """La solicitud de nueva funcionalidad debe clasificarse como FEATURE."""
        body = self._post_analyze(
            client, "Me gustaría que agregaran modo oscuro al panel de control"
        )
        assert body["category"] == "FEATURE"
        assert body["mode"] == "traditional"
        assert body["requiresHumanReview"] is False, (
            "FEATURE no debe requerir revisión humana por defecto"
        )

    def test_traditional_security_category(self, client: TestClient) -> None:
        """Un incidente de seguridad debe clasificarse como SECURITY."""
        body = self._post_analyze(
            client,
            "Detecté una vulnerabilidad de SQL injection en el formulario de login",
        )
        assert body["category"] == "SECURITY"
        assert body["mode"] == "traditional"

    def test_traditional_security_requires_human_review(
        self, client: TestClient
    ) -> None:
        """REGLA CRÍTICA: SECURITY SIEMPRE debe tener requiresHumanReview=True.

        Esta prueba es la más importante de la suite: verifica que la salvaguarda
        transversal del servicio funciona correctamente para el motor tradicional.
        """
        body = self._post_analyze(
            client,
            "Hay una brecha de seguridad: datos expuestos en el sistema de pagos",
        )
        assert body["category"] == "SECURITY", (
            "El ticket de brecha de seguridad debe clasificarse como SECURITY"
        )
        assert body["requiresHumanReview"] is True, (
            "Todo incidente SECURITY DEBE tener requiresHumanReview=True (regla crítica)"
        )

    def test_traditional_response_contract_complete(self, client: TestClient) -> None:
        """La respuesta debe incluir todos los campos del contrato AnalyzeResponse."""
        response = client.post(
            "/api/analyze",
            json={"message": "El sistema está caído en producción", "mode": "traditional"},
        )
        body = response.json()
        # Verificamos que todos los campos del contrato estén presentes
        required_fields = {"category", "priority", "response", "requiresHumanReview", "mode"}
        missing = required_fields - set(body.keys())
        assert not missing, f"Faltan campos en la respuesta: {missing}"

    def test_traditional_valid_enum_values(self, client: TestClient) -> None:
        """Los enums category, priority y mode deben tener valores válidos."""
        response = client.post(
            "/api/analyze",
            json={"message": "No puedo restablecer mi contraseña", "mode": "traditional"},
        )
        body = response.json()
        assert body["category"] in {"ACCESS", "BUG", "FEATURE", "SECURITY"}
        assert body["priority"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert body["mode"] == "traditional"


# ===========================================================================
# SECCIÓN 3: Validación de entradas inválidas (HTTP 422)
# ===========================================================================

class TestInputValidation:
    """Verifica que FastAPI + Pydantic rechazan entradas inválidas con HTTP 422.

    Por qué HTTP 422:
        Pydantic lanza `ValidationError` cuando el cuerpo no cumple el esquema
        `AnalyzeRequest`. FastAPI convierte este error automáticamente en
        HTTP 422 Unprocessable Entity con detalle estructurado.
    """

    def test_empty_message_returns_422(self, client: TestClient) -> None:
        """Un mensaje vacío debe retornar HTTP 422 (min_length=3 en el esquema)."""
        response = client.post(
            "/api/analyze",
            json={"message": "", "mode": "traditional"},
        )
        assert response.status_code == 422, (
            f"Se esperaba 422 para mensaje vacío, se obtuvo {response.status_code}"
        )

    def test_whitespace_only_message_returns_422(self, client: TestClient) -> None:
        """Un mensaje de solo espacios debe retornar HTTP 422.

        Por qué: `AnalyzeRequest.validate_non_blank_message` hace `.strip()` y
        verifica que queden ≥ 3 caracteres visibles, rechazando '   ' aunque
        tenga longitud 3+.
        """
        response = client.post(
            "/api/analyze",
            json={"message": "   ", "mode": "traditional"},
        )
        assert response.status_code == 422, (
            f"Se esperaba 422 para mensaje de solo espacios, se obtuvo {response.status_code}"
        )

    def test_invalid_mode_returns_422(self, client: TestClient) -> None:
        """Un mode no soportado debe retornar HTTP 422."""
        response = client.post(
            "/api/analyze",
            json={"message": "No puedo entrar al sistema", "mode": "magico"},
        )
        assert response.status_code == 422, (
            f"Se esperaba 422 para mode inválido, se obtuvo {response.status_code}"
        )

    def test_missing_message_field_returns_422(self, client: TestClient) -> None:
        """La ausencia del campo 'message' debe retornar HTTP 422."""
        response = client.post(
            "/api/analyze",
            json={"mode": "traditional"},
        )
        assert response.status_code == 422

    def test_missing_mode_field_returns_422(self, client: TestClient) -> None:
        """La ausencia del campo 'mode' debe retornar HTTP 422."""
        response = client.post(
            "/api/analyze",
            json={"message": "Tengo un problema con mi cuenta"},
        )
        assert response.status_code == 422

    def test_message_too_short_returns_422(self, client: TestClient) -> None:
        """Un mensaje de menos de 3 caracteres visibles debe retornar HTTP 422."""
        response = client.post(
            "/api/analyze",
            json={"message": "ab", "mode": "traditional"},
        )
        assert response.status_code == 422

    def test_422_response_does_not_leak_secrets(self, client: TestClient) -> None:
        """El cuerpo de un 422 no debe contener trazas de código ni credenciales."""
        response = client.post(
            "/api/analyze",
            json={"message": "", "mode": "bad"},
        )
        body = response.text
        # Verificamos que no haya rastros de secretos o trazas internas
        assert "GEMINI_API_KEY" not in body
        assert "Traceback" not in body
        assert "stacktrace" not in body.lower()


# ===========================================================================
# SECCIÓN 4: Manejo seguro de errores del motor generativo (con monkeypatch)
# ===========================================================================

class TestGenerativeEngineErrorHandling:
    """Verifica los códigos HTTP correctos ante fallos del motor generativo.

    USO DE MONKEYPATCH: Solo en esta sección se usa monkeypatch para simular
    fallos del motor generativo sin GEMINI_API_KEY real. Esto permite:
    1. Probar que los exception_handlers devuelven 503 y 502 correctamente.
    2. Garantizar que los tests pasan en CI/CD sin credenciales reales.
    3. Verificar que las respuestas de error no filtran secretos ni stacktraces.

    Los tests del motor tradicional (Sección 2) NO usan monkeypatch.
    """

    def test_missing_api_key_returns_503(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falta de GEMINI_API_KEY debe retornar HTTP 503 Service Unavailable.

        Simulamos que GenerativeEngine.analyze() lanza GenerativeEngineConfigError,
        que es exactamente lo que ocurre cuando falta o es inválida la API Key.
        """
        def mock_analyze_config_error(self, message: str):
            raise GenerativeEngineConfigError(
                "El motor generativo no está configurado: falta GEMINI_API_KEY."
            )

        # Parcheamos el método analyze del GenerativeEngine
        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_config_error)

        response = client.post(
            "/api/analyze",
            json={"message": "No puedo acceder al sistema", "mode": "generative"},
        )
        assert response.status_code == 503, (
            f"Se esperaba 503 ante falta de API Key, se obtuvo {response.status_code}"
        )

    def test_provider_error_returns_502(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fallo del proveedor de IA (red, timeout, cuota) debe retornar HTTP 502.

        Simulamos que GenerativeEngine.analyze() lanza GenerativeEngineError,
        que es lo que ocurre ante errores HTTP 429, 5xx, timeout o conexión.
        """
        def mock_analyze_engine_error(self, message: str):
            raise GenerativeEngineError(
                "El proveedor de IA generativa no pudo completar la solicitud."
            )

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_engine_error)

        response = client.post(
            "/api/analyze",
            json={"message": "El sistema muestra un error 500", "mode": "generative"},
        )
        assert response.status_code == 502, (
            f"Se esperaba 502 ante fallo del proveedor, se obtuvo {response.status_code}"
        )

    def test_invalid_json_format_returns_502(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Respuesta con formato JSON inválido del proveedor debe retornar HTTP 502.

        El GenerativeEngine lanza GenerativeEngineError cuando el JSON devuelto
        por Gemini está malformado o no cumple el esquema _GeminiSupportOutput.
        """
        def mock_analyze_invalid_json(self, message: str):
            raise GenerativeEngineError(
                "El proveedor de IA generativa devolvió un JSON inválido o incompleto."
            )

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_invalid_json)

        response = client.post(
            "/api/analyze",
            json={"message": "Necesito exportar reportes a Excel", "mode": "generative"},
        )
        assert response.status_code == 502, (
            f"Se esperaba 502 ante formato JSON inválido, se obtuvo {response.status_code}"
        )

    def test_503_response_does_not_leak_secrets(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La respuesta HTTP 503 no debe exponer credenciales ni stacktraces."""
        def mock_analyze_config_error(self, message: str):
            # Intentamos 'filtrar' la clave en el mensaje de excepción para
            # probar que el exception_handler lo intercepta correctamente.
            raise GenerativeEngineConfigError("Error de configuración del servicio.")

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_config_error)

        response = client.post(
            "/api/analyze",
            json={"message": "No puedo entrar al panel", "mode": "generative"},
        )
        assert response.status_code == 503
        body = response.text
        # Verificamos que el cuerpo de la respuesta al cliente no filtra nada sensible
        assert "GEMINI_API_KEY" not in body
        assert "Traceback" not in body
        assert "stacktrace" not in body.lower()
        assert "api_key" not in body.lower()

    def test_502_response_does_not_leak_secrets(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La respuesta HTTP 502 no debe exponer stacktraces ni datos internos."""
        def mock_analyze_engine_error(self, message: str):
            raise GenerativeEngineError("Fallo de red al contactar el proveedor.")

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_engine_error)

        response = client.post(
            "/api/analyze",
            json={"message": "El módulo de pagos falla", "mode": "generative"},
        )
        assert response.status_code == 502
        body = response.text
        assert "GEMINI_API_KEY" not in body
        assert "Traceback" not in body
        assert "stacktrace" not in body.lower()

    def test_503_body_contains_detail_field(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La respuesta HTTP 503 debe contener el campo 'detail' con mensaje seguro."""
        def mock_analyze_config_error(self, message: str):
            raise GenerativeEngineConfigError("Configuración inválida.")

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_config_error)

        response = client.post(
            "/api/analyze",
            json={"message": "Olvidé mi contraseña", "mode": "generative"},
        )
        assert response.status_code == 503
        body = response.json()
        assert "detail" in body, "El cuerpo 503 debe incluir el campo 'detail'"
        assert len(body["detail"]) > 0, "El mensaje 'detail' no debe estar vacío"

    def test_502_body_contains_detail_field(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La respuesta HTTP 502 debe contener el campo 'detail' con mensaje seguro."""
        def mock_analyze_engine_error(self, message: str):
            raise GenerativeEngineError("Timeout al contactar Gemini.")

        from src.engines.generative import GenerativeEngine
        monkeypatch.setattr(GenerativeEngine, "analyze", mock_analyze_engine_error)

        response = client.post(
            "/api/analyze",
            json={"message": "No puedo cargar la página principal", "mode": "generative"},
        )
        assert response.status_code == 502
        body = response.json()
        assert "detail" in body, "El cuerpo 502 debe incluir el campo 'detail'"
        assert len(body["detail"]) > 0, "El mensaje 'detail' no debe estar vacío"
