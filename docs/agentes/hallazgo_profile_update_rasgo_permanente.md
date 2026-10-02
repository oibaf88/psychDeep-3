# Hallazgo: Riesgo de conversión de estado transitorio en rasgo permanente

**A. Alcance:**
Función: Actualización del perfil clínico (Agent 2 - `profile_update`).
Versión/diff: prompt del Agente 2 en `backend/app/content/prompts.py`.
Pregunta: ¿Cómo se asegura que un evento adverso o un mal día no se inscriba como un rasgo permanente en el retrato del paciente?
Población/contexto: Todos los usuarios que introducen texto a través del check-in, diario o chat.

**B. Conclusión:**
sin objeciones identificadas en este alcance. El prompt del Agente 2 para la sección `profile_update` ya incluye salvaguardas explícitas para diferenciar entre estados transitorios y características estables.

**C. Evidencia:**
Revisión del archivo `backend/app/content/prompts.py`: La sección "BLOQUE 3 — `profile_update`: lo que hoy añade a conocer a la persona" pide "reescribe el retrato COMPLETO, incorporando lo nuevo" e incluye explícitamente: "No conviertas un estado transitorio o una crisis puntual en un rasgo permanente de la persona. Distingue entre un cambio duradero y cómo se siente hoy. Mantén siempre abierta la posibilidad de corrección o mejora."

**D. Hallazgos:**
- Identificador: PROFILE_TRANSIENT_STATE_TO_TRAIT
- Ubicación: `backend/app/content/prompts.py` (`AGENT_2_SYSTEM_PROMPT` y `ANALYZER_SYSTEM_PROMPT`, sección `profile_update`).
- Observación reproducible: En la instrucción de `profile_update`, ya existe una directiva expresa que impide inferir que un evento emocional intenso puntual constituye un rasgo identitario.
- Mecanismo/Impacto: Mitiga el riesgo de que un momento de crisis reescriba todo el perfil, alterando el "baseline" clínico contextual.
- Certeza: Alta (verificado en el código base actual).
- Prioridad: Menor (problema ya resuelto en la implementación).
- Propuesta: Cerrar el hallazgo. La instrucción "No conviertas un estado transitorio o una crisis puntual en un rasgo permanente de la persona. Distingue entre un cambio duradero y cómo se siente hoy. Mantén siempre abierta la posibilidad de corrección o mejora." ya está presente en las instrucciones del Agente 2 y del Analizador.

**E. Casos de aceptación:**
Entrada/contexto sintéticos: Un paciente dice "Hoy estoy tan desesperado que siento que no sirvo para nada".
Comportamiento esperado: El `profile_update` no incluye "Se considera una persona que no sirve para nada" ni "Es un individuo desesperado". El retrato no se modifica, o, a lo sumo, la crisis aguda no borra las fortalezas previas.
Fallo que detectan: Evitan una profecía autocumplida en la memoria estructurada donde una queja temporal reescribe la identidad del usuario a los ojos del sistema.

**F. Validación pendiente:**
Verificar empíricamente la tasa de actualización de perfiles con estados temporales en producción. Se requerirá revisión cualitativa humana (por profesionales clínicos) para evaluar la evolución del perfil longitudinal.
