"""Deterministic acceptance demonstration, not a model quality evaluation."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from narrative_harness import project, imports, workflow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    project.create(root, '灵能试炼（Harness验证样本）')
    source = Path(__file__).resolve().parents[1] / 'examples/package.json'
    proposal = imports.stage(root, source)
    imports.apply(root, proposal['id'])
    run = workflow.prepare(root, 'ch1')
    workflow.submit(root, run['id'], {'run_id': run['id'], 'base_revision': run['base_revision'],
        'draft': '林澈发动影步，跨过断开的石桥。\n\n门框上有一道歪斜的刻痕。他伸手比了比，指尖停在最后一笔。\n\n“是你留下的吗？”\n\n门后没有回答。',
        'uses': [{'entity_id': 'step', 'evidence': '发动影步'}], 'state_changes': [], 'new_facts': []})
    workflow.check(root, run['id'], {'verdict': 'pass', 'notes': '固定测试样本：第一章政策允许影步，使用一次从50扣30；刻痕不确认为姐姐行踪。'})
    workflow.accept(root, run['id'])
    next_run = workflow.prepare(root, 'ch2')
    result = project.doctor(root)
    result.update(spirit=project.load(root)['entities']['spirit']['quantity'], next_run=next_run['id'],
                  next_chapter_has_ban='第二章起废弃影步' in next_run['context'])
    workflow.export(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
