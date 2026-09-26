# Hallazgo: Riesgo de conversión de estado transitorio en rasgo permanente

**A. Alcance:**
Función: Actualización del perfil clínico (Agent 2 - `profile_update`).
Versión/diff: prompt del Agente 2 en `backend/app/content/prompts.py`.
Pregunta: ¿Cómo se asegura que un evento adverso o un mal día no se inscriba como un rasgo permanente en el retrato del paciente?
Población/contexto: Todos los usuarios que introducen texto a través del check-in, diario o chat.

**B. Conclusión:**
El prompt actual del Agente 2 para la sección `profile_update` instruye reescribir el retrato "COMPLETO, incorporando lo nuevo", pero no incluye salvaguardas para diferenciar expresamente entre estados transitorios y características estables. Existe el riesgo de que el perfil acumule crisis aisladas o fluctuaciones del estado de ánimo como definitorias, estigmatizando a la persona y perdiendo la flexibilidad que demanda un seguimiento clínico.

**C. Evidencia:**
1. Instrucciones para la revisión científica: "Comprueba que una actualización de perfil no convierta un estado transitorio en un rasgo permanente y que persista la posibilidad de corrección".
2. Revisión del archivo `backend/app/content/prompts.py`: La sección "BLOQUE 3 — `profile_update`: lo que hoy añade a conocer a la persona" pide "reescribe el retrato COMPLETO, incorporando lo nuevo. Cómo se expresa, qué temas vuelven...", pero omite advertir contra la generalización de estados transitorios.

**D. Hallazgos:**
- Identificador: PROFILE_TRANSIENT_STATE_TO_TRAIT
- Ubicación: `backend/app/content/prompts.py` (`AGENT_2_SYSTEM_PROMPT`, sección `profile_update`).
- Observación reproducible: En la instrucción de `profile_update`, falta una directiva expresa que impida inferir que un evento emocional intenso puntual constituye un rasgo identitario.
- Mecanismo/Impacto: Puede provocar que un momento de crisis reescriba todo el perfil, alterando el "baseline" clínico contextual y, en última instancia, condicionando negativamente la actitud del propio agente o del terapeuta al leer el perfil.
- Certeza: Alta (hallazgo en el prompt).
- Prioridad: Mayor (falla en el principio de autonomía y adaptación, posibilidad de estigmatización).
- Propuesta: Añadir una regla estricta en el prompt del Agente 2 que diga: "No conviertas un estado transitorio o una crisis puntual en un rasgo permanente de la persona. Distingue entre un cambio duradero y cómo se siente hoy. Mantén siempre abierta la posibilidad de corrección o mejora".

**E. Casos de aceptación:**
Entrada/contexto sintéticos: Un paciente dice "Hoy estoy tan desesperado que siento que no sirvo para nada".
Comportamiento esperado: El `profile_update` no debe incluir "Se considera una persona que no sirve para nada" ni "Es un individuo desesperado". El retrato no se modifica, o, a lo sumo, la crisis aguda no borra las fortalezas previas.
Fallo que detectan: Evitan una profecía autocumplida en la memoria estructurada donde una queja temporal reescribe la identidad del usuario a los ojos del sistema.

**F. Validación pendiente:**
Verificar empíricamente la tasa de actualización de perfiles con estados temporales tras aplicar la mejora al prompt. Se requerirá revisión cualitativa humana (por profesionales clínicos) para evaluar la evolución del perfil longitudinal con esta regla en producción.