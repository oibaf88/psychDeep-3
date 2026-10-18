# EIPD / DPIA (art. 35 RGPD) — ítems abiertos

**Estado:** lista de trabajo. **No** es una evaluación de impacto terminada ni un dictamen del DPD. No usar como prueba de conformidad.

El art. 35.1 exige EIPD cuando el tratamiento «entrañe un alto riesgo». El 35.3 cita, entre otros, elaboración de perfiles a gran escala y categorías especiales a gran escala. PsychDeep trata **salud** (a menudo chemsex, orientación, trauma), **perfila** trayectoria/riesgo y puede enviar texto a un modelo. La EIPD **encaja**; falta hacerla.

## Criterios (sí/no provisional)

| Criterio WP248/AEPD | ¿Aplica? | Evidencia |
|---|---|---|
| Categorías especiales | sí | diario, chat, riesgo, señales |
| Perfiles / evaluación predictiva | sí, con matices | riesgo determinista; ChangeSignal ≠ RiskAssessment (Asis). Memoria no versionada **aumentaría** el riesgo — congelada |
| Datos de vulnerables | probable | salud mental, sustancias |
| Nuevas tecnologías (LLM) | sí, si hay `linguistic_analysis` | |
| Impide ejercer derechos | riesgo si no hay 15/17/20 | |
| A gran escala | **incierto** | depende de n.º de afectados — no inventar |

## Lo que bloquea cerrar la EIPD

1. Identidad del responsable, DPD (art. 37: tratamiento a gran escala de salud), registro art. 30.
2. Inventario vivo vs `expected_tables` (Anni) y Data API.
3. DPAs y región de Supabase, Render, LLM; subencargados; logs/prompts.
4. Elección documentada 9.2.a vs 9.2.h.
5. Flujo real de sharing (hoy el revoke no corta lecturas).
6. Derechos 17/20 diseñados con clínico (historia vs olvido).
7. Finalidad MDR: si cambia (memoria/predicción), reabrir EIPD **y** cualificación MDSW.
8. Gold clínico G3 (Asis): umbrales, lenguaje ambiguo, GHB/GBL — riesgo de estigmatización es un daño de la EIPD, no solo de validez ML.

## Medidas que ya cuentan (no suficientes solas)

- Consentimiento granular append-only; fail-closed lingüístico.
- FORCE RLS + revoke PostgREST (BFF); aislamiento en API.
- Riesgo determinista independiente del LLM; sin fallback silencioso de proveedor.
- Trazas de análisis sin duplicar el texto.
- Congelación del pipeline de memoria no versionado.

## Siguiente paso

Cuando Anni traiga el inventario SQL y la organización rellene responsable/DPA, redactar la EIPD en plantilla AEPD (descripción, necesidad/proporcionalidad, riesgos, medidas, consulta previa art. 36 si el alto riesgo permanece). Hasta entonces: **no** declarar «EIPD hecha».
