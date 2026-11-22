"""Motor de IA Tradicional basado en reglas simbolicas (Requerimiento 1 - 25%).

Que hace este modulo:
Implementa un sistema experto determinista que clasifica solicitudes de soporte
utilizando exclusivamente procesamiento simbolico de texto (normalizacion, reglas con
expresiones regulares ponderadas y arbol de prioridades explicitas).

Por que esta disenado asi:
1. Cero IA generativa: cumple estrictamente el Requerimiento 1 al no usar ningun LLM.
2. Transparencia y reproducibilidad: ante una misma entrada siempre produce la misma
   salida, y cada decision puede rastrearse a reglas y pesos concretos.
3. Base comparativa honesta: al depender de patrones literales (por ejemplo, buscar
   la frase "prioridad baja"), muestra de forma natural las fortalezas de velocidad
   y determinismo frente a las limitaciones ante ambiguedad o prompt injection,
   justificando la comparativa de la Fase 4 contra el motor generativo.
"""

import re
import unicodedata
from typing import Pattern

from src.engines.base import BaseSupportEngine
from src.schemas import AnalysisMode, AnalyzeResponse, Category, Priority

# Orden de desempate cuando dos categorias obtienen exactamente el mismo puntaje.
# Se prioriza el riesgo operativo y de seguridad: SECURITY > BUG > ACCESS > FEATURE.
CATEGORY_TIEBREAK_ORDER: tuple[Category, ...] = (
    Category.SECURITY,
    Category.BUG,
    Category.ACCESS,
    Category.FEATURE,
)

# Prioridad base por categoria cuando el mensaje no contiene modificadores explicitos
# de urgencia o severidad.
BASE_PRIORITY_BY_CATEGORY: dict[Category, Priority] = {
    Category.SECURITY: Priority.HIGH,
    Category.BUG: Priority.MEDIUM,
    Category.ACCESS: Priority.MEDIUM,
    Category.FEATURE: Priority.LOW,
}


def _compile_weighted_rules(
    raw_rules: dict[Category, list[tuple[str, int]]],
) -> dict[Category, list[tuple[Pattern[str], int]]]:
    """Precompila las expresiones regulares de la base de conocimiento de categorias.

    Precompilar al cargar el modulo evita recompilar patrones en cada peticion
    y mantiene la tabla de reglas legible para auditoria tecnica.
    """
    return {
        category: [(re.compile(pattern), weight) for pattern, weight in rules]
        for category, rules in raw_rules.items()
    }


def _compile_priority_rules(
    raw_rules: list[tuple[Priority, list[str]]],
) -> list[tuple[Priority, tuple[Pattern[str], ...]]]:
    """Precompila las reglas ordenadas de modificadores explicitos de prioridad."""
    return [
        (priority, tuple(re.compile(pattern) for pattern in patterns))
        for priority, patterns in raw_rules
    ]


# Base de conocimiento simbolica: pares (patron regex, peso en puntos).
# Los terminos mas especificos o criticos reciben mayor peso para evitar falsos
# positivos (por ejemplo, "credenciales expuestas" pesa mas en SECURITY que
# "credenciales" en ACCESS).
CATEGORY_RULES: dict[Category, list[tuple[Pattern[str], int]]] = _compile_weighted_rules(
    {
        Category.SECURITY: [
            (r"\bvulnerabilidad(?:es)?\b", 5),
            (r"\bsql\s+injection\b", 6),
            (r"\binyeccion(?:\s+(?:sql|de\s+codigo|de\s+comandos))?\b", 5),
            (r"\bxss\b", 5),
            (r"\bcsrf\b", 5),
            (r"\bhacke\w*\b", 5),
            (r"\bbrecha(?:\s+de\s+seguridad)?\b", 5),
            (r"\bfiltracion(?:\s+de\s+datos)?\b", 5),
            (r"\bdatos\s+expuestos\b", 6),
            (r"\bransomware\b", 6),
            (r"\bphishing\b", 5),
            (r"\bmalware\b", 5),
            (r"\bataque(?:\s+\w+)?\b", 4),
            (r"\bcomprometid[oa]s?\b", 5),
            (r"\bacceso\s+no\s+autorizado\b", 6),
            (r"\btoken\s+expuesto\b", 6),
            (r"\bcredenciales\s+expuestas\b", 6),
            (r"\bseguridad\b", 4),
            (r"\bexploit\b", 5),
            (r"\bddos\b", 5),
        ],
        Category.ACCESS: [
            (r"\biniciar\s+sesion\b", 5),
            (r"\binicio\s+de\s+sesion\b", 5),
            (r"\blogin\b", 4),
            (r"\blog\s+in\b", 4),
            (r"\bcontrasena\b", 4),
            (r"\bpassword\b", 4),
            (r"\bcredenciales\b", 3),
            (r"\bautenticacion\b", 4),
            (r"\b2fa\b", 4),
            (r"\bmfa\b", 4),
            (r"\btoken\s+de\s+acceso\b", 4),
            (r"\bcuenta\s+bloqueada\b", 5),
            (r"\bbloqueo\s+de\s+cuenta\b", 5),
            (r"\bno\s+puedo\s+entrar\b", 5),
            (r"\bno\s+puedo\s+acceder\b", 5),
            (r"\bpermisos\s+de\s+acceso\b", 4),
            (r"\brecuperar\s+cuenta\b", 4),
            (r"\brestablecer\b", 3),
        ],
        Category.BUG: [
            (r"\berror(?:es)?\b", 3),
            (r"\bfalla(?:s)?\b", 4),
            (r"\bfallo(?:s)?\b", 4),
            (r"\bbug(?:s)?\b", 4),
            (r"\bcrash\w*\b", 5),
            (r"\bse\s+cierra\b", 4),
            (r"\bno\s+carga\b", 4),
            (r"\bno\s+responde\b", 4),
            (r"\bpantalla\s+en\s+blanco\b", 5),
            (r"\b500\b", 4),
            (r"\b502\b", 4),
            (r"\b503\b", 4),
            (r"\b404\b", 3),
            (r"\bexcepcion(?:es)?\b", 4),
            (r"\btimeout\b", 4),
            (r"\blento\b", 3),
            (r"\bcaido\b", 4),
            (r"\broto\b", 4),
            (r"\bno\s+funciona\b", 4),
            (r"\bcalcula\s+mal\b", 5),
            (r"\bduplicad[oa]s?\b", 4),
        ],
        Category.FEATURE: [
            (r"\bnueva\s+funcionalidad\b", 5),
            (r"\bnueva\s+funcion\b", 5),
            (r"\bagregar\b", 3),
            (r"\banadir\b", 3),
            (r"\bimplementar\b", 3),
            (r"\bsugerencia\b", 4),
            (r"\bmejora\b", 4),
            (r"\bmejorar\b", 3),
            (r"\bmodo\s+oscuro\b", 5),
            (r"\bdark\s+mode\b", 5),
            (r"\bseria\s+genial\b", 4),
            (r"\bme\s+gustaria\b", 4),
            (r"\bpodrian\s+incluir\b", 5),
            (r"\bintegracion\s+con\b", 4),
            (r"\bexportar\s+a\b", 4),
            (r"\bsolicitud\s+de\s+cambio\b", 5),
            (r"\bfeature\b", 4),
        ],
    }
)

# Reglas ordenadas para inferir prioridad segun modificadores explicitos en el texto.
# Nota educativa: evaluar primero modificadores literales de prioridad baja ("prioridad baja")
# ilustra exactamente como un motor simbolico basado en patrones literales puede ser
# manipulado en la prioridad mediante inyeccion de texto, a diferencia de un modelo con
# comprension semantica del contexto.
PRIORITY_RULES: list[tuple[Priority, tuple[Pattern[str], ...]]] = _compile_priority_rules(
    [
        (
            Priority.LOW,
            [
                r"\bprioridad\s+baja\b",
                r"\bbaja\s+prioridad\b",
                r"\bsin\s+urgencia\b",
                r"\bno\s+es\s+urgente\b",
            ],
        ),
        (
            Priority.CRITICAL,
            [
                r"\bcritic[oa]\b",
                r"\bproduccion\s+caid[oa]\b",
                r"\bsistema\s+caid[oa]\b",
                r"\bbrecha\b",
                r"\binyeccion\b",
                r"\bsql\s+injection\b",
                r"\bransomware\b",
                r"\bdatos\s+expuestos\b",
                r"\bfiltracion\b",
                r"\burgente\b",
                r"\bperdida\s+de\s+datos\b",
            ],
        ),
        (
            Priority.HIGH,
            [
                r"\bprioridad\s+alta\b",
                r"\balta\s+prioridad\b",
                r"\bbloquead[oa]\b",
                r"\bno\s+puedo\s+trabajar\b",
                r"\bvulnerabilidad\b",
                r"\bataque\b",
                r"\b500\b",
                r"\bse\s+cierra\b",
            ],
        ),
        (
            Priority.MEDIUM,
            [
                r"\bprioridad\s+media\b",
                r"\blento\b",
                r"\bintermitente\b",
            ],
        ),
    ]
)

# Catalogo completo de 16 respuestas predeterminadas (4 categorias x 4 prioridades).
# El motor tradicional no redacta texto libre con IA; selecciona una plantilla acorde
# con la clasificacion simbolica obtenida (Requerimiento 1).
PREDEFINED_RESPONSES: dict[Category, dict[Priority, str]] = {
    Category.ACCESS: {
        Priority.LOW: (
            "Hemos recibido su consulta de acceso. Puede revisar sus permisos o "
            "actualizar sus credenciales desde la configuracion de su perfil."
        ),
        Priority.MEDIUM: (
            "Lamentamos el inconveniente. Verifique sus credenciales y utilice la "
            "recuperación de contraseña si es necesario."
        ),
        Priority.HIGH: (
            "Detectamos un bloqueo de acceso que afecta su operacion. Hemos priorizado "
            "su caso para restablecer credenciales o verificar su autenticacion multifactor."
        ),
        Priority.CRITICAL: (
            "Su incidencia de acceso ha sido marcada como critica. El equipo de soporte "
            "de identidad atendera de inmediato la restauracion de su cuenta."
        ),
    },
    Category.BUG: {
        Priority.LOW: (
            "Gracias por reportar este comportamiento menor. Lo hemos registrado en "
            "nuestra cola de mantenimiento para analizarlo en proximas actualizaciones."
        ),
        Priority.MEDIUM: (
            "Lamentamos el error presentado. Nuestro equipo tecnico revisara los "
            "registros del sistema para reproducir y corregir la falla reportada."
        ),
        Priority.HIGH: (
            "Hemos escalado este fallo tecnico con prioridad alta debido al impacto en "
            "su flujo de trabajo. Ingenieria ya esta investigando la causa raiz."
        ),
        Priority.CRITICAL: (
            "Atencion critica activada: hemos escalado de inmediato la interrupcion "
            "del sistema al equipo de guardia para restablecer el servicio."
        ),
    },
    Category.FEATURE: {
        Priority.LOW: (
            "Muchas gracias por su sugerencia. Hemos registrado la propuesta de nueva "
            "funcionalidad para evaluarla en la planificacion de producto."
        ),
        Priority.MEDIUM: (
            "Agradecemos su solicitud de mejora. El equipo de producto analizara la "
            "viabilidad e impacto de esta funcionalidad para futuras versiones."
        ),
        Priority.HIGH: (
            "Hemos recibido su solicitud de mejora con alta relevancia operativa. Sera "
            "priorizada en la revision con el equipo de producto."
        ),
        Priority.CRITICAL: (
            "Su requerimiento funcional ha sido escalado al equipo de producto para "
            "evaluacion prioritaria debido a su impacto estrategico."
        ),
    },
    Category.SECURITY: {
        Priority.LOW: (
            "Hemos recibido un reporte relacionado con seguridad. Por protocolo sera "
            "escalado automaticamente a revision humana por el equipo de ciberseguridad."
        ),
        Priority.MEDIUM: (
            "Gracias por notificar este posible incidente de seguridad. El caso fue "
            "marcado para revision humana y sera evaluado por nuestros especialistas."
        ),
        Priority.HIGH: (
            "Alerta de seguridad registrada con prioridad alta. El equipo de respuesta "
            "a incidentes realizara una revision humana inmediata para mitigar riesgos."
        ),
        Priority.CRITICAL: (
            "Incidente critico de seguridad detectado. Hemos activado revision humana "
            "urgente y notificado al equipo de ciberseguridad para contencion inmediata."
        ),
    },
}


class TraditionalEngine(BaseSupportEngine):
    """Motor determinista de clasificacion basado en reglas simbolicas y regex."""

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Convierte el texto a minusculas, elimina tildes y colapsa espacios.

        Por que normalizamos: permite que las reglas coincidan de manera uniforme
        sin importar si el usuario escribe "sesion" o "sesión", "codigo" o "código",
        o si inserta saltos de linea entre palabras clave.
        """
        decomposed = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(
            ch for ch in decomposed if unicodedata.category(ch) != "Mn"
        )
        return re.sub(r"\s+", " ", without_accents).strip()

    @staticmethod
    def _infer_category(normalized_text: str) -> Category:
        """Calcula el puntaje ponderado por categoria y resuelve empates.

        Evalua todas las expresiones regulares de `CATEGORY_RULES` sobre el texto
        normalizado. Si ninguna regla coincide, asigna `Category.BUG` por defecto
        para que el ticket reciba atencion tecnica general.
        """
        scores: dict[Category, int] = {
            category: sum(
                weight for pattern, weight in rules if pattern.search(normalized_text)
            )
            for category, rules in CATEGORY_RULES.items()
        }

        max_score = max(scores.values())
        if max_score == 0:
            return Category.BUG

        # En caso de empate con puntaje positivo, aplicamos el orden de riesgo.
        for category in CATEGORY_TIEBREAK_ORDER:
            if scores[category] == max_score:
                return category

        return Category.BUG

    @staticmethod
    def _infer_priority(normalized_text: str, category: Category) -> Priority:
        """Determina la prioridad aplicando reglas explicitas o la prioridad base."""
        for priority, patterns in PRIORITY_RULES:
            if any(pattern.search(normalized_text) for pattern in patterns):
                return priority

        return BASE_PRIORITY_BY_CATEGORY[category]

    def analyze(self, message: str) -> AnalyzeResponse:
        """Clasifica una solicitud usando reglas simbolicas y devuelve contrato fijo.

        Args:
            message: Texto original de la solicitud del usuario.

        Returns:
            AnalyzeResponse: Clasificacion determinista con `mode="traditional"` y
                `requiresHumanReview=True` obligatorio si `category == SECURITY`.
        """
        normalized_text = self._normalize_text(message)
        category = self._infer_category(normalized_text)
        priority = self._infer_priority(normalized_text, category)
        response_text = PREDEFINED_RESPONSES[category][priority]

        # Regla obligatoria de seguridad (Requerimiento 4): todo posible incidente
        # de seguridad debe marcarse para revision humana.
        requires_human_review = category == Category.SECURITY

        return AnalyzeResponse(
            category=category,
            priority=priority,
            response=response_text,
            requiresHumanReview=requires_human_review,
            mode=AnalysisMode.TRADITIONAL,
        )
