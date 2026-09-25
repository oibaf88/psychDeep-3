# Revisión Científica y Clínica de PsychDeep 3

**A. Alcance**
- **Función:** Motor de riesgo clínico (`backend/app/services/risk_engine.py` y `backend/app/services/clinical_view.py`), convergencia estadística (N3) y reglas de emergencia (N4).
- **Versión/diff:** Revisión de las reglas deterministas de seguridad v1.4, específicamente la convergencia de inestabilidad estructural con empeoramiento del sueño o rumiación.
- **Pregunta:** ¿Se garantiza que la inferencia automática basada en rumiación, sueño o similitud descriptiva nunca escale a diagnóstico automatizado de emergencia suicida o médica (N4)?
- **Población/contexto:** Aplicación ambulatoria de monitorización y autocuidado.
- **Material inspeccionado:** `docs/CLINICAL_RISK_BASIS.md`, `backend/app/services/risk_engine.py`, `backend/app/services/clinical_view.py`, y `docs/Especificaciones psychDeep 3.pdf`.

**B. Conclusión**
El sistema actual (v1.4) cumple con el requisito de que **ninguna desviación estadística o inferencia indirecta se interprete automáticamente como una emergencia médica confirmada (N4)**. La convergencia estadística (deterioro estructural adverso > 2.4 combinado con rumiación > 0.85 o empeoramiento del sueño) está correctamente configurada como un Nivel 3 (`N3_convergencia_critica_extrema`), que se define como una alerta prioritaria para revisión profesional, no como una predicción de riesgo suicida o recaída. Las descripciones y explicaciones en `clinical_view.py` son explícitas en rechazar el término "probabilidad".

**C. Evidencia**
- **NICE NG225 (1.6):** Desaconseja usar escalas o estratificaciones globales para predecir suicidio o recaídas. El código se ajusta a esto al evitar referirse a las prioridades como "probabilidades" y al advertir explícitamente en el panel clínico (`clinical_view.py:115`) que "una suma estadística no establece por sí misma emergencia suicida ni probabilidad de recaída".
- **Especificaciones psychDeep 3.pdf:** La sección de Motor de riesgo y seguridad diferencia la revisión profesional pendiente de una crisis médica automática.
- **TRIPOD-LLM:** La transparencia en los componentes se garantiza mediante la separación del cálculo determinista y la inferencia lingüística, y la trazabilidad de los valores de entrada. El LLM no puede modificar el cálculo N4.

**D. Hallazgos**
- **D.1 Separación de Nivel 4 y Nivel 3:** (Prioridad: Crítica; Certeza: Alta). Se confirmó en el código fuente que los flags lingüísticos indirectos, la desestabilización psicosocial aguda y las convergencias extremas están codificados bajo `triggering_rules` de Nivel 3. Nivel 4 (`N4_declaracion_ideacion_o_plan` y `N4_senal_linguistica_ideacion_directa`) está estrictamente reservado para hechos confirmados de ideación directa y explícita.
- **D.2 Ausencia de jerga predictiva (probabilidad):** (Prioridad: Mayor; Certeza: Alta). Los mensajes mostrados al terapeuta evitan deliberadamente usar términos como "probabilidad" en relación al algoritmo.

**E. Casos de aceptación**
- **Caso Sintético 1 (Empeoramiento concurrente severo):**
  - **Entrada:** `adverse_composite_z = 2.5`, `rumination_score = 0.9`. No hay declaración explícita de suicidio.
  - **Comportamiento esperado:** Se genera una alerta de Nivel 3 (`N3_convergencia_critica_extrema`). Se requiere intervención profesional.
  - **Fallo que detecta:** Escalamiento automático de N3 a N4 basado únicamente en estadística.
  - **Fundamento:** NICE NG225; los constructos globales no predicen riesgo suicida de forma aislada.

- **Caso Sintético 2 (Declaración de crisis explícita):**
  - **Entrada:** Hecho confirmado `N4_FACT_CATEGORIES` o ideación detectada directamente (`ideation_direct = True`).
  - **Comportamiento esperado:** Alerta de Nivel 4 (`N4_senal_linguistica_ideacion_directa`).
  - **Fallo que detecta:** Falsa tranquilidad o invisibilización de un riesgo médico explícito.
  - **Fundamento:** SAFE-T (indagación directa) y C-SSRS.

**F. Validación pendiente**
- **Estudio prospectivo necesario:** Validación de la sensibilidad y especificidad de las alertas N3 vs N4 en un entorno clínico piloto real, evaluando la carga de falsas alarmas que recibe el profesional de salud.
- **Criterio de avance:** Adjudicación humana concurrente (un terapeuta real valida las alertas y corrobora si el N3 estadístico fue útil y no introdujo sesgo, documentando la concordancia).
