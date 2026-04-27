# Tasks

## Task List

- [ ] 1. Create script skeleton and environment loading
  - [ ] 1.1 Create `sc/tk_log_chat.py` with module docstring, `load_env()`, module-level `OLLAMA_BASE_URL` / `OLLAMA_MODEL` constants with fallbacks, and `if __name__ == "__main__"` guard that calls `load_env()` and launches the app
  - [ ] 1.2 Implement `load_env()`: call `dotenv.load_dotenv()` and read `OLLAMA_BASE_URL` (default `http://localhost:11434`) and `OLLAMA_MODEL` (default `llama3`) from environment variables into module-level constants

- [ ] 2. Implement OllamaClient
  - [ ] 2.1 Implement `OllamaClient.__init__`: initialise `self.history = []`
  - [ ] 2.2 Implement `OllamaClient.health_check() -> tuple[bool, str]`: GET `{OLLAMA_BASE_URL}/api/tags`; return `(True, ready_message)` on HTTP 200, `(False, error_message_with_url)` on connection error or non-200 status; never raise
  - [ ] 2.3 Implement `OllamaClient.chat(user_message: str) -> str`: append user message to `self.history`, build POST payload with system prompt + full history, POST to `{OLLAMA_BASE_URL}/api/chat` with `"stream": false`, extract `message.content` from response, append assistant reply to `self.history`, return reply; on any error (connection, non-200, malformed JSON) return a human-readable error string without raising

- [ ] 3. Implement ChatApp UI
  - [ ] 3.1 Implement `ChatApp.__init__(root, client)`: store references, call `_build_ui()`, then start health check on a background thread
  - [ ] 3.2 Implement `ChatApp._build_ui()`: create Chat_Window (`tk.Text`, `state=DISABLED`, `wrap=WORD`) with vertical scrollbar filling the upper area; create Input_Area (`tk.Text`, `height=5`) and Send_Button (`ttk.Button`) in the lower area; set window title to "Log & Error Chat"; set `root.minsize(700, 500)`; bind Ctrl+Enter on Input_Area to `_on_send`; bind Send_Button command to `_on_send`
  - [ ] 3.3 Implement `ChatApp._append_message(role, text)`: temporarily set Chat_Window to `NORMAL`, insert formatted text with the appropriate color tag (`user` → blue `#1a73e8`, `ai` → green `#2e7d32`, `system` → grey `#757575`), set back to `DISABLED`, call `_scroll_to_bottom()`
  - [ ] 3.4 Implement `ChatApp._scroll_to_bottom()`: set Chat_Window yview to `tk.END`
  - [ ] 3.5 Implement `ChatApp._health_check()`: run `client.health_check()` on a background thread; use `root.after(0, ...)` to call `_append_message` with the result on the main thread
  - [ ] 3.6 Implement `ChatApp._on_send(event=None)`: read Input_Area content; if empty/whitespace-only return immediately keeping focus on Input_Area; otherwise append "You: <message>" to Chat_Window, clear Input_Area, disable Send_Button, append "Thinking…" system message, then dispatch `client.chat(message)` on a background thread with `root.after(0, _on_response)` as callback
  - [ ] 3.7 Implement `ChatApp._on_response(reply)`: remove "Thinking…" from Chat_Window, append "AI: <reply>" via `_append_message`, re-enable Send_Button

- [ ] 4. Unit tests
  - [ ] 4.1 Write example-based tests for `OllamaClient.health_check`: mocked 200 returns `(True, message)`; mocked connection error returns `(False, message)` containing the URL; mocked non-200 returns `(False, message)`
  - [ ] 4.2 Write example-based tests for `OllamaClient.chat`: mocked 200 returns assistant content; mocked connection error returns error string without raising; mocked 500 returns error string; malformed JSON returns error string
  - [ ] 4.3 Write example-based tests for `ChatApp._on_send`: empty Input_Area → Chat_Window unchanged, no HTTP call; whitespace-only → same; valid text → Send_Button disabled and "Thinking…" in Chat_Window
  - [ ] 4.4 Write example-based tests for `ChatApp._on_response`: Send_Button re-enabled; "Thinking…" removed; AI reply appears in Chat_Window with "AI:" prefix
  - [ ] 4.5 Write example-based tests for UI configuration: window title is "Log & Error Chat"; minsize is (700, 500); Chat_Window state is DISABLED; Ctrl+Enter triggers `_on_send`; Send_Button command triggers `_on_send`
  - [ ] 4.6 Write example-based test for `.env` loading: create temp `.env` with custom values, verify module constants reflect them

- [ ] 5. Property-based tests (Hypothesis)
  - [ ] 5.1 P1 — Non-empty input echoed with "You:" prefix: generate random non-empty non-whitespace strings, simulate submission, assert Chat_Window contains "You: <text>"
  - [ ] 5.2 P2 — Whitespace-only input rejected: generate whitespace-only strings, assert no Chat_Window append and no HTTP call made
  - [ ] 5.3 P3 — POST payload well-formed for any user message: generate random messages, capture POST payload via mock, assert `stream==False`, correct model, system role first, user role last with correct content
  - [ ] 5.4 P4 — Full conversation history included in every request: generate random sequences of user/assistant pairs, assert next POST payload contains all prior pairs in order
  - [ ] 5.5 P5 — Assistant content correctly extracted from any valid response: generate random `message.content` strings in valid Ollama response JSON, assert `OllamaClient.chat` returns that exact string
  - [ ] 5.6 P6 — Any AI_Client failure returns a string, never raises: generate connection errors and non-200 status codes, assert `OllamaClient.chat` returns non-empty string without raising
  - [ ] 5.7 P7 — Assistant reply echoed with "AI:" prefix: generate random reply strings, simulate response, assert Chat_Window contains "AI: <reply>"
  - [ ] 5.8 P8 — Health check failure shows attempted URL: generate random base URLs, simulate health check failure, assert Chat_Window message contains that URL
  - [ ] 5.9 P9 — Health check success shows model name: generate random model name strings, simulate successful health check, assert Chat_Window ready message contains the model name
  - [ ] 5.10 P10 — Environment variable fallback correctness: test all four combinations of OLLAMA_BASE_URL / OLLAMA_MODEL presence/absence, assert resolved values match env var or default
