# Launchpad Cleanup Brief

This document is a focused cleanup brief for the Launchpad repository.

Use it as an implementation prompt for an agent working inside `/opt/launchpad`.
The goal is not to redesign the product or add major new features. The goal is
to make the current repository cleaner, more accurate, more reproducible, and
more ready for long-term operation on the Raspberry Pi.

## Objective

Bring the repository into a coherent, maintainable state where:
- docs match reality
- environment setup is reproducible
- deployment expectations are explicit
- local-only artifacts are handled correctly
- unfinished/stubbed pieces are clearly documented
- future work has a cleaner base

## Guardrails

- Work only in the canonical repo at `/opt/launchpad`
- Do not create additional clones under `/home/patrick` or `/home/aisha`
- Prefer incremental cleanup over architectural rewrites
- Do not expose new services publicly
- Do not weaken auth or security settings
- Do not install unnecessary software
- Do not change networking or firewall settings
- If a step is operationally disruptive, keep it minimal and document it clearly
- Preserve the current core architecture unless there is a compelling cleanup reason

## Current Observed State

Repository and workflow:
- Canonical repo lives at `/opt/launchpad`
- Shared group model is in place via `launchpad`
- `LAUNCHPAD.md` now exists and serves as the operational reference

Implementation reality:
- Dashboard orchestration is implemented
- Portrait renderer is implemented
- Live TfL train integration is implemented
- Live Open-Meteo weather integration is implemented
- Calendar is still mock-backed
- E-ink display driver is still stubbed
- Landscape renderer is still stubbed
- World Cup feature is mock-backed and experimental

Environment reality:
- A `.venv` exists locally in the repo working tree
- The environment does not appear fully provisioned to match declared project needs
- At audit time, modules/tools such as `httpx`, `python-dotenv`, `pytest`, and `ruff` were not available in the project venv
- The package also did not appear installed editable into the venv

Documentation reality:
- `README.md` still describes the project as a scaffold / not implemented
- That is no longer accurate
- `docs/PROJECT_VISION.md` is useful as a long-term vision document, but not as an accurate operational status document

Deployment reality:
- Code is structured for a Pi-hosted Python service
- No checked-in systemd unit, deploy script, or operational wrapper was present during audit

## Cleanup Tasks

### Priority 0 — Make the repository truthful

1. Update `README.md`
   - Remove outdated "scaffold" / "not implemented yet" language
   - Rewrite it to reflect the actual current state
   - Keep it concise: what Launchpad is, what works now, what is still stubbed, and how to run it locally

2. Align docs with reality
   - Ensure `README.md`, `LAUNCHPAD.md`, and `docs/PROJECT_VISION.md` have clearly different roles:
     - `README.md` = current project overview and quickstart
     - `LAUNCHPAD.md` = operator reference / system state / commands / deployment notes
     - `docs/PROJECT_VISION.md` = long-term product direction and philosophy
   - Remove contradictions across those files

3. Clarify implementation status in docs
   - Explicitly document:
     - portrait renderer implemented
     - landscape renderer not implemented
     - mock display implemented
     - e-ink display not implemented yet
     - mock calendar still in use
     - World Cup feature is experimental and mock-backed

### Priority 1 — Fix environment and setup hygiene

4. Make setup reproducible
   - Decide on the intended install path for contributors/operators:
     - likely `python -m venv .venv`
     - then `pip install -e .[dev,render,tfl]` or equivalent
   - Ensure docs describe the real required install command
   - Avoid ambiguous or incomplete setup guidance

5. Reconcile dependency declarations with reality
   - Review `pyproject.toml`, `requirements.txt`, and actual imports
   - Ensure the declared dependency model is coherent
   - Reduce duplication if possible
   - If `requirements.txt` is intentionally lightweight, explain why
   - If extras are the primary installation path, document that clearly

6. Decide how `.venv` should be treated operationally
   - Confirm it remains untracked and ignored
   - Ensure the repo does not rely on ad hoc local environment state
   - If `.venv` should exist on the Pi, document that as an operational convention, not as a repo artifact

7. Make runnable commands consistent
   - Ensure the documented run commands match the actual packaging/install approach
   - Clarify whether the canonical invocation is:
     - `PYTHONPATH=src python -m launchpad`
     - or installed console script `launchpad`
   - Prefer one documented primary path and mention the fallback path if useful

### Priority 1 — Improve deployment clarity

8. Add a minimal deployment definition
   - If appropriate, add a checked-in systemd service file template or actual unit file
   - Keep it simple and specific to Launchpad's current shape
   - Do not overengineer process management
   - If this is not ready yet, document exactly what is missing and why

9. Document the intended runtime mode
   - Clarify whether Launchpad is expected to:
     - render once on demand
     - loop forever as a service
     - or support both, with one being the production standard
   - Document expected environment variables for production

10. Capture the git ownership/operator quirk cleanly
   - The repository previously required `safe.directory` overrides for `aisha`
   - If the issue still exists, document or normalize it
   - Prefer a durable fix or a clearly documented operator convention

### Priority 2 — Clean repo and artifact hygiene

11. Decide what to do with `dashboard.png`
   - Determine whether it is:
     - a checked-in preview artifact
     - a generated local runtime artifact
     - or something that belongs under a docs/examples path instead
   - Put it in the right place and document the intent

12. Review docs and assets organization
   - `docs/ESPN_ACCESS_HANDOFF.md` is useful but tangential to the current MVP
   - Decide whether it should stay where it is, move under a more explicit experimental area, or remain with better context
   - Ensure `assets/fonts/` usage is documented and consistent with renderer expectations

13. Review test placeholders/skips
   - Identify placeholder tests that still reflect older project phases
   - Either implement them, tighten them, or clearly mark them as deferred
   - Avoid misleading "not implemented" wording where functionality now exists

### Priority 2 — Tighten code/documentation consistency

14. Review inline comments and module docstrings for stale wording
   - Look for references to code being "stub", "placeholder", or "not implemented" where that is no longer true
   - Update docstrings/comments to match the current code

15. Confirm feature-flag and mode docs are accurate
   - Verify documented env vars match the code
   - Verify mode behavior described in docs matches `builder.py`
   - Verify experimental feature descriptions are accurate and not aspirational beyond what exists

16. Review naming and path consistency
   - Check whether filenames, module names, and docs use consistent terminology:
     - Launchpad / dashboard / renderer / display / service
   - Prefer clarity over cleverness

## Deliverables

A good cleanup pass should produce most or all of the following:
- updated `README.md`
- updated docs where contradictions exist
- clearer setup/install instructions
- clearer deployment/runtime instructions
- artifact handling clarified (`dashboard.png`, `.venv`, similar local-only state)
- reduced stale wording in docs/comments/tests
- possibly a minimal systemd unit or deployment note if appropriate

## Suggested Execution Order

1. Read `LAUNCHPAD.md`, `README.md`, and `docs/PROJECT_VISION.md`
2. Inspect `pyproject.toml`, `requirements.txt`, `.env.example`, and run paths
3. Audit imports vs declared dependencies
4. Fix README and quickstart/setup guidance
5. Clean stale wording in docs/tests/comments
6. Decide and document artifact handling (`dashboard.png`, `.venv`)
7. Add minimal deployment/service documentation or service file if justified
8. Run available checks/tests after cleanup
9. Summarize what changed and what was intentionally left alone

## Acceptance Criteria

The cleanup is successful if, after the pass:
- a new contributor/operator can understand the repo without being misled
- the main docs do not contradict each other
- setup instructions are concrete and reproducible
- the boundary between implemented vs planned functionality is obvious
- generated/local artifacts are handled intentionally
- deployment expectations are explicit, even if still minimal

## Non-Goals

Do not turn this cleanup pass into:
- a major feature build
- a redesign of the architecture
- a migration to public cloud services
- a broad smart-home expansion
- a speculative rewrite of working code for style alone

## Suggested Final Output From the Cleanup Agent

At the end of the cleanup pass, produce:
1. a short summary of what was cleaned up
2. a list of files changed
3. any remaining unresolved cleanup items
4. any decisions that should be added back into `LAUNCHPAD.md`
