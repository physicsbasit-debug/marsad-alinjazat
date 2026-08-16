import os
import unittest
from pathlib import Path
from unittest.mock import patch

from server.runtime_platform import persistent_configured, persistent_default, public_url_default, railway_volume_root


class RuntimePlatformTests(unittest.TestCase):
    def test_railway_volume_becomes_default_persistent_root(self):
        with patch.dict(
            os.environ,
            {
                "RAILWAY_VOLUME_MOUNT_PATH": "/app/persist",
                "APP_DATA_DIR": "",
                "APP_PUBLIC_URL": "",
                "RAILWAY_PUBLIC_DOMAIN": "marsad-production.up.railway.app",
            },
            clear=False,
        ):
            self.assertEqual(railway_volume_root(), Path("/app/persist"))
            self.assertEqual(persistent_default("data", Path("/fallback")), Path("/app/persist/data"))
            self.assertTrue(persistent_configured("APP_DATA_DIR"))
            self.assertEqual(public_url_default(), "https://marsad-production.up.railway.app")

    def test_storage_mode_normalizes_legacy_drive_alias(self):
        from server.runtime_platform import storage_mode
        with patch.dict(os.environ, {"STORAGE_MODE": "drive"}, clear=False):
            self.assertEqual(storage_mode(), "google_drive")
        with patch.dict(os.environ, {"STORAGE_MODE": "google_drive"}, clear=False):
            self.assertEqual(storage_mode(), "google_drive")

    def test_explicit_values_override_platform_defaults(self):
        with patch.dict(
            os.environ,
            {
                "RAILWAY_VOLUME_MOUNT_PATH": "/app/persist",
                "APP_DATA_DIR": "/custom/data",
                "APP_PUBLIC_URL": "https://marsad.example.edu/",
                "RAILWAY_PUBLIC_DOMAIN": "ignored.up.railway.app",
            },
            clear=False,
        ):
            self.assertTrue(persistent_configured("APP_DATA_DIR"))
            self.assertEqual(public_url_default(), "https://marsad.example.edu")


if __name__ == "__main__":
    unittest.main()
