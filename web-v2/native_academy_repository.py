"""Repositório Firestore para professores, turmas e inscrições fictícias.

Somente namespace CT Pulse sandbox; não cria contas reais de acesso.
Transações do Firestore protegem inscrições concorrentes e limites de vagas.
"""
import hashlib
import re
import secrets
from datetime import datetime, timezone
from native_student_repository import (
    NativeStudentRepository, StudentDataError, StudentNotFound,
    DuplicateStudentEmail, _validate_text, _validate_email,
    _student_id,
)

TEACHER_ID = re.compile(r"^teacher_[a-f0-9]{24}$")
CLASS_ID = re.compile(r"^class_[a-f0-9]{24}$")
CLOCK = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


class AcademyDataError(StudentDataError):
    pass


class AcademyNotFound(AcademyDataError):
    pass


class NoVacancy(AcademyDataError):
    pass


def _validate_id(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise AcademyDataError("Identificador de registro inválido.")
    return value


def _days(value):
    if (not isinstance(value, list) or len(value) not in range(1, 8)
        or any(type(d) is not int or d not in range(7) for d in value)
        or len(set(value)) != len(value)):
        raise AcademyDataError("Informe dias da semana distintos, de 0 (domingo) a 6 (sábado).")
    return sorted(value)


def _capacity(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise AcademyDataError("Capacidade de turma inválida (1 a 100).")
    return value


def _time(value):
    if not isinstance(value, str) or not CLOCK.fullmatch(value):
        raise AcademyDataError("Horário inválido (HH:MM).")
    return value


def _require_role(snapshot, role):
    record = snapshot.to_dict() if snapshot.exists else None
    if not isinstance(record, dict) or record.get("role") != role:
        raise AcademyNotFound("Registro não encontrado.")
    return record


class NativeAcademyRepository(NativeStudentRepository):
    def __init__(self, firestore_client, workspace_id, atomic_runner=None):
        super().__init__(firestore_client, workspace_id, atomic_runner=atomic_runner)
        self.classes = self.root.collection("classes")
        self.enrollments = self.root.collection("enrollments")

    def list_teachers(self):
        out = []
        for record in self.users.stream():
            data = record.to_dict()
            if isinstance(data, dict) and data.get("role") == "teacher":
                out.append({k: data[k] for k in ("id","name","email","role","active","created_at") if k in data})
            if len(out) > 30:
                raise AcademyDataError("Limite de professores de demonstração atingido.")
        return sorted(out, key=lambda t: t["name"].casefold())

    def create_teacher(self, *, name, email):
        name = _validate_text(name, "Nome", 150)
        email = _validate_email(email)
        teacher_id = "teacher_" + secrets.token_hex(12)
        index_id = hashlib.sha256(email.encode("utf-8")).hexdigest()
        email_ref = self.email_index.document(index_id)
        teacher_ref = self.users.document(teacher_id)
        data = {"id":teacher_id, "name":name, "email":email,
                "role":"teacher", "active":1,
                "created_at": datetime.now(timezone.utc).isoformat()}

        def write(tx):
            if email_ref.get(transaction=tx).exists:
                raise DuplicateStudentEmail("Este e-mail já está cadastrado no laboratório.")
            tx.create(email_ref, {"user_id":teacher_id})
            tx.create(teacher_ref, data)
            return teacher_id

        return self._run_atomically(write)

    def list_classes(self):
        out = []
        for doc in self.classes.stream():
            data = doc.to_dict()
            if isinstance(data, dict):
                out.append({k:data[k] for k in
                    ("id","name","teacher_id","days","time","capacity",
                     "enrolled_count","active","created_at") if k in data})
            if len(out) > 50:
                raise AcademyDataError("Limite de turmas de demonstração atingido.")
        return sorted(out, key=lambda c: c["name"].casefold())

    def create_class(self, *, name, teacher_id, days, time, capacity):
        name = _validate_text(name, "Nome", 150)
        teacher_id = _validate_id(teacher_id, TEACHER_ID)
        days = _days(days)
        time = _time(time)
        capacity = _capacity(capacity)
        class_id = "class_" + secrets.token_hex(12)
        teacher_ref = self.users.document(teacher_id)
        ref = self.classes.document(class_id)
        data = {"id":class_id, "name":name, "teacher_id":teacher_id,
                "days":days, "time":time, "capacity":capacity,
                "enrolled_count":0, "active":1,
                "created_at": datetime.now(timezone.utc).isoformat()}

        def write(tx):
            teacher = _require_role(teacher_ref.get(transaction=tx), "teacher")
            if teacher.get("active") != 1:
                raise AcademyDataError("Professor inativo.")
            tx.create(ref, data)
            return class_id

        return self._run_atomically(write)

    def update_class(self, class_id, *, name=None, days=None,
                     time=None, capacity=None, active=None):
        class_id = _validate_id(class_id, CLASS_ID)
        change = {}
        if name is not None: change["name"] = _validate_text(name, "Nome", 150)
        if days is not None: change["days"] = _days(days)
        if time is not None: change["time"] = _time(time)
        if capacity is not None: change["capacity"] = _capacity(capacity)
        if active is not None:
            if type(active) not in (int, bool) or active not in (0, 1):
                raise AcademyDataError("Situação inválida.")
            change["active"] = int(active)
        if not change:
            raise AcademyDataError("Nenhuma alteração enviada.")
        ref = self.classes.document(class_id)

        def write(tx):
            snapshot = ref.get(transaction=tx)
            if not snapshot.exists: raise AcademyNotFound("Turma não encontrada.")
            record = snapshot.to_dict()
            if change.get("capacity", record["capacity"]) < record["enrolled_count"]:
                raise NoVacancy("Capacidade menor que o número de inscritos.")
            tx.update(ref, change)
            return class_id
        return self._run_atomically(write)

    def list_enrollments(self):
        out = []
        for doc in self.enrollments.stream():
            data = doc.to_dict()
            if isinstance(data, dict):
                out.append({k:data[k] for k in ("student_id","class_id","created_at") if k in data})
            if len(out) > 150:
                raise AcademyDataError("Limite de inscrições de demonstração atingido.")
        return sorted(out, key=lambda row: (row["class_id"],row["student_id"]))

    def set_enrollment(self, *, student_id, class_id, active):
        student_id = _student_id(student_id)
        class_id = _validate_id(class_id, CLASS_ID)
        if type(active) not in (int, bool) or active not in (0, 1):
            raise AcademyDataError("Situação de inscrição inválida.")
        active = bool(active)
        class_ref = self.classes.document(class_id)
        student_ref = self.users.document(student_id)
        enrollment_id = hashlib.sha256(f"{student_id}|{class_id}".encode()).hexdigest()
        enroll_ref = self.enrollments.document(enrollment_id)

        def write(tx):
            # Todas as leituras ocorrem antes das escritas na transação.
            course_snapshot = class_ref.get(transaction=tx)
            student_snapshot = student_ref.get(transaction=tx)
            current = enroll_ref.get(transaction=tx)
            if not course_snapshot.exists:
                raise AcademyNotFound("Turma não encontrada.")
            course = course_snapshot.to_dict()
            student = _require_role(student_snapshot, "student")
            count = course.get("enrolled_count", 0)
            if type(count) is not int or count < 0:
                raise AcademyDataError("Contagem de inscritos inválida.")
            if active:
                if current.exists: return False
                if course.get("active") != 1 or student.get("active") != 1:
                    raise AcademyDataError("Aluno ou turma inativo.")
                if count >= course["capacity"]:
                    raise NoVacancy("Turma sem vagas disponíveis.")
                tx.create(enroll_ref, {
                    "student_id":student_id, "class_id":class_id,
                    "created_at":datetime.now(timezone.utc).isoformat()})
                tx.update(class_ref, {"enrolled_count":count+1})
            else:
                if not current.exists: return False
                if count == 0:
                    raise AcademyDataError("Contagem de inscritos inconsistente.")
                tx.delete(enroll_ref)
                tx.update(class_ref, {"enrolled_count":count-1})
            return True

        return self._run_atomically(write)
