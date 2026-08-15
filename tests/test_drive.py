import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="marsad-drive-test-db-"))

from server import drive


class MarsadDriveEventTests(unittest.TestCase):
    def test_event_upload_uses_expected_folder_hierarchy_and_metadata(self):
        path = Path(tempfile.mkstemp(suffix=".pdf")[1])
        path.write_bytes(b"test")
        init_response = Mock()
        init_response.headers = {"Location": "https://upload-session.example"}
        init_response.raise_for_status = Mock()
        upload_response = Mock()
        upload_response.raise_for_status = Mock()
        upload_response.json.return_value = {"id": "file-1", "webViewLink": "https://drive.example/file-1"}

        with patch.object(drive, "get_access_token", return_value="token"), \
             patch.object(drive, "ensure_root_folder", return_value="root"), \
             patch.object(drive, "ensure_child_folder", side_effect=["year", "events", "event-folder"]) as ensure_folder, \
             patch.object(drive.requests, "post", return_value=init_response) as post, \
             patch.object(drive.requests, "put", return_value=upload_response) as put:
            result = drive.upload_event_file(path, "report.pdf", "application/pdf", "2026/2027", 44, "أسبوع العلوم")

        self.assertEqual(result["id"], "file-1")
        self.assertEqual(
            [call.args[:2] for call in ensure_folder.call_args_list],
            [("2026/2027", "root"), ("03 - الفعاليات والتوثيق", "year"), ("فعالية 44 - أسبوع العلوم", "events")],
        )
        metadata = post.call_args.kwargs["data"].decode("utf-8")
        self.assertIn('"marsadEventId": "44"', metadata)
        self.assertIn('"parents": ["event-folder"]', metadata)
        self.assertEqual(put.call_args.args[0], "https://upload-session.example")
        path.unlink(missing_ok=True)

    def test_drive_download_and_delete_use_file_id(self):
        meta = Mock()
        meta.raise_for_status = Mock()
        meta.json.return_value = {"mimeType": "image/jpeg"}
        body = Mock()
        body.raise_for_status = Mock()
        body.content = b"image-bytes"
        deleted = Mock(status_code=204)
        deleted.raise_for_status = Mock()

        with patch.object(drive, "get_access_token", return_value="token"), \
             patch.object(drive.requests, "get", side_effect=[meta, body]) as get, \
             patch.object(drive.requests, "delete", return_value=deleted) as delete:
            content, mime = drive.download_file("drive-file-9")
            drive.delete_file("drive-file-9")

        self.assertEqual(content, b"image-bytes")
        self.assertEqual(mime, "image/jpeg")
        self.assertIn("drive-file-9", get.call_args_list[0].args[0])
        self.assertIn("drive-file-9", delete.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
