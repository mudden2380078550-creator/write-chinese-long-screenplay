# Chinese Long-Form Screenwriting Skill v2

[中文说明](README.md)

A Codex skill for writing Chinese-language feature films and episodic screenplays. The streamlined version has only two author-facing inputs: background setting and character setting, including biographies. Story architecture, scene causality, continuity, and dialogue checks are handled internally.

## Two author-facing blocks

### 1. Background setting

Record the time, place, institutions, historical consequences, world rules, resources, limits, costs, knowledge differences, and fixed facts that change character choices or create visible consequences.

File: `background/story-background.md`

### 2. Character setting

Record each character's biography, objective, need, false belief, defense strategy, resources, limits, secrets, knowledge boundary, relationship exchanges, pressure behavior, speech habits, and final choice.

Files: `bible/characters/*.md`

The feature/series bible, structure map, sequences, scene cards, ledger, and reports remain available as internal working artifacts. They are not additional author-facing theory blocks.

## Chinese AI-style and calibration

The current version uses only the 24 Chinese problem categories publicly listed by [Humanizer-zh](https://github.com/op7418/Humanizer-zh), rephrased as a screenplay review checklist. It does not import that project's rewrite prompts, detector, score, voice templates, or code. Automated checks only flag high-confidence signals; detector scores are not a writing target.

The most useful feedback is a rewrite pair, not “make it natural”:

```text
Original:
Why it feels unnatural: too complete, too explanatory, wrong for the character, or wrong for the relationship?
Rewrite:
Effect to preserve:
```

Put 5–20 pairs in the “real Chinese samples” section of `style/screenplay-style.md`. They calibrate the current project but do not permanently train the base model; permanent changes require a separate dataset and fine-tuning process. Use samples for syntax, rhythm, and character distinction, not for copying copyrighted passages.

## Internal writing engine

Unified feature engine:

```text
thematic proposition → protagonist desire → inciting disruption
→ progressive complications → point of no return → crisis choice
→ climactic action → ending value and aftermath
```

Scene engine:

```text
source → viewpoint/objective → conflict/tactic → expected result
→ actual result → result gap → turn → value change → next pressure
```

Author theories remain internal diagnostic material. Users do not need to select adapters, fill a fifteen-beat sheet, or place scenes by percentage. The core judgment is always character choice, resistance, cost, and change under setting constraints.

Chinese pages receive a local de-templating review for exposition, abstract psychology, identical voices, overly polished syntax, and slogan-like endings. Unflagged lines are not rewritten merely to create variation. See `references/natural-chinese.md`.

## Requirements and installation

- A Codex environment with `SKILL.md` support
- Python 3.10+
- Git when installing by clone

The scripts use only the Python standard library.

Windows PowerShell:

```powershell
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git `
  "$HOME\.codex\skills\write-chinese-long-screenplay"
```

macOS / Linux:

```bash
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git \
  "$HOME/.codex/skills/write-chinese-long-screenplay"
```

## Initialize a v2 project

```powershell
python "<skill-dir>\scripts\init_project.py" `
  --project-root "D:\screenplays\my-feature" `
  --title "Working Title" `
  --format feature
```

After initialization, fill only the background and character blocks. Author-theory adapters remain a compatibility layer and are disabled by default.

Every project declares:

```yaml
schema_version: 2
story_engine: causal-value
structure_adapters: []
```

## Migrate v1

Preview first:

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --report "<project-root>\reviews\v2-migration.md"
```

Apply confirmed structural changes:

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --apply
```

Changed files are backed up under the project's `backups/` directory, and the continuity ledger is upgraded to schema v2. The migration does not invent motivation, story values, conflict, or result gaps; unresolved creative fields remain strict-validation blockers.

Exit code `0` means the applied project passes strict validation. Exit code `1` means the report or deterministic migration completed but blockers remain.

## Context and review

| Profile | Default budget |
| --- | ---: |
| `scene-light` | about 4,000 tokens |
| `scene` | about 7,000 tokens |
| `scene-complex` | about 12,000 tokens |
| `batch` | about 16,000 tokens |
| `sequence` | about 4,200 tokens |
| `dialogue-review` | about 3,200 tokens |
| `structure-review` | about 6,000 tokens |
| `full-review` | about 8,000 tokens |

`review` remains an alias for `full-review`.

```powershell
python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene 18 `
  --profile scene `
  --query "character location clue rule" `
  --source-file "bible/characters/char-id.md" `
  --output "<temp-dir>\scene-context.md"

python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene-from 18 `
  --scene-to 23 `
  --profile batch `
  --query "batch characters locations clues rules sequence objective" `
  --output "<temp-dir>\S018-S023-batch-context.md"

python "<skill-dir>\scripts\self_review.py" `
  --project-root "<project-root>" `
  --focus dialogue `
  --strict `
  --output "<project-root>\reviews\dialogue-review.md"
```

`--focus` accepts `scene`, `dialogue`, `structure`, `continuity`, or `full`.

Use `scene-light` for transitions and low-context scenes, `scene` as the standard drafting profile, and `scene-complex` for ensemble scenes, major reveals, and climaxes. `batch` builds shared context for 1–8 consecutive scenes only. After each scene, update the ledger and build the next scene's local context. At roughly 30-scene checkpoints, validate first and then review scene causality, dialogue, continuity, and structure in layers instead of loading every completed scene indiscriminately.

Context generation refuses to overwrite an existing output by default. Add `--force` only when intentionally replacing a disposable context package.

## Validate, compile, and test

```powershell
python "<skill-dir>\scripts\validate_project.py" `
  --project-root "<project-root>" `
  --strict

python "<skill-dir>\scripts\compile_screenplay.py" `
  --project-root "<project-root>" `
  --output "<project-root>\exports\screenplay.md"

python -m unittest discover -s tests -v
```

Compilation runs strict validation again and refuses to export a project with schema, source, or required scene-field errors.

Deterministic checks cannot replace editorial judgment about motivation, subtext, emotional effect, or climax quality.

## Copyright and method sources

The conceptual mapping is informed by Syd Field's feature-screenplay methods, Robert McKee's story and dialogue methods, and Blake Snyder's feature-screenwriting methods. This repository contains original mappings, workflows, templates, and validation code; it does not distribute the books, extended quotations, or chapter summaries that substitute for the source works.

## License

Copyright © 2026 kobayashikayoubi.

Licensed under [GNU General Public License v3.0 only](LICENSE).
