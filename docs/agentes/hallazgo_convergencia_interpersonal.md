# Hallazgo: Referencia obsoleta de N4 para la convergencia interpersonal en la interfaz del terapeuta

## A. Alcance
- **Función:** Componente frontend `ManualPage.tsx` que documenta las reglas del motor de riesgo.
- **Versión/diff:** Corrección aplicada en la tabla de prioridades operativas del manual.
- **Población/Contexto:** Profesionales que consultan la documentación interna de PsychDeep.
- **Material Inspeccionado:** `frontend/src/pages/ManualPage.tsx`, `backend/app/services/risk_engine.py`, `docs/CLINICAL_RISK_BASIS.md`.

## B. Conclusión
La convergencia interpersonal (ideación indirecta + señal interpersonal vigente + despedida) fue correctamente recategorizada en el motor backend de Nivel 4 (emergencia) a Nivel 3 (valoración prioritaria), de acuerdo con los estándares clínicos. Sin embargo, persistía una referencia desactualizada en el manual del terapeuta (`ManualPage.tsx`) que seguía mostrando esta regla como `N4_convergencia_interpersonal_despedida` (Nivel 4). Esto causaba una inconsistencia entre la implementación real del motor y la documentación mostrada al usuario.

## C. Evidencia
- **Fuentes:**
  1. `docs/CLINICAL_RISK_BASIS.md`: Señala que la evaluación clínica determina el peligro inmediato y actuación; un flag de IA o convergencia de señales indirectas e interpersonales no establece por sí mismo una emergencia (N4).
  2. Implementación de `risk_engine.py`: La regla `N3_convergencia_interpersonal_despedida` ya está implementada como Nivel 3.
  3. NICE NG225 (Sección 1.6): Desaconseja usar categorizaciones de escalas como predictores automáticos de decisiones urgentes.

## D. Hallazgos
- **Identificador:** RISK_MANUAL_INTERPERSONAL_N4_OBSOLETE
- **Ubicación:** `frontend/src/pages/ManualPage.tsx`
- **Observación Reproducible:** En la tabla de reglas del manual, se visualizaba la fila `["3", "N4_convergencia_interpersonal_despedida", 4, "Ideación indirecta + señal interpersonal vigente + despedida; valoración urgente"]`.
- **Mecanismo/Impacto:** Genera confusión en el personal clínico al sugerir que el sistema emitirá alarmas automáticas de emergencia (N4) basadas en señales indirectas (como riesgo interpersonal y despedida), cuando en la realidad técnica esto produce una alerta de prioridad profesional (N3). Esto contraviene el principio de que los profesionales deben entender claramente qué causa las alertas.
- **Certeza:** Alta (inconsistencia directa observada en el código fuente).
- **Prioridad:** Menor (impacto documental, el motor técnico ya operaba correctamente).
- **Propuesta:** Reemplazar el identificador por `N3_convergencia_interpersonal_despedida`, ajustar el nivel a `3`, y modificar la descripción a "valoración prioritaria" en vez de "valoración urgente".

## E. Casos de aceptación
- **Entrada/contexto sintético:** Un usuario visita la página del manual clínico en el frontend.
- **Comportamiento Esperado:** La tabla de riesgos muestra la regla "N3_convergencia_interpersonal_despedida" asociada al nivel 3 y con descripción "Ideación indirecta + señal interpersonal vigente + despedida; valoración prioritaria".
- **Fallo que detectan:** Evita que el clínico asuma incorrectamente que las señales indirectas confluentes generarán una escalada inmediata de emergencia, reduciendo la ansiedad profesional o desconfianza en el sistema.
- **Fundamento:** Alinear la interfaz documental con la implementación técnica y los estándares clínicos de NICE NG225.

## F. Validación pendiente
- **Validación:** Confirmar que no queden más referencias a reglas "N4" obsoletas en otros componentes del frontend.
- **Criterio de avance:** Inspección visual o test automatizado de la página del manual para verificar la visualización correcta de la tabla de reglas operativas.
