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
- Need to expand frontend component testing and accessibility attributes (ARIA roles) for professional panels.
- Optimize frontend chunk sizes; current build logs indicate chunks are larger than 500 kB (consider dynamic `import()` for code-splitting).
- Significant number of `datetime.utcnow()` instances across backend causing Python 3.12 deprecation warnings; requires a comprehensive refactor.

## Recently completed
- Created this documentation (`docs/JULES_PROGRESS.md`) to adhere to the spec requirements.
- Fixed an absolute path bug in `backend/tests/test_llm_endpoint.py` so tests can be run regardless of the directory they're executed from.

## Recommended next work
1. **Implement RAG de Contenidos (Epic E9)**: Build the versioned, curated content library mechanism for the conversational assistant.
2. **Complete Professional Panel (Epic E10)**: Finish selective sharing, professional workflows, and robust UI elements for patient-clinician linkages.
3. **Chunk Splitting & Frontend Optimization**: Address Vite build warnings regarding large JavaScript chunks (>500 kB) to improve initial application load times.
4. **Complete Consent Verification**: Ensure granular revocation flows (E1) are fully robust and visible in the UI.
5. **A11y Review**: Inspect and add keyboard navigation and screen-reader accessibility enhancements to both Patient and Professional Dashboards.
