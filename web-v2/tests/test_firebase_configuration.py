import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from firebase_store import _configuration

class TestFirebaseConfiguration(unittest.TestCase):
    def test_missing_credentials_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                _configuration()

    def test_invalid_json_rejected(self):
        with patch.dict(os.environ, {
            "FIREBASE_PROJECT_ID": "ct-pulse",
            "FIREBASE_SERVICE_ACCOUNT_JSON": "{invalido"
        }, clear=True):
            with self.assertRaises(RuntimeError):
                _configuration()

    def test_wrong_project_rejected(self):
        payload = {"type": "service_account", "project_id": "outro-projeto",
                   "client_email": "example@invalid.test", "private_key": "ficticia"}
        with patch.dict(os.environ, {
            "FIREBASE_PROJECT_ID": "ct-pulse",
            "FIREBASE_SERVICE_ACCOUNT_JSON": json.dumps(payload)
        }, clear=True):
            with self.assertRaises(RuntimeError):
                _configuration()

    def test_matching_service_account_configuration(self):
        payload = {"type": "service_account", "project_id": "ct-pulse",
                   "client_email": "example@invalid.test", "private_key": "ficticia"}
        with patch.dict(os.environ, {
            "FIREBASE_PROJECT_ID": "ct-pulse",
            "FIREBASE_SERVICE_ACCOUNT_JSON": json.dumps(payload)
        }, clear=True):
            project, cred = _configuration()
            self.assertEqual(project, "ct-pulse")
            self.assertEqual(cred["project_id"], "ct-pulse")

    def test_local_application_default_credentials_config(self):
        with patch.dict(os.environ, {
            "FIREBASE_PROJECT_ID": "ct-pulse",
            "GOOGLE_APPLICATION_CREDENTIALS": "/mock/credentials.json"
        }, clear=True):
            project, cred = _configuration()
            self.assertEqual(project, "ct-pulse")
            self.assertIsNone(cred)

if __name__ == "__main__":
    unittest.main()
