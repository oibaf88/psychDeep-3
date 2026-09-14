# Hallazgo: Convergencia interpersonal clasificada erróneamente como emergencia automática (N4)

## A. Alcance
- **Función:** Motor de riesgo clínico (`backend/app/services/risk_engine.py`).
- **Versión/diff:** Corrección aplicada a la regla `N4_convergencia_interpersonal_despedida`.
- **Población/Contexto:** Pacientes monitorizados mediante el sistema PsychDeep 3.
- **Material Inspeccionado:** Código del motor de riesgo (`risk_engine.py`), archivo de trazabilidad (`test_risk_traceability.py`), panel clínico (`clinical_view.py`) y especificaciones de seguridad clínica (`docs/CLINICAL_RISK_BASIS.md`).

## B. Conclusión
La regla de convergencia interpersonal, que detecta ideación indirecta junto con riesgo interpersonal vivo (carga percibida y pertenencia frustrada) y una señal de despedida, no constituye una declaración explícita de emergencia (N4). De acuerdo a las directrices clínicas, se compone de señales indirectas e inferencias textuales que requieren valoración prioritaria, no una intervención de emergencia incondicional. Por tanto, debe ser clasificada como nivel 3 (N3), asegurando que el paciente reciba revisión profesional en vez de detonar protocolos automatizados no validados para este constructo.

## C. Evidencia
- **Fuentes:**
  1. `docs/CLINICAL_RISK_BASIS.md`: Regla de seguridad #1: "Ideación indirecta/no explicitada activa y reciente genera como mínimo N3, valoración clínica prioritaria pendiente. No se transforma en ideación confirmada, intención o plan."
  2. Guía NICE NG225 (Sección 1.6): No utilizar escalas o estratificaciones globales (como las sumas de constructos de riesgo interpersonal) para predecir autolesión y detonar respuestas de emergencia.

## D. Hallazgos
- **Identificador:** RISK_INTERPERSONAL_CONVERGENCE_N4
- **Ubicación:** `backend/app/services/risk_engine.py`, `_trace_rule`
- **Observación Reproducible:** Si los criterios de convergencia interpersonal se cumplían, la regla pre-trazada devolvía un `RiskDecision` de `level=4` bajo la regla `N4_convergencia_interpersonal_despedida`.
- **Mecanismo/Impacto:** Producir alarmas nivel 4 automatizadas basadas en inferencias indirectas, causando una intervención desproporcionada que puede romper el pacto terapéutico y desperdiciar recursos de crisis.
- **Certeza:** Alta (contradicción directa de la regla #1 de `CLINICAL_RISK_BASIS.md` y del C-SSRS).
- **Prioridad:** Crítica.
- **Propuesta:** Reemplazar `N4_convergencia_interpersonal_despedida` por `N3_convergencia_interpersonal_despedida`, establecer `level=3` en la definición de la regla y ajustar los mensajes mostrados en el dashboard profesional en `backend/app/services/clinical_view.py`.

## E. Casos de aceptación
- **Entrada/contexto sintético:** Paciente con ideación indirecta (ej. "no le importaría a nadie si no estoy"), puntuación alta en carga percibida y mensaje vigente categorizado como despedida (ej. "adiós a todos"), sin plan ni declaración explícita de ideación directa suicida confirmada.
- **Comportamiento Esperado:** El sistema produce un nivel de alerta N3, con la regla `N3_convergencia_interpersonal_despedida` y envía a la cola de revisión profesional.
- **Fallo que detectan:** Se evita lanzar un proceso de emergencia automática para una combinación de variables que el marco científico no clasifica como plan de riesgo inminente confirmado.
- **Fundamento:** Alinear la gravedad del escalado a la evidencia disponible en los textos del paciente y las instrucciones dictadas por el consenso (SAFE-T, NICE NG225).

## F. Validación pendiente
- **Validación:** Confirmación con los profesionales clínicos sobre si el downgrade a Nivel 3 mantiene la seguridad del paciente mientras previene fatiga de alertas N4 y daños por intervenciones innecesarias.
- **Criterio de avance:** Auditoría de casos N3 tras un periodo de 30 días para evaluar la idoneidad clínica de la alerta para decisiones en situaciones de la vida real.