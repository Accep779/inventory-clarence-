# Anti-Gravity Kit: The Masterclass Blueprint

> **"Context is the new code."**

This is your Tier One specificiation for operating the Anti-Gravity Kit (GSD Framework). It converts the vague "vibe coding" process into a disciplined, engineering-grade workflow.

---

## 1. The Core Philosophy

You are no longer asking an AI to "write some code." You are operating a **Context Engine**.

### The 4 Golden Rules (Non-Negotiable)

1.  **🔒 Planning Lock:** You NEVER implement without a finalized spec and a plan.
    *   *Why:* AI hallucinates when it guesses intent. Specificity is the antidote.
    *   *Mechanism:* The `/plan` command will physically refuse to run if `SPEC.md` says "DRAFT".
2.  **💾 State is Sacred:** Your memory is finite. `STATE.md` is infinite.
    *   *Why:* Every session wipes the agent's brain. `STATE.md` persists the mission.
    *   *Mechanism:* Workflows update `STATE.md` automatically. Never manually edit it unless correcting a drift.
3.  **🧹 Fresh Context:** Context pollution kills intelligence.
    *   *Why:* After ~30 minutes of debugging, the AI enters a "death spiral" of circular logic.
    *   *Mechanism:* Each phase of execution spawns a *fresh* sub-agent with only the necessary files.
4.  **✅ Empirical Validation:** proof > trust.
    *   *Why:* "It looks right" is how bugs ship. "Here is the screenshot" is how software ships.
    *   *Mechanism:* `/verify` requires hard evidence (screenshots, curl outputs) for every "Must-Have."

---

## 2. The Tier One Workflow

This is the "Happy Path" for 95% of your development.

### Phase 0: Initialization (The Foundation)
1.  **`/new-project`**: The Interview.
    *   The agent interviews *you*. It forces you to clarify your vision.
    *   **Output:** `SPEC.md` (The Source of Truth).
2.  **`/map`**: The Reconnaissance.
    *   Scans your *entire* codebase (files, dependencies, data flow).
    *   **Output:** `ARCHITECTURE.md` (The Map) and `STACK.md` (The Inventory).
    *   *Crucial:* Run this before planning any existing project.

### Phase 1: Planning (The Strategy)
1.  **`/plan [N]`**: The Blueprint.
    *   Reads `SPEC`, `ARCHITECTURE`, and `ROADMAP`.
    *   Generates `PLAN.md` files. **These are PROMPTS.**
    *   **Key Concept:** "Plans as Prompts." We don't tell the AI *what* to do; we hand it a script (`PLAN.md`) that *it* reads to know what to do.
    *   *Review this:* Read the generated `PLAN.md`. If the plan is bad, the code will be bad.

### Phase 2: Execution (The Build)
1.  **`/execute [N]`**: The Assembly Line.
    *   **Wave Execution:** Tasks are grouped by dependency.
        *   *Wave 1:* Database models (Parallel)
        *   *Wave 2:* API endpoints depending on models (Parallel)
    *   **Atomic Commits:** Every single task gets its own git commit.
    *   *Pro Tip:* You can step away here. The agent manages its own context.

### Phase 3: Verification (The Audit)
1.  **`/verify [N]`**: The Quality Gate.
    *   The agent acts as an antagonistic auditor.
    *   It reads the `Must-Haves` from your Roadmap.
    *   It tries to *break* the feature or proving it doesn't work.
    *   **Pass:** Phase complete.
    *   **Fail:** It generates "Gap Closure" plans automatically.
        *   Run `/execute [N] --gaps-only` to fix them.

---

## 3. Tool Deep Dive

### The Architect: `/map`
*   **When to use:** Start of project, after major refactors, or when you feel "lost" in the code.
*   **Pro Tip:** If the AI is making "stupid" mistakes about imports or file locations, your map is stale. Run `/map` to re-ground it.

### The Strategist: `/plan`
*   **Magical Flag:** `--research`
    *   Use `/plan --research` to force the agent to go verify assumptions *before* writing the plan.
    *   *Example:* "Do we use Axios or Fetch?" It will check the codebase, then plan accordingly.
*   **Magical Flag:** `--skip-research`
    *   Use when you are 100% sure of the path and want speed.

### The Builder: `/execute`
*   **The "Context Reset":**
    *   Notice how execution feels "fast" even on huge tasks?
    *   It's because `/execute` spawns a *new* agent for each plan. It doesn't carry the baggage of the chat history.
*   **Commit Strategy:**
    *   Don't worry about manual git commits. The executor writes `feat(phase-1): ...` commits automatically.

### The Auditor: `/verify`
*   **The "Trust Ratio":**
    *   Low complexity task? Trust ratio 50% (Code review).
    *   High complexity task? Trust ratio 0% (Empirical evidence).
*   **Self-Healing:**
    *   If verification fails, it doesn't just cry. It writes a `PLAN.md` specifically to fix the failure.

---

## 4. Advanced Maneuvers

### The "Death Spiral" Escape: `/pause`
*   **Symptoms:**
    *   AI fixes one bug, creates two more.
    *   "I apologize, let me try again" (classic loop).
    *   Context token count > 80%.
*   **The Fix:**
    1.  Type `/pause`. (Dumps everything to `STATE.md`).
    2.  Hit "Restart Session" (or clear chat).
    3.  Type `/resume`.
    *   *Result:* You are back exactly where you were, but with a fresh brain.

### The "Gap Closure" Snipe: `--gaps-only`
*   You verified Phase 3. 9/10 passed. 1 failed.
*   Don't re-run the whole phase.
*   The system creates a `fix-plan`.
*   Run `/execute 3 --gaps-only`. It targets *only* the failure.

### The "Quick Note": `/add-todo`
*   In the middle of execution, you see a problem unrelated to current task.
*   **DO NOT** distract the agent.
*   Type: `/add-todo "Refactor the auth middleware later, it's messy"`
*   The agent stays focused. You didn't lose the thought.

---

## 5. Your Responsibility

The system handles the **How**. You own the **What**.

1.  **Review the SPEC:** If the spec is vague, the software will be generic.
2.  **Review the PLAN:** This is your high-leverage moment. Catching a bad architectural decision in `PLAN.md` costs $0. Catching it in code costs $1000.
3.  **Demand Evidence:** If `/verify` says "Passed" but provides no screenshot/log, reject it.

*Welcome to Anti-Gravity.*
