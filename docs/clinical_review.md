# Revisión de ingeniería de seguridad clínica

## Alcance y estado

Esta revisión fija como línea base el commit `72e8372` y describe el comportamiento propuesto para `risk-engine-v1.5`. Es una revisión documental y de ingeniería: **no constituye validación clínica, certificación de dispositivo médico ni aprobación para producción clínica**. La revisión clínica formal de umbrales, mensajes y protocolos sigue pendiente.

A. Alcance:
- Función, afirmación o cambio que se revisa y versión exacta: Análisis de las reglas deterministas de seguridad en el motor de riesgo (v1.5) y el comportamiento de la actualización del perfil (Agente 2) ante estados transitorios. Específicamente, distinción entre Nivel 3 (N3) y Nivel 4 (N4) y el manejo de `adverse_composite_z`.
- Usuario y población previstos: Pacientes en seguimiento clínico por consumo de estimulantes/chemsex en PsychDeep 3.
- Material inspeccionado: `backend/app/services/risk_engine.py`, `backend/app/content/prompts.py`, `docs/CLINICAL_RISK_BASIS.md`.

B. Conclusión:
- Qué se sostiene: El motor separa de forma segura y consistente el riesgo estadístico (N3) de la ideación directa (N4). Una desviación extrema (`adverse_composite_z > 2.4`) combinada con rumiación o problemas de sueño acciona adecuadamente una bandera N3 para revisión clínica prospectiva en lugar de una emergencia clínica N4 falsa. Las instrucciones a la IA (Analizador) impiden formalmente que asiente un estado afectivo temporal como un rasgo patológico permanente en `profile_update`.
- Qué no se sostiene: Las interpretaciones de que convergencias compuestas deben escalar a 112 se rechazan formalmente. No hay validación de que las escalas sumatorias deban usarse para prescribir emergencia.
- Incertidumbre: Requiere el reporte final empírico usando datos no sintéticos.

C. Evidencia:
- **NICE NG225 (Recomendación 1.6):** "no usar escalas/categorías globales para predecir suicidio ni decidir tratamiento o alta tras autolesión". Se acata este principio relegando el malestar convergente estadístico a evaluación N3 en vez de alerta inminente automática (N4).
- **Psicología Clínica (Formulación Contextual):** El marco adoptado instruye no confundir "estado vs. rasgo", preservando la exactitud y validez, evitando sesgos iatrogénicos o juicios patologizantes sobre el usuario que sufre malestar.
- **TRIPOD-LLM:** Se requiere formalmente el seguimiento de la guía TRIPOD-LLM para la documentación de reproducibilidad del LLM al presentar informes empíricos/validaciones futuras, ya consignado en `docs/CLINICAL_RISK_BASIS.md`.

D. Hallazgos:
- H1: Distinción estructural. Ubicación: `backend/app/services/risk_engine.py`. Observación reproducible: `N3_convergencia_critica_extrema` prioriza N3 frente al deterioro concurrente que sobrepase 2.4 desviaciones estándar. Certeza: Alta. Prioridad: Menor (Confirmatorio). Propuesta: Mantener y aprobar.
- H2: Prevención de Estado-Rasgo. Ubicación: `backend/app/content/prompts.py` (líneas de `profile_update`). Observación: "No conviertas un estado temporal en un rasgo permanente". Certeza: Alta. Prioridad: Menor. Propuesta: Mantener y aprobar.
- H3: Referencia TRIPOD-LLM en marco de trabajo. Ubicación: `docs/CLINICAL_RISK_BASIS.md`. Observación: Incorporación exitosa de los protocolos. Certeza: Alta. Prioridad: Menor (Cierre documental).

E. Casos de aceptación:
- **Convergencia sintética (riesgo extremo sin ideación):** Un registro de `adverse_composite_z > 2.5` con malestar al dormir detona una evaluación (Nivel 3), NO un flag N4 de autolesión de emergencia inminente, puesto que la IA no decide un fallo psiquiátrico de urgencia vital basándose en escalas descriptivas.
- **Transitoriedad (estado de afectación situacional):** Expresión de estrés insoportable tras despido no formará en el perfil del analizador un retrato estable de "individuo colapsado de forma crónica". Se evalúa la valencia emocional para ese check-in sin sobreescribir permanentemente su portrait a largo plazo.

F. Validación pendiente:
- Estudio necesario: Seguimiento retrospectivo en datos de usuarios una vez estabilizado sobre tasas de falsos positivos en N3 respecto a derivaciones humanas. Se deberán presentar los resultados empleando las plantillas dictadas por TRIPOD-LLM.
- Estado: Sin objeciones identificadas en este alcance.
