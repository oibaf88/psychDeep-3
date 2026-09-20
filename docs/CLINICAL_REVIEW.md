# REVISIÓN CIENTÍFICA Y CLÍNICA - MOTOR DE RIESGO v1.4

**A. Alcance**
- **Función:** Reglas de alerta deterministas en el motor clínico (`backend/app/services/risk_engine.py` y `backend/tests/test_false_positive.py`).
- **Versión revisada:** v1.4.
- **Pregunta:** Verificación de la separación de prioridades operativas entre emergencias suicidas confirmadas (N4) y convergencia estadística/psicosocial (N3), y eliminación de referencias incorrectas.
- **Población/contexto:** Usuarios generales y pacientes en seguimiento ambulatorio donde las alertas disparan flujos de revisión profesional o de urgencia.

**B. Conclusión**
- La regla de convergencia estadística (`N3_convergencia_critica_extrema`) y la regla de convergencia interpersonal (`N3_convergencia_interpersonal_despedida`) asignan correctamente la prioridad operativa Nivel 3.
- Sin embargo, las pruebas unitarias y la documentación del código mantenían la denominación obsoleta de "N4" para la convergencia interpersonal, lo cual contradecía la base clínica y sugería que la convergencia determinaba una emergencia aguda en lugar de una revisión profesional.
- **Se sostiene:** Las reglas N4 se mantienen exclusivamente para declaración directa y confirmación explícita.
- **Se modificó:** Corrección de la nomenclatura en los tests (`test_the_n3_interpersonal_convergence_rule_is_unchanged`) y en las directrices de avance, eliminando el artefacto documental de que "N4 es convergencia".

**C. Evidencia**
- **NICE NG225, 1.6:** Las escalas globales y algoritmos no deben predecir el suicidio, sino informar decisiones clínicas. Agrupar factores psicosociales (carga percibida, soledad) en un algoritmo no sustituye la valoración directa para una emergencia (N4).
- **SAFE-T (SAMHSA, 2024):** Indica que las emergencias agudas se confirman con preguntas directas y planes de acción, y no con inferencias estadísticas.
- **Límites documentados (`docs/CLINICAL_RISK_BASIS.md`):** N4 es exclusivamente para crisis confirmadas y N3 para revisión.

**D. Hallazgos**
- **ID:** FND-01-NOMENCLATURA-N4
- **Ubicación:** `backend/tests/test_false_positive.py`
- **Mecanismo:** El título de la prueba (`test_the_n4_convergence_rule_is_unchanged`) y la documentación interna promovían la comprensión errónea de que la convergencia producía una escalada N4, debilitando los controles cognitivos sobre el diseño del sistema.
- **Certeza:** Alta (verificable en código y manuales).
- **Prioridad:** Menor (impacto en desarrolladores, no en comportamiento de producción).
- **Propuesta:** Renombrar la función a `test_the_n3_interpersonal_convergence_rule_is_unchanged` y corregir los docstrings. (COMPLETADO).

**E. Casos de aceptación**
- **Entrada/contexto:** `ideation_indirect=True`, `interpersonal_live=True`, `leave_taking=True`.
- **Comportamiento esperado:** La regla se clasifica bajo `N3_convergencia_interpersonal_despedida` (prioridad operativa Nivel 3) sin gatillar el sistema como Nivel 4 (que requiere `ideation_direct=True` o `n4_declarations>0`).
- **Fallo que detectan:** Evitan que un cambio estadístico o de lenguaje figurado active por sí solo una alarma general de hospitalización en el sistema de profesionales humanos y de salud.

**F. Validación pendiente**
- **Estudio necesario:** Evaluación clínica (adjudicación por psiquiatras/psicólogos) de la sensibilidad de la regla de convergencia N3 real y validación de cuántos casos de N3 se convierten o escalan a una verdadera urgencia de salud en la práctica para la revisión de los umbrales de convergencia (`SUBTLE_RUMINATION_MIN`, etc.).
- **Criterio de avance:** Completar la revisión humana de al menos 50 alertas sintéticas / históticas disparadas bajo `N3_convergencia_critica_extrema` para confirmar la pertinencia de revisión.
