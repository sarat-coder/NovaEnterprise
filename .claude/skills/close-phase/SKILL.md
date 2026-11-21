---
name: close-phase
description: Close a TASKS.md phase - verify exit criteria, then write the four internal/ phase documents with mermaid diagrams.
argument-hint: <phase number, e.g. 1>
disable-model-invocation: true
---

Close **Phase $ARGUMENTS** of `TASKS.md`. Below, `<N>` means the phase number `$ARGUMENTS`.

## 1. Verify
- Every sub-task row in the phase is `Completed ✅`. If not, list the pending ones and stop.
- Check each exit criterion for the phase in `PLAN_PHASE.md` against the code; mark met / not met with `file:line`.
- Run `make test` and ruff; run `make demo` if it exists. Report results honestly.
- Update the phase row in `MEMORY.md` §1 (implemented / validated locally / needs credentials / deployed) — only what is true.

## 2. Write the four documents
Read the code merged in this phase (`git log development --oneline` and the files listed in the phase's plans in `docs/plans/`). Create the folders if missing. Every diagram is a ```mermaid block that renders on GitHub.

1. **`internal/explain_codebase/phase<N>_explained.md`** — for a non-technical interview board, read aloud as is.
   Plain language, no jargon without an everyday analogy. Sections: what this phase built and why it matters ·
   each component as "what it is / what it does / analogy" · one simple mermaid flowchart · how we know it works · what comes next.
2. **`internal/design_evolution/Phase<N>_Project_System_Design_Evolution.md`** — the system design from the
   start of the phase to its end. One mermaid diagram for the starting design, one per sub-task where the design
   changed, and the final design. Under each, 3–5 lines on what changed and why.
3. **`internal/Infra_design_evolution/Phase<N>_Infra_design_evolution.md`** — processes, ports, containers,
   networks, stores and how requests are routed between them (Docker networking once Compose exists; local
   processes before that). A mermaid diagram per component group plus a short explanation of each component.
4. **`internal/QnA/Phase<N>_Interview_QnA.md`** — interview questions with answers for this phase, grouped
   basic / intermediate / advanced / scenario ("what if X fails?"). Answers reference the real code by path.

Use the real file names, endpoints and numbers from the code. Do not describe anything not yet built; mark future
work as "next phase".

## 3. Report
List the four files, the exit-criteria table, and the test/demo results. Remind the user to set the phase status in
README.md's roadmap and to commit the docs on a `docs/phase-<N>` branch or with the last task of the phase.
