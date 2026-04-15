# Freqtrade GUI - First Slice Foundation

This is the foundational layer of the Freqtrade GUI application built with PySide6. It implements:
- Settings management (load/save/validate)
- Process execution with live terminal output
- Freqtrade command building and execution
- Qt-based UI with Settings and Terminal tabs

## Architecture

### Core Services

**app/core/models/settings_models.py**
- `AppSettings`: Main configuration model with path normalization
- `SettingsValidationResult`: Validation result with structured output
- `ProcessOutput`: Process execution output wrapper

**app/core/services/settings_service.py**
- Loads/saves settings from `~/.freqtrade_gui/settings.json`
- Validates Python and Freqtrade availability
- Resolves executable paths from venv

**app/core/services/process_service.py**
- QProcess wrapper for command execution
- Live stdout/stderr streaming
- Process lifecycle management (stop, kill)

**app/core/freqtrade/command_runner.py**
- Builds freqtrade commands with fallback logic:
  - Preferred: `python -m freqtrade`
  - Fallback: direct `freqtrade` executable
- Supports: version check, backtesting, data download

### State Management

**app/app_state/settings_state.py**
- Qt QObject with signals for reactive updates
- Handles: load, save, validation, updates

### UI Components

**app/ui/widgets/terminal_widget.py**
- Live command output display
- Stop button for process control
- Clear & status controls
- Signals: `process_started`, `process_finished`, `output_received`, `error_received`

**app/ui/pages/settings_page.py**
- Venv path selector with auto-resolution
- Python & Freqtrade path preview
- User data & project path management
- Validate & Save buttons

**app/ui/main_window.py**
- Tab-based interface (Settings | Terminal)
- Quick action buttons:
  - Check Python
  - Check Freqtrade
  - Freqtrade --version

## Setup

### Requirements
- Python 3.9+
- PySide6
- Pydantic 2.0+

### Installation

1. Create virtual environment:
```bash
python -m venv .venv
```

2. Activate it:
```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the app:
```bash
python main.py
```

## First Workflow

The app currently supports this workflow:

1. **Settings Tab**
   - Choose your `.venv` directory (or freqtrade project venv)
   - Set User Data path
   - Click "Validate Settings" → confirms Python & Freqtrade work
   - Click "Save Settings" → persists to `~/.freqtrade_gui/settings.json`

2. **Terminal Tab**
   - Click "Check Python" → runs `python --version`
   - Click "Check Freqtrade" → runs `freqtrade --version`
   - View live output with syntax highlighting (errors in red)
   - Click "Stop" to kill process
   - Click "Clear" to clear output

3. **Settings Persistence**
   - Settings auto-load from `~/.freqtrade_gui/settings.json`
   - Changes persist across app restarts

## Design Decisions

### No Shell Activation
The app does NOT use `source activate` or `activate.bat`. Instead, it:
- Resolves Python/Freqtrade paths explicitly
- Injects `VIRTUAL_ENV` and `PATH` into QProcess environment
- Ensures reliability for app-owned commands

### Command Building Fallback
For robustness:
1. Try `python -m freqtrade` (preferred)
2. Fall back to direct `freqtrade` executable
3. Both modes are validated in settings

### QProcess for Terminal
- Native Qt integration
- True subprocess isolation
- Signals for lifecycle events
- No UI blocking

## Extending This Foundation

For future features, you can:

1. **Add new commands**: Extend `CommandRunner` with new command builders
2. **Add new pages**: Extend `MainWindow.tabs` with new pages
3. **Add validators**: Extend `SettingsService.validate_settings()` 
4. **Add terminal features**: Extend `TerminalWidget` with input box, command history, etc.

## File Structure

```
app/
├── app_state/
│   └── settings_state.py       # State management with Qt signals
├── core/
│   ├── freqtrade/
│   │   └── command_runner.py   # Command building logic
│   ├── models/
│   │   └── settings_models.py  # Pydantic models
│   └── services/
│       ├── process_service.py  # QProcess wrapper
│       └── settings_service.py # Settings persistence
└── ui/
    ├── main_window.py          # Main window with tabs
    ├── pages/
    │   └── settings_page.py    # Settings UI
    └── widgets/
        └── terminal_widget.py  # Terminal output widget
main.py                         # Entry point
requirements.txt               # Dependencies
```

## Testing the Foundation

To verify everything works:

```bash
# In a terminal with .venv activated
python main.py
```

Then in the UI:
1. Go to Settings tab
2. Browse to your `.venv`
3. Set User Data path
4. Click "Validate Settings"
5. Go to Terminal tab
6. Click "Check Python" and "Check Freqtrade"
7. Verify output appears in terminal

You should see something like:
```
Python 3.11.x
Freqtrade x.x.x
```

## Next Steps

Once this foundation is solid, you can add:
- Strategy selection & configuration
- Backtest runner with parameter tuning
- Download-data UI
- Optimizer interface
- Performance tracking & charts
- Strategy performance metrics
