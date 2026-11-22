"""Ponte TEMPORÁRIA Firestore / SQLite para demos pequenas do CT Pulse.

O Firestore guarda um snapshot SQL comprimido como fonte durável de dados.
O SQLite permanece somente em memória, para preservar as consultas SQL
existentes. Esta solução NÃO implementa coleções Firestore por entidade e
não é adequada a produção, alta concorrência nem dados pessoais reais.

FireStore transaction lê o estado e grava o próximo estado atomicamente;
quando existe contenção, SDK pode repetir a função com um snapshot novo.
"""
import io
import json
import logging
import os
import sqlite3
import zlib
from datetime import datetime, timezone

COLLECTION = "_ct_pulse_private"
DOCUMENT = "sql_snapshot_v1"
MAX_COMPRESSED_BYTES = 700_000
MAX_UNCOMPRESSED_BYTES = 2_000_000
LOG = logging.getLogger(__name__)


class SnapshotTooLarge(RuntimeError):
    pass


def _decode_sql(blob):
    if not isinstance(blob, bytes):
        raise ValueError("Snapshot de banco inválido.")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(blob, MAX_UNCOMPRESSED_BYTES + 1)
    if len(raw) > MAX_UNCOMPRESSED_BYTES or decoder.unconsumed_tail:
        raise SnapshotTooLarge("Snapshot excedeu o limite do modo demonstrativo.")
    if not decoder.eof or decoder.unused_data:
        raise ValueError("Snapshot incompleto ou corrompido.")
    return raw.decode("utf-8")


def execute_on_snapshot(snapshot_blob, env, request_body, sqlite_app):
    """Processa uma requisição usando um SQLite transitório e retorna novo snapshot.

    Esta função não chama o Firestore, podendo ser testada sem credenciais.
    A escrita remota acontece de forma atômica apenas depois do processamento.
    """
    # Import tardio evita importação circular durante o startup.
    import server

    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    token = server._FIRESTORE_SQL_CONN.set(conn)
    try:
        if snapshot_blob is None:
            if os.environ.get("CT_FIRESTORE_DEMO_SEED") != "1":
                raise RuntimeError("Banco Firestore não inicializado: somente modo demo permitido.")
            server.init()
            server.seed_demo()
        else:
            conn.execute("PRAGMA foreign_keys=OFF")
            try:
                conn.executescript(_decode_sql(snapshot_blob))
            finally:
                conn.execute("PRAGMA foreign_keys=ON")
        local_env = dict(env)
        local_env["wsgi.input"] = io.BytesIO(request_body)
        response = {}

        def capture_start(status, headers, exc_info=None):
            response["status"] = status
            response["headers"] = headers

        output = b"".join(sqlite_app(local_env, capture_start))
        if not response:
            raise RuntimeError("Servidor não retornou resposta HTTP.")
        sql_text = "\n".join(conn.iterdump())
        sql_bytes = sql_text.encode("utf-8")
        if len(sql_bytes) > MAX_UNCOMPRESSED_BYTES:
            raise SnapshotTooLarge("Base de demonstração excedeu o tamanho permitido.")
        packed = zlib.compress(sql_bytes, level=6)
        if len(packed) > MAX_COMPRESSED_BYTES:
            raise SnapshotTooLarge("Base comprimida excedeu o limite de armazenamento.")
        return packed, (response["status"], response["headers"], output)
    finally:
        server._FIRESTORE_SQL_CONN.reset(token)
        conn.close()


def firestore_wsgi_app(env, start_response, sqlite_app):
    """Executa API inteira numa transação Firestore sem fallback ao disco local."""
    from firebase_store import get_firestore_client
    from google.cloud import firestore

    # Nunca chamar o Firestore para HTML/CSS/JS/imagens.
    if not env.get("PATH_INFO", "/").startswith("/api/"):
        return sqlite_app(env, start_response)

    length_text = env.get("CONTENT_LENGTH") or "0"
    try:
        length = int(length_text)
    except (TypeError, ValueError):
        length = 0  # o handler original responde 400, sem ler o corpo
    if length < 0 or length > 65536:
        return _unavailable(start_response, 413, "Conteúdo muito grande.")
    request_body = env["wsgi.input"].read(length) if length else b""

    try:
        client = get_firestore_client()
        ref = client.collection(COLLECTION).document(DOCUMENT)

        @firestore.transactional
        def transact(tx):
            doc = ref.get(transaction=tx)
            saved = doc.to_dict() if doc.exists else {}
            if doc.exists and (not isinstance(saved, dict) or saved.get("schema_version") != 1):
                raise RuntimeError("Versão de snapshot desconhecida.")
            original = saved.get("sqlite_dump_zlib") if doc.exists else None
            if doc.exists and not isinstance(original, bytes):
                raise RuntimeError("Snapshot ausente.")
            packed, result = execute_on_snapshot(original, env, request_body, sqlite_app)
            if original != packed:
                tx.set(ref, {
                    "schema_version": 1,
                    "sqlite_dump_zlib": packed,
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                })
            return result

        status, headers, body = transact(client.transaction(max_attempts=5))
        start_response(status, headers)
        return [body]
    except SnapshotTooLarge:
        LOG.warning("Limite do snapshot Firestore atingido; alteração não persistida.")
        return _unavailable(start_response, 507, "Limite de dados da demonstração atingido.")
    except Exception:
        # Sem impressão de credenciais, tokens ou corpo da requisição nos logs.
        LOG.exception("Erro na operação de persistência Firestore")
        return _unavailable(start_response, 503, "Banco indisponível. Tente novamente.")


def _unavailable(start_response, status, message):
    body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
    status_text = {413: "Payload Too Large", 503: "Service Unavailable",
                   507: "Insufficient Storage"}[status]
    start_response(f"{status} {status_text}", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]
