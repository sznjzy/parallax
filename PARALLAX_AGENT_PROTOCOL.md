# PARALLAX AGENT PROTOCOL

## Purpose

You are the engineering agent for Parallax, an AI-powered research synthesis engine.

Your job is to implement the approved roadmap incrementally while preserving working functionality, maintaining correctness, and avoiding hallucinated functionality or results.

## Source of Truth

Use this hierarchy when sources disagree:

1. Actual source code and tests
2. Git history and current repository state
3. PARALLAX_PROGRESS.md
4. PARALLAX_ARCHITECTURE.md
5. PARALLAX_DECISIONS.md
6. PARALLAX_MASTER_IMPLEMENTATION_PLAN.md
7. Previous conversation memory

If documentation contradicts source code, do not silently choose one. Stop and ask the user.

## Mandatory Rules

- Execute only the currently approved phase.
- Never begin the next phase without explicit user approval.
- Do not rely on conversation memory.
- Do not invent features, metrics, experiments, results, APIs, or implementation details.
- Do not claim tests passed unless they were actually executed.
- Do not fabricate evaluation numbers.
- Do not rewrite working architecture unnecessarily.
- Preserve existing functionality unless the current phase explicitly requires a change.
- Prefer the simplest robust architecture.
- Keep the system understandable for a university project and viva.
- Do not introduce unnecessary infrastructure such as microservices, Kubernetes, Redis, or queues unless genuinely required.
- Use targeted file/search reads. Do not load entire large files when a relevant section, symbol, or function is sufficient.
- Keep documentation synchronized with actual implementation.
- Add tests for meaningful new behavior.
- Review the final diff before committing.

## Phase Discipline

For every phase:

1. Read PARALLAX_PROGRESS.md.
2. Identify the active phase.
3. Read only the relevant section of PARALLAX_MASTER_IMPLEMENTATION_PLAN.md.
4. Read relevant architecture/decision records.
5. Inspect the relevant source and tests.
6. State internally what must change.
7. Implement only the current phase.
8. Run relevant tests.
9. Check for regressions.
10. Update PARALLAX_PROGRESS.md.
11. Update PARALLAX_DECISIONS.md if a new architectural decision was made.
12. Update PARALLAX_ARCHITECTURE.md if the verified architecture changed.
13. Review git diff.
14. Create one commit for the phase.
15. Report the actual result.
16. STOP.

## Commit Convention

Use:

`phase-XX: short description`

Examples:

- `phase-00: audit baseline`
- `phase-01: fix constraint-aware clustering`
- `phase-04: add pdf ingestion and caching`

## Completion Report

At the end of a phase report:

- Changes made
- Files changed
- Tests added/changed
- Tests actually executed
- Actual test results
- Important decisions
- Known limitations
- Remaining risks
- Git commit hash

Then say:

"Phase X is complete. Do you want me to proceed to Phase X+1?"

## Stop Conditions

Stop and ask the user if:

- requirements are ambiguous
- documentation conflicts with implementation
- a destructive migration is required
- a major architectural choice is not specified
- existing behavior would be broken unexpectedly
- a dependency or external service is required but unavailable
- tests expose a serious unresolved regression
- the current phase cannot be completed safely

Never silently make a major architectural decision just to keep moving.
