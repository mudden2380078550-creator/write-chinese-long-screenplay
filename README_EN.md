# Chinese Long-Form Screenwriting Skill

[中文说明](README.md)

A Codex skill for writing long-form Chinese-language feature films and episodic screenplays. It turns character biographies, story background, worldbuilding, themes, and plot material into a maintainable Markdown screenplay project, with workflows for drafting scenes, tracking continuity, self-review, validation, and compilation.

## Key capabilities

- **Feature-film workflow**: Move from characters, background, and world rules through synopsis, treatment, sequence outline, scene outline, and screenplay pages.
- **Multiple long-form formats**: Support feature films, episodic series, short-form drama series, and animation.
- **Character-driven writing**: Convert exposition into immediate pressure, character strategy, visible action, playable dialogue, and audiovisual consequences.
- **Source traceability**: Record the character, background, world, and outline files actually used by each scene.
- **Continuity ledger**: Track character knowledge, relationships, objects, clues, audience evidence, and unresolved questions separately.
- **Bounded context**: Build compact scene, sequence, or review context instead of loading the entire project.
- **Two-layer review**: Use deterministic scripts for structural checks and a model or editor for causality, character, audience comprehension, cinematic quality, and pacing.
- **Safe writes**: Refuse to overwrite existing scenes by default and provide `--dry-run` previews.
- **Validation and compilation**: Check project structure, scene numbering, and references before compiling the screenplay in order.

## Scope and limitations

This repository is not a standalone language model or a one-click film production application. Writing quality still depends on the selected model, the source material, and editorial judgment.

The scripts focus on deterministic issues such as structure, numbering, paths, missing fields, and checkable continuity. They cannot replace semantic judgment about character arcs, subtext, emotional truth, or artistic quality. Final Draft, PDF, and production-format exports are not currently included.

## Supported project types

| `format` | Use case | Scene naming |
| --- | --- | --- |
| `feature` | Feature film | `S001.md` |
| `series` | Episodic series | `E001-S001.md` |
| `short-drama` | Short-form drama series | `E001-S001.md` |
| `animation` | Animated series | `E001-S001.md` |

## Requirements

- A Codex environment with `SKILL.md` support
- Python 3.10 or later
- Git when installing by cloning the repository

The bundled scripts use only the Python standard library.

## Installation

### Windows PowerShell

```powershell
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git `
  "$HOME\.codex\skills\write-chinese-long-screenplay"
```

### macOS / Linux

```bash
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git \
  "$HOME/.codex/skills/write-chinese-long-screenplay"
```

Start a new Codex task after installation. If the skill does not appear in the available skill list, restart Codex.

## Quick start

Ask Codex:

```text
Use $write-chinese-long-screenplay to turn these character biographies,
story background, and world rules into a 100-minute Chinese mystery feature.
Create the synopsis, sequence outline, first three scenes, and a self-review.
```

Or initialize an empty feature-film project:

```powershell
python "$HOME\.codex\skills\write-chinese-long-screenplay\scripts\init_project.py" `
  --project-root "D:\screenplays\my-feature" `
  --title "Working Title" `
  --format feature
```

Initialization refuses to overwrite a non-empty directory.

## Recommended workflow

1. Establish character biographies, story background, and world rules.
2. Define the theme, central conflict, ending direction, and locked constraints.
3. Create the synopsis and treatment.
4. Break the story into acts, sequences, episodes, and scene outlines.
5. Build bounded context for the target scene.
6. Draft and review the scene.
7. Update the continuity ledger.
8. Run self-review, structural validation, and compilation.
9. Revise from the root-cause scene and regression-check affected scenes.

A character may only act on information they possess at that point in the story. Author truth, character knowledge, and audience evidence should remain separate.

## Common commands

The examples below use `<skill-dir>` for this repository or its installation directory and `<project-root>` for the screenplay project.

### Build scene context

```powershell
python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene 18 `
  --profile scene `
  --query "character, location, clue, or rule" `
  --source-file "bible/characters/char-id.md" `
  --source-file "background/story-background.md" `
  --output "<temp-dir>\scene-context.md"
```

Default context budgets are approximately:

- `scene`: 3,200 tokens
- `sequence`: 5,000 tokens
- `review`: 8,000 tokens

Use `--max-tokens` to override the budget. New-scene drafting does not load future screenplay scenes by default.

### Run self-review

```powershell
python "<skill-dir>\scripts\self_review.py" `
  --project-root "<project-root>" `
  --strict `
  --compact `
  --output "<project-root>\reviews\self-review.md"
```

`--compact` omits repeated static review worksheets to reduce output size and token use.

### Validate and compile

```powershell
python "<skill-dir>\scripts\validate_project.py" `
  --project-root "<project-root>" `
  --strict

python "<skill-dir>\scripts\compile_screenplay.py" `
  --project-root "<project-root>" `
  --output "<project-root>\exports\screenplay.md"
```

## Repository structure

```text
write-chinese-long-screenplay/
├── SKILL.md                 # Core routing and workflow
├── agents/openai.yaml       # Codex interface metadata
├── assets/                  # Feature and episodic project templates
├── references/              # Writing and review guidance loaded on demand
└── scripts/                 # Initialization, context, writing, ledger, review, and build tools
```

`SKILL.md` contains only the core workflow. Detailed guidance lives in `references/` and should be loaded only when relevant; do not load every reference file for each writing task.

## Reducing token use

- Use the `scene` profile for individual scene drafting.
- Pass only source files that the scene actually depends on.
- Use a focused `--query` for characters, locations, clues, and rules.
- Do not enable `--include-next-scene` when drafting a new scene.
- Use `--compact` for routine reviews and expand the worksheet only when necessary.
- Run deterministic checks before asking the model to perform semantic review.

## License

Copyright © 2026 kobayashikayoubi.

This project is licensed under the [GNU General Public License v3.0 only](LICENSE). You may use, modify, and redistribute it, provided that distributed modifications and derivative works comply with GPL-3.0 source-availability, notice-preservation, and compatible-licensing requirements.
