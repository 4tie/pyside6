# Requirements Document

## Introduction

A standalone Tkinter desktop chat application (`sc/tk_log_chat.py`) that lets a developer paste or type error messages and log text, then sends the input to a local Ollama AI model and displays the model's explanation in a chat-style UI. The app is runnable from the project root as `python sc/tk_log_chat.py` and requires no application bootstrap beyond `requests` and `python-dotenv` (both already in the project's `requirements.txt`).

## Glossary

- **App**: The Tkinter desktop application defined in `sc/tk_log_chat.py`.
- **Chat_Window**: The scrollable read-only text area that displays the conversation history.
- **Input_Area**: The multi-line editable text widget where the user types or pastes log/error content.
- **Send_Button**: The UI control that submits the current Input_Area content to the AI_Client.
- **AI_Client**: The component responsible for communicating with the Ollama HTTP API.
- **Ollama_Server**: The local Ollama inference server reachable at the URL defined by the `OLLAMA_BASE_URL` environment variable (default: `http://localhost:11434`).
- **Model**: The Ollama model name defined by the `OLLAMA_MODEL` environment variable (default: `llama3`).
- **User_Message**: Text submitted by the user from the Input_Area.
- **Assistant_Message**: The AI explanation returned by the Ollama_Server.
- **Project_Root**: The directory from which the App is invoked.

---

## Requirements

### Requirement 1: Application Layout

**User Story:** As a developer, I want a clean two-panel chat window, so that I can read the AI's explanation while still seeing my input.

#### Acceptance Criteria

1. WHEN the App starts, THE App SHALL display a single window titled "Log & Error Chat".
2. THE App SHALL render a Chat_Window occupying the upper portion of the window that displays the conversation history in chronological order.
3. THE App SHALL render an Input_Area below the Chat_Window where the user can type or paste multi-line text.
4. THE App SHALL render a Send_Button adjacent to the Input_Area that submits the current input.
5. THE App SHALL set a minimum window size of 700 × 500 pixels so that both panels are usable without resizing.

---

### Requirement 2: Sending a Message

**User Story:** As a developer, I want to submit my log or error text with a single action, so that I can get an explanation quickly.

#### Acceptance Criteria

1. WHEN the user activates the Send_Button, THE App SHALL read the full text content of the Input_Area as the User_Message.
2. IF the User_Message is empty or contains only whitespace, THEN THE App SHALL take no action and SHALL keep focus on the Input_Area.
3. WHEN a non-empty User_Message is submitted, THE App SHALL append the User_Message to the Chat_Window prefixed with a "You:" label.
4. WHEN a non-empty User_Message is submitted, THE App SHALL clear the Input_Area.
5. WHEN a non-empty User_Message is submitted, THE App SHALL disable the Send_Button and SHALL display a "Thinking…" status indicator in the Chat_Window until the Assistant_Message is received.
6. WHEN the user presses Ctrl+Enter while the Input_Area has focus, THE App SHALL trigger the same submission behaviour as activating the Send_Button.

---

### Requirement 3: AI Communication

**User Story:** As a developer, I want the app to send my input to the local Ollama model and retrieve an explanation, so that I understand what the error or log means.

#### Acceptance Criteria

1. WHEN a User_Message is submitted, THE AI_Client SHALL send a POST request to `{OLLAMA_BASE_URL}/api/chat` with `"stream": false`, including a system prompt that instructs the Model to act as a senior developer explaining errors and logs in plain language with actionable fix steps.
2. THE AI_Client SHALL include the full conversation history (all prior User_Messages and Assistant_Messages) in the messages array so that follow-up questions retain context.
3. WHEN the Ollama_Server returns a successful response, THE AI_Client SHALL extract the assistant content and return it as the Assistant_Message.
4. IF the POST request raises a connection error or returns a non-200 HTTP status, THEN THE AI_Client SHALL return a human-readable error string describing the failure instead of raising an exception.
5. THE AI_Client SHALL perform the HTTP request on a background thread so that THE App UI remains responsive during the request.

---

### Requirement 4: Displaying the Response

**User Story:** As a developer, I want the AI's explanation shown clearly in the chat history, so that I can read and scroll through it easily.

#### Acceptance Criteria

1. WHEN an Assistant_Message is received, THE App SHALL append it to the Chat_Window prefixed with an "AI:" label.
2. WHEN an Assistant_Message is appended, THE App SHALL automatically scroll the Chat_Window to the bottom so the latest message is visible.
3. WHEN an Assistant_Message is received, THE App SHALL re-enable the Send_Button and SHALL remove the "Thinking…" status indicator.
4. THE Chat_Window SHALL visually distinguish User_Messages from Assistant_Messages using different text colours or font weights.
5. THE Chat_Window SHALL be read-only; the user SHALL NOT be able to edit its contents directly.

---

### Requirement 5: Ollama Availability Check

**User Story:** As a developer, I want a clear message when Ollama is not running, so that I know immediately what to fix rather than seeing a cryptic error.

#### Acceptance Criteria

1. WHEN the App starts, THE AI_Client SHALL perform a health check by sending a GET request to `{OLLAMA_BASE_URL}/api/tags`.
2. IF the health check returns a non-200 HTTP status or raises a connection error, THEN THE App SHALL display a warning message in the Chat_Window explaining that the Ollama_Server is not reachable and stating the URL that was tried.
3. WHEN the health check succeeds, THE App SHALL display a ready message in the Chat_Window confirming the connected Model name.
4. IF the health check fails, THEN THE Send_Button SHALL remain enabled so the user can retry after starting Ollama.

---

### Requirement 6: Configuration and Standalone Execution

**User Story:** As a developer, I want to run the app from the project root with a single command and have it pick up my existing environment settings, so that no extra configuration is needed.

#### Acceptance Criteria

1. THE App SHALL be executable as `python sc/tk_log_chat.py` from the Project_Root without importing any module from the `app/` package.
2. THE App SHALL read `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from environment variables, falling back to `http://localhost:11434` and `llama3` respectively when the variables are absent.
3. WHERE a `.env` file exists in the Project_Root, THE App SHALL load it using `python-dotenv` before reading environment variables.
4. THE App SHALL use only Python standard library modules plus `requests` and `python-dotenv`.
