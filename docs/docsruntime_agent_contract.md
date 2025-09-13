# Runtime Agent Contract
**Version:** 1.0  
**Date:** 2025-09-08  
**Owner:** Runtime Team (with AI Agent integration)

## 0) Purpose & Scope
This contract defines the **runtime guarantees**, **sandbox rules**, **tier limits**, **editing policy**, and **safety checks** for our Manim-based animation platform. It aligns the AI agent, backend runtime, and user experience so outcomes are predictable, safe, and easy to debug.

> **Key goals**  
> - Keep previews fast and consistent (especially for Free users).  
> - Provide more capabilities for Premium without compromising safety.  
> - Make what’s allowed/blocked explicit—no surprises.  
> - Keep a crisp paper trail: planning (TRP), execution (logs), and artifacts.
> - Provide Manim animation reflecting prompt from user.

---

## 1) Definitions

- **Render duration**: Length of the output video (seconds).  
- **Preview preset**: Output settings applied by default (resolution, fps, codec).  
- **Compute budget**: The **agent + host-side** planning/validation budget **before** sandbox execution (wall-clock seconds). This includes validation, linting, planning, and tool orchestration—*not* the renderer’s in-sandbox wall time.  
- **Sandbox wall time**: The time allowed **inside** the isolated execution (the actual render).  
- **Session**: Starts when a user opens a project and ends when they leave/timeout/reset. Editing rules apply per-session.

> ⚠️ Why define both “compute budget” and “sandbox wall time”?  
> They protect us at two layers. The **compute budget** keeps the AI + orchestrator snappy; the **sandbox wall time** ensures render jobs don’t hang or starve the queue.

---

## 2) Tier Definitions & Limits

### 2.1 Free Tier
- **Preview preset**: `480p @ 24 fps`  
- **Max render duration**: `8s`  
- **Compute budget**: `≤ 10s` (agent/orchestrator)  
- **Sandbox wall time**: `≤ 60s` (render step; reasonable margin for 8s at 480p)  
- **Watermark**:  
  - **Not** applied to standard 8s previews.  
  - **Applied** only to the **one 30s premium trial generation** (see below).
- **Premium trial (one-off)**:  
  - A **single 30s** render allowed for Free users as a trial.  
  - Output **must** be watermarked.  
  - Uses **Premium preset** (see §2.2) but retains **Free** editing constraints (see §4).

> Rationale: Free tier must feel responsive and useful, yet bounded. The one-off 30s trial showcases Premium quality in a safe, watermarked way.

### 2.2 Premium Tier
- **Preview preset**: `1080p (or higher) @ 24 fps`  
- **Max render duration**: `30s`  
- **Compute budget**: `≤ 30s` (agent/orchestrator high-thinking mode)  
- **Sandbox wall time**: `≤ 180s` (render step; bounded yet flexible)  
- **Watermark**: None (except when simulating Free’s 30s trial for testing)

> Rationale: Premium gets higher resolution and longer durations. We keep a moderate compute budget for planning, and give the sandbox enough wall time for typical 30s Manim workloads.

---

## 3) Watermarking Policy

### 3.1 When Applied
- **Only** for **Free users’ 30s premium trial** output.

### 3.2 Style (tentative; can be tweaked later)
- Position: **Bottom-right**  
- Size: **10% of video width**, maintaining aspect ratio  
- Safe margins: **4%** from right/bottom edges  
- Opacity: **85–90%** (logo brand guidance)  
- Format: Embedded overlay during post-processing (no removable metadata trick)

### 3.3 Enforcement
- The post-processing pipeline **must fail the job** if watermarking is required but missing.  
- Acceptance test in §8 ensures presence of watermark on applicable outputs.

---

## 4) Editing Rules (Anti-abuse + UX clarity)

- **All users**: May edit code after a generation and preview again (within tier limits).
- **Free users**:
  - If they **edit code after an AI-generated output**, **AI assistance is disabled but generate code should NOT removed or deleted** for the remainder of the **session**.  
  - They can still run previews; the goal is to prevent free-tier agent-chaining to bypass limits.
- **Premium users**:
  - May edit the code and **continue AI-assisted building** after edits.
- **Previews** always respect **duration/fps/resolution constraints** of the current tier.
- **Longer renders**: The UI will prompt users to **export code and run locally** or in their own IDE if they need longer durations.

> UX Note: Provide clear banner text when Free users lose agent assistance due to post-AI edits, and how to re-enable (e.g., start a new session).

---

## 5) Memory Policy (Per-project)

- **Scope**: Per-project memory (e.g., last plans, accepted constraints, assets map).  
- **TTL**: **48 hours** since the last interaction.  
- **Carry limits**:  
  - Up to 10 prior TRPs referenced.  
  - Up to 20 KB of derived notes/constraints.  
- **Content**: Only **non-sensitive** data related to code, assets, constraints, and preferences.  
- **User control**:  
  - “Clear memory” button wipes per-project memory immediately.  
  - Automatic purging after TTL.


> Why: Keeps the agent helpful without hoarding stale or sensitive data.

---

## 6) Sandboxing

### 6.1 Phase 1 (Pre-Beta): Virtualenv + Subprocess + AST Filtering
- **Execution**:  
  - Run Manim in a Python **virtualenv** via **subprocess**.  
  - Pre-execution **AST import filter** blocks disallowed modules (e.g., `socket`, `subprocess`, `os.*` write outside `/project`, `requests`, etc.).  
  - Optional: monkeypatch common network calls to raise immediately.
- **Resource controls**:
  - Set **CPU time** and **RSS memory** limits via `resource.setrlimit` on Linux.  
  - Constrain **open files**, **process count** (no forking).  
  - **No network** by default (attempts are blocked).
- **Filesystem**:
  - Working directory: `/project` (read-write).  
  - Output directory: `/artifacts` (read-write).  
  - Everything else read-only where feasible (depends on host).
- **Pros**: Fast to implement.  
- **Cons**: Weaker isolation than containers; suitable only for **closed alpha**.

### 6.2 Phase 2 (Public Beta+): Dockerized Isolation
- **Container**:
  - **No network** (`--network none`).  
  - **Resource quotas**: `--cpus`, `--memory`, `--pids-limit`, cgroups v2.  
  - **Security**:
    - `--security-opt no-new-privileges`  
    - `--cap-drop=ALL`  
    - `--read-only` (with writable mounts only for `/project` and `/artifacts`)  
    - `--pids-limit` to prevent fork bombs  
    - Seccomp/AppArmor profiles to restrict syscalls
  - **User**: Non-root user (UID/GID remapped).
- **Bind mounts**:
  - `-v /host/project:/project:rw`  
  - `-v /host/artifacts:/artifacts:rw`
- **Example**:
  ```bash
  docker run --rm \
    --network none \
    --cpus="2.0" --memory="2g" --pids-limit=128 \
    --security-opt no-new-privileges \
    --cap-drop=ALL \
    --read-only \
    -v /host/project:/project:rw \
    -v /host/artifacts:/artifacts:rw \
    --name manim-job-<id> \
    manim-runtime:latest \
    bash -lc "python -m manim -qk -p -o /artifacts output_scene.py"
  ```

  # RECAP of Runtime Agent Contract
**Version:** 1.0  
**Date:** 2025-09-08  
**Owner:** Runtime Team (with AI Agent integration)

## Purpose & Scope
Defines runtime guarantees, sandbox rules, tier limits, editing policy, and safety checks for the Manim-based animation platform.

---

## Tier Definitions

### Free Tier
- Preview preset: `480p @ 24 fps`
- Max render duration: `8s`
- Compute budget: `≤10s`
- Sandbox wall time: `≤60s`
- Watermark: Only on the **one 30s premium trial**.

### Premium Tier
- Preview preset: `1080p @ 24 fps`
- Max render duration: `30s`
- Compute budget: `≤30s`
- Sandbox wall time: `≤180s`
- Watermark: None.

---

## Editing Rules
- All users can edit code after generation and preview again.
- Free users: If they edit after AI generation, **AI assistance is disabled** for that session.
- Premium users: Can edit and continue AI-assisted building.

---

## Memory Policy
- Per-project memory with **48h TTL**.
- Stores TRPs, constraints, and notes (max 20 KB).
- User can clear memory anytime.

---

## Sandboxing
### Phase 1 (Pre-Beta)
- Virtualenv + subprocess.
- AST import filter to block unsafe modules.
- No network, resource limits applied.

### Phase 2 (Public Beta)
- Docker container:
  - `--network none`
  - Resource quotas (CPU, memory)
  - Security flags: `no-new-privileges`, `seccomp`, `drop caps`
  - Bind mounts: `/project` and `/artifacts`

---

## Validation Pipeline
1. **Preflight**: Validate TRP, lint AST, enforce limits.
2. **Execute**: Run in sandbox, capture logs.
3. **Postflight**: Verify MP4, apply watermark if needed, run acceptance tests.

---

## Acceptance Tests
- Reject over-duration requests.
- Enforce watermark on Free 30s trial.
- Block unsafe imports.
- Validate MP4 duration ±0.25s.
- Kill jobs exceeding wall time.

---

## Error Messaging
- Over-duration: “Free previews limited to 8s at 480p/24fps.”
- Watermark notice: “Your 30s trial will include a watermark.”
- Timeout: “Render exceeded time limit.”

---

## Governance
- Versioned doc; changes require PR and approval.

I am here to see if these changes will be saved.