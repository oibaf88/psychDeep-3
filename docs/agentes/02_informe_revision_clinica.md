# Revisión Científica y Clínica - Corrección de Convergencia Estadística

La cascada pre-trazado ya no está en el runtime. La regla vigente evalúa `adverse_composite_z > 2.4` junto con rumiación extrema o empeoramiento del sueño, y selecciona `N3_convergencia_critica_extrema` en `calculate_risk_level`.

## A. Alcance
- **Función:** Motor de riesgo clínico (`backend/app/services/risk_engine.py`), específicamente la función `_convergencia_critica_extrema` utilizada en el cálculo legacy (`_calculate_risk_level_legacy`).
- **Versión/diff:** Reemplazo de la variable y umbral desaprobado (`structural_score < 0.20`) por la métrica corregida y alineada a los estándares de la versión actual (`adverse_composite_z > 2.4`).
- **Población/Contexto:** Pacientes monitorizados mediante PsychDeep 3 en la plataforma de autocuidado clínico.
- **Material Inspeccionado:** Lógica de convergencia estadística en `risk_engine.py`, el documento base de riesgo clínico (`docs/CLINICAL_RISK_BASIS.md`), el manual del terapeuta (`docs/MANUAL_TERAPEUTA.md`), y los tests automatizados asociados (`backend/tests/test_risk_safety_v14.py`).

## B. Conclusión
La métrica legacy `structural_score` penalizaba las desviaciones de una manera que dificultaba la interpretabilidad y validación clínica, recortando a cero las desviaciones mayores (incluidas mejoras). Se sostiene que la lógica de convergencia (`_convergencia_critica_extrema`) debe utilizar obligatoriamente `adverse_composite_z` > 2.4, en lugar del antiguo `structural_score < 0.20`. Esto asegura que el deterioro extremo coincidente con altos niveles de rumiación o problemas de sueño accione correctamente un umbral de Nivel 3 (N3), proporcionando alertas proporcionadas a los profesionales y manteniendo la consistencia con el diseño validado de PsychDeep 3.

## C. Evidencia
- **Fuentes:**
  1. `docs/CLINICAL_RISK_BASIS.md`: Detalla que el `structural_score` ha sido actualizado ("structural-v2") a un formato donde los cambios adversos están representados sin un recorte forzoso a cero.
  2. `docs/clinical_review.md`: Específica y explícitamente requiere que "La condición N3 vigente es `adverse_composite_z > 2.4` y además (`rumination_score > 0.85` o empeoramiento del sueño)."
  3. Guía NICE NG225 (Sección 1.6): No deben usarse variables globales opacas y arbitrarias que mezclan componentes para activar protocolos automáticos. El uso de la desviación z de compuestos adversos permite identificar un deterioro sin predecir artificialmente una emergencia.

## D. Hallazgos
- **Identificador:** CLINICAL_COMPOSITE_Z_FIX
- **Ubicación:** `backend/app/services/risk_engine.py`, en la función `_convergencia_critica_extrema`.
- **Observación reproducible:** El motor continuaba llamando a `_convergencia_critica_extrema` usando `structural.score` contra un límite `< 0.20`, ignorando que la política vigente requiere `adverse_composite_z > 2.4`.
- **Mecanismo/Impacto:** Se arriesgaba una divergencia entre el comportamiento del algoritmo principal y los tests o referencias legacy, además de contradecir el estándar clínico documentado para PsychDeep.
- **Certeza:** Alta (violación directa de `clinical_review.md`).
- **Prioridad:** Mayor (Conclusión inválida o fallo relevante).
- **Propuesta:** Reemplazar el argumento de `_convergencia_critica_extrema` a `adverse_composite_z` evaluando contra un límite de `2.4`.

## E. Casos de aceptación
- **Entrada/contexto sintético:** Paciente que exhibe un deterioro extremo (`adverse_composite_z` de 2.6) combinado con problemas de sueño (`sleep_worsening` es verdadero), sin menciones de ideación.
- **Comportamiento esperado:** La lógica evaluará las dos condiciones de convergencia de manera afirmativa y emitirá un flag `N3_convergencia_critica_extrema`, requiriendo de una revisión humana, en lugar de predecir o accionar diagnósticos.
- **Fallo que detectan:** Evita clasificaciones fallidas donde la regresión del score estructural (corte a cero en vez del análisis de los z-scores adversos) oscurecía la señal de un verdadero deterioro perjudicial concurrente con variables de estrés.
- **Fundamento:** Identificación asertiva de deterioro concurrente mediante los compuestos z adversos antes de escalar para un seguimiento prospectivo, previniendo falsas emergencias.

## F. Validación pendiente
- **Estudio o revisión humana necesarios:** Seguimiento longitudinal con operadores clínicos reales.
- **Comparador:** Tasas de falsos positivos en las alertas N3 generadas por el compuesto adverso Z versus el índice de desestabilización cualitativa humana.
- **Riesgos y Criterio de avance:** Posible fatiga de alertas si el 2.4 resulta en la práctica muy conservador. Se debe acordar una re-evaluación retrospectiva de la métrica después de 30 días de operación clínica observacional.