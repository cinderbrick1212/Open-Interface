"""Gradio-based web UI for Open Interface.

Replaces the previous Tkinter UI with a modern AI-frontend chat
interface.  Provides a ChatGPT / Claude-like experience with an
integrated, searchable settings panel.

Architecture
------------
::

    Browser ←→ Gradio (uvicorn) ←→ WebUI ←→ Core ←→ LLM / Interpreter

The chat handler spawns ``Core.execute_user_request`` in a background
thread and streams status updates from ``Core.status_queue`` back to
the chatbot via Gradio's generator protocol.
"""

import queue
import threading
from typing import Optional

import gradio as gr

from version import version
from utils.window_selector import get_capture_choices, _NO_WINDOWS_LABEL

# ── Constants ────────────────────────────────────────────────────────
PROVIDERS = ['OpenAI', 'Gemini', 'Claude', 'OpenRouter', 'Ollama']
LLM_MODES = ['Single LLM', 'Dual LLM']
RETENTION_POLICIES = [
    'Delete immediately', 'Keep 1 day', 'Keep 30 days', 'Keep forever',
]
BROWSERS = ['', 'Chrome', 'Firefox', 'Safari', 'Edge']

# Keywords used by the settings search filter (one list per accordion).
_SEARCH_KEYWORDS: list[list[str]] = [
    # 0 – LLM Mode & Provider
    ['llm', 'mode', 'provider', 'model', 'primary', 'secondary',
     'dual', 'single'],
    # 1 – API Keys
    ['key', 'api', 'openai', 'gemini', 'claude', 'openrouter',
     'ollama', 'endpoint'],
    # 2 – General
    ['general', 'browser', 'ding', 'instruction', 'url', 'base'],
    # 3 – Storage
    ['storage', 'buffer', 'retention', 'directory', 'folder',
     'save', 'delete', 'screenshot'],
    # 4 – Advanced
    ['advanced', 'fps', 'interval', 'moondream', 'video'],
    # 5 – Debug & Test
    ['debug', 'test', 'raw', 'logging', 'dry'],
]


class WebUI:
    """Gradio-based web UI for Open Interface."""

    def __init__(self, core=None):
        self._core = core
        self._stop_event = threading.Event()
        # Map capture labels → rects; populated at UI build time
        self._capture_map: dict[str, Optional[tuple[int, int, int, int]]] = {}
        self.demo = self._build_ui()

    # ── Core (lazy) ──────────────────────────────────────────────────

    @property
    def core(self):
        """Lazily create :class:`Core` on first request."""
        if self._core is None:
            from core import Core
            self._core = Core()
        return self._core

    # ── Public API ───────────────────────────────────────────────────

    def run(self, **kwargs):
        """Launch the Gradio web server."""
        self.demo.launch(
            server_name='127.0.0.1',
            server_port=7860,
            share=False,
            inbrowser=True,
            theme=gr.themes.Soft(primary_hue='violet'),
            **kwargs,
        )

    def cleanup(self):
        if self._core is not None:
            self._core.cleanup()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        from utils.settings import Settings
        sd = Settings().get_dict()

        with gr.Blocks(
            title='Open Interface',
        ) as demo:
            gr.Markdown(
                f"## 🔮 Open Interface `v{version}`\n"
                "Control your computer with natural language."
            )

            with gr.Tabs():
                # ─── Chat Tab ────────────────────────────────────────
                with gr.Tab("💬 Chat"):
                    chatbot = gr.Chatbot(
                        height=450,
                        placeholder=(
                            "Send a message to control your computer…"
                        ),
                    )
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder='What would you like me to do?',
                            show_label=False,
                            scale=8,
                            container=False,
                        )
                        submit_btn = gr.Button(
                            '▶ Submit', variant='primary', scale=1,
                        )
                        stop_btn = gr.Button(
                            '⏹ Stop', variant='stop', scale=1,
                        )

                    # ── Capture region selector ──────────────────────
                    self._build_capture_selector()

                # ─── Settings Tab ────────────────────────────────────
                with gr.Tab("⚙️ Settings"):
                    accordions = self._build_settings_tab(sd)

            # ── Event wiring ─────────────────────────────────────────
            submit_btn.click(
                fn=self._handle_message,
                inputs=[msg, chatbot],
                outputs=[chatbot, msg],
            )
            msg.submit(
                fn=self._handle_message,
                inputs=[msg, chatbot],
                outputs=[chatbot, msg],
            )
            stop_btn.click(fn=self._handle_stop)

        return demo

    # ── Capture region selector ──────────────────────────────────────

    def _build_capture_selector(self):
        """Build the 'Choose what to share' capture region picker."""

        labels, self._capture_map = get_capture_choices()

        # Separate screen vs window labels
        screen_labels = [l for l in labels if l.startswith("🖥️")]
        window_labels = [l for l in labels if l.startswith("🪟")]

        with gr.Accordion("🖥️ Choose what to capture", open=False):
            with gr.Tabs():
                with gr.Tab("Entire Screen"):
                    screen_radio = gr.Radio(
                        choices=screen_labels,
                        value=screen_labels[0] if screen_labels else None,
                        label='Select a screen',
                        info='Choose which screen to capture',
                    )
                    for lbl in screen_labels:
                        rect = self._capture_map.get(lbl)
                        if rect:
                            gr.Markdown(
                                f"&nbsp;&nbsp;&nbsp;**{lbl}** — "
                                f"Position: ({rect[0]}, {rect[1]}), "
                                f"Size: {rect[2]}×{rect[3]}",
                            )

                with gr.Tab("Window"):
                    if window_labels:
                        window_radio = gr.Radio(
                            choices=window_labels,
                            value=None,
                            label='Select a window',
                            info='Choose an application window to capture '
                                 '(Windows only)',
                        )
                    else:
                        window_radio = gr.Radio(
                            choices=[_NO_WINDOWS_LABEL],
                            value=None,
                            label='Select a window',
                            info='Window enumeration requires Windows OS. '
                                 'Use "Entire Screen" on other platforms.',
                            interactive=False,
                        )

            with gr.Row():
                refresh_btn = gr.Button(
                    "🔄 Refresh", size='sm',
                )
                share_btn = gr.Button(
                    "✅ Share", variant='primary', size='sm',
                )
                capture_status = gr.Markdown("")

            # ── Event wiring ─────────────────────────────────────
            share_btn.click(
                fn=self._apply_capture_selection,
                inputs=[screen_radio, window_radio],
                outputs=capture_status,
            )
            refresh_btn.click(
                fn=self._refresh_capture_choices,
                outputs=[screen_radio, window_radio],
            )

    def _apply_capture_selection(self, screen_sel, window_sel):
        """Apply the selected capture region to Core."""
        # Window selection takes priority if set
        selection = window_sel if (window_sel and window_sel != _NO_WINDOWS_LABEL) else screen_sel

        if not selection:
            return "⚠️ No selection made"

        rect = self._capture_map.get(selection)

        try:
            core = self.core
            core.set_capture_region(rect)
        except Exception as exc:
            return f"❌ Error: {exc}"

        if rect is None:
            return f"✅ Capturing: **Full Screen**"
        return (
            f"✅ Capturing: **{selection}**\n\n"
            f"Region: ({rect[0]}, {rect[1]}) — {rect[2]}×{rect[3]}"
        )

    def _refresh_capture_choices(self):
        """Re-enumerate screens and windows."""
        labels, self._capture_map = get_capture_choices()
        screen_labels = [l for l in labels if l.startswith("🖥️")]
        window_labels = [l for l in labels if l.startswith("🪟")]

        screen_update = gr.update(
            choices=screen_labels,
            value=screen_labels[0] if screen_labels else None,
        )

        if window_labels:
            window_update = gr.update(
                choices=window_labels,
                value=None,
                interactive=True,
            )
        else:
            window_update = gr.update(
                choices=[_NO_WINDOWS_LABEL],
                value=None,
                interactive=False,
            )

        return screen_update, window_update

    # ── Settings panel ───────────────────────────────────────────────

    def _build_settings_tab(self, sd: dict) -> list:
        """Build the categorised settings panel.  Returns accordion refs."""

        search_box = gr.Textbox(
            placeholder='🔍 Search settings…',
            show_label=False,
            container=False,
        )

        # ── LLM Mode & Provider ──────────────────────────────────────
        with gr.Accordion(
            "🤖 LLM Mode & Provider", open=True,
        ) as acc_llm:
            mode_radio = gr.Radio(
                LLM_MODES,
                value=sd.get('llm_mode', 'Single LLM'),
                label='LLM Mode',
                info=(
                    'Single: one LLM receives both screenshot and video.  '
                    'Dual: primary LLM gets screenshots, secondary gets '
                    'video for planning.'
                ),
            )
            with gr.Group():
                gr.Markdown("**Primary LLM**")
                provider_dd = gr.Dropdown(
                    PROVIDERS,
                    value=sd.get('provider', 'OpenAI'),
                    label='Provider',
                )
                model_tb = gr.Textbox(
                    value=sd.get('model', 'gpt-5.2'),
                    label='Model Name',
                    info='e.g. gpt-5.2, gemini-2.5-pro, '
                         'claude-sonnet-4-20250514, llama3.3',
                )

            with gr.Group(
                visible=(sd.get('llm_mode') == 'Dual LLM'),
            ) as dual_group:
                gr.Markdown(
                    "**Secondary LLM** (Dual mode — handles "
                    "video / planning)"
                )
                sec_provider_dd = gr.Dropdown(
                    PROVIDERS,
                    value=sd.get('secondary_provider', 'Gemini'),
                    label='Secondary Provider',
                )
                sec_model_tb = gr.Textbox(
                    value=sd.get(
                        'secondary_model', 'gemini-2.0-flash',
                    ),
                    label='Secondary Model Name',
                )

            mode_radio.change(
                fn=lambda m: gr.update(visible=(m == 'Dual LLM')),
                inputs=mode_radio,
                outputs=dual_group,
            )

        # ── API Keys ─────────────────────────────────────────────────
        with gr.Accordion("🔑 API Keys", open=True) as acc_keys:
            openai_key_tb = gr.Textbox(
                value=sd.get(
                    'openai_api_key', sd.get('api_key', ''),
                ),
                label='OpenAI API Key',
                type='password',
                info='For GPT-4o, GPT-5, etc.',
            )
            gemini_key_tb = gr.Textbox(
                value=sd.get('gemini_api_key', ''),
                label='Gemini API Key',
                type='password',
                info='For Gemini models',
            )
            claude_key_tb = gr.Textbox(
                value=sd.get('claude_api_key', ''),
                label='Claude API Key',
                type='password',
                info='For Claude models (Anthropic)',
            )
            openrouter_key_tb = gr.Textbox(
                value=sd.get('openrouter_api_key', ''),
                label='OpenRouter API Key',
                type='password',
                info='For any model via OpenRouter',
            )
            ollama_ep_tb = gr.Textbox(
                value=sd.get(
                    'ollama_endpoint', 'http://localhost:11434',
                ),
                label='Ollama Endpoint',
                info='Local Ollama server URL',
            )

        # ── General ──────────────────────────────────────────────────
        with gr.Accordion("🎛️ General", open=False) as acc_gen:
            base_url_tb = gr.Textbox(
                value=sd.get('base_url', ''),
                label='Custom API Base URL',
                info='Override the API endpoint (leave empty for '
                     'provider default)',
            )
            browser_dd = gr.Dropdown(
                BROWSERS,
                value=sd.get('default_browser', ''),
                label='Default Browser',
            )
            ding_cb = gr.Checkbox(
                value=sd.get('play_ding_on_completion', False),
                label='Play ding on completion',
            )
            instructions_ta = gr.Textbox(
                value=sd.get('custom_llm_instructions', ''),
                label='Custom LLM Instructions',
                lines=4,
                info='Additional context / instructions for the LLM',
            )

        # ── Storage ──────────────────────────────────────────────────
        with gr.Accordion("📁 Storage", open=False) as acc_store:
            buffer_dir_tb = gr.Textbox(
                value=sd.get('buffer_directory', ''),
                label='Buffer & Screenshot Directory',
                info='Where screenshots and video buffers are saved. '
                     'Leave empty for default (~/.open-interface/)',
            )
            retention_dd = gr.Dropdown(
                RETENTION_POLICIES,
                value=sd.get('retention_policy', 'Delete immediately'),
                label='File Retention Policy',
                info='How long to keep screenshots and buffer files',
            )

        # ── Advanced ─────────────────────────────────────────────────
        with gr.Accordion("⚡ Advanced", open=False) as acc_adv:
            fps_sl = gr.Slider(
                1, 10, step=1,
                value=int(sd.get('video_fps', 2)),
                label='Video FPS',
                info='Frames per second for video sent to API LLM',
            )
            interval_sl = gr.Slider(
                1, 10, step=1,
                value=int(sd.get('api_review_interval', 3)),
                label='API Review Interval (Dual mode)',
                info='Local steps between API LLM reviews',
            )
            md_ep_tb = gr.Textbox(
                value=sd.get(
                    'moondream_endpoint', 'http://localhost:2020/v1',
                ),
                label='Moondream Endpoint',
                info='Local Moondream Station URL',
            )

        # ── Debug & Test ─────────────────────────────────────────────
        with gr.Accordion("🐛 Debug & Test", open=False) as acc_dbg:
            debug_cb = gr.Checkbox(
                value=sd.get('debug_logging', False),
                label='Enable debug logging',
            )
            raw_cb = gr.Checkbox(
                value=sd.get('show_raw_responses', False),
                label='Show raw LLM responses',
            )
            test_cb = gr.Checkbox(
                value=sd.get('test_mode', False),
                label='Test mode (dry run — no commands executed)',
            )

        # ── Save ─────────────────────────────────────────────────────
        save_btn = gr.Button(
            "💾 Save Settings", variant='primary', size='lg',
        )
        save_status = gr.Markdown("")

        all_inputs = [
            mode_radio, provider_dd, model_tb,
            sec_provider_dd, sec_model_tb,
            openai_key_tb, gemini_key_tb, claude_key_tb,
            openrouter_key_tb, ollama_ep_tb,
            base_url_tb, browser_dd, ding_cb, instructions_ta,
            buffer_dir_tb, retention_dd,
            fps_sl, interval_sl, md_ep_tb,
            debug_cb, raw_cb, test_cb,
        ]
        save_btn.click(
            fn=self._save_settings,
            inputs=all_inputs,
            outputs=save_status,
        )

        # ── Search filter ────────────────────────────────────────────
        accordions = [
            acc_llm, acc_keys, acc_gen, acc_store, acc_adv, acc_dbg,
        ]
        search_box.change(
            fn=_filter_settings,
            inputs=search_box,
            outputs=accordions,
        )

        return accordions

    # ── Chat handler ─────────────────────────────────────────────────

    def _handle_message(self, message, history):
        """Stream status updates from Core into the chatbot."""
        if not message or not message.strip():
            yield history or [], ""
            return

        history = list(history or [])
        history.append({"role": "user", "content": message})
        history.append({
            "role": "assistant", "content": "🔄 Processing…",
        })
        yield history, ""

        # Initialise Core (may fail if settings are bad)
        try:
            core = self.core
        except Exception as exc:
            history[-1] = {
                "role": "assistant",
                "content": f"❌ Initialisation error: {exc}\n\n"
                           "Please check your settings.",
            }
            yield history, ""
            return

        self._stop_event.clear()

        thread = threading.Thread(
            target=core.execute_user_request,
            args=(message,),
            daemon=True,
        )
        thread.start()

        updates: list[str] = []
        while thread.is_alive():
            if self._stop_event.is_set():
                updates.append("⏹ Stopped by user")
                break
            try:
                status = core.status_queue.get(timeout=0.3)
                updates.append(str(status))
                history[-1] = {
                    "role": "assistant",
                    "content": "\n".join(updates),
                }
                yield history, ""
            except queue.Empty:
                continue

        # Drain any remaining messages
        while True:
            try:
                status = core.status_queue.get_nowait()
                updates.append(str(status))
            except queue.Empty:
                break

        if updates:
            history[-1] = {
                "role": "assistant",
                "content": "\n".join(updates),
            }
        else:
            history[-1] = {"role": "assistant", "content": "✅ Done"}

        yield history, ""

    # ── Stop handler ─────────────────────────────────────────────────

    def _handle_stop(self):
        self._stop_event.set()
        if self._core is not None:
            self._core.stop_previous_request()

    # ── Save settings ────────────────────────────────────────────────

    def _save_settings(
        self,
        mode, provider, model,
        sec_provider, sec_model,
        openai_key, gemini_key, claude_key, openrouter_key,
        ollama_ep,
        base_url, browser, ding, instructions,
        buffer_dir, retention,
        fps, interval, md_ep,
        debug, raw, test_mode,
    ):
        from utils.settings import Settings
        settings = Settings()

        d = {
            'llm_mode': mode,
            'provider': provider,
            'model': model,
            'secondary_provider': sec_provider,
            'secondary_model': sec_model,
            'openai_api_key': openai_key,
            'gemini_api_key': gemini_key,
            'claude_api_key': claude_key,
            'openrouter_api_key': openrouter_key,
            'ollama_endpoint': ollama_ep,
            'base_url': base_url,
            'default_browser': browser,
            'play_ding_on_completion': ding,
            'custom_llm_instructions': instructions,
            'buffer_directory': buffer_dir,
            'retention_policy': retention,
            'video_fps': int(fps),
            'api_review_interval': int(interval),
            'moondream_endpoint': md_ep,
            'debug_logging': debug,
            'show_raw_responses': raw,
            'test_mode': test_mode,
        }

        # Backward compat: mirror the selected provider's key as api_key
        _provider_key_map = {
            'OpenAI': openai_key,
            'Gemini': gemini_key,
            'Claude': claude_key,
            'OpenRouter': openrouter_key,
        }
        legacy_key = _provider_key_map.get(provider, '')
        if legacy_key:
            d['api_key'] = legacy_key

        settings.save_settings_to_file(d)

        # Reset Core so new settings take effect on next request
        if self._core is not None:
            try:
                self._core.cleanup()
            except Exception:
                pass
            self._core = None

        return "✅ Settings saved! New settings apply on the next request."


# ── Module-level helpers ─────────────────────────────────────────────

def _filter_settings(query: str):
    """Hide/show accordion sections based on a search query."""
    if not query or not query.strip():
        return [gr.update(visible=True)] * len(_SEARCH_KEYWORDS)
    q = query.lower().strip()
    return [
        gr.update(visible=any(kw in q for kw in kws))
        for kws in _SEARCH_KEYWORDS
    ]
