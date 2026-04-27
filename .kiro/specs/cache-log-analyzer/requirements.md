# Requirements Document

## Introduction

A standalone Python maintenance and diagnostic script (`sc/cache_log_analyzer.py`) for the FreqTrade GUI trading bot assistant. The script performs three coordinated tasks: cleaning Python cache artifacts from the project tree, scanning all application log files in `data/log/` for errors and anomalous entries, and submitting a structured summary to a local Ollama model to produce a human-friendly analysis with actionable fix instructions. The final analysis is saved to `data/app_event_analysis.md` and printed to the terminal. The script is runnable from the project root without any application bootstrap.

## Glossary

- **Script**: The standalone Python file `sc/cache_log_analyzer.py`.
- **Cache_Cleaner**: The component of the Script responsible for removing `__pycache__` directories and `.pyc` files.
- **Log_Scanner**: The component of the Script responsible for reading and filtering log files.
- **Log_Entry**: A single line from a log file conforming to the format `YYYY-MM-DD HH:MM:SS.mmm | LEVEL | name | message`.
- **Error_Entry**: A Log_Entry whose level is `ERROR` or `CRITICAL`.
- **Unusual_Entry**: A Log_Entry whose level is `WARNING`, or whose message contains a known anomaly keyword (e.g., `exception`, `traceback`, `timeout`, `failed`, `refused`).
- **AI_Analyzer**: The component of the Script that calls the Ollama HTTP API to generate the analysis.
- **Analysis_Report**: The Markdown document produced by the AI_Analyzer and saved to `data/app_event_analysis.md`.
- **Ollama_Server**: The local Ollama inference server reachable at the URL defined by the `OLLAMA_BASE_URL` environment variable (default: `http://localhost:11434`).
- **Project_Root**: The directory from which the Script is invoked.

---

## Requirements

### Requirement 1: Cache Cleaning

**User Story:** As a developer, I want the script to remove all `__pycache__` directories and `.pyc` files from the project, so that stale bytecode does not interfere with development or testing.

#### Acceptance Criteria

1. WHEN the Script is executed, THE Cache_Cleaner SHALL recursively find and delete all `__pycache__` directories under the Project_Root, excluding `.venv/` and `.git/` subtrees.
2. WHEN the Script is executed, THE Cache_Cleaner SHALL recursively find and delete all `.pyc` files under the Project_Root, excluding `.venv/` and `.git/` subtrees.
3. WHEN a `__pycache__` directory or `.pyc` file is successfully deleted, THE Cache_Cleaner SHALL print a confirmation line to stdout identifying the removed path.
4. WHEN the Script completes cache cleaning, THE Cache_Cleaner SHALL print a summary line stating the total count of directories and files removed.
5. IF a path cannot be deleted due to a permission error, THEN THE Cache_Cleaner SHALL print a warning identifying the path and the reason, and SHALL continue processing remaining paths.

---

### Requirement 2: Log File Discovery and Parsing

**User Story:** As a developer, I want the script to discover and parse all log files in `data/log/`, so that I have a complete picture of application events without manually opening each file.

#### Acceptance Criteria

1. WHEN the Script is executed, THE Log_Scanner SHALL discover all files matching `*.log` and `*.log.*` in the `data/log/` directory relative to the Project_Root.
2. WHEN a log file is discovered, THE Log_Scanner SHALL parse each line into a structured Log_Entry containing timestamp, level, logger name, and message.
3. IF a line does not match the expected Log_Entry format, THEN THE Log_Scanner SHALL skip that line without raising an exception.
4. THE Log_Scanner SHALL collect all Error_Entries and Unusual_Entries from all discovered log files into a single ordered list, preserving original timestamp order.
5. WHEN no log files are found in `data/log/`, THE Log_Scanner SHALL print a warning to stdout and SHALL proceed to the AI_Analyzer phase with an empty entry list.

---

### Requirement 3: Error and Anomaly Detection

**User Story:** As a developer, I want the script to identify errors and unusual calls in the logs, so that I can quickly focus on what needs attention.

#### Acceptance Criteria

1. THE Log_Scanner SHALL classify a Log_Entry as an Error_Entry WHEN its level field is `ERROR` or `CRITICAL`.
2. THE Log_Scanner SHALL classify a Log_Entry as an Unusual_Entry WHEN its level field is `WARNING`.
3. THE Log_Scanner SHALL classify a Log_Entry as an Unusual_Entry WHEN its message field contains any of the following substrings (case-insensitive): `exception`, `traceback`, `timeout`, `failed`, `refused`, `connection error`, `not found`.
4. WHEN the Log_Scanner finishes scanning, THE Log_Scanner SHALL print a summary to stdout stating the total count of Error_Entries and Unusual_Entries found across all log files.
5. WHERE the total count of collected entries exceeds 200, THE Log_Scanner SHALL truncate the list to the 200 most recent entries before passing them to the AI_Analyzer, and SHALL note the truncation in the summary.

---

### Requirement 4: Ollama Availability Check

**User Story:** As a developer, I want the script to verify that Ollama is reachable before attempting analysis, so that I receive a clear message instead of a cryptic connection error.

#### Acceptance Criteria

1. BEFORE sending the analysis request, THE AI_Analyzer SHALL perform a health check by sending a GET request to `{OLLAMA_BASE_URL}/api/tags`.
2. IF the health check returns a non-200 HTTP status or raises a connection error, THEN THE AI_Analyzer SHALL print a human-readable error message explaining that Ollama is not reachable, SHALL skip the AI analysis phase, and SHALL save a partial Analysis_Report containing only the cache cleaning summary and log scan results.
3. WHEN the health check succeeds, THE AI_Analyzer SHALL list available models from the Ollama server and SHALL select the model specified by the `OLLAMA_MODEL` environment variable (default: `llama3`).
4. IF the requested model is not present in the available model list, THEN THE AI_Analyzer SHALL print a warning listing available models and SHALL proceed using the first available model.
5. IF no models are available on the Ollama server, THEN THE AI_Analyzer SHALL skip the AI analysis phase and SHALL save a partial Analysis_Report.

---

### Requirement 5: AI-Powered Log Analysis

**User Story:** As a developer, I want the script to send collected log events to an Ollama model and receive a human-friendly analysis, so that I understand what happened and how to fix any issues.

#### Acceptance Criteria

1. WHEN the AI_Analyzer sends a request, THE AI_Analyzer SHALL construct a prompt containing: the cache cleaning summary, the count of errors and warnings found, and the full text of all collected Error_Entries and Unusual_Entries.
2. THE AI_Analyzer SHALL instruct the model via the system prompt to act as a senior Python developer reviewing application logs, to explain each issue in plain language, and to provide numbered fix instructions for each identified problem.
3. WHEN the Ollama server returns a successful response, THE AI_Analyzer SHALL extract the response content and include it verbatim in the Analysis_Report.
4. IF the Ollama request raises an exception or returns a non-200 status, THEN THE AI_Analyzer SHALL print the error to stdout and SHALL save a partial Analysis_Report noting the AI analysis failure.
5. THE AI_Analyzer SHALL use a blocking (non-streaming) POST to `{OLLAMA_BASE_URL}/api/chat` with `"stream": false`, matching the pattern used by `app/core/ai/providers/ollama_provider.py`.

---

### Requirement 6: Analysis Report Generation

**User Story:** As a developer, I want the analysis saved to a file, so that I can review it later or share it with teammates.

#### Acceptance Criteria

1. WHEN the Script completes all phases, THE Script SHALL write the Analysis_Report to `data/app_event_analysis.md` relative to the Project_Root, overwriting any existing file.
2. THE Analysis_Report SHALL be a valid Markdown document containing: a header with the run timestamp, a cache cleaning summary section, a log scan summary section listing counts per log file, an errors and warnings section listing each collected entry, and an AI analysis section with the model's response.
3. WHEN the Analysis_Report is successfully written, THE Script SHALL print the absolute path of the saved file to stdout.
4. IF the `data/` directory does not exist, THEN THE Script SHALL create it before writing the Analysis_Report.
5. THE Script SHALL also print the full AI analysis text to stdout after saving the file, so the developer can read it without opening the file.

---

### Requirement 7: Standalone Execution

**User Story:** As a developer, I want to run the script from the project root with a single command, so that I don't need to configure anything beyond having Ollama running.

#### Acceptance Criteria

1. THE Script SHALL be executable as `python sc/cache_log_analyzer.py` from the Project_Root without requiring any application imports from the `app/` package.
2. THE Script SHALL read `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from environment variables, falling back to `http://localhost:11434` and `llama3` respectively when the variables are absent.
3. WHERE a `.env` file exists in the Project_Root, THE Script SHALL load it using `python-dotenv` before reading environment variables, so that project-level configuration is respected.
4. THE Script SHALL use only Python standard library modules plus `requests` and `python-dotenv`, both of which are already present in the project's `requirements.txt`.
5. WHEN the Script starts, THE Script SHALL print a banner to stdout identifying the tool name, the Ollama base URL in use, and the target model name.
