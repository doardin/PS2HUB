"""Regression tests for archive preservation. No real network or 7z calls."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import create_app
from app.routes import downloads
from app.services import extractor
from app.services.aria2_client import Aria2Error


class ArchivePreservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ps2-hub-extraction-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        config = {
            'TESTING': True,
            'PS2_ROOT': str(self.root),
            'TITLES_DIR': str(self.root / 'titles'),
        }
        for key, name in (
            ('DVD_DIR', 'DVD'), ('CD_DIR', 'CD'), ('ART_DIR', 'ART'),
            ('CFG_DIR', 'CFG'), ('VMC_DIR', 'VMC'), ('DOWNLOADS_DIR', 'downloads'),
        ):
            config[key] = str(self.root / name)
        self.app = create_app(config)
        self.client = self.app.test_client()
        self.archive = self.root / 'downloads' / 'game.zip'
        self.archive.write_bytes(b'original archive')
        self.archive_bytes = self.archive.read_bytes()
        self.extracted_bytes = b'x' * (1024 * 1024 + 1)
        self.gid = '0123456789abcdef'
        self.success = Mock()
        extractor.EXTRACTION_TASKS.clear()
        self.addCleanup(extractor.EXTRACTION_TASKS.clear)
        network = patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Network must not be used by these tests'),
        )
        network.start()
        self.addCleanup(network.stop)
        output = patch('sys.stdout', new_callable=io.StringIO)
        output.start()
        self.addCleanup(output.stop)

    def fake_7z(self, command, **kwargs):
        if command[1] == 'l':
            return SimpleNamespace(stdout='Path = game.iso\nSize = 1048577\n')
        (self.archive.parent / 'game.iso').write_bytes(self.extracted_bytes)
        return SimpleNamespace(stdout='')

    def extract(self):
        extractor._extract_and_process_task(
            self.gid, str(self.archive), self.app.config['DVD_DIR'],
            self.app.config['CD_DIR'], None, self.app.app_context,
            password='test-password', on_success=self.success,
        )

    def assert_preserved_failure(self):
        self.assertEqual(self.archive.read_bytes(), self.archive_bytes)
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'error')
        self.success.assert_not_called()

    def test_wrong_password_preserves_original_at_both_7z_steps(self):
        for failing_step in ('l', 'e'):
            with self.subTest(step=failing_step):
                def fail_at_step(command, **kwargs):
                    if command[1] == failing_step:
                        raise subprocess.CalledProcessError(
                            2, command, stderr='Wrong password'
                        )
                    return self.fake_7z(command, **kwargs)
                with patch.object(extractor.subprocess, 'run', side_effect=fail_at_step):
                    self.extract()
                self.assert_preserved_failure()

    def test_missing_7z_preserves_original(self):
        with patch.object(extractor.subprocess, 'run', side_effect=FileNotFoundError('7z')):
            self.extract()
        self.assert_preserved_failure()

    def test_archive_without_image_preserves_original(self):
        output = SimpleNamespace(stdout='Path = readme.txt\nSize = 42\n')
        with patch.object(extractor.subprocess, 'run', return_value=output):
            self.extract()
        self.assert_preserved_failure()

    def test_missing_extracted_file_preserves_original(self):
        output = SimpleNamespace(stdout='Path = game.iso\nSize = 1048577\n')
        with patch.object(extractor.subprocess, 'run', return_value=output):
            self.extract()
        self.assert_preserved_failure()

    def test_invalid_image_does_not_report_success_or_delete_original(self):
        self.extracted_bytes = b'bad'
        with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
            self.extract()
        self.assert_preserved_failure()
        self.assertEqual(list((self.root / 'CD').iterdir()), [])

    def test_import_exception_preserves_original(self):
        with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
            with patch.object(extractor, 'process_iso', side_effect=OSError('Disk full')):
                self.extract()
        self.assert_preserved_failure()

    def test_result_without_existing_destination_preserves_original(self):
        for result in (None, {'path': str(self.root / 'CD' / 'missing.iso')}):
            with self.subTest(result=result):
                with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
                    with patch.object(extractor, 'process_iso', return_value=result):
                        self.extract()
                self.assert_preserved_failure()

    def test_success_imports_bytes_before_deleting_original_and_metadata(self):
        def after_import():
            self.assertEqual(
                (self.root / 'CD' / 'game.iso').read_bytes(), self.extracted_bytes
            )
            self.assertFalse(self.archive.exists())
        self.success.side_effect = after_import
        with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
            self.extract()
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'complete')
        self.assertEqual(
            (self.root / 'CD' / 'game.iso').read_bytes(), self.extracted_bytes
        )
        self.assertFalse(self.archive.exists())
        self.success.assert_called_once_with()

    def test_metadata_cleanup_error_does_not_turn_import_into_failure(self):
        self.success.side_effect = Aria2Error('RPC unavailable')
        with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
            self.extract()
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'complete')
        self.assertTrue((self.root / 'CD' / 'game.iso').is_file())
        self.success.assert_called_once_with()

    def test_archive_cleanup_error_leaves_import_complete(self):
        with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
            with patch.object(extractor.os, 'remove', side_effect=PermissionError('Read-only')):
                self.extract()
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'complete')
        self.assertTrue((self.root / 'CD' / 'game.iso').is_file())
        self.assertEqual(self.archive.read_bytes(), self.archive_bytes)
        self.success.assert_called_once_with()

    def prepare_download(self):
        self.password_file = self.root / 'passwords.json'
        self.password_file.write_text(json.dumps({self.gid: 'test-password'}))
        password_path = patch.object(downloads, '_PWD_FILE', str(self.password_file))
        password_path.start()
        self.addCleanup(password_path.stop)
        self.aria2 = Mock()
        self.aria2.get_status.return_value = {
            'status': 'complete', 'files': [{'path': str(self.archive)}],
        }
        aria2_patch = patch.object(downloads, '_get_aria2', return_value=self.aria2)
        aria2_patch.start()
        self.addCleanup(aria2_patch.stop)

    def run_worker_inline(self, task_id, filepath, dvd, cd, art, app, **kwargs):
        extractor._extract_and_process_task(
            task_id, filepath, dvd, cd, None, app.app_context, **kwargs
        )
        return task_id

    def test_download_keeps_password_and_aria2_result_until_worker_succeeds(self):
        self.prepare_download()
        with patch.object(extractor, 'start_extraction') as start:
            response = self.client.post(f'/api/downloads/{self.gid}/process')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['background'])
        self.assertEqual(start.call_args.kwargs['password'], 'test-password')
        self.assertEqual(downloads._get_password(self.gid), 'test-password')
        self.aria2.remove.assert_not_called()
        self.assertEqual(self.archive.read_bytes(), self.archive_bytes)

    def test_failed_download_worker_keeps_password_aria2_result_and_original(self):
        self.prepare_download()
        failure = subprocess.CalledProcessError(2, ['7z'], stderr='Wrong password')
        with patch.object(extractor, 'start_extraction', side_effect=self.run_worker_inline):
            with patch.object(extractor.subprocess, 'run', side_effect=failure):
                response = self.client.post(f'/api/downloads/{self.gid}/process')
        self.assertEqual(response.status_code, 200)
        self.assert_preserved_failure()
        self.assertEqual(downloads._get_password(self.gid), 'test-password')
        self.aria2.remove.assert_not_called()

    def test_successful_download_cleans_original_password_and_aria2_result(self):
        self.prepare_download()
        with patch.object(extractor, 'start_extraction', side_effect=self.run_worker_inline):
            with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
                response = self.client.post(f'/api/downloads/{self.gid}/process')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'complete')
        self.assertFalse(self.archive.exists())
        self.assertIsNone(downloads._get_password(self.gid))
        self.aria2.remove.assert_called_once_with(self.gid)
        self.assertEqual((self.root / 'CD' / 'game.iso').read_bytes(), self.extracted_bytes)

    def test_failed_aria2_cleanup_keeps_password_after_successful_import(self):
        self.prepare_download()
        self.aria2.remove.side_effect = Aria2Error('RPC unavailable')
        with patch.object(extractor, 'start_extraction', side_effect=self.run_worker_inline):
            with patch.object(extractor.subprocess, 'run', side_effect=self.fake_7z):
                self.client.post(f'/api/downloads/{self.gid}/process')
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'complete')
        self.assertEqual(downloads._get_password(self.gid), 'test-password')

    def test_download_list_does_not_duplicate_tracked_extractions(self):
        self.prepare_download()
        self.aria2.list_all.return_value = [
            {'gid': self.gid, 'status': 'complete'},
            {'gid': 'other', 'status': 'active'},
        ]
        for status in ('extracting', 'error', 'complete'):
            with self.subTest(status=status):
                extractor.EXTRACTION_TASKS[self.gid] = {'status': status}
                response = self.client.get('/api/downloads')
                self.assertEqual(
                    [item['gid'] for item in response.get_json()['downloads']], ['other']
                )
                task_response = self.client.get('/api/extractions')
                self.assertEqual(task_response.get_json()['tasks'][self.gid]['status'], status)

    def test_repeated_start_does_not_create_duplicate_workers(self):
        for status in ('waiting', 'extracting', 'processing', 'complete'):
            with self.subTest(status=status):
                extractor.EXTRACTION_TASKS[self.gid] = {'status': status}
                with patch.object(extractor.threading, 'Thread') as thread:
                    result = extractor.start_extraction(
                        self.gid, str(self.archive), self.app.config['DVD_DIR'],
                        self.app.config['CD_DIR'], None, self.app,
                    )
                self.assertEqual(result, self.gid)
                thread.assert_not_called()

    def test_failed_task_can_start_again(self):
        extractor.EXTRACTION_TASKS[self.gid] = {'status': 'error'}
        with patch.object(extractor.threading, 'Thread') as thread:
            extractor.start_extraction(
                self.gid, str(self.archive), self.app.config['DVD_DIR'],
                self.app.config['CD_DIR'], None, self.app,
            )
        thread.return_value.start.assert_called_once_with()
        self.assertEqual(extractor.EXTRACTION_TASKS[self.gid]['status'], 'waiting')

    def test_upload_preserves_original_if_background_worker_cannot_start(self):
        uploaded = self.client.post(
            '/api/uploads/init', json={'filename': 'game.zip', 'totalSize': 16}
        ).get_json()
        archive = (
            self.root / 'downloads' / 'temp_uploads'
            / f"{uploaded['uploadId']}_{uploaded['filename']}"
        )
        archive.write_bytes(self.archive_bytes)
        with patch.object(extractor.threading, 'Thread', side_effect=RuntimeError('No threads')):
            response = self.client.post(
                f"/api/uploads/{uploaded['uploadId']}/complete",
                json={'filename': uploaded['filename']},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(archive.read_bytes(), self.archive_bytes)
        self.assertEqual(
            extractor.EXTRACTION_TASKS[uploaded['uploadId']]['status'], 'error'
        )


if __name__ == '__main__':
    unittest.main()
