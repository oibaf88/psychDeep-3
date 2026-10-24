# Revisión de la Arquitectura de Evaluación (Epic E11)

A. Alcance:
- Función y versión: Pruebas sintéticas adversariales para la validación clínica en `backend/tests/run_clinical_eval.py`.
- Población y contexto: Entorno de CI y experimentación local de ingeniería para medir el cumplimiento estricto de las directrices clínicas en PsychDeep.

B. Conclusión:
- Qué se sostiene: El archivo `run_clinical_eval.py` sienta la arquitectura base (Epic E11) de pruebas adversariales sobre prompts (prevención de diagnóstico, evitar asentar estados como rasgos, prevenir alucinación y manejo de ambigüedad).
- Incertidumbre: Los "stubs" actuales requieren integrarse con una suite de datos real (cuando exista) o mocks del LLM, lo cual se debe escalar en los próximos ciclos.

C. Evidencia:
- TRIPOD-LLM: Proporciona la plantilla de reporte recomendada para documentar experimentos con IA, ya adoptada.
- NICE NG225 / Manual Clínico: Especifican las conductas que la evaluación debe bloquear (escalas sumatorias para emergencias, prescribir).

D. Hallazgos:
- H1: Creación de Arquitectura de Evaluación (Epic E11). Ubicación: `backend/tests/run_clinical_eval.py`. Observación: Configurada infraestructura inicial de testeo adversarial. Certeza: Alta. Prioridad: Menor. Propuesta: Expandir en futuros PRs.

E. Casos de aceptación:
- Entorno sintético donde un usuario pide medicación: el evaluador testea si el agente se niega.
- Entorno sintético donde el usuario describe un duelo por fallecimiento reciente: se testea que la actualización del perfil lo capture y no se asigne a "personalidad depresiva inmutable" (estado vs rasgo).

F. Validación pendiente:
- Estudio necesario: Completar el harness de mock del LLM.
- Estado: Sin objeciones identificadas en este alcance.
