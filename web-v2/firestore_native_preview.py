"""Projeção de dados demonstrativos em coleções nativas do Firestore.

Origem: snapshot SQL privado da ponte existente.
Destino: ct_pulse_native_previews/<export_id>/<collection>/<document_id>.

- Não altera ou apaga o snapshot de origem.
- Não muda o backend em execução; a API continua usando a ponte SQL.
- Exclui hashes de senha, sessões e tentativas de login.
- Exportação opt-in, apenas com dados fictícios.
- O manifesto só fica "complete" após todas as escritas bem-sucedidas.
"""
import argparse
import hashlib
import json
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from firestore_sql_bridge import _decode_sql

SOURCE_COLLECTION = "_ct_pulse_private"
SOURCE_DOCUMENT = "sql_snapshot_v1"
DESTINATION_COLLECTION = "ct_pulse_native_previews"
MAX_EXPORT_DOCUMENTS = 1500
BATCH_SIZE = 175

# Colunas explicitamente autorizadas: nunca exportar password_hash,
# sessions, login_attempts ou qualquer token de autenticação.
TABLES = {
    "users": ("id", ("id", "name", "email", "role", "active",
                     "plan_cents", "belt", "created_at")),
    "classes": ("id", ("id", "name", "teacher_id", "days", "time",
                       "capacity", "active")),
    "enrollments": (("student_id", "class_id"), ("student_id", "class_id")),
    "bookings": ("id", ("id", "student_id", "class_id", "date")),
    "attendance": (("student_id", "class_id", "date"),
                   ("student_id", "class_id", "date", "present")),
    "payments": ("id", ("id", "student_id", "month", "amount_cents",
                        "due", "status", "paid_at")),
    "payment_requests": ("payment_id", ("payment_id", "method", "created_at")),
    "grades": ("id", ("id", "student_id", "author_id", "belt", "note", "date")),
    "notices": ("id", ("id", "author_id", "class_id", "title", "body",
                       "created_at")),
    "inbox": (("notice_id", "student_id"),
              ("notice_id", "student_id", "read_at")),
}


def _identifier(value):
    if value is None:
        raise ValueError("Chave primária nula na exportação.")
    text = str(value)
    if not text or "/" in text or len(text) > 120:
        raise ValueError("Identificador inválido na exportação.")
    return text


def _document_id(row, pk):
    keys = pk if isinstance(pk, tuple) else (pk,)
    return "_".join(_identifier(row[k]) for k in keys)


def snapshot_to_documents(blob):
    """Converte snapshot Firestore para documentos nativos, sem acesso à rede."""
    sql = _decode_sql(blob)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        # SQL produzido exclusivamente pelo SQLite iterdump() da aplicação.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(sql)
        conn.execute("PRAGMA foreign_keys=ON")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("O snapshot tem relações inválidas.")
        documents = {}
        total = 0
        for table, (pk, columns) in TABLES.items():
            selected = ",".join(columns)  # colunas constantes sob controle do código
            result = {}
            for record in conn.execute(f"SELECT {selected} FROM {table}"):
                row = dict(record)
                key = _document_id(row, pk)
                if table == "classes":
                    row["days"] = json.loads(row["days"])
                if key in result:
                    raise ValueError(f"ID duplicado na coleção {table}.")
                result[key] = row
                total += 1
                if total > MAX_EXPORT_DOCUMENTS:
                    raise ValueError("Limite de documentos da demonstração excedido.")
            documents[table] = result
        return documents
    finally:
        conn.close()


def plan_summary(documents):
    return {name: len(items) for name, items in documents.items()}


def write_native_preview(client, documents, source_digest):
    """Escreve snapshot somente em namespace isolado e retorna ID do manifesto.

    Falha parcial deixa status incomplete e não afeta o estado utilizado pela API.
    """
    export_id = secrets.token_hex(12)
    base = client.collection(DESTINATION_COLLECTION).document(export_id)
    counts = plan_summary(documents)
    now = datetime.now(timezone.utc).isoformat()
    base.create({
        "schema_version": 1,
        "status": "incomplete",
        "source_sha256": source_digest,
        "collection_counts": counts,
        "created_at_utc": now,
        "demo_only": True,
        "password_hashes_exported": False,
        "sessions_exported": False,
        "ready_for_runtime": False,
    })
    batch = client.batch()
    pending = 0
    for collection, items in documents.items():
        for document_id, data in items.items():
            target = base.collection(collection).document(document_id)
            batch.create(target, data)
            pending += 1
            if pending == BATCH_SIZE:
                batch.commit()
                batch = client.batch()
                pending = 0
    if pending:
        batch.commit()
    base.update({"status": "complete",
                 "completed_at_utc": datetime.now(timezone.utc).isoformat()})
    return export_id


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cria prévia de coleções Firestore a partir da demo atual."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Gravar a prévia em namespace isolado.")
    parser.add_argument("--ack-demo-only", action="store_true",
                        help="Confirmo que a origem contém apenas dados fictícios.")
    args = parser.parse_args(argv)
    if args.ack_demo_only and not args.apply:
        parser.error("--ack-demo-only é usado somente com --apply.")
    if args.apply and not args.ack_demo_only:
        parser.error("Para gravar, informe --apply --ack-demo-only.")

    # A primeira leitura remota é apenas da fonte. Nunca apagamos dados.
    from firebase_store import get_firestore_client
    client = get_firestore_client()
    existing = client.collection(SOURCE_COLLECTION).document(SOURCE_DOCUMENT).get()
    if not existing.exists:
        raise RuntimeError("Snapshot original não encontrado no projeto.")
    data = existing.to_dict()
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise RuntimeError("Versão de origem desconhecida.")
    blob = data.get("sqlite_dump_zlib")
    if not isinstance(blob, bytes):
        raise RuntimeError("Snapshot sem dados válidos.")

    documents = snapshot_to_documents(blob)
    counts = plan_summary(documents)
    print("Prévia de coleções nativas (sem gravar logins/senhas/sessões):")
    for collection, count in counts.items():
        print(f"  {collection}: {count}")
    print("Total de documentos:", sum(counts.values()))
    if not args.apply:
        print("Modo dry-run: nenhuma escrita efetuada.")
        print("Para exportar somente dados fictícios: "
              "python firestore_native_preview.py --apply --ack-demo-only")
        return 0

    digest = hashlib.sha256(blob).hexdigest()
    export_id = write_native_preview(client, documents, digest)
    print("Prévia nativa gravada em:")
    print(f"  {DESTINATION_COLLECTION}/{export_id}")
    print("O aplicativo continua utilizando o snapshot SQL original.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Sem imprimir exceção: stack traces podem conter dados do snapshot.
        print("Exportação não concluída: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
