"""Rotas admin-only para professores, turmas e inscrições do laboratório Firestore.

Reaproveita sessão e CSRF do CT Pulse, mas grava exclusivamente em
ct_pulse_native_sandboxes/<workspace_id>; sem contas de login ou cobrança real.
"""
import json
import logging
import os
from native_student_api import _authenticate_admin, _json_response, lab_enabled
from native_academy_repository import (
    NativeAcademyRepository, AcademyDataError, AcademyNotFound, NoVacancy
)
from native_student_repository import DuplicateStudentEmail, StudentDataError

LOG = logging.getLogger(__name__)
ROUTES = {
    ("GET", "/api/native-academy"),
    ("POST", "/api/native-academy/teacher/create"),
    ("POST", "/api/native-academy/class/create"),
    ("POST", "/api/native-academy/class/update"),
    ("POST", "/api/native-academy/enrollment"),
}


def handle_native_academy(env, start_response, raw_body, client):
    import server
    path = env.get("PATH_INFO", "")
    method = env.get("REQUEST_METHOD", "GET")
    if not lab_enabled():
        return _json_response(start_response, 404, {"error": "Recurso indisponível."})
    if (method, path) not in ROUTES:
        status = 405 if any(p == path for _, p in ROUTES) else 404
        return _json_response(start_response, status, {
            "error": "Método não permitido." if status == 405 else "Rota não encontrada."
        })
    try:
        if method == "POST":
            if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                raise server.APIError(400, "Envie JSON.")
            if not 0 < len(raw_body) <= 65536:
                raise server.APIError(400, "Conteúdo inválido.")
            try:
                data = json.loads(raw_body)
            except (UnicodeError, ValueError):
                raise server.APIError(400, "JSON inválido.")
            if not isinstance(data, dict):
                raise server.APIError(400, "JSON inválido.")
        # Verifica papel admin na sessão do estado atual. Em POST verifica CSRF.
        _authenticate_admin(client, env)
        repo = NativeAcademyRepository(
            client, os.environ["CT_NATIVE_STUDENT_WORKSPACE_ID"]
        )
        if path == "/api/native-academy":
            return _json_response(start_response, 200, {
                "teachers": repo.list_teachers(),
                "classes": repo.list_classes(),
                "enrollments": repo.list_enrollments(),
                "demo_only": True, "login_enabled": False,
            })
        if path == "/api/native-academy/teacher/create":
            if set(data) != {"name", "email"}:
                raise server.APIError(400, "Informe somente nome e e-mail fictícios.")
            new_id = repo.create_teacher(name=data["name"], email=data["email"])
        elif path == "/api/native-academy/class/create":
            if set(data) != {"name", "teacher_id", "days", "time", "capacity"}:
                raise server.APIError(400, "Campos de turma inválidos.")
            new_id = repo.create_class(**data)
        elif path == "/api/native-academy/class/update":
            if "id" not in data or not (set(data) - {"id"}):
                raise server.APIError(400, "Informe turma e alterações.")
            if set(data) - {"id", "name", "days", "time", "capacity", "active"}:
                raise server.APIError(400, "Campo de turma não permitido.")
            new_id = repo.update_class(data["id"], **{k:v for k,v in data.items() if k!="id"})
        elif path == "/api/native-academy/enrollment":
            if set(data) != {"student_id", "class_id", "active"}:
                raise server.APIError(400, "Informe aluno, turma e situação.")
            changed = repo.set_enrollment(**data)
            return _json_response(start_response, 200, {"ok": True, "changed": changed})
        else:
            raise server.APIError(404, "Rota não encontrada.")
        return _json_response(start_response, 201 if path.endswith("/create") else 200,
                              {"ok": True, "id": new_id})
    except server.APIError as exc:
        return _json_response(start_response, exc.status, {"error": exc.message})
    except DuplicateStudentEmail as exc:
        return _json_response(start_response, 409, {"error": str(exc)})
    except AcademyNotFound as exc:
        return _json_response(start_response, 404, {"error": str(exc)})
    except NoVacancy as exc:
        return _json_response(start_response, 409, {"error": str(exc)})
    except (AcademyDataError, StudentDataError) as exc:
        return _json_response(start_response, 400, {"error": str(exc)})
    except Exception:
        LOG.error("Falha do laboratório de turmas no Firestore; status 503")
        return _json_response(start_response, 503, {
            "error": "Laboratório Firestore indisponível."
        })
