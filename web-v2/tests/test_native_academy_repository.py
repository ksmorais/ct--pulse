"""Testes locais e sem rede do laboratório professores/turmas/inscrições."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_native_student_repository import FakeClient
from native_academy_repository import (
    NativeAcademyRepository, AcademyDataError, AcademyNotFound, NoVacancy
)
from native_student_repository import DuplicateStudentEmail


class AcademyClient(FakeClient):
    def atomic(self, operation):
        queue = []
        class Tx:
            def create(self, ref, record):
                queue.append(("create", ref, record))
            def update(self, ref, record):
                queue.append(("update", ref, record))
            def delete(self, ref):
                queue.append(("delete", ref, None))
        result = operation(Tx())
        for method, ref, data in queue:
            if method == "delete":
                ref.store.pop(ref.path, None)
            else:
                getattr(ref, method)(data)
        return result


class AcademyRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.client = AcademyClient()
        self.workspace = "a" * 24
        self.repo = NativeAcademyRepository(
            self.client, self.workspace, atomic_runner=self.client.atomic
        )
        self.teacher = self.repo.create_teacher(
            name="Instrutor Exemplo", email="professor@example.test")
        self.student1 = self.repo.create_student(
            name="Aluno Um", email="aluno1@example.test")
        self.student2 = self.repo.create_student(
            name="Aluno Dois", email="aluno2@example.test")
        self.course = self.repo.create_class(
            name="Turma de Teste", teacher_id=self.teacher,
            days=[1,3,5], time="18:30", capacity=1)

    def test_teacher_and_class_documents(self):
        teachers = self.repo.list_teachers()
        courses = self.repo.list_classes()
        self.assertEqual(len(teachers), 1)
        self.assertEqual(teachers[0]["role"], "teacher")
        self.assertEqual(courses[0]["teacher_id"], self.teacher)
        self.assertEqual(courses[0]["enrolled_count"], 0)
        self.assertFalse(any("password" in key for record in self.client.store.values()
                             for key in record))
        self.assertTrue(all(key.startswith("ct_pulse_native_sandboxes/" + self.workspace + "/")
                            for key in self.client.store))

    def test_duplicate_email_across_student_and_teacher(self):
        with self.assertRaises(DuplicateStudentEmail):
            self.repo.create_teacher(name="Outro", email="ALUNO1@example.test")
        with self.assertRaises(DuplicateStudentEmail):
            self.repo.create_student(name="Outro", email="PROFESSOR@example.test")

    def test_only_teacher_may_own_class(self):
        with self.assertRaises(AcademyDataError):
            self.repo.create_class(name="Falha",teacher_id=self.student1,
                                   days=[2],time="19:00",capacity=10)
        with self.assertRaises(AcademyNotFound):
            self.repo.create_class(name="Falha",teacher_id="teacher_"+"f"*24,
                                   days=[2],time="19:00",capacity=10)

    def test_enrollment_capacity_and_idempotency(self):
        self.assertTrue(self.repo.set_enrollment(
            student_id=self.student1,class_id=self.course,active=1))
        self.assertFalse(self.repo.set_enrollment(
            student_id=self.student1,class_id=self.course,active=1))
        with self.assertRaises(NoVacancy):
            self.repo.set_enrollment(
                student_id=self.student2,class_id=self.course,active=1)
        self.assertEqual(len(self.repo.list_enrollments()), 1)
        self.assertEqual(self.repo.list_classes()[0]["enrolled_count"], 1)
        self.assertTrue(self.repo.set_enrollment(
            student_id=self.student1,class_id=self.course,active=0))
        self.assertFalse(self.repo.set_enrollment(
            student_id=self.student1,class_id=self.course,active=0))
        self.assertTrue(self.repo.set_enrollment(
            student_id=self.student2,class_id=self.course,active=1))
        self.assertEqual(self.repo.list_classes()[0]["enrolled_count"], 1)
        self.assertEqual(self.repo.list_enrollments()[0]["student_id"],self.student2)

    def test_student_must_be_active(self):
        self.repo.update_student(self.student1,active=0)
        with self.assertRaises(AcademyDataError):
            self.repo.set_enrollment(
                student_id=self.student1,class_id=self.course,active=True)
        self.assertEqual(self.repo.list_enrollments(),[])

    def test_capacity_cannot_be_less_than_enrollment(self):
        self.repo.update_class(self.course,capacity=2)
        self.repo.set_enrollment(student_id=self.student1,class_id=self.course,active=1)
        self.repo.set_enrollment(student_id=self.student2,class_id=self.course,active=1)
        with self.assertRaises(NoVacancy):
            self.repo.update_class(self.course,capacity=1)
        self.assertEqual(self.repo.list_classes()[0]["capacity"],2)

    def test_invalid_class_inputs(self):
        for kwargs in [
            {"days":[1,1]},
            {"days":[True,2]},
            {"days":[]},
            {"time":"24:00"},
            {"capacity":True},
            {"capacity":101},
            {"teacher_id":"../../users"},
        ]:
            data=dict(name="Turma",teacher_id=self.teacher,days=[1],
                      time="09:00",capacity=12)
            data.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(AcademyDataError):
                    self.repo.create_class(**data)

    def test_class_update_and_inactive_course(self):
        self.repo.update_class(self.course,name="Outra turma", days=[2,4],
                               time="21:00",active=0)
        course = self.repo.list_classes()[0]
        self.assertEqual(course["days"],[2,4])
        self.assertEqual(course["name"],"Outra turma")
        with self.assertRaises(AcademyDataError):
            self.repo.set_enrollment(student_id=self.student1,
                                     class_id=self.course,active=True)

    def test_cannot_enroll_teacher_or_unknown_student(self):
        with self.assertRaises((AcademyDataError, ValueError)):
            self.repo.set_enrollment(student_id=self.teacher,
                                     class_id=self.course,active=1)
        with self.assertRaises(AcademyNotFound):
            self.repo.set_enrollment(student_id="student_"+"e"*24,
                                     class_id=self.course,active=1)


if __name__ == "__main__":
    unittest.main()
