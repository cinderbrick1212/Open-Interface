# Open Interface

### Usage
```commandline
python3 app.py
```

### System Diagram

**Standard mode** (single LLM — GPT-5, GPT-4o, Gemini, etc.):
```
+--------------------------------------------------------------------+
| App                                                                |
|                                                                    |
|    +-------+                                                       |
|    |  GUI  |                                                       |
|    +-------+                                                       |
|        ^                                                           |
|        | (via MP Queues)                                           |
|        v                                                           |
|  +-----------+  (Screenshot + Goal)  +-----------+                 |
|  |           | --------------------> |           |                 |
|  |    Core   |                       |    LLM    |                 |
|  |           | <-------------------- | (GPT-5/…) |                 |
|  +-----------+    (Instructions)     +-----------+                 |
|        |                                                           |
|        v                                                           |
|  +-------------+                                                   |
|  | Interpreter |                                                   |
|  +-------------+                                                   |
+--------------------------------------------------------------------+
```

**Moondream2 Hybrid mode** (unified pipeline — Moondream local + Gemini Flash API):
```
+--------------------------------------------------------------------+
| App                                                                |
|                                                                    |
|    +-------+                                                       |
|    |  GUI  |                                                       |
|    +-------+                                                       |
|        ^                                                           |
|        | (via MP Queues)                                           |
|        v                                                           |
|  +-----------+         +------------------------------------------+|
|  |           |         | MoondreamHybrid (unified pipeline)       ||
|  |           |  Goal   |                                          ||
|  |           | ------> |  Screenshot ──┬──► Gemini Flash (API)    ||
|  |    Core   |         |              │     (first + periodic)     ||
|  |           |         |              │     full plan + guidance   ||
|  |           |         |              │          │                 ||
|  |           |         |              │          │ guidance ──┐    ||
|  |           |         |              │          v            │    ||
|  |           |         |              └──► Moondream (local)  │    ||
|  |           |         |                   query() per step ◄─┘   ||
|  |           |         |                   fast, real-time         ||
|  |           |         |                        │                  ||
|  |           | <------ |                   JSON instructions       ||
|  +-----------+  JSON   |                                          ||
|        |               | Moondream can ESCALATE → triggers Gemini ||
|        v               +------------------------------------------+|
|  +-------------+                                                   |
|  | Interpreter | ──► pyautogui (mouse + keyboard)                  |
|  +-------------+                                                   |
+--------------------------------------------------------------------+
```

### Unified pipeline data flow (Moondream2 Hybrid)

Both LLMs share a **single data pipeline** (screenshot → grid).  The first
screenshot after a user prompt always goes to **Gemini Flash** for full
planning.  Then **Moondream** takes over locally, with Gemini called again
only periodically or when Moondream escalates:

```
Step 0:  [Screenshot] → [Gemini Flash plans + guidance] → [Execute cmds]   ← first SS → API
Step 1:  [Screenshot] → [Moondream local plan]          → [Execute]
Step 2:  [Screenshot] → [Moondream local plan]          → [Execute]
Step 3:  [Screenshot] → [Gemini Flash review + guidance] → [Execute]       ← periodic
Step 4:  [Screenshot] → [Moondream / ESCALATE?]         → [Execute]
  ...
```

The local model can **decide to stop** and let Gemini Flash analyse by
responding with ``UNCERTAIN``.  This triggers an immediate API review
regardless of the step interval.