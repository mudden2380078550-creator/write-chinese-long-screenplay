# Chinese Narrative Harness Skill

This installed skill contains the v3 narrative workflow and legacy v2 screenplay scripts. Use `python scripts/harness.py --help` with Python 3.10+. The core is bundled in `scripts/_vendor/narrative_harness/`, so the installation is portable without the original source checkout.

Ask the host AI to create a book from a source package, continue a chapter, or update an author policy. The AI structures inputs and writes/reviews prose; the harness stores outlines, character/resource state, policies and accepted history in a separate book workspace.

The v3 lifecycle is prepare/submit/check/accept. Semantic review is a host/author responsibility, not a guarantee made by lexical rules. Use one accepting device at a time and run doctor after synchronization. Legacy migration preserves originals and marks unknown history.

See [SKILL.md](SKILL.md) and [the protocol](references/harness-workflow.md).
