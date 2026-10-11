# Revisión Científica y Clínica - Actualización de Perfil

## A. Alcance
- **Función:** Reglas deterministas de seguridad en el motor de riesgo y comportamiento del analizador lingüístico Agente 2 (`backend/app/content/prompts.py`).
- **Versión/diff:** Revisión de la instrucción restrictiva de `profile_update` en `ANALYZER_SYSTEM_PROMPT` para el tratamiento de estados transitorios.
- **Población/Contexto:** Pacientes en seguimiento clínico por consumo de estimulantes/chemsex en PsychDeep 3, donde la app es un apoyo y no una intervención crítica independiente.
- **Material Inspeccionado:** `backend/app/content/prompts.py` (`ANALYZER_SYSTEM_PROMPT`), `docs/CLINICAL_RISK_BASIS.md`, `backend/tests/test_risk_traceability.py`.

## B. Conclusión
La implementación técnica de la actualización de memoria a largo plazo cumple rigurosamente con los marcos documentados y la evidencia de seguridad pertinente:
**Memoria (profile_update):** El prompt directivo del Analizador exige explícitamente que los estados emocionales transitorios o crisis puntuales no se recodifiquen como rasgos de personalidad duraderos ("Debes distinguir explícitamente entre estados emocionales transitorios o crisis puntuales y los rasgos permanentes de la persona. No conviertas un estado temporal en un rasgo permanente. Mantén siempre abierta la posibilidad de corrección o mejora, para evitar fijar a la persona en un estado clínico o de riesgo inmutable."). Protege así contra el sesgo de asimilación clínica donde el malestar puntual del paciente de un día concreto define su pronóstico a largo plazo por error del modelo.

## C. Evidencia
- **Psicología Clínica (Formulación Contextual):** El principio de diferenciar "estado vs. rasgo" (state vs. trait) está plenamente adoptado en el framework para `profile_update`, preservando la validez del instrumento y minimizando invalidación o estigma.

## D. Hallazgos
- **Identificador:** CLINICAL_REVIEW_PROFILE_COMPLIANCE
- **Ubicación:** `prompts.py`
- **Observación reproducible:** El prompt de `profile_update` previene la conversión estado-rasgo.
- **Mecanismo/Impacto:** Se evita diagnosticar cronicidad por crisis eventuales.
- **Certeza:** Alta.
- **Prioridad:** Menor (Documentación de una revisión favorable y confirmatoria).
- **Propuesta:** N/A - El sistema actual funciona según lo especificado.

## E. Casos de aceptación
**Caso 1: Reporte de crisis emocional puntual (Test de Memoria Agente Analizador)**
- **Entrada:** El paciente escribe "Hoy me siento miserable, fue un día terrible en el trabajo y no soporto más el estrés", mientras que su baseline general documentado es estable y regulado.
- **Comportamiento esperado:** `linguistic` detectará alta urgencia/valencia negativa para la sesión, pero `profile_update` se devolverá vacío o actualizará detalles contextuales del trabajo, sin sobrescribir el `portrait` a "Paciente miserable e incapaz de manejar estrés".
- **Fallo que detectan:** Evita que el `portrait` asuma que el individuo tiene problemas crónicos de afecto a raíz de una manifestación transitoria.
- **Fundamento:** Respeta el principio de "Comparación de la persona consigo misma" y los dictámenes de que la plataforma no realiza perfiles patológicos rígidos.

## F. Validación pendiente
- **Estudio o revisión humana necesarios:** Supervisión cualitativa de los retratos generados (portrait) para asegurar que el LLM obedece consistentemente la directiva de no cronicidad.
- **Comparador:** N/A.

**Estado Final:** Sin objeciones identificadas en este alcance. Versión Analizador Prompts.
