# Revisión Científica y Clínica de PsychDeep 3

## A. Alcance
- **Función:** Modificaciones recientes en el motor de riesgo (`backend/app/services/risk_engine.py`) relativas a convergencia estadística, así como la configuración y despliegue del modelo (`backend/app/config.py`).
- **Versión/diff:** Versión actual del repositorio (Septiembre 2026), enfocada en los cambios que recategorizan convergencias y eliminan terminología de emergencia automática para riesgos estadísticos.
- **Población/Contexto:** Pacientes utilizando PsychDeep 3 en un entorno ambulatorio.
- **Material Inspeccionado:** `backend/app/services/risk_engine.py`, `backend/app/content/safety_resources.py`, `docs/CLINICAL_RISK_BASIS.md`, `docs/Especificaciones psychDeep 3.pdf` y la configuración de modelos en backend y frontend.

## B. Conclusión
Las modificaciones recientes logran una alineación adecuada con las directrices de seguridad clínica. La degradación de `N4_convergencia_critica_extrema` a nivel N3 es un paso crítico para evitar diagnósticos automáticos y falsas alarmas, dejando las decisiones de emergencia en manos de declaraciones explícitas o profesionales humanos. Asimismo, el cambio del uso de `structural_score < 0.20` a `adverse_composite_z > 2.4` refina la detección de inestabilidad estructural basándose en desviaciones significativas antes que en la similitud cruda. En cuanto a modelos de lenguaje, el uso exclusivo de modelos válidos asegura compatibilidad y prevención de fallos de enrutamiento, manteniendo el motor clínico independiente.

## C. Evidencia
- **Fuentes:**
  1. `docs/CLINICAL_RISK_BASIS.md`: Regla de seguridad del producto #4 establece claramente: "Los cambios estadísticos, incluso concurrentes con rumiación/sueño, alcanzan revisión profesional N3; no se interpreta esa suma como emergencia suicida N4".
  2. Guía NICE NG225 (Sección 1.6): Desaconseja utilizar escalas de estratificación global para predecir el suicidio, avalando la decisión de no disparar el Nivel 4 únicamente mediante un compuesto estadístico (`adverse_composite_z`).
  3. Especificaciones del producto: Se prohíbe el comportamiento de "chatbot-clínico" que improvise el tratamiento; por ello, la separación entre IA y reglas deterministas es esencial.

## D. Hallazgos
- **Identificador:** CLINICAL_REVIEW_N3_CONVERGENCE
- **Ubicación:** `backend/app/services/risk_engine.py`, `backend/app/content/safety_resources.py`
- **Observación Reproducible:** La convergencia extrema utiliza ahora `adverse_composite_z > 2.4` en lugar de `structural_score < 0.20`. Las alertas de Nivel 4 en la interfaz y recursos de seguridad ya no se etiquetan genéricamente como "Emergencia", sino que aclaran que el modelo no llama autónomamente a urgencias y que los niveles determinan prioridad de "Revisión clínica urgente" humana.
- **Mecanismo/Impacto:** Se minimiza el riesgo de sobrediagnóstico por parte de un sistema que carece de criterio clínico humano, previniendo intervenciones invasivas inapropiadas o alarmas innecesarias para los terapeutas.
- **Certeza:** Alta (en cumplimiento con protocolos clínicos estandarizados).
- **Prioridad:** Crítico.
- **Propuesta:** Mantener las modificaciones actuales y asegurar que no haya regresiones hacia categorizaciones de IA que presuman emergencia sin declaración expresa del usuario.

## E. Casos de aceptación
- **Entrada/contexto sintético:** Paciente con un empeoramiento súbito en autoinformes, reflejado en un `adverse_composite_z` de 2.6 y rumiación alta (>0.85).
- **Comportamiento Esperado:** El sistema clasifica la evaluación en Nivel 3 (Prioridad de revisión profesional) bajo la regla `N3_convergencia_critica_extrema`, sin disparar un protocolo N4 ni mensajes de emergencia en el flujo de usuario.
- **Fallo que detectan:** Un modelo que asuma una "emergencia suicida inminente" sólo por una acumulación de signos indirectos de inestabilidad, evitando un falso positivo que pudiera comprometer la confianza del usuario y sobrecargar al clínico.
- **Fundamento:** Evitar que un algoritmo determinista sin contexto clínico decida acciones críticas a partir de inferencias y métricas longitudinales no validadas paramétricamente en tiempo real.

## F. Validación pendiente
- **Validación:** Se requiere evaluación prospectiva de sensibilidad y especificidad tras un despliegue controlado (Piloto), revisando si el umbral de `adverse_composite_z > 2.4` captura efectivamente a los pacientes que los clínicos consideran en riesgo de desestabilización aguda (N3) en comparación con el umbral anterior.
- **Criterio de avance:** Completar la revisión sistemática de falsos positivos en el umbral z y calibrar si el valor 2.4 es demasiado sensible o específico para la población clínica objetivo antes de extenderlo a la base de usuarios global.
