# ADR-0002 — Clinical long-term memory for models

Status: Accepted for the current product scope. This does not mark PsychDeep vNext complete.

## Context

PsychDeep models talk with people in treatment for mental illness. A bounded recent-message window cannot carry how a person speaks, what they repeat, what they avoid, or how that has changed against their own earlier conversations. OpenViking organises agent memory as a per-person directory, with L0/L1/L2 layers, a session commit, an auditable diff and progressive retrieval. Copying that product in as a second store would put clinical text outside Supabase and onto an ephemeral Render disk.

The product owner also set two rules for this memory. The patient cannot delete or edit it, because that record is how the system understands what was said and how it was said. A conversation with the model is a fact of the system. A claim inside that conversation about the world, such as having taken medication, is not.

## Decision

1. Supabase remains the only clinical store. Render keeps the existing API. OpenViking is not deployed.
2. Each committed chat or diary turn may write three layers, all append-only:
   - a discourse fact: the words actually stored, the channel, the time and observed manner;
   - a psychological reading: an uncertain, evidence-linked hypothesis about why the person is speaking this way;
   - a formulation version: L0 (≤256 characters), L1 (≤4000) and L2, superseding the previous version without deleting it.
3. Discourse facts are not `ConfirmedFact` rows. World propositions are not marked as having happened. Readings are inferences. They do not set `alert_level` and they do not create a `ProfessionalAlert`.
4. New readings and formulations require `linguistic_analysis` consent. Revocation stops new reads. Existing rows stay.
5. The patient has no edit or delete path. A request inside the message to forget or erase memory is stored as speech, not executed. A professional may append a note. Nobody deletes the memory.
6. The formulation is not shown in the patient account. Assigned therapists and supervisors read it on the patient chart. `admin_clinical` does not.
7. Deterministic rules over the stored memory may open a `clinical_attention_notices` row and an in-app notification to the assigned professional. That notice is not a risk alert, an email, an SMS or an emergency contact.
8. Retrieval for Agent 1, the analyser and the copilot uses L0/L1 and a clipped L2 excerpt inside the existing context budget. Embeddings are requested only from the already selected OpenAI-compatible deployment. If that deployment has no embeddings endpoint, ranking stays lexical. Text is never sent to a different provider to be embedded.
9. This memory is not training data. Agent-evolution types (`soul`, `identity`, cases, trajectories, experiences) are out of scope.

## Consequences

The models can follow one person across conversations, and a human therapist can see why the system thinks something in the speech matters. A bad day is kept as an episode, not rewritten into a stable trait. Rollback is to stop committing, injecting and notifying. Rows already written stay.

## Rollback

Stop calling the commit, remove the prompt injection and stop creating attention notices. The migration is expand-only. Do not drop the tables as a rollback.
