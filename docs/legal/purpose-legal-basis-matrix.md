# Matriz finalidad → art. 6 + art. 9 → retención → encargado

**Estado:** instrumento de trabajo interno. **No** es una EIPD cerrada, **no** es un registro de actividades (art. 30 RGPD) completo y **no** afirma conformidad, marcado CE ni autorización AEMPS.

**Fuentes vinculantes:** Reglamento (UE) 2016/679 (RGPD); Ley Orgánica 3/2018 (LOPDGDD); Ley 41/2002; Ley 14/2007; Reglamento (UE) 2017/745 (MDR).  
**Guía (no vinculante):** AEPD, guía sector sanitario y FAQs de datos de salud; MDCG 2019-11.  
**Hecho de producto (Asis, 2026-10-18):** PsychDeep es autorregulación longitudinal, no investigación y no chatbot clínico. La seguridad determinista es independiente del LLM.

**Incertidumbre abierta:** identidad jurídica del responsable; DPD; contratos de encargado (Supabase, Render, Anthropic u otros LLM); si el tratamiento es «asistencia sanitaria» art. 9.2.h (profesional con secreto) o producto digital con 9.2.a; si el diario constituye historia clínica Ley 41/2002 art. 17.

Inventario de esquema el 2026-11-02, proyecto Supabase `psychdeep`: `memory_event_ledger`, `memory_jobs`, `memory_embeddings`, `change_signal_embeddings`, el modelo de paciente y `patient_clinical_documents` **existen**. El worker `psychdeep-memory-worker` está en `render.yaml` y **no** está entre los servicios Render en marcha, así que un job encolado no tiene consumidor desplegado. No reintentar jobs en masa. Esto no afirma base jurídica ni conformidad.

## Cómo leer la tabla

- Toda fila de salud / texto clínico / riesgo / perfilado necesita **art. 6 y art. 9.2**.
- Un toggle en UI no es base jurídica. Un `Consent` escrito por el servidor en el alta **no** es consentimiento explícito (arts. 4.11 y 7 RGPD).
- RLS `backend_full_access … using (true)` no aísla filas de paciente; el aislamiento es FastAPI.

| Finalidad (código) | Datos | Art. 6 (hipótesis) | Art. 9.2 (hipótesis) | Gate en código (hoy) | Retención (propuesta, no fijada) | Encargados (a verificar) | Decisión |
|---|---|---|---|---|---|---|---|
| Cuenta / autenticación | email, password hash, nombre | 6.1.b contrato de cuenta | no es salud por sí | alta | vida de la cuenta | hosting auth/DB | Permitido. Informar art. 13 en el registro. |
| `data_processing` — núcleo (check-in, diario, trayectoria, baseline, riesgo **determinista**, plan de seguridad) | salud, a menudo chemsex/LGBTQ+/trauma | 6.1.a **o** 6.1.b si hay contrato de servicio de autorregulación (elegir y documentar; no ambos como si fueran lo mismo) | **9.2.a** explícito mientras no haya asistencia con secreto (9.2.h). 9.2.c solo crisis vital puntual, no el núcleo. | `require_granted` / `is_granted` en chat, diario, check-in, vNext observations. **Alta auto-grantía el 9.2.a → corregido: flag explícito.** | Mientras la cuenta esté activa y el grant vigente. Si un día es historia clínica: Ley 41/2002 art. 17 (mín. 5 años desde última atención) **solo si** el responsable es prestador sanitario — no está acreditado. Art. 17.3.b RGPD puede oponerse al olvido. | Supabase (BD), Render (API/front). LLM **no** es necesario para esta fila. | **Ofrecida.** Revocar bloquea **nuevas** escrituras clínicas. `POST /api/v1/me/erasure-request` cierra la cuenta y revoca grants; no borra el histórico. |
| `linguistic_analysis` — análisis de texto (agentes 1/2/4, analyzer_merged, psicosocial) | texto de chat/diario = categoría especial | 6.1.a | 9.2.a (opt-in **aparte** del núcleo) | `agent2_trace.start` fail-closed para `analyzer_merged`, `agent2_linguistic` y `agent4_psychosocial`. | Trazas sin duplicar el texto; se conservan por auditoría/seguridad. Revocar **para** nuevos envíos a modelo. | Proveedor LLM (Anthropic u endpoint aprobado), backend | **Ofrecida**, opt-in. Fail-closed. |
| `professional_sharing` | acceso del profesional al seguimiento | 6.1.a y/o 6.1.b según modelo de vinculación | 9.2.a y, si hay acto sanitario, 9.2.h **además** del secreto | Se escribe al aceptar la assignment. Las lecturas clínicas del terapeuta pasan por `sharing_allowed`: assignment vigente y grant global `professional_sharing`. El grant no va por `scope.professional_id`. | Duración de la assignment `active` (algunas lecturas admiten también `paused`) | mismos + cuenta profesional | **Ofrecida en UI.** Revocar el grant corta esas lecturas de terapeuta. No afirmar por ello que el art. 7.3 queda cerrado: el consentimiento sigue sin ser por profesional. |
| `crisis_sms` | teléfono + salud + contexto de crisis | 6.1.a o 6.1.d (vital, excepcional) | 9.2.a u 9.2.c | **Ningún** sender en código | n/a | n/a | **No ofrecer.** No recabar. La ayuda de crisis del producto debe existir **sin** SMS. |
| `research` / I+D / fine-tune / embeddings de memoria | reutilización secundaria | 6.1.a o 6.1.e/c con norma | **9.2.j** + Ley 14/2007 + garantías LOPDGDD; CEI si aplica | Solo tests. `fine_tune_runs` en esquema **sin** processor | n/a hasta protocolo | n/a | **No ofrecer.** Cero diario/chat/jobs/embeddings hacia I+D. |
| Memoria longitudinal y documentos clínicos | perfilado sobre categoría especial, más texto de informe | 6.1.a donde hay grant (`linguistic_analysis`, `clinical_document_analysis`) | 9.2.a en esos grants. No afirmar otra base. | Tablas presentes en producción. Subida de PDF/DOCX/TXT con los dos grants. Worker de memoria no desplegado. | no fijada | Supabase, Render | **No afirmar conformidad.** No reintentar jobs. Posible empuje MDR art. 2.1 — no afirmar clase ni autorización. |
| vNext `observations` → features → baselines → ChangeSignal | derivados de autoinforme | misma que `data_processing` | 9.2.a (o 9.2.h si se acredita) | grant núcleo. `consent_id` de la observación sigue sin rellenarse en el cálculo canónico. Tras el cálculo, `embed_change_signals` escribe una huella en `change_signal_embeddings` solo con cuenta activa y `linguistic_analysis`; no lee ni escribe `alert_level`. | alineada al núcleo | Supabase | Permitido como expand-only. La huella no es I+D ni art. 9.2.j. Rellenar `consent_id` en la observación sigue pendiente. |
| Telemetría `biometric_data` / `app_usage_data` | si quedaron filas | 6.1.a | biométricos: 9.2.a estricto | drop condicional en migraciones | borrar si existen | ? | Anni: confirmar vacío. No reactivar. |

## Destinatarios (art. 13.1.e) — lista de trabajo

| Actor | Papel | Transferencia (cap. V) | Nota |
|---|---|---|---|
| Rol `psychdeep_backend` | acceso BFF a **todas** las filas (RLS using true) | EEE si el proyecto Supabase está en UE — **verificar región** | No es aislamiento paciente-paciente |
| Terapeuta con assignment `active` | destinatario interno | no | Debe cortarse al pausar/terminar **y** al revocar sharing |
| supervisor / admin_clinical | destinatario interno amplio | no | Minimización: no leer por rol solo (checklist §6) |
| Proveedor LLM | encargado (si hay DPA) o tercero | según DPA/SCC; región | Solo con `linguistic_analysis`. Sin fallback silencioso. |
| Data API / `anon` / `authenticated` / `service_role` | **no** deben tener SELECT | — | `verify.sql` check 7 + check de relaciones extra (Anni) |

## Derechos (arts. 15–21) — estado

| Derecho | Estado en producto | Nota |
|---|---|---|
| 15 acceso | `GET /api/v1/me/data-export` + la app | Paquete JSON. No es un certificado de integridad forense. |
| 16 rectificación | parcial (hechos, perfil de cuenta) | |
| 17 supresión | `POST /api/v1/me/erasure-request` **sin** hard-delete | Cierra cuenta, revoca grants, termina vinculaciones. Conserva diario/check-in/hechos/riesgo (Ley 41/2002 art. 17 *si* hay historia clínica; si no, 17.3.c/e y auditoría). No capar ML: el cese es del tratamiento futuro, no de la evidencia. |
| 18 limitación | ausente | |
| 20 portabilidad | mismo JSON: cuenta, consents, check-ins, diario, hechos, plan | Risk/assignments van como art. 15, no como 20. |
| 21 oposición | revocación de grants + erasure | `sharing_allowed` y `require_granted` cortan lecturas/escrituras. |
| 22 decisiones automatizadas | riesgo determinista + LLM | Informar lógica; el LLM **no** fija `alert_level` (contrato clínico) |

## Capa de secuencia / memoria canónica (profiling, no investigación)

**Finalidad clínica (Asis):** ambulatorio remoto, autorregulación longitudinal. **No** planta de agudos, no EHR de recetas, no fMRI, no redes sociales, no “crisis sistémica a 28 días”, no restricción física.

La capa time-aware (FeatureValue + BaselineVersion + Δt → **ChangeSignal**) es **elaboración de perfiles** (art. 4.4 RGPD) sobre categoría especial. Bases: **art. 6.1.a + art. 9.2.a** (`data_processing` para series de check-in; `linguistic_analysis` si el input es texto/embeddings). **No** es art. 9.2.j ni Ley 14/2007: no hay I+D, no hay CEI, no hay fine-tune.

**Art. 22:** ChangeSignal **no** puede ser la decisión de alerta. RiskAssessment sigue determinista y humano-en-el-bucle. Un transformer que calcule `alert_level` sería decisión automatizada + empujón MDR art. 2.1 (predicción/pronóstico) **sin** expediente. No hacerlo.

**Gates del siguiente PR (Roberto), vinculantes para no capar sino gobernar:**
1. Solo cuentas `is_active=true` y grants vigentes.
2. Texto/embeddings solo con `linguistic_analysis`. Hecho en `embed_change_signals`.
3. `consent_id` en cada Observation/commit. Sigue sin rellenarse en el cálculo canónico.
4. Crisis/chemsex **fuera** del update de baseline (Asis). Sigue abierto en el ledger de `AGENTS.md`.
5. Explicabilidad: evidencia, missingness, incertidumbre — no SHAP de teatro.
6. Lecturas de `routers/memory.py` con `sharing_allowed` (art. 7.3). Hecho, junto con las lecturas clínicas del terapeuta en `professional.py`.

No hay consumidor Render para `memory_jobs`. No reintentar esos jobs ni publicar un modelo de paciente desde un lote a medias. El camino canónico versionado sigue siendo el hogar de la señal de cambio.

## MDR

Calificación **en juego** si el software se destina a diagnóstico, predicción, pronóstico o tratamiento (MDR art. 2.1; guía MDCG 2019-11). Asis: finalidad = autorregulación + cambio ≠ riesgo, seguridad determinista. **No** hay expediente de conformidad ni autorización AEMPS en el repo. Un worker de memoria clínica **cambiaría** el análisis de finalidad. No asignar clase aquí.

## Acciones por dueño

1. **Legal (este doc):** mantener la matriz; no afirmar bases no elegidas; EIPD abierta en `dpia-art35-open-items.md`.
2. **Ingeniería:** gates listados; no reintentar `memory_jobs` (el worker no está desplegado); `consent_id` en la observación; `valid_until`/`scope` en ORM; alta con flag explícito; no ofrecer research/crisis.
3. **Datos:** `verify.sql` relaciones extra; Data API; owner/FORCE RLS; telemetría residual.
4. **Clínico:** sign-off G3; protocolo crisis sin SMS; no I+D.
5. **Responsable (organización):** identidad, DPD si aplica (art. 37; salud a gran escala), DPAs, región, EIPD firmada.
