"""Testes integrados sem rede das rotas nativas de professores/turmas/inscrições."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import server
import native_academy_api as academy_api
from firestore_sql_bridge import execute_on_snapshot
from native_academy_repository import NativeAcademyRepository
from test_native_academy_repository import AcademyClient


class SnapshotDocument:
    def __init__(self, client):
        self.client = client
    def get(self):
        class Snap:
            exists = True
            def __init__(self, blob):
                self.blob = blob
            def to_dict(self):
                return {"schema_version": 1, "sqlite_dump_zlib": self.blob}
        return Snap(self.client.blob)


class SnapshotCollection:
    def __init__(self, client):
        self.client = client
    def document(self, name):
        if name != "sql_snapshot_v1":
            raise AssertionError("Documento privado incorreto.")
        return SnapshotDocument(self.client)


class MixedClient(AcademyClient):
    def __init__(self):
        super().__init__()
        self.blob = None
    def collection(self, name):
        if name == "_ct_pulse_private":
            return SnapshotCollection(self)
        return super().collection(name)


class NativeAcademyApiTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {
            "CT_PERSISTENCE": "firestore", "CT_FIRESTORE_DEMO_SEED": "1",
            "CT_NATIVE_STUDENTS_LAB": "1",
            "CT_NATIVE_STUDENT_WORKSPACE_ID": "a" * 24,
            "CT_DEMO_PASSWORD": "AlunoTesteSeguro2026!",
            "CT_DEMO_ADMIN_PASSWORD": "AdminTesteSeguro2026!",
            "CT_DEMO_TEACHER_PASSWORD": "ProfessorTesteSeguro2026!",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = MixedClient()
        self.client.blob, _ = execute_on_snapshot(
            None, self.env("GET", "/api/state"), b"", server.sqlite_app
        )
        self.admin_cookie, self.admin_csrf = self.login(
            "admin@ctpulse.com", "AdminTesteSeguro2026!"
        )
        self.student_cookie, self.student_csrf = self.login(
            "aluno@ctpulse.com", "AlunoTesteSeguro2026!"
        )
        self.blob_at_start = self.client.blob
        self.real_repo = NativeAcademyRepository(
            self.client, "a" * 24, atomic_runner=self.client.atomic
        )
        repo_patch = patch.object(
            academy_api, "NativeAcademyRepository",
            side_effect=lambda client, workspace: NativeAcademyRepository(
                client, workspace, atomic_runner=client.atomic))
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

    @staticmethod
    def env(method, path, raw=b"", cookie="", csrf=""):
        return {
            "REQUEST_METHOD": method, "PATH_INFO": path,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": io.BytesIO(raw),
            "HTTP_COOKIE": cookie, "HTTP_X_CSRF_TOKEN": csrf,
            "REMOTE_ADDR": "127.0.0.1",
        }

    def login(self, email, password):
        raw=json.dumps({"email":email,"password":password}).encode()
        self.client.blob, (status, headers, body) = execute_on_snapshot(
            self.client.blob, self.env("POST", "/api/login", raw),
            raw, server.sqlite_app
        )
        self.assertTrue(status.startswith("200 "), status)
        cookie = next(v.split(";")[0] for k,v in headers if k=="Set-Cookie")
        return cookie, json.loads(body)["csrf"]

    def api(self, method, path, data=None, cookie=None, csrf=None):
        raw = json.dumps(data).encode() if data is not None else b""
        env = self.env(method, path, raw,
                       self.admin_cookie if cookie is None else cookie,
                       self.admin_csrf if csrf is None else csrf)
        received = {}
        def response_start(status, headers):
            received["status"] = int(status.split()[0])
        result = b"".join(academy_api.handle_native_academy(
            env, response_start, raw, self.client
        ))
        return received["status"], json.loads(result)

    def test_admin_creates_teacher_class_and_enrolls_with_capacity(self):
        code,teacher = self.api("POST", "/api/native-academy/teacher/create",
                                {"name":"Instrutor Fictício","email":"professor@example.test"})
        self.assertEqual(code, 201)
        student1 = self.real_repo.create_student(
            name="Aluno Teste 1", email="aluno1@example.test"
        )
        student2 = self.real_repo.create_student(
            name="Aluno Teste 2", email="aluno2@example.test"
        )
        code,course=self.api("POST", "/api/native-academy/class/create",
                             {"name":"Jiu-jítsu demo","teacher_id":teacher["id"],
                              "days":[1,3,5],"time":"19:30","capacity":1})
        self.assertEqual(code,201)
        enrollment={"student_id":student1,"class_id":course["id"],"active":1}
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",enrollment)[0],200)
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",enrollment)[1]["changed"],False)
        second={"student_id":student2,"class_id":course["id"],"active":1}
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",second)[0],409)
        enrollment["active"]=0
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",enrollment)[0],200)
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",second)[0],200)
        code, listing=self.api("GET","/api/native-academy")
        self.assertEqual(code,200)
        self.assertEqual(len(listing["teachers"]),1)
        self.assertEqual(len(listing["classes"]),1)
        self.assertEqual(listing["classes"][0]["enrolled_count"],1)
        self.assertEqual(listing["enrollments"][0]["student_id"],student2)
        self.assertFalse(listing["login_enabled"])
        self.assertEqual(self.blob_at_start,self.client.blob)

    def test_authentication_and_csrf(self):
        self.assertEqual(self.api("GET","/api/native-academy",cookie="")[0],401)
        self.assertEqual(self.api("GET","/api/native-academy",
                                  cookie=self.student_cookie)[0],403)
        body={"name":"Fictício","email":"example@example.test"}
        self.assertEqual(self.api("POST","/api/native-academy/teacher/create",
                                  body,csrf="")[0],403)
        self.assertEqual(self.api("POST","/api/native-academy/teacher/create",
                                  body,cookie=self.student_cookie,
                                  csrf=self.student_csrf)[0],403)
        self.assertEqual(self.client.store,{})

    def test_forbidden_fields_and_methods(self):
        self.assertEqual(self.api("POST","/api/native-academy/teacher/create",
                      {"name":"X","email":"x@example.test","role":"admin"})[0],400)
        self.assertEqual(self.api("POST","/api/native-academy/class/create",
                      {"name":"X"})[0],400)
        self.assertEqual(self.api("POST","/api/native-academy/enrollment",
                      {"class_id":"x"})[0],400)
        self.assertEqual(self.api("POST","/api/native-academy/class/update",
                      {"id":"class_"+"a"*24,"teacher_id":"teacher_"+"b"*24})[0],400)
        self.assertEqual(self.api("GET","/api/native-academy/enrollment")[0],405)
        self.assertEqual(self.client.store,{})

    def test_disabled_lab_is_inaccessible(self):
        with patch.dict(os.environ, {"CT_NATIVE_STUDENTS_LAB":"0"}):
            self.assertEqual(self.api("GET","/api/native-academy")[0],404)


if __name__=="__main__":
    unittest.main()
