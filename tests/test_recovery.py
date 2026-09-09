import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from narrative_harness import project, transactions, workflow
from narrative_harness.errors import HarnessError
from narrative_harness.storage import inside, write_json


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'book'
        project.create(self.root, '恢复测试')
        project.configure(self.root, units=[{'id': 'c1', 'title': '第一章', 'outline': '开门。'}])

    def test_writer_lock_is_exclusive(self):
        with transactions.lock(self.root):
            with self.assertRaises(HarnessError) as error:
                project.configure(self.root, entities=[{'id': 'x', 'type': 'item', 'name': '钥匙'}])
        self.assertEqual(error.exception.code, 'PROJECT_BUSY')

    def test_failures_at_each_file_leave_recoverable_old_state(self):
        for fail_at in (1, 2, 3):
            with self.subTest(fail_at=fail_at):
                old = project.load(self.root)['revision']
                count = 0
                original = transactions.replace_file
                def failing(path, text):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError('simulated failure')
                    original(path, text)
                with patch.object(transactions, 'replace_file', side_effect=failing):
                    with self.assertRaises(OSError):
                        project.configure(self.root, entities=[{'id': 'x', 'type': 'item', 'name': '钥匙'}])
                transactions.recover(self.root)
                self.assertEqual(project.load(self.root)['revision'], old)
                project.doctor(self.root)

    def test_crash_after_manifest_is_completed_without_rollback(self):
        original = transactions.replace_file
        def after_write(path, text):
            original(path, text)
            if path.name == 'project.json':
                raise OSError('process stopped after manifest')
        with patch.object(transactions, 'replace_file', side_effect=after_write):
            with self.assertRaises(OSError):
                project.configure(self.root, entities=[{'id': 'x', 'type': 'item', 'name': '钥匙'}])
        self.assertEqual(transactions.recover(self.root)['status'], 'completed')
        self.assertIn('x', project.load(self.root)['entities'])

    def test_recovery_refuses_to_destroy_intervening_edit(self):
        original = transactions.replace_file
        def interrupted(path, text):
            if path.name == 'project.json':
                raise OSError('failure')
            original(path, text)
        with patch.object(transactions, 'replace_file', side_effect=interrupted):
            with self.assertRaises(OSError):
                project.configure(self.root, entities=[{'id': 'x', 'type': 'item', 'name': '钥匙'}])
        (self.root / 'canon/entities/x.json').write_text('{"author":"manual change"}', encoding='utf-8')
        with self.assertRaises(HarnessError):
            transactions.recover(self.root)
        self.assertIn('manual change', (self.root / 'canon/entities/x.json').read_text(encoding='utf-8'))

    def test_path_escape_is_rejected(self):
        for name in ('../outside', '/absolute', 'canon/../outside', 'canon\\outside'):
            with self.subTest(name=name), self.assertRaises(HarnessError):
                inside(self.root, name)

    def test_stale_explicit_configuration_is_rejected(self):
        revision = project.load(self.root)['revision']
        project.configure(self.root, entities=[{'id': 'a', 'type': 'item', 'name': 'A'}])
        with self.assertRaises(HarnessError):
            project.configure(self.root, entities=[{'id': 'b', 'type': 'item', 'name': 'B'}], expected_revision=revision)
        self.assertNotIn('b', project.load(self.root)['entities'])

    def test_forged_run_state_is_rejected_at_acceptance(self):
        run = workflow.prepare(self.root, 'c1')
        candidate = {'run_id': run['id'], 'base_revision': run['base_revision'], 'draft': '门开了。', 'uses': [], 'state_changes': [], 'new_facts': []}
        workflow.submit(self.root, run['id'], candidate)
        workflow.check(self.root, run['id'], {'verdict': 'pass', 'notes': '已审阅'})
        path = self.root / 'runs' / run['id'] / 'run.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['state_before']['entities']['invented'] = {'id': 'invented', 'name': '凭空道具', 'type': 'item'}
        write_json(path, data)
        with self.assertRaises(HarnessError):
            workflow.accept(self.root, run['id'])


if __name__ == '__main__':
    unittest.main()
