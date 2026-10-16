# Human care coordination and capacity management

## Objective
Use limited therapist and clinical-team time more effectively while preserving continuity, clinical judgement, patient agency and equitable access. This module is an operational decision-support workflow, not automated allocation of clinical responsibility.

## Core workflow
1. **Signal enters the work queue:** a source-linked observation, patient request, overdue agreed follow-up or validated model output. Unvalidated research scores must not enter the production urgency queue.
2. **Triage separates urgency from workload priority:** existing approved safety pathways determine urgent escalation; operational prioritisation considers due time, clinical relevance, continuity, expected benefit and backlog.
3. **Eligibility filter:** identify professionals permitted to access the case and qualified for the task; respect assignment, scope of practice, language/access needs and local service rules.
4. **Capacity match:** consider available hours, current caseload, leave, task duration, required response window and continuity. Do not expose unnecessary clinical detail to workforce administrators.
5. **Human assignment:** an authorised coordinator accepts or changes the proposed match. The interface records candidate factors, override and rationale.
6. **Action and feedback:** the responsible professional documents contact, session, attempted contact, referral or other outcome. A missed/declined task remains visible and follows a defined escalation policy.
7. **Review:** monitor overdue tasks, workload balance, response times, continuity, patient outcomes and inequities.

## Minimum entities/fields to map before implementation
- Care task: stable ID, patient reference, source/evidence references, task type, created/due times, urgency class, operational priority, status, estimated duration, required competency, assigned professional, assignment history, outcome, cancellation/defer reason and audit events.
- Professional capacity: professional ID, role/scope, competencies, assignment eligibility, availability windows, workload/capacity units, language/access competencies and service/team.
- Assignment decision: eligible candidate set or reproducible eligibility rules, matching factors, human decision-maker, timestamp, override reason and final assignee.
- Service policy: urgency definitions, response SLAs, coverage windows, escalation rules and approved exceptions.

This is a logical contract, not a claim that all entities currently exist in the database. Inventory the current schema and workflows before implementing or migrating any fields.

## Prioritisation policy
- Clinical urgency is separate from administrative workload.
- Existing deterministic crisis/safety rules always take precedence and do not depend on model-provider availability.
- A predictive score, if later validated, may contribute evidence but cannot be the only factor.
- Consider continuity and patient preference, not only raw availability.
- A case must not be silently deprioritised because the patient has not used the app, does not consent to language analysis, has a disability, lacks a device, or has sparse data.
- Include an abstain/manual-review option when data are insufficient or model uncertainty is high.
- Supervisors can rebalance capacity; clinicians can flag unsafe workload; patients can request human contact through an explicit route.

## Minimum UI
- Team queue with task status, due window, required skill, assigned owner and non-PHI aggregate workload.
- Case-level rationale showing source evidence, uncertainty, missingness and why follow-up is proposed.
- Session preparation view with recent change, baseline comparison, protective factors, open questions and prior actions.
- Assignment controls with eligibility validation, human confirmation, override and audit.
- Workload dashboard with overdue counts, capacity and continuity indicators; role-based aggregate view only.
- Clear “data unavailable / consent required / no validated model” states.

## Evaluation
Measure task completion and timeliness, time to first human response, overdue backlog, continuity, workload distribution, clinician override rates, inappropriate alerts, patient-reported usefulness and adverse events. Evaluate by service, clinician workload band and relevant patient groups where lawful and adequately powered. Do not optimise only for number of alerts handled or time saved.

## Safe rollout
Start with a read-only workflow inventory and synthetic task fixtures. Then prototype queue/assignment on synthetic or staging data. Conduct user testing with clinicians and patient representatives. Shadow the priority policy before operational use. No automatic assignment or production writes until access controls, audit, escalation, workload safeguards and rollback are approved.
