# Revisión Científica y Clínica - Evaluación Integral de Seguridad y Límites (Motor de Riesgo v1.4)

## A. Alcance
- **Función:** Evaluación sistémica de las reglas deterministas de seguridad en el motor de riesgo (`backend/app/services/risk_engine.py`), concretamente la separación entre prioridades de revisión urgentes (Nivel 4) y valoraciones prioritarias por deterioro clínico (Nivel 3).
- **Versión/diff:** Motor de Riesgo v1.4, revisando la formulación vigente de `calculate_risk_level`, las variables calculadas como `adverse_composite_z`, y el enrutamiento de las alertas.
- **Población/Contexto:** Pacientes monitorizados de manera longitudinal en el entorno de autocuidado de PsychDeep 3, donde la intervención del algoritmo es descriptiva y de enrutamiento profesional, no diagnóstica ni terapéutica per se.
- **Material Inspeccionado:** `backend/app/services/risk_engine.py`, `docs/CLINICAL_RISK_BASIS.md`, `docs/MANUAL_TERAPEUTA.md`, y especificaciones principales.

## B. Conclusión
El sistema evaluado protege adecuadamente a los usuarios al no extrapolar variaciones estadísticas de series temporales hacia emergencias clínicas automáticas. Se sostiene la validez de la arquitectura en la cual las alarmas N4 (Revisión clínica urgente) están estrictamente reservadas a confirmaciones directas de ideación/planes, o a la detección unívoca y vigente de dichas señales por parte del analizador lingüístico (`ideation_direct`). Por otro lado, la convergencia de estresores, las señales de despedida, la ideación indirecta o los saltos extremos en el `adverse_composite_z`, desencadenan alertas N3. Este diseño es seguro, minimiza la falsa atribución de intencionalidad autolítica por parte de la IA, y adhiere a la necesidad de evaluación prospectiva humana frente a la ambigüedad.

## C. Evidencia
- **Guía NICE NG225, Sección 1.6:** Prohíbe el uso de escalas o estratificaciones globales (p. ej., sumas de malestar psicosocial o de sueño) para predecir eventos agudos como el suicidio. El sistema acata esta norma al relegar el deterioro estadístico al Nivel 3 (valoración clínica) en lugar del Nivel 4 (emergencia inminente).
- **SAFE-T (SAMHSA, 2024):** Respalda que los factores de protección no anulan las señales agudas; en el motor, las señales lingüísticas vigentes no se refutan automáticamente ante intervenciones neutrales subsecuentes en la ventana, manteniendo la prioridad N3/N4 según proceda.
- **Reglas del Producto (CLINICAL_RISK_BASIS.md):** La política vigente establece de manera imperativa: "Los niveles N0–N4 [...] no son puntos de corte clínicamente validados. No deben decidir por sí solos alta, acceso a tratamiento o intervención de emergencia". El motor técnico se alinea estrictamente con este contrato y no escala a N4 derivaciones que no sean declaraciones directas.

## D. Hallazgos
- **Identificador:** CLINICAL_COMPLIANCE_N4_BOUNDARIES
- **Ubicación:** `backend/app/services/risk_engine.py` (`calculate_risk_level`).
- **Observación reproducible:** El motor restringe las etiquetas N4 únicamente a las reglas `N4_declaracion_ideacion_o_plan` y `N4_senal_linguistica_ideacion_directa`. Cualquier otro deterioro concurrente, como el riesgo interpersonal, la inestabilidad con rumiación o el contexto de recaída, está restringido al nivel máximo N3.
- **Mecanismo/Impacto:** Esto previene la fatiga de alertas por parte de los profesionales clínicos, las disrupciones graves no indicadas sobre la autonomía del paciente (falsas emergencias 112), y la reificación diagnóstica por parte de un modelo predictivo.
- **Certeza:** Alta (Evaluación confirmada por inspección del flujo determinista de la aplicación).
- **Prioridad:** Menor (Se trata de un hallazgo confirmatorio y de validación documental).
- **Propuesta:** Mantener las reglas vigentes; ninguna convergencia indirecta o estadística debe ser recategorizada a Nivel 4 bajo ninguna circunstancia sin re-validación prospectiva profunda de su VPP (Valor Predictivo Positivo).

## E. Casos de aceptación
**Caso de Seguridad: Prevención de salto de categoría predictiva**
- **Entrada sintética:** Paciente con score z adverso de 2.8, rumiación reportada en 0.90, tendencia de sueño empeorando, índice de riesgo interpersonal vivo, y señal de despedida inferida del texto ("Dejé los papeles en la mesa, gracias"). No hay ideación directa reportada.
- **Comportamiento esperado:** El sistema dispara las reglas de convergencia extrema (`N3_convergencia_critica_extrema`) y convergencia interpersonal (`N3_convergencia_interpersonal_despedida`), estableciendo el nivel final en N3 (Revisión profesional prioritaria pendiente).
- **Fallo que detectan:** Un sistema sobre-entrenado podría asumir que la gran carga de sufrimiento y preparación indica emergencia inminente, lo cual es una probabilidad, no una certeza. El N3 impone una barrera de evaluación clínica que confirma o refuta, evitando falsos 112.
- **Fundamento:** Salvaguardar la autonomía del paciente evitando respuestas desproporcionadas cuando la intención y el método letal no son explícitos, conforme al contrato del software.

## F. Validación pendiente
- **Estudio o revisión humana necesarios:** Monitorear durante 6 meses el desempeño retrospectivo de casos N3 generados por riesgo interpersonal e ideación indirecta, comparándolos con el dictamen final del operador humano al resolver la alerta.
- **Comparador:** Tasa de alertas N3 descartadas ("dismissed") frente a las resueltas con plan de seguridad escalado, para ajustar si los umbrales de convergencia son demasiado sensibles.
- **Riesgos:** La sobredependencia del profesional en esperar a un "N4" para intervenir. La capacitación humana (MANUAL_TERAPEUTA.md) debe asegurar que los profesionales entiendan que el "N3" sigue requiriendo acción urgente (a valoración).

**Estado Final:** Sin objeciones identificadas en este alcance. El motor determinista v1.4 es robusto y fiel a los estatutos clínicos definidos.
