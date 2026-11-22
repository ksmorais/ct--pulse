import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import firestore_persistence_check as probe


class FakeDoc:
    def __init__(self, ref):
        self.ref = ref
        self.exists = ref.data is not None

    def to_dict(self):
        return dict(self.ref.data) if self.ref.data is not None else None


class FakeRef:
    def __init__(self):
        self.data = None

    def create(self, data):
        if self.data is not None:
            raise RuntimeError("Já existe.")
        self.data = dict(data)

    def get(self):
        return FakeDoc(self)

    def delete(self):
        self.data = None


class FakeClient:
    def __init__(self):
        self.refs = {}

    def collection(self, name):
        if name != probe.COLLECTION:
            raise AssertionError("Coleção incorreta.")
        return self

    def document(self, name):
        return self.refs.setdefault(name, FakeRef())


class TestFirestorePersistenceCheck(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.patch = patch.object(probe, "get_firestore_client", return_value=self.client)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_write_read_delete_lifecycle(self):
        output = io.StringIO()
        with redirect_stdout(output):
            probe.write_probe()
        doc_id = output.getvalue().strip().split()[-1]
        self.assertRegex(doc_id, r"^[a-f0-9]{24}$")
        with redirect_stdout(io.StringIO()) as result:
            probe.read_probe(doc_id)
        self.assertIn("confirmada", result.getvalue())
        with redirect_stdout(io.StringIO()):
            probe.delete_probe(doc_id)
        self.assertIsNone(self.client.refs[doc_id].data)

    def test_refuses_unknown_document_id(self):
        with self.assertRaises(ValueError):
            probe.reference("../outro-documento")
        with self.assertRaises(ValueError):
            probe.reference("x" * 24)

    def test_refuses_delete_for_non_diagnostic_record(self):
        doc_id = "1" * 24
        self.client.document(doc_id).data = {"kind": "outro"}
        with self.assertRaises(RuntimeError):
            probe.delete_probe(doc_id)
        self.assertEqual(self.client.refs[doc_id].data["kind"], "outro")

    def test_missing_document_is_not_confirmed(self):
        with self.assertRaises(RuntimeError):
            probe.read_probe("0" * 24)


if __name__ == "__main__":
    unittest.main()
