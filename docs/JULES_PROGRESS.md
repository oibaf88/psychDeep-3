# Jules progress

## Target
A web-based platform for longitudinal mental health monitoring that combines patient-authorized conversation data (check-ins, diary, chat), a deterministic clinical risk engine, and a conversational LLM orchestrator (Agent 1) to support self-regulation and professional review without autonomously prescribing or diagnosing.

## Specification coverage
- **Consentimiento y control (E1):** PARTIAL
- **Check-in y diario (E2):** DONE
- **Perfil y baseline (E3):** DONE
- **Timeline (E4):** DONE
- **Motor temporal (E5):** DONE
- **Explicaciones (E6):** DONE
- **Plan preventivo (E7):** DONE
- **Seguridad (E8):** DONE
- **RAG de contenidos (E9):** NOT STARTED
- **Panel profesional (E10):** PARTIAL
- **Evaluación (E11):** PARTIAL
- **Operaciones (E12):** PARTIAL

## Current technical debt
- Need to expand frontend component testing. (Fixed `errorDetail` missing tests in `api.test.ts`)
- Significant number of `datetime.utcnow()` instances across backend causing Python 3.12 deprecation warnings; requires a comprehensive refactor.

## Recently completed
- **Clinical Safety:** Evaluated the risk engine rules to ensure deterministic rules governing emergencies (`N4`) strictly follow safety guidelines (never triggered from indirect combinations), and authored the scientific and clinical evaluation report (`docs/revisión_clínica.md`) as requested.
- **Backend refactor:** Migrated backend Pydantic models from `class Config:` to `model_config = ConfigDict(from_attributes=True)` as per Pydantic v2 standards.
- **Clinical Safety:** Removed obsolete `N4_convergencia_critica_extrema` references from the therapist manual and frontend component (`ClinicalTraceability.tsx`), completing the alignment of statistical convergence handling with N3 professional review requirements.
- **Clinical Safety:** Actualizada la terminología de las alertas Nivel 4 en toda la aplicación de "Emergencia" a "Revisión clínica urgente" para cumplir con las directrices de seguridad clínica de que las señales de IA determinan prioridades de revisión, no diagnósticos de emergencia automatizados.
- **Clinical Safety:** Convergencia interpersonal recategorizada de N4 a N3 (`N3_convergencia_interpersonal_despedida`) y eliminada entrada obsoleta de N4 en panel clínico, siguiendo CLINICAL_RISK_BASIS.md y lineamientos de NICE NG225.
- **Clinical Safety:** Fixed the statistical convergence rule (`N3_convergencia_critica_extrema`) in the clinical risk engine (`backend/app/services/risk_engine.py`) to properly trigger a Level 3 review when severe structural deterioration is combined with rumination *or* sleep worsening, adhering to clinical safety guidelines.
- **Performance:** Fixed N+1 query issue in the professional patient listing endpoint (`backend/app/routers/professional.py`) by utilizing batched DB queries for assessments, alerts and checkins.
- **A11y Review:** Added accessibility enhancements (ARIA roles, live regions, labels) to both Patient and Professional Dashboards.
- Implemented frontend manual chunk splitting in `vite.config.ts` to solve large Vite bundle sizes (>500kB) and improve application initial load times.
- Created this documentation (`docs/JULES_PROGRESS.md`) to adhere to the spec requirements.
- Fixed an absolute path bug in `backend/tests/test_llm_endpoint.py` so tests can be run regardless of the directory they're executed from.
- Refactored `aggregate_daily_statistics` function in `backend/app/services/daily_statistics.py` by extracting logic into smaller helpers for improved readability and maintainability.
- **Testing:** Expanded frontend component testing by adding test suites for the ConsentsPage and SharingPage components.

## Recommended next work
1. **Implement RAG de Contenidos (Epic E9)**: Build the versioned, curated content library mechanism for the conversational assistant.
2. **Complete Professional Panel (Epic E10)**: Finish selective sharing, professional workflows, and robust UI elements for patient-clinician linkages.
3. **Complete Consent Verification**: Ensure granular revocation flows (E1) are fully robust and visible in the UI.
