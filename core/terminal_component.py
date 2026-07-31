import streamlit as st


_TERMINAL_HTML = """
<div class="terminal">
  <div class="toolbar">
    <span class="dots"><i></i><i></i><i></i></span>
    <span class="title"></span>
    <button class="expand" title="Fullscreen">⛶</button>
  </div>
  <div class="screen">
    <pre class="scrollback"></pre>
    <div class="prompt-row">
      <span class="prompt"></span>
      <input class="command" autocomplete="off" autocapitalize="off" spellcheck="false">
    </div>
  </div>
  <div class="status">Enter: execute · ↑/↓: history · clear: clear this terminal</div>
</div>
"""


_TERMINAL_CSS = """
* { box-sizing: border-box; }
:host { display: block; width: 100%; height: 100%; }
.terminal {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #263445;
  border-radius: 8px;
  background: #05080c;
  color: #d9f7df;
  font: 14px/1.5 SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.toolbar {
  height: 34px;
  flex: 0 0 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid #263445;
  background: #111720;
}
.dots { display: flex; gap: 6px; }
.dots i { display: block; width: 10px; height: 10px; border-radius: 50%; }
.dots i:nth-child(1) { background: #ff5f57; }
.dots i:nth-child(2) { background: #febc2e; }
.dots i:nth-child(3) { background: #28c840; }
.title { color: #94a4b8; font-size: 12px; }
.expand {
  border: 0;
  background: transparent;
  color: #b8c5d6;
  cursor: pointer;
  font-size: 17px;
}
.screen {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
  cursor: text;
}
.scrollback {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: #d9f7df;
  font: inherit;
}
.prompt-row { display: flex; align-items: center; gap: 8px; min-height: 25px; }
.prompt { color: #6fe58d; white-space: nowrap; font-weight: 600; }
.command {
  flex: 1;
  min-width: 3rem;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #f2f7fb;
  caret-color: #65ff8d;
  font: inherit;
}
.status { padding: 0 12px 8px; color: #7d8da3; font-size: 11px; }
:host(:fullscreen) .terminal { border: 0; border-radius: 0; }
"""


_TERMINAL_JS = """
export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const terminal = parentElement.querySelector(".terminal");
  const title = parentElement.querySelector(".title");
  const screen = parentElement.querySelector(".screen");
  const scrollback = parentElement.querySelector(".scrollback");
  const prompt = parentElement.querySelector(".prompt");
  const command = parentElement.querySelector(".command");
  const expand = parentElement.querySelector(".expand");
  const history = Array.isArray(data.history) ? data.history : [];
  let historyIndex = history.length;

  title.textContent = data.title || "Kubernetes Simulator Terminal";
  scrollback.textContent = data.transcript || "";
  prompt.textContent = data.prompt || "$";
  command.value = "";
  command.disabled = false;

  const submit = () => {
    const value = command.value.trim();
    if (!value) return;
    command.disabled = true;
    setTriggerValue("submitted", {
      command: value,
      nonce: `${Date.now()}-${Math.random()}`,
    });
  };
  const onKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    } else if (event.key === "ArrowUp" && history.length) {
      event.preventDefault();
      historyIndex = Math.max(0, historyIndex - 1);
      command.value = history[historyIndex];
      command.setSelectionRange(command.value.length, command.value.length);
    } else if (event.key === "ArrowDown" && history.length) {
      event.preventDefault();
      historyIndex = Math.min(history.length, historyIndex + 1);
      command.value = historyIndex === history.length ? "" : history[historyIndex];
    }
  };
  const focusCommand = () => command.focus();
  const toggleFullscreen = async (event) => {
    event.stopPropagation();
    if (!document.fullscreenElement) await parentElement.requestFullscreen();
    else await document.exitFullscreen();
    command.focus();
  };

  command.addEventListener("keydown", onKeyDown);
  terminal.addEventListener("click", focusCommand);
  expand.addEventListener("click", toggleFullscreen);
  requestAnimationFrame(() => {
    screen.scrollTop = screen.scrollHeight;
    command.focus();
  });

  return () => {
    command.removeEventListener("keydown", onKeyDown);
    terminal.removeEventListener("click", focusCommand);
    expand.removeEventListener("click", toggleFullscreen);
  };
}
"""


_TERMINAL_COMPONENT = st.components.v2.component(
    "kubernetes_simulator_terminal",
    html=_TERMINAL_HTML,
    css=_TERMINAL_CSS,
    js=_TERMINAL_JS,
    isolate_styles=True,
)


def terminal_component(key, title, prompt, transcript, history):
    return _TERMINAL_COMPONENT(
        key=key,
        data={
            "title": title,
            "prompt": prompt,
            "transcript": transcript,
            "history": history,
        },
        default={"submitted": None},
        height=640,
        on_submitted_change=lambda: None,
    )
