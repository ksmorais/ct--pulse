"""Teste controlado de escrita e leitura persistente no Firestore.

Usa documentos fictícios em _ct_pulse_diagnostics, sem consultar ou editar
usuários do CT Pulse. Não realiza migração do SQLite.
Uso:
    python firestore_persistence_check.py write
    python firestore_persistence_check.py read <id>
    python firestore_persistence_check.py delete <id>
"""
import argparse
import re
import secrets
from datetime import datetime, timezone
from firebase_store import get_firestore_client

COLLECTION = "_ct_pulse_diagnostics"
PATTERN = re.compile(r"^[a-f0-9]{24}$")


def reference(document_id):
    if not PATTERN.fullmatch(document_id):
        raise ValueError("Identificador inválido; use o ID retornado no comando write.")
    return get_firestore_client().collection(COLLECTION).document(document_id)


def write_probe():
    document_id = secrets.token_hex(12)
    ref = reference(document_id)
    ref.create({
        "kind": "ct-pulse-firestore-smoke-test",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "manual-local-check",
        "no_personal_data": True,
    })
    print("Documento fictício gravado no Firestore.")
    print("ID para consultar depois:", document_id)


def read_probe(document_id):
    doc = reference(document_id).get()
    if not doc.exists:
        raise RuntimeError("Documento não encontrado. Verifique o ID e o projeto.")
    data = doc.to_dict() or {}
    if data.get("kind") != "ct-pulse-firestore-smoke-test":
        raise RuntimeError("Documento encontrado, mas não pertence ao teste.")
    print("Persistência remota confirmada: documento fictício encontrado.")
    print("Criado em UTC:", data.get("created_at_utc", "não informado"))


def delete_probe(document_id):
    ref = reference(document_id)
    doc = ref.get()
    if not doc.exists:
        print("Documento já não existe.")
        return
    if (doc.to_dict() or {}).get("kind") != "ct-pulse-firestore-smoke-test":
        raise RuntimeError("Recusando apagar documento que não pertence ao teste.")
    ref.delete()
    print("Documento fictício de teste apagado.")


def main():
    parser = argparse.ArgumentParser(description="Teste de persistência remota em Firestore")
    parser.add_argument("action", choices=["write", "read", "delete"])
    parser.add_argument("document_id", nargs="?")
    args = parser.parse_args()
    if args.action == "write":
        if args.document_id:
            parser.error("O comando write gera o ID automaticamente.")
        write_probe()
    else:
        if not args.document_id:
            parser.error("Informe o ID exibido pelo comando write.")
        if args.action == "read":
            read_probe(args.document_id)
        else:
            delete_probe(args.document_id)


if __name__ == "__main__":
    main()
