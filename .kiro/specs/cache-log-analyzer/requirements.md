# Requirements Document

## Introduction

A standalone Python maintenance/diagnostic script (`sc/cache_log_analyzer.py`) that performs two housekeeping tasks and one AI-assisted analysis task in sequence:

1. **Cache cleanup** — removes `__pycache__` directories and `.pyc` files from the project tree, skipping `.venv/` and `.git/`.
2. **Log scanning** — reads every log file under `data/log/`, collects lines that contain `ERROR`, `CRITICAL`, or `WARNING` level markers, and also flags lines that match a configurable set of anomaly keywords.
3. **AI analysis** — sends the collected events to a local Ollama model via `/api/chat` and saves the model's Markdown-formatted analysis to `data/app_event_analysis.md`.

The script is runnable as `python sc/cache_log_analyzer.py` from the project root and depends only on Python stdlib, `requests`, and `python-dotenv`.

## Glossary

- **Script**: The standalone file `sc/cache_log_analyzer.py`.
- **Project_Root**: The directory from which the Script is invoked (i.e. the working directory).
- **Cache_Target**: Any `__pycache__` directory or `.pyc` file found under Project_Root, excluding paths inside `.venv/` or `.git/`.
- **Log_Dir**: `data/log/` relative to Project_Root.
- **Log_File**: Any file inside Log_Dir (e.g. `app.log`, `services.log`, `ui.log`, rotated variants like `app.log.1`).
- **Event_Line**: A line from a Log_File whose level field is `ERROR`, `CRITICAL`, or `WARNING`, or whose text matches an Anomaly_Keyword.
- **Anomaly_Keyword**: A configurable string whose presence in a log line signals an unusual condition (e.g. `"Traceback"`, `"Exception"`, `"exit code"`).
- **Event_Collection**: The aggregated list of Event_Lines gathered from all Log_Files.
- **Ollama_Server**: The local Ollama inference server at the URL defined by `OLLAMA_BASE_URL` (default: `http://localhost:11434`).
- **Model**: The Ollama model name defined by `OLLAMA_MODEL` (default: `llama3`).
- **Report_File**: `data/app_event_analysis.md` — the Markdown file written by the Script.

---

## Requirements

### Requirement 1: Cache Cleanup

**User Story:** As a developer, I want stale Python bytecode removed automatically, so that the project tree stays clean without manual intervention.

#### Acceptance Criteria

1. WHEN the Script runs, IT SHALL walk the Project_Root directory tree and delete every `__pycache__` directory found.
2. WHEN the Script runs, IT SHALL delete every `.pyc` file found under Project_Root.
3. THE Script SHALL skip any path whose components include `.venv` or `.git`.
4. WHEN a Cache_Target is deleted, THE Script SHALL print a confirmation message to stdout naming the deleted path.
5. WHEN no Cache_Targets are found, THE Script SHALL print a message stating that no cache files were found.

---

### Requirement 2: Log Scanning

**User Story:** As a developer, I want the script to collect all warnings, errors, and anomalies from the application logs, so that I have a focused set of events to review.

#### Acceptance Criteria

1. WHEN the Script runs, IT SHALL open and read every file in Log_Dir.
2. FOR each line in a Log_File, IF the line contains the substring `ERROR`, `CRITICAL`, or `WARNING` (case-sensitive), THEN IT SHALL be added to the Event_Collection.
3. FOR each line in a Log_File, IF the line contains any Anomaly_Keyword (case-insensitive), THEN IT SHALL be added to the Event_Collection, even if it does not match a level marker.
4. THE default Anomaly_Keywords SHALL include at least: `"Traceback"`, `"Exception"`, `"exit code"`, `"failed"`, `"timeout"`, `"connection refused"`.
5. WHEN a Log_File cannot be opened or read, THE Script SHALL print a warning to stdout and continue processing remaining files.
6. WHEN the Event_Collection is empty after scanning all Log_Files, THE Script SHALL print a message stating no events were found and SHALL skip the AI analysis step.

---

### Requirement 3: AI Analysis via Ollama

**User Story:** As a developer, I want the collected events sent to a local AI model for analysis, so that I get an actionable summary without reading raw logs manually.

#### Acceptance Criteria

1. WHEN the Event_Collection is non-empty, THE Script SHALL send a POST request to `{OLLAMA_BASE_URL}/api/chat` with `"stream": false`.
2. THE request body SHALL include a system prompt instructing the Model to act as a senior developer analysing application log events and to produce a structured Markdown report.
3. THE request body SHALL include the full Event_Collection as the user message content.
4. WHEN the Ollama_Server returns a successful response (HTTP 200), THE Script SHALL extract the assistant message content from the response JSON.
5. IF the POST request raises a connection error or returns a non-200 HTTP status, THE Script SHALL print a human-readable error message to stdout and SHALL NOT raise an unhandled exception.
6. THE Script SHALL NOT require streaming; `"stream": false` SHALL always be set.

---

### Requirement 4: Report Generation

**User Story:** As a developer, I want the AI analysis saved as a Markdown file, so that I can review it later without re-running the script.

#### Acceptance Criteria

1. WHEN the AI analysis succeeds, THE Script SHALL write the assistant message content to Report_File, overwriting any previous content.
2. THE Report_File SHALL begin with a header line containing the generation timestamp (e.g. `# App Event Analysis Report\nGenerated: YYYY-MM-DD`).
3. WHEN the Report_File is written successfully, THE Script SHALL print a confirmation message to stdout stating the file path.
4. IF writing the Report_File fails (e.g. permission error), THE Script SHALL print an error message to stdout and SHALL NOT raise an unhandled exception.

---

### Requirement 5: Configuration and Standalone Execution

**User Story:** As a developer, I want to run the script from the project root with a single command and have it pick up my existing environment settings, so that no extra configuration is needed.

#### Acceptance Criteria

1. THE Script SHALL be executable as `python sc/cache_log_analyzer.py` from the Project_Root without importing any module from the `app/` package.
2. THE Script SHALL read `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from environment variables, falling back to `http://localhost:11434` and `llama3` respectively when the variables are absent.
3. WHERE a `.env` file exists in the Project_Root, THE Script SHALL load it using `python-dotenv` before reading environment variables.
4. THE Script SHALL use only Python standard library modules plus `requests` and `python-dotenv`.
5. THE Script SHALL execute its three phases (cache cleanup → log scanning → AI analysis) in order and SHALL print a clear phase header to stdout before each phase.
