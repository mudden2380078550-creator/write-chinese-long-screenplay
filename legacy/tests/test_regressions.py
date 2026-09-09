import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from harness_io import render_harness_context
from build_context import compact_ledger
from validate_harness import match_disallowed_usage
from update_harness_state import apply_update
from create_project_from_package import parse_bullet, split_h1_sections
import test_harness
from test_harness import write, SCRIPTS


class RegressionTests(unittest.TestCase):
    def test_context_preserves_fields_aliases_and_directives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root/'harness/abilities.json', json.dumps({'items': [{'id':'a','name':'技能','aliases':['dash'],'mechanics':'瞬移','cost':3,'limits':['一次'],'quantity':2,'cooldown':8}]}))
            write(root/'harness/author-directives.json', json.dumps({'items':[{'id':'d','name':'不可复活','description':'死亡不可逆'}]}))
            result = render_harness_context(root, ['DASH'])
            for value in ('瞬移','cost','limits','quantity','cooldown','死亡不可逆'):
                self.assertIn(value, result)

    def test_required_overflow_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root/'harness/abilities.json', json.dumps({'items':[{'id':'a','status':'forbidden','author_note':'禁'*2000}]}))
            with self.assertRaises(ValueError):
                render_harness_context(root, max_chars=700)

    def test_usage_negation_contrast_alias_and_invalid_regex(self):
        item = {'terms':['影步','Shadow Step'],'allow_mention':True}
        for text, expected in [('明知影步已经禁用还是发动影步',True),('没有用影步而是硬跑',False),('发动shadow step',True)]:
            with self.subTest(text=text):
                self.assertEqual(match_disallowed_usage(text,item)[0],expected)
        with self.assertRaises(ValueError):
            match_disallowed_usage('无关', {'patterns':['[']})

    def test_invalid_updates_are_rejected_without_mutation(self):
        for items, patch in [([{'id':'a'}], {'id':'b'}),([{'id':'a'},{'id':'a'}],{}),([{'id':'a'},3],{}),([{'id':'a'}],{'generation_policy':{'allow_use':'false'}}),([{'id':'a'}],{'generation_policy':{'allow_mention':0}})]:
            doc = {'items':items}
            before = copy.deepcopy(doc)
            with self.subTest(items=items,patch=patch), self.assertRaises(ValueError):
                apply_update(doc,{'id':'a','patch':patch})
            self.assertEqual(doc,before)

    def test_ledger_excludes_future_even_query_hits(self):
        text = json.dumps({'records':[{'scene_id':'E001-S002','text':'past'},{'scene_id':'E002-S002','text':'future'}]})
        result = compact_ledger(text,['future'],2,2,1)
        self.assertIn('past',result)
        self.assertNotIn('future',result)
        self.assertIn('past', compact_ledger(text,[],2,2))

    def test_context_search_does_not_recall_future_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_harness.HarnessTests().make_project(root)
            write(root/'screenplay/scenes/E001-S099.md','# 未来\n泄漏暗号\n')
            output = root/'context.md'
            result = subprocess.run([sys.executable,'-B',str(SCRIPTS/'build_context.py'),'--project-root',str(root),'--episode','1','--scene','2','--query','泄漏暗号','--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('E001-S099.md',output.read_text(encoding='utf-8'))

    def test_import_preserves_prose_and_duplicate_sections(self):
        self.assertEqual(parse_bullet('- 影步：瞬移三米；消耗体力', 'abilities.json').get('description'),'瞬移三米；消耗体力')
        result = split_h1_sections('# 技能\n- A\n# 技能\n- B')
        self.assertIn('- A',result['技能'])
        self.assertIn('- B',result['技能'])

    def test_cli_body_and_error_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_harness.HarnessTests().make_project(root)
            draft = root/'draft.md'
            write(draft,'# 场次\n## 场次卡\n禁止发动影步\n## 正文\n没有用影步而是硬跑\n## 连续性\n发动影步是旧设定\n')
            result = subprocess.run([sys.executable,'-B',str(SCRIPTS/'validate_harness.py'),'--project-root',str(root),'--target-file',str(draft)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            write(root/'harness/abilities.json',json.dumps({'items':[{'id':'a','status':'forbidden','author_note':'禁'*3000}]}))
            result = subprocess.run([sys.executable,'-B',str(SCRIPTS/'build_context.py'),'--project-root',str(root),'--episode','1','--scene','2','--max-tokens','1000','--output',str(root/'context.md')],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertNotIn('Traceback',result.stderr)
            self.assertFalse((root/'context.md').exists())

    def test_import_archive_unknown_and_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = '# 自定义\n秘密原文\n# 主角\n- 林澈：伤势未愈\n# 成长\n- 等级：三级\n# 大纲\n先逃亡后归来\n'
            write(root/'source.md',source)
            result = subprocess.run([sys.executable,'-B',str(SCRIPTS/'create_project_from_package.py'),'--package',str(root/'source.md'),'--project-root',str(root/'project'),'--title','测试'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('自定义',result.stdout)
            self.assertEqual((root/'project/imports/source-package.md').read_text(encoding='utf-8'),source)
            self.assertIn('林澈',(root/'project/harness/protagonist.json').read_text(encoding='utf-8'))
            self.assertIn('三级',(root/'project/harness/progression.json').read_text(encoding='utf-8'))
            self.assertIn('先逃亡后归来',(root/'project/outline/master-outline.md').read_text(encoding='utf-8'))
