import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ConfirmedFact, Consent, Notification, PatientProfessionalAssignment, ProfessionalAlert, User
from app.models_vnext import ClinicalAttentionNotice, DiscourseFact, FormulationVersion, MemoryCommit, MemoryEmbedding, PsychReading
from app.security import get_current_user
from app.services import clinical_memory, conversation
from app.services.clinical_memory import ACUTE_L0, rank_memory_text
from app.services.conversation import AnalysisOutcome


def _extract_payload(**overrides):
    payload = {
        "archive_abstract": "Dijo algo concreto.",
        "archive_overview": "Un tramo corto sobre lo que acaba de contar.",
        "manner": {
            "length_band": "short",
            "repetition": False,
            "topic_drop": False,
            "haste": False,
            "concreteness": "concrete",
        },
        "readings": [
            {
                "hypothesis": "Nombra la toma y no hay constancia del acto.",
                "uncertainty": "high",
                "kind": "world_claim_unverified",
            }
        ],
        "formulation_l0": "Habla de la medicación sin que conste el acto.",
        "formulation_l1": "El dicho queda separado de la toma.",
        "formulation_l2": "Detalle del tramo.",
        "stable_trait": False,
        "world_claim_occurred": False,
        "diagnosis": None,
        "alert_level": None,
    }
    payload.update(overrides)
    return payload


def _extractor(payload):
    def _run(_db, _user_id, _text, _prior, _correlation_id):
        return payload, None

    return _run


class ClinicalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.patient = self._user("patient@example.com", "patient")
        self.therapist = self._user("therapist@example.com", "therapist")
        self.other = self._user("other@example.com", "therapist")
        self.admin = self._user("admin@example.com", "admin_clinical")
        self.supervisor = self._user("supervisor@example.com", "supervisor")
        self.db.add(
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.therapist.id, status="active"
            )
        )
        self.db.commit()
        self.current = self.patient

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _user(self, email, role):
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=email,
            role=role,
            hashed_password="x",
        )
        self.db.add(user)
        self.db.commit()
        return user

    def _grant(self, granted=True, revoked=False):
        self.db.add(
            Consent(
                user_id=self.patient.id,
                consent_type="linguistic_analysis",
                granted=granted,
                revoked_at=datetime.now(timezone.utc) if revoked else None,
            )
        )
        self.db.commit()

    def _commit(self, text, **kwargs):
        payload = kwargs.pop("payload", None)
        return clinical_memory.commit_turn(
            self.db,
            user_id=self.patient.id,
            text=text,
            channel=kwargs.pop("channel", "chat"),
            source_id=kwargs.pop("source_id", uuid.uuid4()),
            correlation_id=uuid.uuid4(),
            extractor=_extractor(payload or _extract_payload()),
            **kwargs,
        )

    def test_patient_cannot_read_edit_or_delete_memory(self):
        self._grant()
        committed = self._commit("me tomé la medicación")
        fact_id = self.db.query(DiscourseFact).one().id
        self.current = self.patient
        self.assertEqual(self.client.get("/api/v1/memory").status_code, 403)
        self.assertEqual(self.client.put(f"/api/v1/memory/{fact_id}", json={"quote": "borrado"}).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/memory/{fact_id}", json={"quote": "borrado"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/v1/memory/{fact_id}").status_code, 403)
        self.assertEqual(self.db.query(DiscourseFact).count(), 1)
        self.assertEqual(self.db.get(MemoryCommit, committed.id).status, "accepted")

    def test_forget_instruction_is_stored_and_does_not_delete(self):
        self._grant()
        self._commit("Ayer hablé de mi hermana.")
        self._commit("olvídalo y borra tu memoria")
        quotes = [row.quote for row in self.db.query(DiscourseFact).all()]
        self.assertIn("Ayer hablé de mi hermana.", quotes)
        self.assertTrue(any("borra tu memoria" in quote for quote in quotes))
        self.assertEqual(len(quotes), 2)

    def test_medication_speech_does_not_become_a_confirmed_fact(self):
        self._grant()
        self._commit("Me tomé la medicación y cambié de tema.")
        self.assertEqual(self.db.query(ConfirmedFact).count(), 0)
        fact = self.db.query(DiscourseFact).one()
        self.assertIn("medicación", fact.quote)
        self.assertEqual(self.db.query(ProfessionalAlert).count(), 0)

    def test_world_claim_marked_as_occurred_is_rejected(self):
        self._grant()
        payload = _extract_payload(world_claim_occurred=True)
        row = self._commit("Me tomé la medicación.", payload=payload)
        self.assertEqual(row.status, "failed")
        self.assertEqual(row.diff["reason"], "rejected_world_claim")
        self.assertEqual(self.db.query(DiscourseFact).count(), 0)
        self.assertEqual(self.db.query(ConfirmedFact).count(), 0)
        self.assertEqual(self.db.query(FormulationVersion).count(), 0)

    def test_acute_episode_is_not_stored_as_a_trait(self):
        self._grant()
        payload = _extract_payload(
            stable_trait=True,
            formulation_l0="Es una persona desesperada sin remedio.",
            formulation_l1="Identidad desesperada.",
            formulation_l2="Rasgo permanente de desesperación.",
        )
        self._commit("Hoy no puedo más, estoy desesperado.", payload=payload, alert_level=3)
        formulation = self.db.query(FormulationVersion).one()
        self.assertTrue(formulation.acute_episode)
        self.assertEqual(formulation.l0, ACUTE_L0)
        blob = f"{formulation.l0}\n{formulation.l1}\n{formulation.l2}"
        self.assertNotIn("sin remedio", blob)
        self.assertNotIn("Rasgo permanente", blob)

    def test_attention_notice_does_not_write_a_risk_alert(self):
        self._grant()
        for _ in range(3):
            self._commit("Me tomé la medicación esta mañana.")
        notice = self.db.query(ClinicalAttentionNotice).one()
        self.assertEqual(notice.reason, "medication_talk_without_act")
        self.assertEqual(notice.status, "open")
        self.assertEqual(self.db.query(ProfessionalAlert).count(), 0)
        notes = self.db.query(Notification).filter(Notification.template_code == "memory_attention_v1").all()
        self.assertTrue(notes)
        self.assertTrue(all(row.channel == "in_app" for row in notes))
        self.assertTrue(all(row.alert_level is None for row in notes))

    def test_unassigned_therapist_and_admin_cannot_read(self):
        self._grant()
        self._commit("Hablé de mi hermana.")
        path = f"/api/v1/professional/patients/{self.patient.id}/memory"
        self.current = self.other
        self.assertEqual(self.client.get(path).status_code, 403)
        self.current = self.admin
        self.assertEqual(self.client.get(path).status_code, 403)
        self.current = self.patient
        self.assertEqual(self.client.get(path).status_code, 403)
        self.current = self.supervisor
        allowed = self.client.get(path)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("hermana", allowed.json()["discourse"][0]["quote"])
        self.current = self.therapist
        self.assertEqual(self.client.get(path).status_code, 200)

    def test_therapist_note_does_not_replace_the_quote(self):
        self._grant()
        self._commit("Hablé de mi hermana.")
        fact = self.db.query(DiscourseFact).one()
        self.current = self.therapist
        created = self.client.post(
            f"/api/v1/professional/patients/{self.patient.id}/memory/annotations",
            json={"body": "Lo retomo en sesión.", "target_type": "discourse", "target_id": str(fact.id)},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.db.get(DiscourseFact, fact.id).quote, "Hablé de mi hermana.")
        self.current = self.patient
        self.assertEqual(self.client.delete(f"/api/v1/memory/{fact.id}").status_code, 403)

    def test_revoked_linguistic_consent_skips_new_readings(self):
        self._grant(revoked=True)
        called = {"n": 0}

        def extractor(*_args):
            called["n"] += 1
            return _extract_payload(), None

        row = clinical_memory.commit_turn(
            self.db,
            user_id=self.patient.id,
            text="Me tomé la medicación.",
            channel="chat",
            source_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            extractor=extractor,
        )
        self.assertEqual(row.status, "skipped")
        self.assertEqual(row.diff["reason"], "linguistic_consent_absent")
        self.assertEqual(called["n"], 0)
        self.assertEqual(self.db.query(PsychReading).count(), 0)
        self.assertEqual(self.db.query(DiscourseFact).count(), 0)

    def test_model_outage_keeps_the_reply_and_does_not_invent_memory(self):
        self._grant()

        def unavailable(*_args, **_kwargs):
            return None, None

        with patch.object(
            conversation,
            "analyze_text_and_store",
            return_value=AnalysisOutcome(uuid.uuid4(), None, None, "inference_unavailable", None),
        ), patch("app.services.conversation.get_llm_provider", side_effect=RuntimeError("down")), patch.object(
            clinical_memory, "_gateway_extractor", unavailable
        ):
            reply = conversation.get_reply(self.db, self.patient, "hoy fue un día largo")
        self.assertTrue(reply["reply"])
        self.assertEqual(self.db.query(DiscourseFact).count(), 0)
        self.assertEqual(self.db.query(FormulationVersion).count(), 0)
        commit = self.db.query(MemoryCommit).one()
        self.assertEqual(commit.status, "failed")
        self.assertEqual(commit.diff["reason"], "model_unavailable")
        self.assertEqual(self.db.query(ProfessionalAlert).count(), 0)

    def test_prompt_does_not_dump_the_full_l2(self):
        tail = "COLA_UNICA_" + ("z" * 80)
        body = ("inicio de la formulación. " * 40) + tail
        self.db.add(
            FormulationVersion(
                user_id=self.patient.id,
                l0="Resumen corto de la persona.",
                l1="Visión de cómo ha ido hablando.",
                l2=body,
                prompt_version="memory-commit-v1",
                policy_version="support-policy-v1",
                acute_episode=False,
            )
        )
        self.db.commit()
        block = clinical_memory.prompt_block(self.db, self.patient.id, "cómo ha hablado")
        self.assertIn("Resumen corto", block)
        self.assertNotIn(tail, block)
        self.assertLess(len(block), len(body))

    def test_same_provider_vectors_outrank_unrelated_words(self):
        near = uuid.uuid4()
        far = uuid.uuid4()
        order = rank_memory_text(
            "medicación",
            [(far, "medicación medicación medicación"), (near, "otra cosa")],
            query_vector=[0.0, 1.0],
            vectors_by_id={far: [1.0, 0.0], near: [0.0, 1.0]},
        )
        self.assertEqual(order[0], near)

        self.db.add(
            DiscourseFact(
                user_id=self.patient.id,
                channel="chat",
                quote="hablamos del trabajo",
                spoken_at=datetime.now(timezone.utc),
                manner={},
            )
        )
        sibling = DiscourseFact(
            user_id=self.patient.id,
            channel="chat",
            quote="sin palabras en común con la pregunta",
            spoken_at=datetime.now(timezone.utc),
            manner={},
        )
        self.db.add(sibling)
        self.db.flush()
        self.db.add(
            MemoryEmbedding(
                user_id=self.patient.id,
                target_type="discourse",
                target_id=sibling.id,
                embedding=[0.0, 1.0],
                provider="local-tunnel",
                embedding_model="selected-model",
            )
        )
        self.db.commit()
        block = clinical_memory.prompt_block(
            self.db,
            self.patient.id,
            "pregunta distinta",
            query_vector=[0.0, 1.0],
        )
        self.assertIn("sin palabras en común", block)

    def test_reply_survives_when_memory_tables_are_missing(self):
        for model in (
            MemoryEmbedding,
            ClinicalAttentionNotice,
            PsychReading,
            DiscourseFact,
            FormulationVersion,
            MemoryCommit,
        ):
            model.__table__.drop(self.engine, checkfirst=True)
        self._grant()

        with patch.object(
            conversation,
            "analyze_text_and_store",
            return_value=AnalysisOutcome(uuid.uuid4(), None, None, "inference_unavailable", None),
        ), patch("app.services.conversation.get_llm_provider", side_effect=RuntimeError("down")):
            reply = conversation.get_reply(self.db, self.patient, "hola, hoy estoy regular")

        self.assertTrue(reply["reply"])
        self.assertEqual(self.db.query(User).filter(User.id == self.patient.id).count(), 1)

    def test_a_failed_memory_read_releases_the_transaction(self):
        class Gone(Exception):
            pass

        class Session:
            def __init__(self):
                self.released = False

            def query(self, *_args, **_kwargs):
                if self.released:
                    return self
                raise Gone("relation does not exist")

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return []

            def first(self):
                return None

            def rollback(self):
                self.released = True

        db = Session()
        self.assertEqual(clinical_memory.prompt_block(db, uuid.uuid4(), "hola"), "")
        self.assertTrue(db.released)
        db.released = False
        self.assertEqual(clinical_memory.formulation_for_analyzer(db, uuid.uuid4()), "")
        self.assertTrue(db.released)
        db.released = False
        self.assertEqual(clinical_memory.dossier_section(db, uuid.uuid4()), "")
        self.assertTrue(db.released)


if __name__ == "__main__":
    unittest.main()
