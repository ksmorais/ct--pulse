"""Conexão segura ao Cloud Firestore do projeto CT Pulse.

Este módulo inicializa o cliente no servidor. Ainda não substitui as consultas
SQLite de server.py; a migração das tabelas precisa ser concluída e testada.
Nunca retorne as credenciais a clientes HTTP nem as imprima em logs.
"""
import json
import os


DEFAULT_PROJECT_ID = "ct-pulse"


def _configuration():
    project_id = (os.environ.get("FIREBASE_PROJECT_ID") or DEFAULT_PROJECT_ID).strip()
    if not project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID não configurado.")

    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if secret:
        try:
            data = json.loads(secret)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON não é JSON válido.") from exc
        if not isinstance(data, dict) or data.get("type") != "service_account":
            raise RuntimeError("Credencial Firebase inválida: conta de serviço esperada.")
        if data.get("project_id") != project_id:
            raise RuntimeError("O projeto da conta de serviço não corresponde a FIREBASE_PROJECT_ID.")
        if not all(isinstance(data.get(k), str) and data[k] for k in ("client_email", "private_key")):
            raise RuntimeError("Credencial Firebase incompleta.")
        return project_id, data

    # Opcional para desenvolvimento local com GOOGLE_APPLICATION_CREDENTIALS.
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return project_id, None

    raise RuntimeError(
        "Configure FIREBASE_SERVICE_ACCOUNT_JSON no ambiente seguro do Render "
        "ou GOOGLE_APPLICATION_CREDENTIALS no ambiente local."
    )


def get_firestore_client():
    """Retorna cliente Firestore autenticado para acesso exclusivamente no backend."""
    project_id, service_account = _configuration()

    # Import tardio: tests da aplicação SQLite não dependem do Firebase.
    import firebase_admin
    from firebase_admin import credentials, firestore

    app_name = "ct-pulse-firestore"
    try:
        firebase_app = firebase_admin.get_app(app_name)
    except ValueError:
        credential = (
            credentials.Certificate(service_account)
            if service_account is not None
            else credentials.ApplicationDefault()
        )
        firebase_app = firebase_admin.initialize_app(
            credential, {"projectId": project_id}, name=app_name
        )
    return firestore.client(app=firebase_app)


def check_connection():
    """Leitura de prova, sem escrever nem criar dados no banco."""
    client = get_firestore_client()
    client.collection("_ct_pulse_internal").document("connection_check").get()
    return True


if __name__ == "__main__":
    try:
        check_connection()
        print("Conexão com o Cloud Firestore validada.")
    except Exception as exc:
        # Não imprimir detalhes que possam incluir dados privados das credenciais.
        print("Não foi possível validar a conexão: " + type(exc).__name__)
        raise SystemExit(1)
