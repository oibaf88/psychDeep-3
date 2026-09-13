# Hallazgo: Convergencia crítica extrema clasificada erróneamente como emergencia automática (N4)

## A. Alcance
- **Función:** Motor de riesgo clínico (`backend/app/services/risk_engine.py`) en su versión legacy (`_calculate_risk_level_legacy`).
- **Versión/diff:** Corrección aplicada en la ruta del motor legacy para igualarlo con la versión trazada (`calculate_risk_level`).
- **Población/Contexto:** Pacientes monitorizados mediante el sistema PsychDeep 3.
- **Material Inspeccionado:** Código del motor de riesgo (`risk_engine.py`), especificaciones de seguridad clínica (`docs/CLINICAL_RISK_BASIS.md`), y tests automatizados (`test_clinical_view.py`).

## B. Conclusión
La regla de convergencia crítica extrema, que detecta un gran deterioro estructural combinado con rumiación alta y empeoramiento del sueño, no debe clasificar automáticamente a un paciente en nivel de emergencia (N4). Un empeoramiento en métricas estadísticas no equivale a una probabilidad predictiva validada de suicidio y, por lo tanto, debe generar una revisión prioritaria por parte del profesional (N3) sin iniciar protocolos de emergencia automática (N4).

## C. Evidencia
- **Fuentes:**
  1. `docs/CLINICAL_RISK_BASIS.md`: Regla de seguridad del producto #4 establece claramente: "Los cambios estadísticos, incluso concurrentes con rumiación/sueño, alcanzan revisión profesional N3; no se interpreta esa suma como emergencia suicida N4".
  2. Guía NICE NG225 (Sección 1.6): Desaconseja utilizar escalas de estratificación global para predecir el suicidio o tomar decisiones automáticas sobre intervenciones mayores, confirmando el principio de que los cálculos estadísticos compuestos (suma de riesgos) requieren revisión clínica humana en lugar de automatización ciega.

## D. Hallazgos
- **Identificador:** RISK_LEGACY_CONVERGENCE_N4
- **Ubicación:** `backend/app/services/risk_engine.py`, método `_calculate_risk_level_legacy`
- **Observación Reproducible:** Si `_convergencia_critica_extrema` devolvía True, el motor pre-trazado devolvía un `RiskDecision` de `level=4` bajo la regla `N4_convergencia_critica_extrema`.
- **Mecanismo/Impacto:** Producir falsas alarmas de nivel 4 basadas puramente en deterioro estadístico, generando fatiga de alertas para el sistema de emergencias y sobreestimando riesgos (falsa clasificación de probabilidad suicida).
- **Certeza:** Alta (violación directa y documentada de `CLINICAL_RISK_BASIS.md`).
- **Prioridad:** Crítico.
- **Propuesta:** Reemplazar `N4_convergencia_critica_extrema` por `N3_convergencia_critica_extrema` en el cálculo legacy, estableciendo `level=3` y alineando el mensaje de razón con su equivalente en la versión por trazabilidad ("Deterioro estadístico con rumiación y sueño empeorando: revisión profesional, no emergencia inferida de una suma").

## E. Casos de aceptación
- **Entrada/contexto sintético:** Paciente que presenta un `structural_score` < 0.20, una `rumination` > 0.85, y un empeoramiento en horas de sueño (`sleep_worsening=True`), sin señales explícitas de ideación suicida directa o indirecta.
- **Comportamiento Esperado:** El sistema debe producir un nivel N3, invocando la regla `N3_convergencia_critica_extrema`, y mostrar esta recomendación en el panel clínico.
- **Fallo que detectan:** Evitan que un usuario con deterioro pero sin un plan suicida confirmado dispare recursos de intervención para casos N4, previniendo así un malgasto de tiempo profesional de urgencias o medidas invasivas no indicadas.
- **Fundamento:** Alinear el impacto práctico de la aplicación con las directrices de NICE NG225 sobre limitación de categorizaciones globales para pronósticos automáticos.

## F. Validación pendiente
- **Validación:** Confirmación con los profesionales clínicos de prueba de que las alertas producidas por convergencia estadística extrema proveen información útil como advertencias de Nivel 3.
- **Criterio de avance:** Adjudicación por profesionales humanos en los paneles de revisión para determinar el valor predictivo real en la clínica tras 30 días de despliegue.
