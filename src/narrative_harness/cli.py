import argparse
import json
import sys

from . import __version__, project, workflow, imports, history, transactions, migration
from .errors import HarnessError, require
from .storage import read_json


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise HarnessError('ARGUMENT_ERROR', message)


def parser():
    p = Parser(prog='harness', description='本地长篇创作状态与接受流程。所有budget以字符计。')
    p.add_argument('--version', action='version', version=__version__)
    groups = p.add_subparsers(dest='group', required=True, parser_class=Parser)
    projects = groups.add_parser('project').add_subparsers(dest='action', required=True, parser_class=Parser)
    new = projects.add_parser('new')
    new.add_argument('--root', required=True)
    new.add_argument('--title', required=True)
    new.add_argument('--format', default='novel', choices=['novel', 'feature', 'series', 'short-drama', 'animation'])
    for action in ('configure', 'doctor', 'recover'):
        command = projects.add_parser(action)
        command.add_argument('--project', required=True)
        if action == 'configure':
            command.add_argument('--input', required=True)
    migrate = projects.add_parser('migrate')
    migrate.add_argument('--source', required=True)
    migrate.add_argument('--root', required=True)
    migrate.add_argument('--title')
    confirm = projects.add_parser('migration-confirm')
    confirm.add_argument('--project', required=True)
    confirm.add_argument('--review', required=True)
    units = groups.add_parser('unit').add_subparsers(dest='action', required=True, parser_class=Parser)
    for action in ('prepare', 'submit', 'check', 'accept', 'revalidate'):
        command = units.add_parser(action)
        command.add_argument('--project', required=True)
        if action in {'prepare', 'revalidate'}:
            command.add_argument('--unit', required=True)
        else:
            command.add_argument('--run', required=True)
        if action == 'prepare':
            command.add_argument('--budget', type=int, default=14000)
            command.add_argument('--revision', action='store_true')
        if action == 'submit':
            command.add_argument('--input', required=True)
        if action in {'check', 'revalidate'}:
            command.add_argument('--review', required=action == 'revalidate')
    importer = groups.add_parser('import').add_subparsers(dest='action', required=True, parser_class=Parser)
    for action in ('stage', 'apply'):
        command = importer.add_parser(action)
        command.add_argument('--project', required=True)
        command.add_argument('--source' if action == 'stage' else '--proposal', required=True)
    state = groups.add_parser('state').add_subparsers(dest='action', required=True, parser_class=Parser)
    show = state.add_parser('show')
    show.add_argument('--project', required=True)
    show.add_argument('--before-unit')
    revision = groups.add_parser('revision').add_subparsers(dest='action', required=True, parser_class=Parser)
    impact = revision.add_parser('impact')
    impact.add_argument('--project', required=True)
    impact.add_argument('--entity', action='append', required=True)
    fork = revision.add_parser('fork')
    fork.add_argument('--project', required=True)
    fork.add_argument('--root', required=True)
    fork.add_argument('--unit', required=True)
    export = groups.add_parser('export')
    export.add_argument('--project', required=True)
    return p


def dispatch(a):
    if a.group == 'project':
        if a.action == 'new':
            return project.create(a.root, a.title, a.format)
        if a.action == 'doctor':
            return project.doctor(a.project)
        if a.action == 'recover':
            return transactions.recover(a.project)
        if a.action == 'migrate':
            return migration.migrate(a.source, a.root, a.title)
        if a.action == 'migration-confirm':
            return migration.confirm(a.project, read_json(a.review))
        config = read_json(a.input)
        require(isinstance(config, dict) and not set(config) - {'entities', 'policies', 'units', 'expected_revision'}, '配置仅允许entities/policies/units/expected_revision')
        return project.configure(a.project, **config)
    if a.group == 'unit':
        if a.action == 'prepare':
            run = workflow.prepare(a.project, a.unit, a.budget, a.revision)
            return {key: run[key] for key in ('id', 'base_revision', 'unit_id', 'status', 'characters', 'coverage')} | {
                'context_file': f"runs/{run['id']}/context.md", 'run_file': f"runs/{run['id']}/run.json"}
        if a.action == 'submit':
            return workflow.submit(a.project, a.run, read_json(a.input))
        if a.action == 'check':
            return workflow.check(a.project, a.run, read_json(a.review) if a.review else None)
        if a.action == 'revalidate':
            return workflow.revalidate(a.project, a.unit, read_json(a.review))
        return workflow.accept(a.project, a.run)
    if a.group == 'import':
        return imports.stage(a.project, a.source) if a.action == 'stage' else imports.apply(a.project, a.proposal)
    if a.group == 'state':
        if a.before_unit:
            return history.before(a.project, a.before_unit)
        data = project.load(a.project)
        return dict(project.snapshot(data), revision=data['revision'])
    if a.group == 'revision':
        if a.action == 'fork':
            return history.fork(a.project, a.root, a.unit)
        return history.impact(a.project, a.entity)
    text = workflow.export(a.project)
    return {'file': 'exports/manuscript.md', 'characters': len(text)}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        data = dispatch(parser().parse_args(argv))
        code = 1 if isinstance(data, dict) and data.get('status') in {'blocked', 'needs_review'} else 0
        print(json.dumps({'ok': code == 0, 'code': 'OK' if code == 0 else 'REVIEW_REQUIRED', 'data': data}, ensure_ascii=False, indent=2))
        return code
    except (HarnessError, OSError, UnicodeError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'code': getattr(exc, 'code', 'IO_OR_DATA_ERROR'), 'message': str(exc)}, ensure_ascii=False))
        return getattr(exc, 'exit_code', 2)


if __name__ == '__main__':
    raise SystemExit(main())
