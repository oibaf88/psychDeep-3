# Revisión Científica y Clínica - Convergencia Estadística y Actualización de Perfil

## A. Alcance
- **Función:** Reglas deterministas de seguridad en el motor de riesgo (`backend/app/services/risk_engine.py`) y comportamiento del analizador lingüístico Agente 2 (`backend/app/content/prompts.py`).
- **Versión/diff:** Revisión de la implementación de `N3_convergencia_critica_extrema` evaluando `adverse_composite_z > 2.4` junto con empeoramiento concurrente (rumiación o sueño), y la instrucción restrictiva de `profile_update` en `AGENT2_SYSTEM_PROMPT` para el tratamiento de estados transitorios.
- **Población/Contexto:** Pacientes en seguimiento clínico por consumo de estimulantes/chemsex en PsychDeep 3, donde la app es un apoyo y no una intervención crítica independiente.
- **Material Inspeccionado:** `backend/app/services/risk_engine.py` (Líneas 340-355, 420-450, 790-810), `backend/app/content/prompts.py` (Instrucción 6 de `AGENT2_SYSTEM_PROMPT`, Líneas 206-209), `docs/CLINICAL_RISK_BASIS.md`, `backend/tests/test_risk_traceability.py`.

## B. Conclusión
La implementación técnica de ambas funciones clínicas (convergencia estadística y actualización de memoria a largo plazo) cumple rigurosamente con los marcos documentados y la evidencia de seguridad pertinente:
1. **Convergencia Estadística (N3):** El motor separa de forma fiable el riesgo estadístico (N3) de la ideación directa (N4). Un paciente con un cambio severo en su métrica adversa (`adverse_composite_z > 2.4`) junto con rumiación o problemas de sueño acciona adecuadamente una bandera N3 (Revisión Clínica Prioritaria Pendiente) en lugar de un falso N4 (Emergencia / Revisión Clínica Urgente). Esto se ajusta al principio de que la desviación de medidas repetidas no predice eventos agudos automáticamente, pero requiere un seguimiento prospectivo profesional.
2. **Memoria (profile_update):** El prompt directivo del Agente 2 exige explícitamente que los estados emocionales transitorios o crisis puntuales no se recodifiquen como rasgos de personalidad duraderos ("No conviertas un estado transitorio o una crisis puntual en un rasgo permanente"). Protege así contra el sesgo de asimilación clínica donde el malestar puntual del paciente de un día concreto define su pronóstico a largo plazo por error del modelo.

## C. Evidencia
- **NICE NG225 (Recomendación 1.6):** Las herramientas y escalas no deben usarse para estratificar el riesgo en alto/bajo ni predecir el suicidio o repeticiones de autolesión. El uso de `adverse_composite_z` gatillando un flag de revisión prospectiva *clínica* (N3), y no un dictamen automático de emergencia 112 (N4), es compatible con esto.
- **CLINICAL_RISK_BASIS.md:** Establece que "Los cambios estadísticos, incluso concurrentes con rumiación/sueño, alcanzan revisión profesional N3; no se interpreta esa suma como emergencia suicida N4". El código vigente y los tests (`test_risk_traceability.py`) confirman la adhesión.
- **Psicología Clínica (Formulación Contextual):** El principio de diferenciar "estado vs. rasgo" (state vs. trait) está plenamente adoptado en el framework para `profile_update`, preservando la validez del instrumento y minimizando invalidación o estigma.

## D. Hallazgos
- **Identificador:** CLINICAL_REVIEW_N3_PROFILE_COMPLIANCE
- **Ubicación:** `risk_engine.py` y `prompts.py`
- **Observación reproducible:** El código asocia la regla de convergencia `N3_convergencia_critica_extrema` al nivel de alerta 3, comprobando la variable de `adverse_composite_z` > 2.4 (deterioro estructural) más `extreme_convergence` o problemas de sueño. Simultáneamente, el prompt de `profile_update` previene la conversión estado-rasgo.
- **Mecanismo/Impacto:** Se evita activar alarmas N4 infundadas por suma de problemas estructurales sin intencionalidad expresa; se evita diagnosticar cronicidad por crisis eventuales.
- **Certeza:** Alta (El código estático y los tests lo corroboran directamente).
- **Prioridad:** Menor (Documentación de una revisión favorable y confirmatoria).
- **Propuesta:** N/A - El sistema actual funciona según lo especificado.

## E. Casos de aceptación
**Caso 1: Convergencia de estrés sin ideación explícita (Test de seguridad N3)**
- **Entrada:** Paciente que registra un empeoramiento súbito en las cuatro dimensiones (score z compuesto > 2.5) y señala estar durmiendo 2 horas menos (tendencia "empeorando"), pero no hay mención a ideación.
- **Comportamiento esperado:** Flag de alerta `N3_convergencia_critica_extrema` (Nivel 3).
- **Fallo que detectan:** Un modelo predictivo defectuoso podría inferir erróneamente un estado N4 por el elevado peso del malestar. El motor determinista vigente rechaza ese salto.
- **Fundamento:** Se solicita validación profesional humana para evaluar si la carga estresante compromete la seguridad.

**Caso 2: Reporte de crisis emocional puntual (Test de Memoria Agente 2)**
- **Entrada:** El paciente escribe "Hoy me siento miserable, fue un día terrible en el trabajo y no soporto más el estrés", mientras que su baseline general documentado es estable y regulado.
- **Comportamiento esperado:** `linguistic` detectará alta urgencia/valencia negativa para la sesión, pero `profile_update` se devolverá vacío o actualizará detalles contextuales del trabajo, sin sobrescribir el `portrait` a "Paciente miserable e incapaz de manejar estrés".
- **Fallo que detectan:** Evita que el `portrait` asuma que el individuo tiene problemas crónicos de afecto a raíz de una manifestación transitoria.
- **Fundamento:** Respeta el principio de "Comparación de la persona consigo misma" y los dictámenes de que la plataforma no realiza perfiles patológicos rígidos.

## F. Validación pendiente
- **Estudio o revisión humana necesarios:** Supervisión de la saturación de alertas (alert fatigue) a los 30 días de la implementación del N3 con el corte 2.4 de `adverse_composite_z`.
- **Comparador:** Frecuencia de verdaderos positivos (desestabilización real comprobada por el clínico) versus falsos positivos en las derivaciones N3 debidas a fluctuaciones no perjudiciales normales en la línea base de los pacientes.

**Estado Final:** Sin objeciones identificadas en este alcance. Versión `v1.4` (Motor de riesgo v1.4, Analizador `analyzer-prompt-2026-08-25c`).