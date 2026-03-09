# Noclip Desktop

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

**Moondream2 Hybrid mode** (Moondream local + Gemini Flash API via video):
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
|  |           |         | MoondreamHybrid                          ||
|  |           |  Goal   |                                          ||
|  |           | ------> |  Screenshot ──► Grid overlay ──┐         ||
|  |    Core   |         |                                │         ||
|  |           |         |         ┌──────────────────────┤         ||
|  |           |         |         ▼                      ▼         ||
|  |           |         |    FrameBuffer            Moondream       ||
|  |           |         |    (rolling window)       (local, fast)   ||
|  |           |         |    gridded frames         gridded SS      ||
|  |           |         |         │                 query()/step    ||
|  |           |         |         ▼ (periodic)           │         ||
|  |           |         |    Compile MP4                  │         ||
|  |           |         |         │                      │         ||
|  |           |         |         ▼                      │         ||
|  |           |         |    Gemini Flash   guidance ──►  │         ||
|  |           |         |    (API, video)                 │         ||
|  |           |         |         │                      │         ||
|  |           | <------ |         └──► JSON instructions ◄┘        ||
|  +-----------+  JSON   |                                          ||
|        |               | Moondream can ESCALATE → triggers Gemini ||
|        v               +------------------------------------------+|
|  +-------------+                                                   |
|  | Interpreter | ──► pyautogui (mouse + keyboard)                  |
|  +-------------+                                                   |
+--------------------------------------------------------------------+
```

### Data pipeline (Moondream2 Hybrid)

Both LLMs receive **gridded screenshots** (with cell overlay), but in
different formats:

* **Moondream** (local) gets a single gridded screenshot every step — fast,
  real-time action planning.
* **Gemini Flash** (API) gets a **video** compiled from the continuous
  rolling frame buffer of gridded screenshots — temporal context about what
  happened on screen.

The frame buffer is **never cleared between API calls** — each video is a
continuous, overlapping window of recent activity:

```
Step 0:  [Grid SS] → buffer=[0]       → [Gemini: video(0)]     → [Execute]  ← first
Step 1:  [Grid SS] → buffer=[0,1]     → [Moondream: SS(1)]     → [Execute]
Step 2:  [Grid SS] → buffer=[0,1,2]   → [Moondream: SS(2)]     → [Execute]
Step 3:  [Grid SS] → buffer=[0,1,2,3] → [Gemini: video(0..3)]  → [Execute]  ← periodic
Step 4:  [Grid SS] → buffer=[0..4]    → [Moondream: SS(4)]      → [Execute]
Step 5:  [Grid SS] → buffer=[0..5]    → [Moondream / ESCALATE?] → [Execute]
Step 6:  [Grid SS] → buffer=[0..6]    → [Gemini: video(0..6)]   → [Execute]  ← continuous!
  ...
```

The local model can **decide to stop** and let Gemini Flash analyse by
responding with ``UNCERTAIN``.  This triggers an immediate API review
regardless of the step interval.