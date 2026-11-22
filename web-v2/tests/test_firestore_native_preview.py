"""Testes sem rede para a prévia nativa do Firestore do CT Pulse."""
import hashlib
import os
import sqlite3
import sys
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import firestore_native_preview as exporter


def snapshot(fake_broken_fk=False):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO users(id,name,email,password_hash,role,plan_cents) VALUES(?,?,?,?,?,?)",
        [
            (1, "Administrador", "admin@example.test", "segredo-hash-admin", "admin", 0),
            (2, "Professor", "teacher@example.test", "segredo-hash-prof", "teacher", 0),
            (3, "Aluno Ficticio", "student@example.test", "segredo-hash-student", "student", 10000),
        ],
    )
    conn.execute("INSERT INTO classes(id,name,teacher_id,days,time,capacity) VALUES(?,?,?,?,?,?)",
                 (7, "Jiu Jitsu", 2, "[2,4]", "19:00", 15))
    conn.execute("INSERT INTO enrollments(student_id,class_id) VALUES(?,?)", (3, 7))
    conn.execute("INSERT INTO notices(id,author_id,title,body) VALUES(?,?,?,?)",
                 (9, 1, "Bem-vindo", "Aviso fictício"))
    conn.execute("INSERT INTO inbox(notice_id,student_id) VALUES(?,?)", (9, 3))
    conn.execute(
        "INSERT INTO payments(id,student_id,month,amount_cents,due) VALUES(?,?,?,?,?)",
        (11, 3, "2026-11", 10000, "2026-11-30"),
    )
    conn.execute("INSERT INTO payment_requests(payment_id,method) VALUES(?,?)", (11, "pix"))
    conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)",
                 ("token-secreto", 1, "csrf-secreto", 5000000000))
    if fake_broken_fk:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("INSERT INTO enrollments(student_id,class_id) VALUES(?,?)", (999, 7))
    dump = "\n".join(conn.iterdump()).encode("utf-8")
    conn.close()
    return zlib.compress(dump)


class FakeDocument:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def create(self, value):
        if self.path in self.store:
            raise ValueError("Documento existente")
        self.store[self.path] = dict(value)

    def update(self, value):
        if self.path not in self.store:
            raise ValueError("Documento ausente")
        self.store[self.path].update(value)

    def collection(self, name):
        return FakeCollection(self.store, self.path + "/" + name)


class FakeCollection:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def document(self, identifier):
        return FakeDocument(self.store, self.path + "/" + identifier)


class FakeBatch:
    def __init__(self):
        self.ops = []

    def create(self, ref, value):
        self.ops.append((ref, value))

    def commit(self):
        for ref, value in self.ops:
            ref.create(value)
        self.ops = []


class FakeClient:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return FakeCollection(self.data, name)

    def batch(self):
        return FakeBatch()


class NativePreviewTests(unittest.TestCase):
    def test_export_all_expected_collections(self):
        docs = exporter.snapshot_to_documents(snapshot())
        self.assertEqual(set(docs), set(exporter.TABLES))
        self.assertEqual(docs["users"]["3"]["role"], "student")
        self.assertEqual(docs["classes"]["7"]["days"], [2, 4])
        self.assertEqual(docs["enrollments"]["3_7"]["class_id"], 7)
        self.assertEqual(docs["inbox"]["9_3"]["notice_id"], 9)
        self.assertEqual(docs["payment_requests"]["11"]["method"], "pix")

    def test_does_not_copy_credentials_or_sessions(self):
        docs = exporter.snapshot_to_documents(snapshot())
        self.assertNotIn("sessions", docs)
        self.assertNotIn("login_attempts", docs)
        self.assertNotIn("password_hash", docs["users"]["1"])
        flat = str(docs)
        self.assertNotIn("segredo-hash", flat)
        self.assertNotIn("token-secreto", flat)
        self.assertNotIn("csrf-secreto", flat)

    def test_rejects_broken_relations(self):
        with self.assertRaises(ValueError):
            exporter.snapshot_to_documents(snapshot(fake_broken_fk=True))

    def test_rejects_invalid_or_oversize_blob(self):
        with self.assertRaises((ValueError, zlib.error)):
            exporter.snapshot_to_documents(b"invalid")
        with patch.object(exporter, "MAX_EXPORT_DOCUMENTS", 1):
            with self.assertRaises(ValueError):
                exporter.snapshot_to_documents(snapshot())

    def test_writes_isolated_version_and_finalizes_manifest(self):
        client = FakeClient()
        docs = exporter.snapshot_to_documents(snapshot())
        digest = hashlib.sha256(b"teste").hexdigest()
        with patch.object(exporter.secrets, "token_hex", return_value="a" * 24):
            version = exporter.write_native_preview(client, docs, digest)
        self.assertEqual(version, "a" * 24)
        root = "ct_pulse_native_previews/" + version
        self.assertEqual(client.data[root]["status"], "complete")
        self.assertFalse(client.data[root]["ready_for_runtime"])
        self.assertFalse(client.data[root]["password_hashes_exported"])
        self.assertEqual(client.data[root]["source_sha256"], digest)
        self.assertEqual(client.data[root + "/users/3"]["email"], "student@example.test")
        self.assertEqual(client.data[root + "/classes/7"]["name"], "Jiu Jitsu")
        self.assertNotIn("_ct_pulse_private/sql_snapshot_v1", client.data)

    def test_incomplete_export_not_marked_complete(self):
        client = FakeClient()
        docs = exporter.snapshot_to_documents(snapshot())
        base = client.batch
        def fail_on_commit():
            class FailingBatch(FakeBatch):
                def commit(self):
                    raise RuntimeError("falha simulada")
            return FailingBatch()
        client.batch = fail_on_commit
        with patch.object(exporter.secrets, "token_hex", return_value="b" * 24):
            with self.assertRaises(RuntimeError):
                exporter.write_native_preview(client, docs, "abcd")
        root = "ct_pulse_native_previews/" + "b" * 24
        self.assertEqual(client.data[root]["status"], "incomplete")

    def test_requires_explicit_demo_ack_for_apply(self):
        with self.assertRaises(SystemExit) as raised:
            exporter.main(["--apply"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
