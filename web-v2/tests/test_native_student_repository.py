"""Testes do repositório nativo de alunos, sem acesso à rede."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from native_student_repository import (
    NativeStudentRepository, DuplicateStudentEmail, StudentDataError, StudentNotFound,
    SANDBOX_COLLECTION,
)


class FakeSnapshot:
    def __init__(self, record):
        self.value = record
        self.exists = record is not None

    def to_dict(self):
        return dict(self.value) if self.value is not None else None


class FakeRef:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def collection(self, name):
        return FakeCollection(self.store, self.path + "/" + name)

    def get(self, transaction=None):
        return FakeSnapshot(self.store.get(self.path))

    def create(self, value):
        if self.path in self.store:
            raise ValueError("Documento já existe")
        self.store[self.path] = dict(value)

    def update(self, value):
        if self.path not in self.store:
            raise ValueError("Documento inexistente")
        self.store[self.path].update(value)


class FakeCollection:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def document(self, doc_id):
        return FakeRef(self.store, self.path + "/" + doc_id)

    def stream(self):
        prefix = self.path + "/"
        for key, value in list(self.store.items()):
            if key.startswith(prefix) and "/" not in key[len(prefix):]:
                yield FakeSnapshot(value)


class FakeClient:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self.store, name)

    def atomic(self, operation):
        queued = []

        class Transaction:
            def create(self, reference, record):
                queued.append(("create", reference, record))

            def update(self, reference, record):
                queued.append(("update", reference, record))

        result = operation(Transaction())
        for action, reference, record in queued:
            getattr(reference, action)(record)
        return result


class StudentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.workspace_id = "a" * 24
        self.repo = NativeStudentRepository(
            self.client, self.workspace_id, atomic_runner=self.client.atomic
        )

    def test_creates_student_and_reads_document(self):
        student_id = self.repo.create_student(name="  Aluno Ficticio  ",
                                              email="  STUDENT@example.test  ")
        student = self.repo.get_student(student_id)
        self.assertEqual(student["name"], "Aluno Ficticio")
        self.assertEqual(student["email"], "student@example.test")
        self.assertEqual(student["role"], "student")
        self.assertEqual(student["active"], 1)
        self.assertEqual(student["belt"], "Branca")
        self.assertEqual(student["plan_cents"], 0)
        self.assertEqual(len(self.client.store), 2)  # usuário e índice atômico
        self.assertFalse(any("password" in str(rec).lower() for rec in self.client.store.values()))
        self.assertFalse(any("session" in key for key in self.client.store))

    def test_duplicate_email_rejected_case_insensitively(self):
        self.repo.create_student(name="Aluno Um", email="a@example.test")
        with self.assertRaises(DuplicateStudentEmail):
            self.repo.create_student(name="Aluno Dois", email="A@example.test")
        self.assertEqual(len(self.repo.list_students()), 1)

    def test_updates_only_safe_student_fields(self):
        student_id = self.repo.create_student(name="Aluna Teste", email="aluna@example.test")
        self.repo.update_student(student_id, name="Nome Atualizado",
                                 plan_cents=12000, active=False, belt="Amarela")
        updated = self.repo.get_student(student_id)
        self.assertEqual(updated["name"], "Nome Atualizado")
        self.assertEqual(updated["active"], 0)
        self.assertEqual(updated["plan_cents"], 12000)
        self.assertEqual(updated["belt"], "Amarela")
        self.assertEqual(updated["role"], "student")

    def test_refuses_role_email_and_password_mutation(self):
        student_id = self.repo.create_student(name="Aluna Teste", email="aluna@example.test")
        for change in ({"role": "admin"}, {"email": "outro@example.test"},
                       {"password_hash": "x"}, {"name": ""}, {"plan_cents": -10},
                       {"plan_cents": True}, {"belt": "Inventada"}):
            with self.subTest(change=change):
                with self.assertRaises(StudentDataError):
                    self.repo.update_student(student_id, **change)
        self.assertEqual(self.repo.get_student(student_id)["role"], "student")

    def test_invalid_creation_refused_without_writes(self):
        for params in (
            {"name": "", "email": "test@example.test"},
            {"name": "X", "email": "nao_e_email"},
            {"name": "X", "email": "test@example.test", "plan_cents": True},
            {"name": "X", "email": "test@example.test", "plan_cents": 10000001},
        ):
            with self.subTest(params=params):
                with self.assertRaises(StudentDataError):
                    self.repo.create_student(**params)
        self.assertEqual(self.client.store, {})

    def test_cannot_modify_other_role(self):
        teacher_id = "student_" + "b" * 24
        teacher_ref = self.repo.users.document(teacher_id)
        teacher_ref.create({"id": teacher_id, "role": "teacher", "name": "Prof"})
        with self.assertRaises(StudentNotFound):
            self.repo.update_student(teacher_id, name="Invasao")
        self.assertEqual(teacher_ref.get().to_dict()["name"], "Prof")

    def test_workspace_isolated_from_original_snapshot_and_export(self):
        original_keys = set(self.client.store)
        student_id = self.repo.create_student(name="Aluno A", email="x@example.test")
        self.assertTrue(student_id.startswith("student_"))
        for key in set(self.client.store) - original_keys:
            self.assertTrue(key.startswith(
                SANDBOX_COLLECTION + "/" + self.workspace_id + "/"
            ))
        self.assertFalse(any("_ct_pulse_private" in key for key in self.client.store))
        self.assertFalse(any("ct_pulse_native_previews" in key for key in self.client.store))

    def test_list_sorted_and_missing_record(self):
        self.repo.create_student(name="Zeca", email="zeca@example.test")
        self.repo.create_student(name="Ana", email="ana@example.test")
        self.assertEqual([s["name"] for s in self.repo.list_students()], ["Ana", "Zeca"])
        with self.assertRaises(StudentNotFound):
            self.repo.get_student("student_" + "0" * 24)

    def test_reject_invalid_workspace_or_student_ids(self):
        with self.assertRaises(StudentDataError):
            NativeStudentRepository(self.client, "../forbidden", self.client.atomic)
        with self.assertRaises(StudentDataError):
            self.repo.get_student("../forbidden")
        with self.assertRaises(StudentDataError):
            self.repo.update_student("../forbidden", name="X")

    def test_transaction_failure_does_not_partially_create_student(self):
        def fail_before_commit(operation):
            class Tx:
                def create(self, ref, value):
                    pass
            operation(Tx())
            raise RuntimeError("Conflito simulado")
        failing = NativeStudentRepository(
            self.client, self.workspace_id, atomic_runner=fail_before_commit
        )
        with self.assertRaises(RuntimeError):
            failing.create_student(name="Falha", email="falha@example.test")
        self.assertEqual(self.client.store, {})

    def test_email_unique_per_workspace(self):
        self.repo.create_student(name="Aluno A", email="x@example.test")
        other = NativeStudentRepository(self.client, "b" * 24, self.client.atomic)
        other.create_student(name="Aluno B", email="x@example.test")
        self.assertEqual(len(other.list_students()), 1)
        self.assertEqual(len(self.repo.list_students()), 1)


if __name__ == "__main__":
    unittest.main()
