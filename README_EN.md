# Narrative Harness 0.4.0

A local, model-independent state and acceptance workflow for long-form Chinese fiction and screenplays. The host AI writes and reviews; the harness persists outlines, entities, author policies, history and accepted prose. Tool source, installed skill and book workspaces remain separate.

Requires Python 3.10+. No third-party runtime dependencies. Run `python scripts/harness.py --help`, or install with `python -m pip install .` and use `harness`.

Download [v0.4.0](https://github.com/mudden2380078550-creator/write-chinese-long-screenplay/releases/tag/v0.4.0), or clone `main`, which has carried this layout since v0.4.0:

```text
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git narrative-harness
cd narrative-harness
```

The previous layout is retained inside the repository as `legacy/`; historical tags and releases are unchanged. Do not copy the entire new repository into a skills directory; use the installer below. The old root-level dsh plugin layout is not the v0.4.0 entry point.

The lifecycle is `project new → import stage/apply → unit prepare → submit → check → accept → export`. Natural-language source extraction is performed by the host into a reviewed proposal; the source archive and unresolved sections are retained. The program does not call a model API.

Author policies are separate from story entities. Required context never silently truncates. Declared ability costs are applied once. Acceptance checks revisions, candidate hashes and review coverage, and commits prose and state using a recoverable journal. Repeated acceptance is idempotent. Old chapters can be revalidated without applying costs again; `revision fork` creates an independent rewrite workspace.

Install the self-contained Codex adapter with `python scripts/install_skill.py --destination <skills>/write-chinese-long-screenplay --backup-root <backups>`. Existing skill files are backed up first. Legacy v2 scripts are retained, while v3 projects use the unified launcher.

Then ask the host to use `write-chinese-long-screenplay`, create a project outside the tool directory, and structure your source package into characters, abilities, author policies and an outline. The host fills proposals; unresolved decisions still require review. Back up books before upgrades and use `project migrate --help` for copy-only v2 migration. Internal development 0.3.0 projects retain their old tool/version lock; do not hand-edit locks to bypass compatibility checks. Synchronize each book separately from the tool and avoid concurrent cross-device writers.

This release continues GPL-3.0-only; see [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and [CHANGELOG.md](CHANGELOG.md).

Semantic review is an explicit host/author attestation, not an automatic guarantee. The lock protects one local host, not distributed writers. Windows verification has been run locally; the included Windows/Linux/macOS CI matrix must execute before claiming cross-platform validation. Legacy migration preserves source files and labels unknown history; legacy state requires review before further drafting.

Run `python -B -m unittest discover -s tests -v` and `python -B -m unittest discover -s legacy/tests -v`. See [the Chinese guide](README.md), [protocol examples](integrations/write-chinese-long-screenplay/references/harness-workflow.md), and [provenance notice](NOTICE.md).
