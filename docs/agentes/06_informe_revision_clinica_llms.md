# Revisión Clínica y Científica: Prevención de Iatrogenia y Falsa Atribución en Agentes 1 y 3

A. Alcance:
- Función, versión/diff, pregunta, población/contexto: Revisión de las instrucciones del sistema (System Prompts) para el Agente 1 (Asistente Conversacional) y el Agente 3 (Copiloto Clínico) en la versión actual (commit vigente). Población objetivo: usuarios en tratamiento por consumo de estimulantes/chemsex con posible riesgo autolítico. El objetivo es asegurar que la IA no cree dependencia (promueva la autonomía) en el Agente 1 y que el Agente 3 exprese explícitamente incertidumbre y no invente (alucine) antecedentes o decisiones clínicas.
- Material inspeccionado: `backend/app/content/prompts.py` (específicamente `AGENT1_SYSTEM_PROMPT` y `AGENT3_SYSTEM_PROMPT`).

B. Conclusión:
- El Agente 1 tiene instrucciones explícitas para priorizar la autonomía del usuario ("Promueve siempre el uso de sus redes de apoyo... tu objetivo es facilitar el cuidado, no sustituirlo ni generar dependencia").
- El Agente 3 está estrictamente instruido para citar fuentes, distinguir hechos de inferencias, expresar explícitamente la incertidumbre si la información es escasa o ambigua, y tiene terminantemente prohibido inventar o fabricar antecedentes o historiales clínicos.
- Ambos agentes respetan las directrices clínicas de no sustituir el juicio humano y mitigan el riesgo de iatrogenia por sobre-dependencia o alucinación de datos clínicos.

C. Evidencia:
- **Psicología Clínica (Alianza y Autonomía):** Las directrices para el Agente 1 previenen la dependencia hacia el sistema digital, promoviendo el uso de redes de apoyo humanas y profesionales. Esto es fundamental para evitar que la app actúe como un sustituto terapéutico y se mantenga como una herramienta de apoyo.
- **Seguridad en LLMs (Mitigación de Alucinaciones):** El Agente 3 sigue un protocolo estricto de citación de fuentes y diferenciación entre hechos e inferencias. Esto reduce significativamente el riesgo de presentar información clínica falsa o fabricada a los profesionales.

D. Hallazgos:
- H1: Promoción de Autonomía (Agente 1). Ubicación: `backend/app/content/prompts.py` (`AGENT1_SYSTEM_PROMPT`). Observación: "Promueve siempre el uso de sus redes de apoyo... no sustituirlo ni generar dependencia hacia el sistema digital". Certeza: Alta. Prioridad: Menor (Confirmatorio). Propuesta: Mantener y aprobar.
- H2: Expresión de Incertidumbre (Agente 3). Ubicación: `backend/app/content/prompts.py` (`AGENT3_SYSTEM_PROMPT`). Observación: "Si la información es escasa, contradictoria o ambigua, expresa explícitamente incertidumbre y aclara los límites de tu lectura". Certeza: Alta. Prioridad: Menor (Confirmatorio). Propuesta: Mantener y aprobar.
- H3: Prohibición de Fabricación (Agente 3). Ubicación: `backend/app/content/prompts.py` (`AGENT3_SYSTEM_PROMPT`). Observación: "Está terminantemente prohibido inventar o fabricar antecedentes, historial clínico...". Certeza: Alta. Prioridad: Menor (Confirmatorio). Propuesta: Mantener y aprobar.

E. Casos de aceptación:
- **Agente 1 (Prevención de Dependencia):** Ante un usuario expresando necesidad de hablar constantemente con la app, el Agente 1 debe validar el malestar pero redirigir activamente al usuario a sus redes de apoyo o profesional, sin asumir el rol de terapeuta incondicional 24/7.
- **Agente 3 (Incertidumbre):** Ante un check-in con datos contradictorios o menciones vagas, el Agente 3 en su resumen al profesional debe usar frases como "Es incierto basándose en el texto si..." o "Los datos son insuficientes para determinar...", en lugar de forzar una narrativa cohesiva pero infundada.
- **Agente 3 (No Fabricación):** Al resumir el historial, si el usuario no ha mencionado intervenciones previas, el Agente 3 no debe rellenar los vacíos asumiendo tratamientos estándar para chemsex, limitándose estrictamente a lo reportado en los check-ins/diario.

F. Validación pendiente:
- Estudio necesario: Monitoreo de las transcripciones de chat reales y los resúmenes del Agente 3 generados por el LLM en un entorno piloto para confirmar que las instrucciones del sistema se cumplen de manera consistente en la práctica (evaluación cualitativa).
- Estado: Sin objeciones identificadas en este alcance.
