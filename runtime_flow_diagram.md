</details>

---

### ✅ 3. `docs/runtime_flow_diagram.md`

<details>
<summary>Click to expand</summary>

```markdown
# Runtime Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Web App
    participant A as AI Agent
    participant V as Validator
    participant S as Sandbox
    participant ST as Storage

    U->>UI: Provide code or request AI help
    UI->>A: Send goal + context
    A->>V: Generate TRP and validate
    V-->>A: TRP approved or rejected
    alt Valid
        A->>S: Execute plan (run_manim, etc.)
        S-->>ST: Save artifacts
        S-->>A: Logs + exit code
        A->>V: Postflight checks
        V-->>A: Pass/Fail
        A-->>UI: Results + artifacts
        UI-->>U: Show video + logs
    else Invalid
        V-->>A: Reasons
        A-->>UI: Error guidance
        UI-->>U: Display fixes
    end