# psychDeep-vOG — investigación de modelos predictivos y arquitectura objetivo
**Estado:** propuesta de investigación e ingeniería; no valida ni activa ningún predictor clínico.  
**Fecha de corte:** 16 de octubre de 2026.  
**Restricción absoluta:** preservar tablas, IDs, timestamps, consentimientos, historial, auditoría y recogida del piloto de \`psychdeep_v12\`. Sin cambios productivos en esta PR.

## 1. Decisión ejecutiva

El producto necesita tres capacidades separadas:

1. **Predicción longitudinal de deterioro ambulatorio** mediante modelos temporales de deep learning sobre eventos clínicos estructurados/semi-estructurados.
2. **Predicción de desviaciones conductuales/digitales** mediante modelos longitudinales personalizados, con datos activos (EMA, diario y check-ins) en primera instancia y sensores pasivos solo como una opción futura, voluntaria y jurídicamente revisada.
3. **Coordinación de cuidados y capacidad profesional** que convierta señales validadas en trabajo priorizado, transparente y supervisado por personas, sin automatizar decisiones coercitivas o clínicas irreversibles.

La memoria longitudinal existente es un contexto/representación versionada y trazable, no un predictor de recaída. Los LLM de síntesis no se reutilizarán como clasificadores de riesgo. El motor determinista de seguridad seguirá independiente.

No seleccionar un “mejor modelo” solo a partir del AUROC informado en publicaciones. La elección depende de etiquetas disponibles, número de eventos positivos, frecuencia temporal, calidad del registro, modalidad presente y posible desplazamiento entre población publicada y el piloto.

## 2. Evidencia revisada y límites de transferencia

### 2.1 EHR secuencial: BEHRT / Hi-BEHRT

- **BEHRT**, Scientific Reports 2020: preentrenado/evaluado en casi 1,6 millones de personas para predecir diagnósticos futuros; comunica una mejora del 8–13,2% en average precision frente a modelos deep-EHR anteriores en sus tareas. Integra múltiples códigos clínicos y fechas/edad. Fuente: https://www.nature.com/articles/s41598-020-62922-y
- **Hi-BEHRT**, IEEE JBHI / artículo disponible en PMC: jerarquía temporal para historiales más largos; superó BEHRT y otros baselines en predicción a cinco años de insuficiencia cardiaca, diabetes, enfermedad renal crónica e ictus. No fue una validación específica de recaída psiquiátrica: https://pmc.ncbi.nlm.nih.gov/articles/PMC7615082/
- **RETAIN**, NeurIPS 2016: atención en dos niveles y lectura inversa del historial que facilita atribuir contribuciones a visitas/códigos; un baseline útil si la explicabilidad es prioritaria, aunque antiguo y no validado para este uso: https://papers.nips.cc/paper_files/paper/2016/hash/231141b34c82aa95e48810a9d1b33a79-Paper.pdf
- La evaluación de BEHRT en UK Biobank publicada en 2026 reporta rendimiento sensible al tamaño del modelo, vocabulario clínico y división de datos; es evidencia contra asumir que el mismo modelo/vocabulario gana en cada contexto: https://pubmed.ncbi.nlm.nih.gov/41743675/
- Un estudio de predicción de ingreso involuntario con EHR psiquiátrico danés (Psychological Medicine, 2024) demuestra que sí existen trabajos directamente psiquiátricos que combinan predictores rutinarios y texto; requiere una lectura metodológica completa y evaluación de adecuación al piloto antes de adoptar sus features o su target: https://pubmed.ncbi.nlm.nih.gov/39552381/

**Conclusión:** estudiar BEHRT/Hi-BEHRT como referencias de arquitectura/preentrenamiento, no copiarlas a ciegas. Un piloto pequeño no puede entrenar razonablemente un Transformer clínico desde cero. Primero medir eventos/etiquetas; luego comparar transferencia congelada/ajuste fino solo si vocabulario, licencias, idioma, tamaño y representatividad son adecuados.

### 2.2 Digital phenotyping / EMA / NLP

- Revisión sistemática 2024 de fenotipado digital en depresión: resultados generalmente moderados; ausencia de validación externa y datos faltantes son barreras recurrentes: https://www.sciencedirect.com/science/article/pii/S0149763424000095
- Estudio de bipolaridad con Fitbit durante nueve meses en 54 adultos, evaluaciones quincenales y validación de prueba: ROC-AUC 0,860 para sintomatología depresiva y 0,852 para (hipo)manía con BiMM forest; es detección de síntomas por ventanas y un conjunto pequeño, no una garantía de predecir crisis del piloto: https://pubmed.ncbi.nlm.nih.gov/39397313/
- Estudio de señales tempranas de recaída bipolar publicado en 2025: algunas medidas de actividad y sueño predijeron semanas preepisodio, pero los mejores predictores no superaron los umbrales predefinidos de utilidad clínica: https://pubmed.ncbi.nlm.nih.gov/40738339/
- Revisión sistemática de fenotipado pasivo publicada en 2026 comunicó AUC 0,70–0,88 en estudios incluidos, pero también riesgo de sesgo alto y validación externa limitada; los valores probablemente sobreestiman el rendimiento real: https://doi.org/10.1186/s12888-026-08157-z
- Estudio BiAffect de metadatos de tecleo en bipolaridad (2018) ofrece evidencia de factibilidad, no una autorización general para vigilancia del teclado: https://pubmed.ncbi.nlm.nih.gov/30030209/

**Conclusión:** empezar por EMA/check-ins/diario que ya se recogen o puedan añadirse de forma explícita. Priorizar desviaciones respecto a la línea base de la propia persona y permitir que “no hay datos suficientes” sea una salida. No inferir por defecto geolocalización, contactos, teclado, uso de apps ni latencia de mensajes. La actividad nocturna, el uso de primera persona o el absolutismo lingüístico son hipótesis de features, no hechos clínicos ni marcadores específicos.

### 2.3 Guía metodológica obligatoria

El diseño y reporte del predictor seguirá TRIPOD+AI (BMJ 2024), con evaluación de riesgo de sesgo mediante PROBAST/PROBAST+AI cuando corresponda: https://www.bmj.com/content/385/bmj-2023-078378

## 3. Modelo candidato A — deterioro ambulatorio

### 3.1 Target antes que arquitectura

Antes de entrenar, panel clínico debe definir outcome observable, momento cero, ventana, horizonte y etiquetas disponibles. Targets candidatos, en orden de factibilidad para un piloto:

- **A1. Cambio clínico validado** a partir de escalas estructuradas y repetidas (si el piloto las recoge).
- **A2. Episodio de descompensación adjudicado por clínico**, con fecha y definición explícitas, si la calidad de anotación lo permite.
- **A3. Utilización urgente/hospitalización** como outcome de servicio, dejando claro que es proxy y depende del acceso/estilo de registro.
- **A4. Cambios clínicos compuestos** solamente si cada componente, horizonte y adjudicación se preespecifican.

No usar un cambio de medicación aislado como label automático de recaída: puede reflejar eficacia, efecto adverso, preferencia, disponibilidad o una decisión preventiva. La prescripción/dispensación tampoco demuestra adherencia real.

Los horizontes 14–28 días son **hipótesis a estudiar**, no una promesa de anticipación útil. Evaluar 7/14/28 días únicamente si los datos y el número de eventos permiten comparaciones preespecificadas.

### 3.2 Fuentes y features que sí pueden estudiarse

Mapear contra las tablas y campos reales antes de codificar:

- eventos temporales de observación, check-in y EMA: estado de ánimo, sueño autoinformado, craving, autoeficacia y escalas existentes;
- diagnósticos y eventos clínicos explícitos y codificados, únicamente si están almacenados y son suficientemente normalizables;
- inicio, cambio o suspensión de medicación si hay una fuente fiable con fechas, no inferir la exposición desde conversación;
- utilización de servicios, citas canceladas o urgencias solo si el sistema dispone legalmente de esa información estructurada;
- patrones de ausencia y frecuencia de medida como metafeatures de **calidad/observación**, nunca como equivalentes a salud estable/deteriorada;
- historia temporal de desviaciones personales, tendencias, variabilidad, cambios abruptos y tiempo transcurrido desde cada evento.

MPR/PDC se implementan solo si existen datos válidos de dispensación y denominador de exposición. No inventar cobertura farmacológica a partir de la lista de medicación.

### 3.3 Comparativa experimental escalonada

Siempre comparar con el mismo target, conjunto de pacientes y splits temporales:

1. **Baseline no-DL**: regresión logística/elastic net o modelo de supervivencia simple y regla clínica vigente; incluye calibración y constituye control de complejidad.
2. **Baseline temporal interpretable**: RETAIN o GRU-D / GRU con máscara explícita de missingness y tiempo transcurrido, según densidad de eventos.
3. **Transformer temporal compacto**: eventos como tokens (tipo/código/valor), embedding de tiempo real entre eventos (\`time-delta\`), tiempo absoluto/contexto relevante y máscara de ausencia; causalidad en inferencia (ningún evento posterior a la fecha índice).
4. **Hi-BEHRT o preentrenamiento tipo BEHRT** solo si hay dataset clínico de preentrenamiento utilizable, licencias compatibles y vocabulary mapping defensible. Evitar entrenamiento desde cero con pocos positivos.
5. **Fusión multimodal** cuando se disponga de texto clínico autorizado además de estructurados: encoder para secuencia EHR y encoder textual separados, luego fusión tardía y calibrada. Evitar early fusion irrestricta que haga opaco qué modalidad causó la salida.

### 3.4 Salida del modelo

Un registro por ejecución debe contener: target y definición/versión, horizonte, probabilidad calibrada si puede calibrarse, modelo/versión, timestamp de corte, watermark y fuentes incluidas, cobertura/missingness, intervalos/incertidumbre si aplican, estado de validación, motivos legibles y límites. \`unavailable/insufficient_data\` es preferible a un cero falso.

El término “rolling risk score” solo se habilita si evaluación demuestra estabilidad/calibración en cortes temporales repetidos. No reutilizar \`ChangeSignal\` estructural como riesgo; no sobrescribir \`RiskAssessment.alert_level\` determinista.

## 4. Modelo candidato B — desviación digital/afectiva individual

### 4.1 Primera versión: EMA + diario consentido

- Encoder de texto en español solo sobre diario/check-in compartido voluntariamente para análisis lingüístico, con finalidad separada, consentimiento revocable y límites claros.
- Encoder de señales estructuradas EMA/sueño/actividad auto-reportada.
- Agregador temporal por ventanas irregulares: GRU-D/GRU con delta temporal o pequeño Transformer con codificación explícita de tiempos y máscara de ausencia.
- Representación personalizada contra baseline de esa persona; salida primaria: “desviación respecto al patrón habitual” con dominio, evidencia y nivel de incertidumbre. Una desviación no equivale a diagnóstico ni riesgo.
- Solo si existe un target clínico prospectivo adjudicado se entrena un segundo cabezal de predicción clínica. No optimizar solo para reproducir notas de terapeuta/LLM.
- NLP candidate: encoder tipo RoBERTa en español con licencia revisada; los nombres MentalBERT/PsychBERT no implican validez en español ni en esta población. Comparar TF-IDF + modelo simple / embeddings congelados antes de fine-tuning.

### 4.2 Modalidades pasivas: no para la primera entrega

En fase separada y opcional: sleep/activity de wearable o métricas agregadas de uso del dispositivo, solo tras evaluación de impacto, base legal y consentimiento granular. No recoger GPS, contactos, mensajes de terceros o contenido del teclado por defecto. Latencia de respuesta solo si el canal y el evento son válidos y el paciente lo conoce; puede reflejar disponibilidad, conectividad o preferencia, no psicomotricidad.

### 4.3 Diseño contra sesgos de observación

- Baseline personal versionado; mínimo de cobertura configurado con clínicos y validado.
- Missingness explícita; ninguna imputación silenciosa a “normal”.
- Ablation por modalidad para comprobar valor incremental y detectar modalidad dominante.
- Sensibilidad por grupos demográficos/clínicos que sean lícitamente disponibles y suficientes; nunca inferir atributos sensibles a partir de texto.
- Analizar alert burden y falsas alarmas por paciente/mes, duración de alertas, utilidad percibida y posibilidad de pausar/revocar.

## 5. Evaluación y release gates

### Particiones y leakage
- Split por persona y por tiempo; no dividir ventanas de un mismo paciente entre entrenamiento y test como si fueran sujetos independientes.
- Evaluación temporal rolling-origin. Nunca usar eventos/notes registrados después del momento de predicción.
- Ajustar hiperparámetros y calibración únicamente en los conjuntos designados; bloquear un test temporal final.
- Si existe más de un centro/población, reservar validación externa; con un piloto pequeño, reportar explícitamente que no existe.

### Métricas preespecificadas
- Discriminación: AUPRC (primaria cuando outcome raro), AUROC secundaria.
- Calibración: Brier score, calibration-in-the-large, slope y curvas de calibración.
- Operación: sensibilidad/PPV a umbrales definidos clínicamente, falsas alertas por paciente/mes, anticipación útil y carga de revisión.
- Utilidad clínica: decision-curve/net benefit y evaluación prospectiva de si las acciones recomendadas son oportunas y aceptables.
- Desigualdad: rendimiento y calibración por subgrupos; intervalos de confianza/bootstrapping por paciente.
- Comparación incremental con baseline, no solo número absoluto.
- Test de robustez a datos atrasados, campos ausentes, cambios de práctica, código diagnóstico, proveedor y frecuencia de check-in.

### Umbral para piloto
1. **Retrospectivo silencioso**: no muestra riesgo al equipo/paciente; genera artefactos de evaluación versionados.
2. **Shadow prospective**: ejecuta sin influir en atención; revisa alertas y misses con equipo clínico.
3. **Asistencia visible supervisada** solo con evidencia de utilidad, seguridad, aceptación y evaluación legal/dispositivo.
4. Cualquier auto-retraining/version promotion requiere evaluación, modelo aprobado, rollback y auditoría. Nunca actualizaciones silenciosas.

Los límites mínimos de sensibilidad, PPV, calibración y carga de alertas debe fijarlos el equipo clínico antes del test final, no elegirse retrospectivamente según los resultados.

## 6. Datos y contratos interoperables

No reemplazar las tablas actuales. Añadir una capa de lectura/adaptación versionada sobre fuentes existentes. Los registros derivados propuestos deben preservar:
- UUID estable del paciente bajo control del backend; referencia de fuente/tabla/ID;
- \`event_time\`, \`recorded_at\`, timezone/calidad temporal por separado;
- categoría/código original y código normalizado + versión de terminología, si aplica;
- valor/unidad/escala, procedencia (patient/clinician/system/derived), modalidad y missingness;
- propósito/base de tratamiento, scope/versión de consentimiento al tiempo de procesamiento, retiro y supresiones futuras;
- modelo/versión, versión del feature contract, watermark y digest de entradas;
- status \`research_only | shadow | approved | stale | insufficient_data | failed | consent_blocked\`.

FHIR R4 / perfiles aplicables (Patient, Observation, Condition, MedicationRequest/Statement, Encounter, QuestionnaireResponse, Provenance, Consent, Task) será la interfaz de interoperabilidad si se precisa integrar EHR externos; no hace falta migrar almacenamiento interno para empezar. Mapear códigos locales a terminologías estándar con source raw preservada. HL7/FHIR no resuelve por sí mismo la base jurídica ni la gobernanza.

Los nuevos artefactos deberían ser tablas/contratos **aditivos** solo después de revisar el esquema real, las políticas RLS y las migraciones. Esta PR solo define el contrato; no toca SQL ni la DB.

## 7. Capa operativa de recursos clínicos

La predicción solo genera una señal documentada, no una tarea automática irrevocable. La capa de coordinación requiere:

- cola de revisión con urgencia, vencimiento, evidencia y motivo;
- asignación por ámbito/competencias acreditadas, paciente asignado, continuidad y carga disponible;
- capacidad declarada por profesional, horarios, tiempo estimado por intervención, ausencias y reglas de escalado;
- acciones sugeridas por protocolo: revisar, contactar por canal consentido, ofrecer check-in, preparar sesión, supervisión o derivación;
- aceptación/rechazo, motivo, resolución y feedback del profesional, todo auditado;
- límites de SLA configurables por organización; la ausencia de respuesta no se interpreta como ausencia de riesgo;
- reglas deterministas de seguridad independientes del ranking predictivo;
- el score nunca debe utilizarse para reducir el acceso o penalizar a pacientes que registran pocos datos.

Métricas de impacto: tiempo hasta revisión, carga del equipo, alertas accionables/descartadas, continuidad, carga por profesional, tareas vencidas y experiencia del paciente. La optimización deberá tener restricciones de equidad y asignación humana final.

## 8. Marco UE: gates de producto, no asesoramiento jurídico

- Datos de salud son categoría especial bajo GDPR (art. 9); determinar base del art. 6 y excepción del art. 9, roles responsable/encargado, minimización, finalidad, retención, seguridad, derechos y DPIA según riesgo. El consentimiento para funciones no debe agruparse de forma opaca con tratamiento asistencial.
- La predicción de enfermedad o deterioro para uso individual puede entrar en software producto sanitario por su finalidad prevista. Analizar MDR 2017/745 y Rule 11 con asesoramiento experto y guía vigente **MDCG 2019-11 rev.1 (junio 2025)**: https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=md_mdcg_2019_11_guidance_qualification_classification_software_en.pdf
- Evaluar junto al MDR el AI Act, incluidas obligaciones de alto riesgo cuando se cumplan las condiciones del art. 6 y anexo aplicables; consultar FAQ conjunta MDCG 2025-6: https://health.ec.europa.eu/latest-updates/mdcg-2025-6-faq-interplay-between-medical-devices-regulation-vitro-diagnostic-medical-devices-and-artificial-intelligence-act-2025-06-19_en
- La declaración de una función como “investigación” o “apoyo” no evita automáticamente la regulación: importan la finalidad prevista, funcionalidad, comercialización y uso real.
- Minimizar datos de terceros; no usar los resultados para empleo, seguros o elegibilidad. No decisiones exclusivamente automatizadas de gran efecto; valorar art. 22, intervención humana significativa, explicabilidad y vías de impugnación.
- El EHDS (Reglamento UE 2025/327) tendrá aplicación escalonada; incorporar FHIR y portabilidad ahora, sin tratar el calendario transitorio como una exención para el piloto.
- Legal/DPO/clinical safety officer deben aprobar finalidad prevista, evaluación de impacto, consentimientos, contratos de encargados/subencargados, ubicación, transferencias internacionales y procedimiento de incidentes antes de habilitar predicción para atención real.

## 9. Supabase, Render y Modal

### Recomendación ahora
**Mantener Supabase PostgreSQL como fuente de verdad del piloto y Render para frontend/API**. La base actual está activa, tiene historial real e identificadores y el esquema contiene entidades para trayectoria, consentimiento, asignación, trazabilidad y memoria. Migrar la DB ahora aportaría riesgo sin una necesidad de rendimiento demostrada y amenazaría la continuidad de la recogida. No crear un segundo sistema de registro.

Supabase ofrece PostgreSQL gestionado, RLS, Auth, vectores con pgvector, API, backups y opciones PITR/branches según plan. Los diagnósticos del proyecto encontraron 1 aviso de seguridad por extensión \`vector\` en \`public\` y múltiples índices ausentes para claves foráneas; son hallazgos para revisar con bajo riesgo y pruebas, no prueba de que el proveedor sea inadecuado. No trasladar la extensión ni crear índices en producción dentro de este trabajo.

Render ya aloja los servicios productivos en Frankfurt y puede seguir con FastAPI/frontend. Recomendación de revisar límites del plan, logs de PHI, backups y health checks. El plan actual de servicios API/web es free según el inventario recibido; antes de operar clínicamente hay que verificar backups, recuperación, uptime, retención y soporte. No se ha identificado una instancia de Render Postgres en este workspace.

### Posible segunda fase: Modal para cómputo de ML
Modal tiene precio por segundo para CPU/GPU y selección de región UE en modalidades/planes compatibles. Puede reducir coste de GPUs ociosas para entrenamiento por lotes e inferencia intermitente. No reemplaza automáticamente una base clínica transaccional, Auth/RLS, auditoría ni API principal.

- Fase 1: Render mantiene API/web y worker ligero; Supabase mantiene fuente de verdad; entrenar/evaluar con entorno controlado, datos sintéticos o de-identificados.
- Fase 2: Modal como **servicio de cómputo aislado**, invocado desde worker con payload mínimo seudonimizado, región UE verificada, no almacenar fuente de verdad; versionar artefactos y devolver solo predicción/trazas mínimas.
- Antes de transmitir datos clínicos reales: revisar DPA/subprocesadores, región de ejecución/entrada/logging/volúmenes/snapshots, clave de cifrado, retención y borrado, acceso y contrato, transferencias, DPIA y condiciones Enterprise aplicables. No confiar solo en escoger \`eu\` o tener documentación de seguridad.
- Comparar coste total: minutos CPU/GPU, carga de modelo, cold starts, egress, almacenamiento de checkpoints, telemetría, tiempo de ingeniería y modalidad de contratación. Coste de GPU aislado no es coste total.
- No migrar la DB clínica a Modal. La ubicación de cómputo se puede cambiar sin cambiar los contratos de datos ni romper el seguimiento.

Fuentes de infraestructura:
- Supabase features/backups: https://supabase.com/docs/guides/getting-started/features y https://supabase.com/features/database-backups
- Pricing Supabase (consultado 16-10-2026): https://supabase.com/pricing
- Render Postgres/backups: https://render.com/docs/postgresql y https://render.com/docs/postgresql-backups
- Precios Modal: https://modal.com/pricing
- Regiones Modal: https://modal.com/blog/region-selection-launch
- Seguridad y DPA Modal: https://modal.com/docs/guide/security y https://modal.com/legal/dpa

## 10. Roadmap con gates y aceptación

### R0 — Auditoría de datos (antes de arquitectura final)
- Inventario de campos/entidades realmente usados; disponibilidad y periodicidad de los eventos por paciente y en conjunto.
- Counts agregados de pacientes, eventos, escalas/outcomes, ventanas de seguimiento y eventos positivos. Nunca en tickets públicos ni con filas/PII.
- Definir target y fecha índice con clínicos; comprobar eventos suficientes y sesgos por seguimiento/ausencia.
- Resultado: diccionario de features + etiqueta de target y decision log.

### R1 — Dataset reproducible
- Export/feature builder read-only, versionado y con snapshot watermark, sin escribir o cambiar registros fuente.
- Splits por paciente y tiempo, prevención de leakage, fixture sintética.
- Tests de límites temporales, zona horaria, eventos duplicados, consentimientos y revocación.
- Aceptación: misma versión de código y snapshot produce la misma matriz/manifest; no hay fuente post-index en features.

### R2 — Benchmarking
- Logística/survival baseline, RETAIN/GRU-D o GRU temporal y Transformer compacto con deltas de tiempo.
- Modelo EHR tipo BEHRT/Hi-BEHRT solo si datos/terminología/licencia/escala lo permiten. Modelo digital EMA+texto comparado con EMA estructurada sola.
- AUPRC, AUROC, calibración, intervalos por paciente, carga de falsas alertas y resultados por grupos relevantes.
- Aceptación: tabla comparativa preespecificada en conjunto de test bloqueado, sin claims clínicos si no hay utilidad/calibración.

### R3 — Shadow mode prospectivo
- Predicciones invisibles a usuarios; revisión clínica de verdaderos/falsos positivos y misses.
- Monitoreo de drift, cobertura, calibration decay, latencia, abstenciones y número de alertas por persona.
- Aceptación: safety board aprueba umbrales y carga; protocolo documentado.

### R4 — Operacionalización supervisada
- UI de tendencias y alertas con fuente, horizonte, incertidumbre, ausencia de datos y opción de contexto/corrección.
- Bandeja de tareas por prioridad/protocolo; capacidad/competencia del profesional; asignación siempre revisable; feedback para evaluación.
- Aceptación: autorización por asignación, auditoría, fallos seguros, pruebas de accesibilidad y simulacro de carga clínica.

### R5 — Regulación y despliegue
- Intended purpose, MDR/AI Act, DPIA, consentimiento por modalidad, revisión de proveedor/cloud y transferencia de datos.
- Aprobación clínica/legal y evaluación formal antes de cambiar de \`research_only\` a visible.
- Entrenamiento, registry, artefactos, rollback, incident response y monitoring.
- Aceptación: no se activa automáticamente por merge ni se retraina sin revisión.

## 11. Estado conocido y cuestiones abiertas

Con base en README y esquema observado:
- Existe el sistema Supabase \`psychdeep_v12\` con tablas de observación/features/baseline/change signals/model runs/consentimiento y de memoria.
- Existen check-ins/EMA-like inputs, diario y chat, pero no se ha demostrado que exista EHR enlazado/ICD-10, recetas dispensadas, actividad de citas o sensor pasivo con suficiente calidad para un Transformer clínico.
- El análisis longitudinal de memoria es un flujo LLM separado; la métrica canónica actual compara observaciones recientes con baseline personal y **no equivale** a probabilidad de recaída.
- La generación de modelos de memoria tenía fallos observados y cero versiones activas en la comprobación anterior; resolverlo es necesario para memoria, pero no sustituye investigación/entrenamiento del predictor.
- Proyecto Supabase activo en \`eu-north-1\`, PostgreSQL 17; servicios Render API y frontend en Frankfurt, con servicio en free según lectura del panel. La configuración contractual de retención/logs y aptitud regulatoria de los proveedores exige revisión.
- La PR no cambia producción, schema, consentimientos, configuración Render ni datos clínicos.

Preguntas que requieren datos/decisión clínica:
1. Outcome primario viable con fecha: episodio, escala, urgencias, ingreso u otro.
2. Número de pacientes y eventos positivos en el piloto, años de observación y calidad temporal.
3. Si hay fuente legítima de medicación dispensada/cambios de tratamiento/citas o solo información auto-reportada.
4. Objetivos clínicos de sensibilidad, PPV, falsas alertas/mes y antelación mínima útil.
5. Finalidad prevista y clasificación MDR/AI Act, responsable del tratamiento, DPO/ética y protocolo de investigación.
