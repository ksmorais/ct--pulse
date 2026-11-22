"""Testes sem rede para autorização da API nativa de alunos do CT Pulse."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from firestore_sql_bridge import execute_on_snapshot
import native_student_api as native_api


class FakeSnapshot:
    exists = True

    def __init__(self, blob):
        self.blob = blob

    def to_dict(self):
        return {"schema_version": 1, "sqlite_dump_zlib": self.blob}


class FakeDoc:
    def __init__(self, client):
        self.client = client

    def get(self):
        return FakeSnapshot(self.client.blob)


class FakeCollection:
    def __init__(self, client):
        self.client = client

    def document(self, name):
        if name != "sql_snapshot_v1":
            raise AssertionError("Documento não autorizado")
        return FakeDoc(self.client)


class FakeClient:
    def __init__(self):
        self.blob = None
        self.students = []
        self.updates = []

    def collection(self, name):
        if name != "_ct_pulse_private":
            raise AssertionError("Coleção incorreta: " + name)
        return FakeCollection(self)


class FakeRepository:
    def __init__(self, client, workspace_id):
        if workspace_id != "a" * 24:
            raise AssertionError("Workspace incorreto")
        self.client = client

    def list_students(self):
        return self.client.students

    def create_student(self, **data):
        student_id = "student_" + "b" * 24
        self.client.students.append({**data, "id": student_id, "role": "student", "active": 1, "belt": "Branca"})
        return student_id

    def update_student(self, student_id, **changes):
        self.client.updates.append((student_id, changes))
        for record in self.client.students:
            if record["id"] == student_id:
                record.update(changes)
        return student_id


class NativeStudentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "SenhaAdministradorUnit2026!"
        cls.env_patch = patch.dict(os.environ, {
            "CT_PERSISTENCE": "firestore",
            "CT_FIRESTORE_DEMO_SEED": "1",
            "CT_NATIVE_STUDENTS_LAB": "1",
            "CT_NATIVE_STUDENT_WORKSPACE_ID": "a" * 24,
            "CT_DEMO_PASSWORD": cls.password,
            "CT_DEMO_ADMIN_PASSWORD": cls.password,
            "CT_DEMO_TEACHER_PASSWORD": cls.password,
        })
        cls.env_patch.start()
        cls.addClassCleanup(cls.env_patch.stop)

    def setUp(self):
        self.client = FakeClient()
        env = self.environment("GET", "/api/state")
        self.client.blob, _ = execute_on_snapshot(
            None, env, b"", server.sqlite_app
        )
        self.admin_cookie, self.admin_csrf = self.get_session("admin@ctpulse.com")
        self.student_cookie, self.student_csrf = self.get_session("aluno@ctpulse.com")
        self.original_blob = self.client.blob

        self.repo_patch = patch.object(native_api, "NativeStudentRepository", FakeRepository)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)

    @staticmethod
    def environment(method, path, raw=b"", cookie="", csrf=""):
        return {
            "REQUEST_METHOD": method, "PATH_INFO": path,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": io.BytesIO(raw),
            "HTTP_COOKIE": cookie,
            "HTTP_X_CSRF_TOKEN": csrf,
            "REMOTE_ADDR": "127.0.0.1"
        }

    def get_session(self, email):
        body = json.dumps({"email": email, "password": self.password}).encode()
        env = self.environment("POST", "/api/login", body)
        self.client.blob, (status, headers, response) = execute_on_snapshot(
            self.client.blob, env, body, server.sqlite_app
        )
        self.assertTrue(status.startswith("200 "), status)
        cookie = next(val.split(";")[0] for key,val in headers if key == "Set-Cookie")
        csrf = json.loads(response)["csrf"]
        return cookie, csrf

    def request(self, method, path, data=None, cookie="", csrf=""):
        raw = json.dumps(data).encode() if data is not None else b""
        env = self.environment(method, path, raw, cookie, csrf)
        meta = {}
        def start(status, headers):
            meta["status"] = int(status.split()[0])
            meta["headers"] = headers
        result = b"".join(native_api.handle_native_students(
            env, start, raw, self.client
        ))
        return meta["status"], json.loads(result)

    def test_admin_can_list_create_and_update_sandbox_only(self):
        code, listing = self.request("GET", "/api/native-students",
                                     cookie=self.admin_cookie)
        self.assertEqual(code, 200)
        self.assertTrue(listing["demo_only"])
        self.assertFalse(listing["login_enabled"])
        code, created = self.request("POST", "/api/native-students/create",
            {"name": "Pessoa Fictícia", "email": "alunoficticio@example.test", "plan_cents": 0},
            self.admin_cookie, self.admin_csrf)
        self.assertEqual(code, 201)
        self.assertEqual(self.client.students[0]["role"], "student")
        code, updated = self.request("POST", "/api/native-students/update",
            {"id": created["id"], "name": "Nome de Teste"},
            self.admin_cookie, self.admin_csrf)
        self.assertEqual(code, 200)
        self.assertEqual(self.client.students[0]["name"], "Nome de Teste")
        self.assertEqual(self.original_blob, self.client.blob)

    def test_requires_login_admin_and_csrf(self):
        self.assertEqual(self.request("GET", "/api/native-students")[0], 401)
        self.assertEqual(self.request("GET", "/api/native-students",
                                      cookie=self.student_cookie)[0], 403)
        body = {"name": "X", "email": "x@example.test"}
        self.assertEqual(self.request("POST", "/api/native-students/create",
                                      body, self.admin_cookie, "")[0], 403)
        self.assertEqual(self.request("POST", "/api/native-students/create",
                                      body, self.student_cookie, self.student_csrf)[0], 403)
        self.assertEqual(len(self.client.students), 0)

    def test_rejects_role_and_password_injection(self):
        for unwanted in ("role", "password", "password_hash", "active", "id"):
            body = {"name": "Exemplo", "email": "exemplo@example.test", unwanted: "admin"}
            self.assertEqual(self.request("POST", "/api/native-students/create",
                body, self.admin_cookie, self.admin_csrf)[0], 400)
        self.assertEqual(len(self.client.students), 0)

    def test_disabling_feature_returns_404(self):
        with patch.dict(os.environ, {"CT_NATIVE_STUDENTS_LAB": "0"}):
            self.assertEqual(self.request("GET", "/api/native-students",
                                          cookie=self.admin_cookie)[0], 404)
        with patch.dict(os.environ, {"CT_PERSISTENCE": "sqlite"}):
            self.assertEqual(self.request("GET", "/api/native-students",
                                          cookie=self.admin_cookie)[0], 404)

    def test_invalid_methods_and_payloads(self):
        self.assertEqual(self.request("GET", "/api/native-students/create",
                                      cookie=self.admin_cookie)[0], 405)
        self.assertEqual(self.request("POST", "/api/native-students/update",
                                     {"name": "X"}, self.admin_cookie, self.admin_csrf)[0], 400)
        self.assertEqual(self.request("POST", "/api/native-students/create",
                                     {"name": "X"}, self.admin_cookie, self.admin_csrf)[0], 400)


if __name__ == "__main__":
    unittest.main()
