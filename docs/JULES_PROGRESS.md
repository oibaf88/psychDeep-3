# Jules progress

## Target
PsychDeep is a longitudinal mental health monitoring and support platform that combines user-authorized data, structured memory, and temporal analysis. Its purpose is not to replace professional evaluation or issue diagnoses, but to help understand patterns, detect relevant changes, reinforce protective factors, and facilitate earlier human intervention when appropriate.

## Specification coverage

- **Identidad y consentimiento:** DONE
- **Ingesta y conectores (Check-in, Diario, Chat):** DONE
- **Normalización temporal:** DONE
- **Feature Store clínico-conductual (Score Estructural, Índice Psicosocial):** DONE
- **Memoria longitudinal:** DONE
- **Inferencia clínica (Riesgo Determinista, RAG):** PARTIAL
- **Intervención y acompañamiento (Safety Plan, Wave, Crisis):** DONE
- **Auditoría y trazabilidad:** DONE

## Current technical debt
- Accessibility in forms (e.g., PatientDashboard check-ins lack proper labels and scale descriptions).
- SMS and push notification integration is missing (currently only DB/in-app and email are supported).

## Recently completed
- Setup project architecture and basic modules.
- Implemented core entities and the deterministic risk engine.

## Recommended next work
1. Improve accessibility and UX of the daily check-in form.
2. Refine empty states across dashboards.
3. Enhance the accessibility of the diary page.
4. Implement mobile responsive polish for the timeline charts.
5. Add additional RAG content modules to expand `safety_resources.py` and `prompts.py`.
