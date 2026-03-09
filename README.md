# Noclip Desktop

<picture>
  <img src="assets/icon.png" align="right" alt="Noclip Desktop Logo" width="120" height="120">
</picture>

### Control Your Computer Using Natural Language

Noclip Desktop lets you control your computer just by describing what you want — in plain English (or any language). It sends your request to an LLM backend (GPT-4o, Gemini, Claude, and more), receives step-by-step instructions, and automatically executes them by simulating keyboard and mouse input.

<div align="center">
<h4>Full Autopilot for All Computers, Powered by LLMs</h4>

  [![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/cinderbrick1212/Noclip-Desktop?tab=readme-ov-file#install)
  [![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/cinderbrick1212/Noclip-Desktop?tab=readme-ov-file#install)
  [![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/cinderbrick1212/Noclip-Desktop?tab=readme-ov-file#install)
  <br>
  [![Github All Releases](https://img.shields.io/github/downloads/cinderbrick1212/Noclip-Desktop/total.svg)](https://github.com/cinderbrick1212/Noclip-Desktop/releases/latest)
  ![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/cinderbrick1212/Noclip-Desktop)
  ![GitHub Repo stars](https://img.shields.io/github/stars/cinderbrick1212/Noclip-Desktop)
  ![GitHub](https://img.shields.io/github/license/cinderbrick1212/Noclip-Desktop)
  [![GitHub Latest Release](https://img.shields.io/github/v/release/cinderbrick1212/Noclip-Desktop)](https://github.com/cinderbrick1212/Noclip-Desktop/releases/latest)

</div>

---

## ✨ Features

- **Natural language control** — just describe what you want done
- **Multi-provider LLM support** — OpenAI, Gemini, Claude, OpenRouter, and Ollama
- **Modern Gradio web UI** with an integrated chat interface and settings panel
- **Single or Dual LLM mode** — pair a fast local model (Moondream) with a cloud model for hybrid inference
- **Screen & window capture selector** — target a specific monitor or application window
- **Course-correction** — the app takes screenshots to check its progress and adjusts as needed
- **Cross-platform** — runs on macOS, Linux, and Windows

---

## 🎬 Demo

**"Solve Today's Wordle"**
![Solve Today's Wordle](assets/wordle_demo_2x.gif)
*clipped, 2x speed*

<details>
  <summary>More Demos</summary>
  <ul>
    <li>
      "Make me a meal plan in Google Docs"
      <img src="assets/meal_plan_demo_2x.gif" style="margin: 5px; border-radius: 10px;">
    </li>
    <li>
      "Write a Web App"
      <img src="assets/code_web_app_demo_2x.gif" style="margin: 5px; border-radius: 10px;">
    </li>
  </ul>
</details>

---

## 💽 Install

<details>
  <summary><b>🍎 macOS</b></summary>
  <ul>
    <li>Download the macOS binary from the latest <a href="https://github.com/cinderbrick1212/Noclip-Desktop/releases/latest">release</a>.</li>
    <li>Unzip the file and move Noclip Desktop to your Applications folder.<br><br>
      <img src="assets/macos_unzip_move_to_applications.png" width="350" style="border-radius: 10px; border: 3px solid black;">
    </li>
  </ul>

  <details>
    <summary><b>Apple Silicon (M-Series) Macs</b></summary>
    <ul>
      <li>Noclip Desktop will ask for <b>Accessibility</b> access (to operate your keyboard and mouse) and <b>Screen Recording</b> access (to take screenshots and assess progress).</li>
      <li>If the prompts don't appear, add them manually via <b>System Settings → Privacy and Security</b>.<br><br>
        <img src="assets/mac_m3_accessibility.png" width="400" style="margin: 5px; border-radius: 10px; border: 3px solid black;"><br>
        <img src="assets/mac_m3_screenrecording.png" width="400" style="margin: 5px; border-radius: 10px; border: 3px solid black;">
      </li>
    </ul>
  </details>

  <details>
    <summary><b>Intel Macs</b></summary>
    <ul>
      <li>
        Launch the app from the Applications folder.<br>
        You may see the standard Mac <i>"Noclip Desktop cannot be opened" error</i>.<br><br>
        <img src="assets/macos_unverified_developer.png" width="200" style="border-radius: 10px; border: 3px solid black;"><br>
        Press <b><i><ins>Cancel</ins></i></b>, then go to <b>System Preferences → Security & Privacy → Open Anyway</b>.<br><br>
        <img src="assets/macos_system_preferences.png" width="100" style="border-radius: 10px; border: 3px solid black;">&nbsp;
        <img src="assets/macos_security.png" width="100" style="border-radius: 10px; border: 3px solid black;">&nbsp;
        <img src="assets/macos_open_anyway.png" width="400" style="border-radius: 10px; border: 3px solid black;">
      </li>
      <li>Noclip Desktop also needs <b>Accessibility</b> and <b>Screen Recording</b> permissions.<br><br>
        <img src="assets/macos_accessibility.png" width="400" style="margin: 5px; border-radius: 10px; border: 3px solid black;"><br>
        <img src="assets/macos_screen_recording.png" width="400" style="margin: 5px; border-radius: 10px; border: 3px solid black;">
      </li>
    </ul>
  </details>

  <ul>
    <li>See the <a href="#setup">Setup</a> section to connect Noclip Desktop to your LLM provider.</li>
  </ul>
</details>

<details>
  <summary><b>🐧 Linux</b></summary>
  <ul>
    <li>Tested on Ubuntu 20.04.</li>
    <li>Download the Linux zip from the latest <a href="https://github.com/cinderbrick1212/Noclip-Desktop/releases/latest">release</a>.</li>
    <li>Extract the executable and see the <a href="#setup">Setup</a> section to connect Noclip Desktop to your LLM provider.</li>
  </ul>
</details>

<details>
  <summary><b>🪟 Windows</b></summary>
  <ul>
    <li>Tested on Windows 10.</li>
    <li>Download the Windows zip from the latest <a href="https://github.com/cinderbrick1212/Noclip-Desktop/releases/latest">release</a>.</li>
    <li>Unzip the folder, move the exe to your preferred location, and double-click to launch.</li>
    <li>See the <a href="#setup">Setup</a> section to connect Noclip Desktop to your LLM provider.</li>
  </ul>
</details>

<details>
  <summary><b>🐍 Run as a Script</b></summary>
  <ul>
    <li>Clone the repo: <code>git clone https://github.com/cinderbrick1212/Noclip-Desktop.git</code></li>
    <li>Enter the directory: <code>cd Noclip-Desktop</code></li>
    <li><b>Optionally</b> create a virtual environment:
      <ul>
        <li><code>python -m venv .venv</code></li>
        <li><code>source .venv/bin/activate</code> (or <code>.venv\Scripts\activate</code> on Windows)</li>
      </ul>
    </li>
    <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
    <li>Run the app: <code>python app/app.py</code></li>
    <li>The Gradio web UI will open in your browser at <code>http://127.0.0.1:7860</code></li>
  </ul>
</details>

---

## 🛠️ Setup <a id="setup"></a>

Noclip Desktop supports multiple LLM providers. Configure your preferred one in the **⚙️ Settings** tab of the web UI.

| Provider | Example Models | API Key |
|----------|---------------|---------|
| **OpenAI** | GPT-5, GPT-4o | [platform.openai.com](https://platform.openai.com/settings/organization/api-keys) |
| **Gemini** | Gemini 2.5 Pro, Flash | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **Claude** | Claude Sonnet 4, Opus 4 | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| **OpenRouter** | Any model via OpenRouter | [openrouter.ai](https://openrouter.ai/keys) |
| **Ollama** | Llama 3, Mistral, etc. | No key needed — set endpoint URL |

<details>
  <summary><b>Quick Start</b></summary>

1. Launch Noclip Desktop (`python app/app.py` or run the executable).
2. Open the **⚙️ Settings** tab in the web UI.
3. Under **🤖 LLM Mode & Provider**, select your provider and model.
4. Under **🔑 API Keys**, paste your API key for the selected provider.
5. Click **💾 Save Settings**.
6. Switch to the **💬 Chat** tab and start sending requests!

</details>

<details>
  <summary><b>Single vs Dual LLM Mode</b></summary>

- **Single LLM** — one model handles both screenshot analysis and action planning.
- **Dual LLM** — a fast local model (e.g. Moondream) handles real-time screenshots while a cloud model (e.g. Gemini Flash) handles video context and high-level planning. Great for privacy or low-latency setups.

Configure this under **🤖 LLM Mode & Provider** in Settings.

</details>

<details>
  <summary><b>Using Ollama (local models)</b></summary>

1. Install [Ollama](https://ollama.com) and pull a model: `ollama pull llama3.3`
2. In Settings, select **Ollama** as the provider.
3. Set the endpoint to `http://localhost:11434`.
4. Enter the model name (e.g. `llama3.3`).

</details>

<details>
  <summary><b>Custom / OpenAI-compatible LLMs</b></summary>

Noclip Desktop supports any OpenAI-compatible API. Select **OpenRouter** or set a custom base URL under **🎛️ General** settings. If your LLM doesn't use the OpenAI API format, use a compatibility layer like [LiteLLM](https://github.com/BerriAI/litellm).

</details>

---

## 🖼️ Architecture

```
+----------------------------------------------------+
| App                                                |
|                                                    |
|    +----------+                                    |
|    | Gradio   |                                    |
|    | Web UI   |                                    |
|    +----------+                                    |
|        ^                                           |
|        | (direct calls + status_queue)             |
|        v                                           |
|  +-----------+  (Screenshot + Goal)  +-----------+ |
|  |           | --------------------> |           | |
|  |    Core   |                       |    LLM    | |
|  |           | <-------------------- |           | |
|  +-----------+    (Instructions)     +-----------+ |
|        |                              Providers:   |
|        v                              · OpenAI     |
|  +-------------+                      · Gemini     |
|  | Interpreter |                      · Claude     |
|  +-------------+                      · OpenRouter |
|        |                              · Ollama     |
|        v                                           |
|  +-------------+                                   |
|  |   Executer  |                                   |
|  +-------------+                                   |
+----------------------------------------------------+
```

---

## ⚠️ Known Limitations

- **Spatial reasoning** — clicking small or precise UI elements can be unreliable depending on the model.
- **Tabular navigation** — keeping track of cell positions in Excel or Google Sheets is error-prone.
- **GUI-heavy apps** — applications like games or DAWs that rely heavily on cursor actions may struggle.

---

## 📝 Notes

- **Cost estimate:** ~$0.0005–$0.002 per LLM request, depending on model. Complex tasks may require 2–30 LLM calls.
- **Stop anytime** — press the Stop button in the UI, or drag your cursor to any screen corner.
- **Multi-monitor support** — use the **🖥️ Choose what to capture** section in the Chat tab to target a specific screen or window.
- **Build options** — the CI workflow builds for Windows, macOS, and Linux in two modes:
  - **Server (localhost):** PyInstaller executable running the Gradio web UI in your browser.
  - **Electron (desktop app):** Native desktop window wrapping the Gradio UI.

---

## 🔮 The Future

*(with better models trained on video walkthroughs like YouTube tutorials)*

- "Create a couple of bass samples for me in Garage Band for my latest project."
- "Read this design document, edit the code on GitHub, and submit it for review."
- "Find my friends' music taste from Spotify and create a party playlist for tonight."
- "Take the pictures from my trip and make a montage in iMovie."

---

## ⭐ Star History

<picture>
  <img src="https://api.star-history.com/svg?repos=cinderbrick1212/Noclip-Desktop&type=Date" alt="Star History" width="720">
</picture>

