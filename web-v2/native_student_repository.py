"""Repositório experimental de alunos usando documentos Firestore individuais.

Não é usado pela API CT Pulse e NÃO substitui autenticação ou permissões.
O namespace ct_pulse_native_sandboxes é isolado do snapshot e das prévias
exportadas: somente dados fictícios de desenvolvimento, sem senhas.

Métodos create/update usam transações Firestore para garantir unicidade do
e-mail dentro de um sandbox. A integração posterior com o servidor precisa
validar quem está autorizado a chamar essas operações.
"""
import hashlib
import re
import secrets
from datetime import datetime, timezone

SANDBOX_COLLECTION = "ct_pulse_native_sandboxes"
WORKSPACE_PATTERN = re.compile(r"^[a-f0-9]{24}$")
STUDENT_ID_PATTERN = re.compile(r"^student_[a-f0-9]{24}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BELTS = ("Branca", "Amarela", "Laranja", "Verde", "Azul", "Marrom", "Preta")
ALLOWED_FIELDS = ("id", "name", "email", "role", "active", "plan_cents", "belt", "created_at")


class StudentDataError(ValueError):
    """Dados inválidos ou operação não permitida no repositório."""


class DuplicateStudentEmail(StudentDataError):
    """E-mail já usado neste sandbox."""


class StudentNotFound(StudentDataError):
    """O estudante solicitado não existe neste sandbox."""


def _validate_text(value, label, limit):
    if not isinstance(value, str):
        raise StudentDataError(f"{label} deve ser texto.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise StudentDataError(f"{label} deve ter entre 1 e {limit} caracteres.")
    return cleaned


def _validate_email(value):
    mail = _validate_text(value, "E-mail", 254).lower()
    if not EMAIL_PATTERN.fullmatch(mail):
        raise StudentDataError("E-mail inválido.")
    return mail


def _validate_plan(value):
    if type(value) is not int or not 0 <= value <= 10_000_000:
        raise StudentDataError("Valor de plano inválido.")
    return value


def _validate_active(value):
    if type(value) not in (int, bool) or value not in (0, 1, False, True):
        raise StudentDataError("Situação ativa inválida.")
    return int(value)


def _student_id(value):
    if not isinstance(value, str) or not STUDENT_ID_PATTERN.fullmatch(value):
        raise StudentDataError("Identificador de aluno inválido.")
    return value


def _public_record(record):
    if not isinstance(record, dict) or record.get("role") != "student":
        raise StudentNotFound("Registro de aluno não encontrado.")
    # Retorno por allow-list: não expor campos de autenticação em evolução futura.
    return {key: record[key] for key in ALLOWED_FIELDS if key in record}


class NativeStudentRepository:
    """CRUD parcial nativo de alunos para sandbox Firestore isolado."""

    def __init__(self, firestore_client, workspace_id, atomic_runner=None):
        if not isinstance(workspace_id, str) or not WORKSPACE_PATTERN.fullmatch(workspace_id):
            raise StudentDataError("ID do sandbox inválido (24 dígitos hexadecimais).")
        self.client = firestore_client
        self.workspace_id = workspace_id
        self.root = firestore_client.collection(SANDBOX_COLLECTION).document(workspace_id)
        self.users = self.root.collection("users")
        self.email_index = self.root.collection("email_index")
        self.atomic_runner = atomic_runner

    def _run_atomically(self, procedure):
        if self.atomic_runner is not None:
            return self.atomic_runner(procedure)
        from google.cloud import firestore
        wrapped = firestore.transactional(procedure)
        return wrapped(self.client.transaction(max_attempts=5))

    def get_student(self, student_id):
        snapshot = self.users.document(_student_id(student_id)).get()
        if not snapshot.exists:
            raise StudentNotFound("Aluno não encontrado.")
        return _public_record(snapshot.to_dict())

    def list_students(self):
        # Apenas para demos pequenas. Não usar varredura total em produção.
        output = []
        for snapshot in self.users.stream():
            record = snapshot.to_dict()
            if isinstance(record, dict) and record.get("role") == "student":
                output.append(_public_record(record))
            if len(output) > 50:
                raise StudentDataError("O sandbox excedeu o limite demonstrativo.")
        return sorted(output, key=lambda entry: entry.get("name", "").casefold())

    def create_student(self, *, name, email, plan_cents=0):
        cleaned_name = _validate_text(name, "Nome", 150)
        cleaned_email = _validate_email(email)
        plan = _validate_plan(plan_cents)
        student_id = "student_" + secrets.token_hex(12)
        index_id = hashlib.sha256(cleaned_email.encode("utf-8")).hexdigest()
        email_ref = self.email_index.document(index_id)
        user_ref = self.users.document(student_id)
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": student_id,
            "name": cleaned_name,
            "email": cleaned_email,
            "role": "student",  # não é controlado pelo chamador
            "active": 1,
            "plan_cents": plan,
            "belt": "Branca",
            "created_at": now,
        }

        def write(tx):
            if email_ref.get(transaction=tx).exists:
                raise DuplicateStudentEmail("Este e-mail já está cadastrado no sandbox.")
            # Ambas as criações são atômicas no Firestore.
            tx.create(email_ref, {"user_id": student_id})
            tx.create(user_ref, record)
            return student_id

        return self._run_atomically(write)

    def update_student(self, student_id, **changes):
        student_id = _student_id(student_id)
        if not changes or set(changes) - {"name", "plan_cents", "active", "belt"}:
            raise StudentDataError(
                "A atualização só aceita nome, plano, situação e faixa."
            )
        update = {}
        for key, value in changes.items():
            if key == "name":
                update[key] = _validate_text(value, "Nome", 150)
            elif key == "plan_cents":
                update[key] = _validate_plan(value)
            elif key == "active":
                update[key] = _validate_active(value)
            elif key == "belt":
                if value not in BELTS:
                    raise StudentDataError("Graduação inválida.")
                update[key] = value

        ref = self.users.document(student_id)

        def write(tx):
            current = ref.get(transaction=tx)
            if not current.exists:
                raise StudentNotFound("Aluno não encontrado.")
            _public_record(current.to_dict())  # bloqueia atualizar outro perfil
            tx.update(ref, update)
            return student_id

        return self._run_atomically(write)
