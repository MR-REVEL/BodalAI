# Project Context: Manim Platform Integration

This document provides essential context for agents working on the Manim-based educational platform. It outlines technical specifications, infrastructure preferences, user experience goals, and agent behavior expectations to ensure seamless implementation and alignment with project objectives.

## 🎬 Manim & Media Configuration

**Manim Version:** Use Manim Community v0.19.0 as the standard baseline. Future updates will be integrated post-launch.

**Rendering Strategy:** Begin with CPU-only rendering. Consider GPU acceleration in future phases based on performance needs.

**FFmpeg Integration:** Bundle FFmpeg within the runner image to support media encoding. The platform must be fully web-based (similar to Google Colab), allowing users to preview creations without extensions or downloads. An integrated AI agent will assist users.

## ⚙️ Runtime & Infrastructure

**Phase 1:** Host runner on a single VM to simplify orchestration and debugging.

**Phase 2:** Evaluate Docker-in-Docker vs. Kubernetes with strict PodSecurity policies. Choose based on cache efficiency, memory usage, speed, and agent accuracy.

## 🔐 Security & Classroom Readiness

**User Demographics:** Primarily for adult learners and math educators. Student accounts (including minors) may be included. Guardrails optional.

**Privacy Compliance:** Adhere to Canadian/Ontario educational privacy standards.

**Project Isolation:** Implement only if necessary for classroom or tenant segregation. Prioritize cache, memory, and usability for individual accounts.

## 🎨 Product Experience & UX

**Branding:** Watermark assets and brand guidelines will be added later.

**Trial Experience:** Display a 30-second trial banner in the bottom-right corner of the preview window.

**MVP Criteria:**
- Seamless scene rendering
- Basic classroom account provisioning
- Trial experience without watermark unless using premium features
- UI feedback loop for render status

## 🤖 Agent Behavior & Prompting

**Request Handling:** Agent will prompt users before auto-downgrading requests (e.g., suggesting 8s @ 480p).

**Prompting Style:** Encourage users to provide detailed prompts. Include an instructional page to guide users in crafting effective prompts. Maintain educational tone without restricting creativity.

## 📊 Observability & Metrics

**Key Metrics:**
- Render success rate
- Timeout frequency
- Average wall time
- Watermark coverage
- Documentation compliance

**UI Features:** Display per-project run history in the UI. Note: history may be cleared periodically.

---

This context page is designed for integration within VS Code to support agent understanding and implementation.
