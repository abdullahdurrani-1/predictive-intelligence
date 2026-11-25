# Predictive Intelligence — working agreement

End-to-end aircraft-engine RUL prediction system on NASA C-MAPSS (simulated benchmark data). The owner is a student and aspiring AI/ML engineer who wants to understand and defend every decision, not just receive finished code.

## Start of every session
1. Read `docs/PROGRESS.md` for current status and open items.
2. Read `docs/PROJECT_PLAN.md` for the phase roadmap, and `docs/DECISIONS.md` before changing any earlier choice.

## How to work
- Work in numbered phases and milestones. Never jump ahead to the final model or app.
- Stop at the end of each milestone, show what was achieved and how to verify it, and wait for approval.
- Before each major step, explain its purpose, why this method was chosen, and when it should not be used. Explain maths in plain language first. Use aircraft-maintenance examples. Assume no prior knowledge of a concept.
- Be economical: no multi-agent workflows or long output unless asked.
- Investigate the root cause of errors; no workarounds that hide them.
- Inspect any existing file and explain the change before overwriting it.
- Update `docs/PROGRESS.md` at the end of each milestone and log every methodological choice in `docs/DECISIONS.md`.

## Research integrity
- Never fabricate results, metrics, figures, or citations. Verify numbers against the files.
- Never describe C-MAPSS as real aircraft data. Predictions are estimates, not maintenance authorisation.
- Split by engine, never by row. The test set is for final evaluation only.
- Fit scalers and any learned preprocessing on training engines only.
- Feature importance is not causation.

## Data
- `data/raw/` is read-only and never edited; verify with `data/checksums.sha256`.
- Load with `sep=r"\s+"`, `header=None`. Start with FD001.

## Code and notebooks
- Jupyter notebooks are central: title, objective, markdown before important code, real outputs, interpretation, conclusion, next steps.
- Readable, PEP 8, meaningful names, no needless abstraction, no hardcoded machine-specific paths.
- Visual identity: dark charcoal/navy backgrounds, restrained teal/blue/silver/amber accents; Plotly for interactive and 3D, Matplotlib/Seaborn for static. 3D only where it communicates something.
- Environment: `.venv` (Python 3.13), pinned `requirements.txt`; add dependencies in the phase that needs them.
- Add folders and files only when a phase needs them.
