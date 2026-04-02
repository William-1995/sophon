# Sophon Roadmap

This document keeps the release direction visible without turning the README into a technical dump.

## 0.2 — Boundary, Contract, and Refinement Release

Focus:

- Make the product boundaries obvious to contributors.
- Keep the documentation centered on principles, contracts, and responsibilities.
- Keep the web UI aligned with the backend protocol.
- Keep multi-file upload/download, artifact visibility, and batch progress as first-class workflow behavior.
- Fold the 0.2.1 cleanup work into the same release train so the launch feels coherent.

Expected outcomes:

- Documentation clearly explains what belongs in chat, workflow, tools, skills, workspace, and persistence.
- API and architecture docs describe the actual workspace protocol.
- README stays product-oriented and avoids over-explaining implementation details.
- Tighten documentation wording and reduce duplication.
- Split or archive process-only documents that are no longer needed.
- Continue polishing workflow presentation and artifact handling.
- Keep the product readable for engineers joining the project.
- Define installable skill/package contracts more clearly.
- Clarify Python/Node runtime support for packaged skills and adapters.
- Continue moving toward adapter-based compatibility with Claude Code and Codex ecosystems.

## 0.3 — Assistant + Digital Worker Direction

This release is about capability growth, not just cleanup.

Likely focus:

- Personal assistant workflows.
- Digital worker / harness-style execution.
- Hooks.
- Harness-style execution.
- Scheduled tasks.
- Notifications and outbound actions such as email sending.
- Deeper workflow automation without breaking the protocol boundaries established in 0.2.

## Non-goals

- Hardcoding new use cases into the frontend.
- Reintroducing tool-specific logic into workflow presentation.
- Letting the README drift into implementation detail again.
