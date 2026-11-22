"""Testa a ponte Firestore usando SQLite apenas em memória (sem nuvem)."""
import io
import json
import os
import sys
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from firestore_sql_bridge import execute_on_snapshot, _decode_sql, SnapshotTooLarge


class FirestoreSnapshotSimulation(unittest.TestCase):
    def setUp(self):
        self.context = patch.dict(os.environ, {"CT_FIRESTORE_DEMO_SEED": "1", "CT_DEMO_PASSWORD": "SenhaTemporaria2026!"})
        self.context.start()
        self.addCleanup(self.context.stop)
        self.snapshot = None
        self.cookie = ""
        self.csrf = ""

    def request(self, path, data=None):
        body = b"" if data is None else json.dumps(data).encode("utf-8")
        env = {
            "REQUEST_METHOD": "GET" if data is None else "POST",
            "PATH_INFO": "/api/" + path,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_COOKIE": self.cookie,
            "HTTP_X_CSRF_TOKEN": self.csrf,
            "REMOTE_ADDR": "127.0.0.1",
        }
        next_blob, (status, headers, resp) = execute_on_snapshot(
            self.snapshot, env, body, server.sqlite_app
        )
        self.snapshot = next_blob
        out = json.loads(resp)
        for key, value in headers:
            if key == "Set-Cookie":
                self.cookie = value.split(";")[0]
        if "csrf" in out:
            self.csrf = out["csrf"]
        return int(status.split()[0]), out

    def test_login_and_new_user_persist_between_requests(self):
        code, _ = self.request("state")
        self.assertEqual(code, 401)  # banco é inicializado mesmo antes do login
        self.assertGreater(len(self.snapshot), 100)
        code, result = self.request("login", {
            "email": "admin@ctpulse.com", "password": "SenhaTemporaria2026!"
        })
        self.assertEqual(code, 200)
        self.assertEqual(result["user"]["role"], "admin")
        code, result = self.request("user/save", {
            "name": "Aluno Ficticio", "email": "cadastro@exemplo.test",
            "role": "student", "password": "SenhaDeTeste2026!", "plan_cents": 0
        })
        self.assertEqual(code, 200)
        # Um novo SQLite em memória será criado em cada chamada;
        # logo, a consulta abaixo depende exclusivamente do snapshot remoto.
        code, result = self.request("state")
        self.assertEqual(code, 200)
        self.assertTrue(any(s["email"] == "cadastro@exemplo.test" for s in result["students"]))
        self.assertIn("cadastro@exemplo.test", _decode_sql(self.snapshot))

    def test_unauthorized_update_does_not_change_data(self):
        self.request("state")
        before = self.snapshot
        code, _ = self.request("notice/delete", {"id": 1})
        self.assertEqual(code, 401)
        self.assertEqual(before, self.snapshot)

    def test_recovery_does_not_seed_again(self):
        self.request("state")
        before = self.snapshot
        with patch.dict(os.environ, {"CT_FIRESTORE_DEMO_SEED": "0"}):
            self.request("state")
        self.assertEqual(self.snapshot, before)

    def test_invalid_blob_fails_closed(self):
        with self.assertRaises((ValueError, zlib.error)):
            _decode_sql(b"not a valid compressed db")

    def test_refuses_uninitialized_backend_without_explicit_seed(self):
        with patch.dict(os.environ, {"CT_FIRESTORE_DEMO_SEED": "0"}):
            with self.assertRaises(RuntimeError):
                self.request("state")


if __name__ == "__main__":
    unittest.main()
