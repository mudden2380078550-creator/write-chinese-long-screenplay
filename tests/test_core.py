import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from narrative_harness import project, workflow, transactions, imports, history
from narrative_harness.errors import HarnessError


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / '中文 novel'
        project.create(self.root, '灵能试炼', 'novel')

    def seed(self, balance=50, ban=False):
        entities = [
            {'id': 'hero', 'type': 'character', 'name': '林澈'},
            {'id': 'spirit', 'type': 'resource', 'name': '灵力', 'owner_id': 'hero', 'quantity': balance},
            {'id': 'step', 'type': 'ability', 'name': '影步', 'owner_id': 'hero',
             'aliases': ['暗影步', 'Shadow Step'], 'mechanics': {'range_meters': 10},
             'cost': {'resource_id': 'spirit', 'amount': 30}},
        ]
        policies = [{'id': 'no-step', 'target_ids': ['step'], 'strength': 'hard',
                     'effect': {'allow_use': False, 'allow_mention': True},
                     'author_note': '废弃影步，不能用于逃脱'}] if ban else []
        return project.configure(self.root, entities=entities, policies=policies, units=[
            {'id': 'ch1', 'title': '入塔', 'outline': '林澈寻找门锁。', 'entity_ids': ['hero', 'step']},
            {'id': 'ch2', 'title': '上楼', 'outline': '继续上楼。', 'entity_ids': ['hero']},
        ])

    def candidate(self, run, draft='林澈推开门。“有人吗？”他意识到楼上还有人。', uses=None):
        return {'run_id': run['id'], 'base_revision': run['base_revision'],
                'draft': draft, 'uses': uses or [], 'state_changes': [], 'new_facts': []}

    def finish(self, run, candidate):
        workflow.submit(self.root, run['id'], candidate)
        report = workflow.check(self.root, run['id'], semantic_review={'verdict': 'pass', 'notes': '已核对正文、能力使用和知识边界。'})
        self.assertEqual(report['status'], 'passed', report)
        return workflow.accept(self.root, run['id'])

    def test_context_includes_effect_cost_dependencies_and_policy(self):
        self.seed(ban=True)
        run = workflow.prepare(self.root, 'ch1')
        self.assertIn('range_meters', run['context'])
        self.assertIn('30', run['context'])
        self.assertIn('no-step', run['context'])
        self.assertIn('spirit', run['selected_entities'])

    def test_full_novel_flow_persists_and_accept_is_idempotent(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        candidate = self.candidate(run, '林澈发动影步，落在门前。', [{'entity_id': 'step', 'evidence': '发动影步'}])
        self.finish(run, candidate)
        workflow.accept(self.root, run['id'])
        self.assertEqual(project.load(self.root)['entities']['spirit']['quantity'], 20)
        next_run = workflow.prepare(self.root, 'ch2')
        self.assertIn('林澈发动影步', next_run['context'])
        self.assertIn('林澈发动影步', workflow.export(self.root))
        self.assertEqual(history.before(self.root, 'ch1')['entities']['spirit']['quantity'], 50)

    def test_banned_contrast_is_blocked_and_negation_is_not(self):
        self.seed(ban=True)
        run = workflow.prepare(self.root, 'ch1')
        workflow.submit(self.root, run['id'], self.candidate(run, '他明知影步已经禁用，还是发动影步逃脱。'))
        report = workflow.check(self.root, run['id'])
        self.assertEqual(report['status'], 'blocked')
        with self.assertRaises(HarnessError):
            workflow.accept(self.root, run['id'])
        run2 = workflow.prepare(self.root, 'ch1')
        self.finish(run2, self.candidate(run2, '他没有用影步，而是硬跑穿过雨幕。'))

    def test_insufficient_resource_blocks_use(self):
        self.seed(balance=20)
        run = workflow.prepare(self.root, 'ch1')
        workflow.submit(self.root, run['id'], self.candidate(run, '发动影步。', [{'entity_id': 'step', 'evidence': '发动影步'}]))
        self.assertEqual(workflow.check(self.root, run['id'])['status'], 'blocked')
        self.assertEqual(project.load(self.root)['entities']['spirit']['quantity'], 20)

    def test_unreviewed_or_modified_candidate_cannot_be_accepted(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        workflow.submit(self.root, run['id'], self.candidate(run))
        self.assertEqual(workflow.check(self.root, run['id'])['status'], 'needs_review')
        with self.assertRaises(HarnessError):
            workflow.accept(self.root, run['id'])
        workflow.check(self.root, run['id'], semantic_review={'verdict': 'pass', 'notes': '核对通过'})
        path = self.root / 'runs' / run['id'] / 'candidate.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['draft'] = '被替换的新正文。'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(HarnessError):
            workflow.accept(self.root, run['id'])

    def test_stale_run_and_hand_edit_detected(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        project.configure(self.root, entities=[{'id': 'new', 'type': 'item', 'name': '钥匙', 'quantity': 1}])
        with self.assertRaises(HarnessError):
            workflow.submit(self.root, run['id'], self.candidate(run))
        path = self.root / 'canon' / 'entities' / 'spirit.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['quantity'] = 999
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(HarnessError):
            project.load(self.root)

    def test_schema_errors_do_not_change_revision(self):
        self.seed()
        rev = project.load(self.root)['revision']
        for entity in [
            {'id': 'x', 'type': 'item', 'name': 'x', 'quantity': -1},
            {'id': '../x', 'type': 'item', 'name': 'x'},
            {'id': 'x', 'type': 'ability', 'name': 'x', 'owner_id': 'missing'},
        ]:
            with self.subTest(entity=entity), self.assertRaises(HarnessError):
                project.configure(self.root, entities=[entity])
        with self.assertRaises(HarnessError):
            project.configure(self.root, policies=[{'id': 'bad', 'target_ids': ['step'], 'strength': 'hard', 'effect': {'allow_use': 'false'}, 'author_note': 'bad'}])
        self.assertEqual(project.load(self.root)['revision'], rev)

    def test_required_context_overflow_fails(self):
        self.seed(ban=True)
        with self.assertRaises(HarnessError) as error:
            workflow.prepare(self.root, 'ch1', budget=100)
        self.assertEqual(error.exception.code, 'CONTEXT_REQUIRED_OVERFLOW')

    def test_interrupted_commit_blocks_read_and_recovers(self):
        self.seed()
        old = project.load(self.root)['revision']
        original = transactions.replace_file
        calls = 0
        def fail_second(path, text):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('simulated disk failure')
            original(path, text)
        with patch.object(transactions, 'replace_file', side_effect=fail_second):
            with self.assertRaises((OSError, HarnessError)):
                project.configure(self.root, entities=[{'id': 'key', 'type': 'item', 'name': '钥匙', 'quantity': 1}])
        with self.assertRaises(HarnessError):
            project.load(self.root)
        transactions.recover(self.root)
        self.assertEqual(project.load(self.root)['revision'], old)
        self.assertNotIn('key', project.load(self.root)['entities'])

    def test_import_retains_all_text_and_duplicate_sections(self):
        package = Path(self.tmp.name) / '资料.md'
        package.write_text('# 技能\n- 影步：可以瞬移十米，每次消耗30灵力\n# 技能\n- 火球：造成灼烧\n# 未知材料\n保留这句。', encoding='utf-8')
        staged = imports.stage(self.root, package)
        self.assertEqual(staged['id'], imports.stage(self.root, package)['id'])
        self.assertEqual(len(staged['sections']), 3)
        self.assertTrue(staged['unclassified'])
        self.assertIn('消耗30灵力', (self.root / staged['source_file']).read_text(encoding='utf-8'))
        self.assertEqual(project.load(self.root)['entities'], {})

    def test_policy_scope_does_not_rewrite_history(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        self.finish(run, self.candidate(run))
        project.configure(self.root, policies=[{'id': 'later', 'target_ids': ['step'], 'strength': 'hard', 'effect': {'allow_use': False}, 'scope': {'from_unit_id': 'ch2'}, 'author_note': '第二章起禁用'}])
        early = workflow.prepare(self.root, 'ch1', revision_mode=True)
        late = workflow.prepare(self.root, 'ch2')
        self.assertNotIn('第二章起禁用', early['context'])
        self.assertIn('第二章起禁用', late['context'])

    def test_project_move_keeps_protocol_portable(self):
        import shutil
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        other = Path(self.tmp.name) / '另一台设备'
        shutil.copytree(self.root, other)
        workflow.submit(other, run['id'], self.candidate(run))
        self.assertEqual(project.load(other)['id'], project.load(self.root)['id'])

    def test_repeated_revision_does_not_double_charge(self):
        self.seed()
        for n in range(3):
            run = workflow.prepare(self.root, 'ch1', revision_mode=n > 0)
            self.finish(run, self.candidate(run, f'林澈发动影步，落在第{n}扇门前。', [{'entity_id': 'step', 'evidence': '发动影步'}]))
        self.assertEqual(project.load(self.root)['entities']['spirit']['quantity'], 20)
        project.doctor(self.root)

    def test_revision_cannot_overwrite_later_author_entity_changes(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        self.finish(run, self.candidate(run))
        project.configure(self.root, entities=[{'id': 'extra', 'type': 'item', 'name': '新钥匙', 'quantity': 1}])
        with self.assertRaises(HarnessError):
            run = workflow.prepare(self.root, 'ch1', revision_mode=True)
            self.finish(run, self.candidate(run))
        self.assertIn('extra', project.load(self.root)['entities'])

    def test_old_chapters_can_be_revalidated_without_reapplying_state(self):
        self.seed()
        for uid in ('ch1', 'ch2'):
            run = workflow.prepare(self.root, uid)
            self.finish(run, self.candidate(run))
        project.configure(self.root, policies=[{'id': 'cost-rule', 'strength': 'hard', 'effect': {}, 'author_note': '胜利要付出代价'}])
        for uid in ('ch1', 'ch2'):
            workflow.revalidate(self.root, uid, {'verdict': 'pass', 'notes': '已结合新规则审阅已有章节'})
        self.assertIn('林澈', workflow.export(self.root))
        self.assertEqual(project.load(self.root)['entities']['spirit']['quantity'], 50)

    def test_configuration_units_do_not_override_runtime_manifest(self):
        self.seed()
        manifest = self.root / 'project.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['accepted'] = {'ch1': {'file': '../outside.md'}}
        manifest.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(HarnessError):
            project.doctor(self.root)

    def test_structured_import_applies_once_and_preserves_provenance(self):
        package = Path(self.tmp.name) / 'input.json'
        package.write_text(json.dumps({'entities': [{'id': 'hero', 'type': 'character', 'name': '林澈'}]}), encoding='utf-8')
        proposal = imports.stage(self.root, package)
        imports.apply(self.root, proposal['id'])
        rev = project.load(self.root)['revision']
        imports.apply(self.root, proposal['id'])
        self.assertEqual(project.load(self.root)['revision'], rev)
        self.assertIn('hero', project.load(self.root)['entities'])
        self.assertTrue(project.load(self.root)['entities']['hero']['provenance'])

    def test_revision_fork_keeps_parent_and_resets_to_write_before(self):
        self.seed()
        for uid in ('ch1', 'ch2'):
            run = workflow.prepare(self.root, uid)
            self.finish(run, self.candidate(run))
        original_revision = project.load(self.root)['revision']
        branch = Path(self.tmp.name) / '修订分支'
        history.fork(self.root, branch, 'ch1')
        data = project.load(branch)
        self.assertNotEqual(data['id'], project.load(self.root)['id'])
        self.assertEqual(data['metadata']['accepted'], {})
        self.assertEqual(data['entities']['spirit']['quantity'], 50)
        workflow.prepare(branch, 'ch1')
        project.doctor(branch)
        self.assertEqual(project.load(self.root)['revision'], original_revision)

    def test_cooldown_requires_story_clock(self):
        self.seed()
        entity = project.load(self.root)['entities']['step']
        entity['cooldown'] = {'duration': 60, 'unit': 'second', 'ready_at': 0}
        project.configure(self.root, entities=[entity])
        run = workflow.prepare(self.root, 'ch1')
        workflow.submit(self.root, run['id'], self.candidate(run, '发动影步。', [{'entity_id': 'step', 'evidence': '发动影步'}]))
        self.assertEqual(workflow.check(self.root, run['id'])['status'], 'blocked')

    def test_unresolved_candidate_cannot_be_marked_passed(self):
        self.seed()
        run = workflow.prepare(self.root, 'ch1')
        draft = self.candidate(run)
        draft['uncertainties'] = ['不确定主角是否知道这扇门的密码']
        workflow.submit(self.root, run['id'], draft)
        report = workflow.check(self.root, run['id'], {'verdict': 'pass', 'notes': '泛泛确认'})
        self.assertEqual(report['status'], 'blocked')

    def test_optional_entity_fields_follow_exchange_types(self):
        for field, value in [('description', 42), ('provenance', 'source'), ('extensions', [])]:
            with self.subTest(field=field), self.assertRaises(HarnessError):
                project.configure(self.root, entities=[{'id': 'x', 'type': 'item', 'name': 'x', field: value}])


if __name__ == '__main__':
    unittest.main()
