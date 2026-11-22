"""Rotas experimentais ADMIN-only para alunos Firestore nativos em sandbox.

Habilitação opt-in: CT_NATIVE_STUDENTS_LAB=1 e CT_NATIVE_STUDENT_WORKSPACE_ID
com 24 caracteres hex. A sessão e o token CSRF são verificados contra
o snapshot SQLite remoto atual, mas ESTE ENDPOINT NÃO O MODIFICA.

Os alunos criados aqui são registros de demonstração SEM login, inscrição,
mensalidade ou integração com as telas e rotas existentes.
"""
import io
import json
import logging
import os
import re
import sqlite3

from firestore_sql_bridge import COLLECTION as PRIVATE_COLLECTION, DOCUMENT as PRIVATE_DOCUMENT
from firestore_sql_bridge import _decode_sql
from native_student_repository import (
    NativeStudentRepository, StudentDataError, StudentNotFound,
    DuplicateStudentEmail, WORKSPACE_PATTERN
)

LOG = logging.getLogger(__name__)
ROUTES = {
    ("GET", "/api/native-students"),
    ("POST", "/api/native-students/create"),
    ("POST", "/api/native-students/update"),
}


def lab_enabled():
    workspace = os.environ.get("CT_NATIVE_STUDENT_WORKSPACE_ID", "")
    return (os.environ.get("CT_NATIVE_STUDENTS_LAB", "0") == "1"
            and bool(WORKSPACE_PATTERN.fullmatch(workspace)))


def _authenticate_admin(client, env):
    import server

    snapshot = client.collection(PRIVATE_COLLECTION).document(PRIVATE_DOCUMENT).get()
    if not snapshot.exists:
        raise RuntimeError("Fonte de autenticação ainda não inicializada.")
    data = snapshot.to_dict()
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise RuntimeError("Versão de autenticação incompatível.")
    blob = data.get("sqlite_dump_zlib")
    if not isinstance(blob, bytes):
        raise RuntimeError("Snapshot de autenticação indisponível.")
    sql = _decode_sql(blob)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(sql)
        conn.execute("PRAGMA foreign_keys=ON")
        user = server.auth(conn, env)  # cookie + token CSRF para POST
        server.allow(user, "admin")
    finally:
        conn.close()


def _json_response(start_response, status, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    reason = {200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized",
              403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
              409: "Conflict", 413: "Payload Too Large",
              503: "Service Unavailable"}.get(status, "Error")
    start_response(f"{status} {reason}", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
        ("X-Frame-Options", "DENY"),
    ])
    return [body]


def handle_native_students(env, start_response, raw_body, client):
    import server

    path = env.get("PATH_INFO", "")
    method = env.get("REQUEST_METHOD", "GET")
    if not lab_enabled():
        return _json_response(start_response, 404, {"error": "Recurso indisponível."})
    if (method, path) not in ROUTES:
        code = 405 if any(p == path for _, p in ROUTES) else 404
        return _json_response(start_response, code,
                              {"error": "Método não permitido." if code == 405 else "Rota não encontrada."})
    try:
        if method == "POST":
            if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                raise server.APIError("Envie JSON.", 400)
            if not 0 < len(raw_body) <= 65536:
                raise server.APIError("Conteúdo inválido.", 400)
            try:
                data = json.loads(raw_body)
            except (ValueError, UnicodeError):
                raise server.APIError("JSON inválido.", 400)
            if not isinstance(data, dict):
                raise server.APIError("JSON inválido.", 400)
        _authenticate_admin(client, env)
        repo = NativeStudentRepository(
            client, os.environ["CT_NATIVE_STUDENT_WORKSPACE_ID"]
        )
        if method == "GET":
            return _json_response(start_response, 200, {
                "students": repo.list_students(),
                "demo_only": True,
                "login_enabled": False,
                "persistent": True,
            })
        if path == "/api/native-students/create":
            if set(data) not in ({"name", "email"}, {"name", "email", "plan_cents"}):
                raise server.APIError("Informe apenas nome, e-mail e plano demonstrativo.", 400)
            new_id = repo.create_student(
                name=data["name"], email=data["email"],
                plan_cents=data.get("plan_cents", 0)
            )
            return _json_response(start_response, 201, {
                "ok": True, "id": new_id,
                "message": "Aluno fictício salvo no Firestore nativo (sem conta de login)."
            })
        if path == "/api/native-students/update":
            if "id" not in data:
                raise server.APIError("Informe o ID do aluno.", 400)
            changes = {k: v for k, v in data.items() if k != "id"}
            student_id = repo.update_student(data["id"], **changes)
            return _json_response(start_response, 200, {"ok": True, "id": student_id})
        return _json_response(start_response, 404, {"error": "Rota não encontrada."})
    except server.APIError as exc:
        return _json_response(start_response, exc.status, {"error": exc.message})
    except DuplicateStudentEmail as exc:
        return _json_response(start_response, 409, {"error": str(exc)})
    except StudentNotFound as exc:
        return _json_response(start_response, 404, {"error": str(exc)})
    except StudentDataError as exc:
        return _json_response(start_response, 400, {"error": str(exc)})
    except Exception:
        LOG.error("Falha da API nativa de alunos; status 503")
        return _json_response(start_response, 503,
                              {"error": "Repositório de demonstração indisponível."})
