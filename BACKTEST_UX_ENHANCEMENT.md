# Backtest UX Enhancement - Implementation Complete ✅

## What Was Implemented

### 1. **BacktestPreferences Model** (`app/core/models/settings_models.py`)

Added nested Pydantic model to store user preferences:

```python
class BacktestPreferences(BaseModel):
    last_strategy: str                    # Last used strategy name
    default_timeframe: str = "5m"         # Default timeframe
    default_pairs: str                    # Last used pairs
    paired_favorites: list[str]           # Common pairs favorites
    last_timerange_preset: str = "30d"   # Last used preset
```

Integrated into `AppSettings`:
- Auto-persists to `~/.freqtrade_gui/settings.json`
- Pydantic handles serialization automatically
- Backwards compatible with existing settings

### 2. **Date Utilities** (`app/core/utils/date_utils.py`)

New utility function for timerange preset calculation:

```python
def calculate_timerange_preset(preset: str) -> str:
    """Convert 7d, 14d, 30d, 90d, 120d, 360d → YYYYMMDD-YYYYMMDD"""
```

Example:
- Input: `"30d"` → Output: `"20260316-20260415"` (30 days ago to today)
- Handles all 6 presets: 7d, 14d, 30d, 90d, 120d, 360d

### 3. **Enhanced BacktestPage UI** (`app/ui/pages/backtest_page.py`)

#### A. Timerange Preset Buttons
```
Timerange: [7d] [14d] [30d] [90d] [120d] [360d]  Custom: [input]
```

- 6 preset buttons for common timeranges
- Clicking button auto-calculates and fills the date range
- Custom input field for manual dates
- Button clicks auto-save preference

#### B. Pairs Favorites Dropdown
```
Pairs: [BTC/USDT ↓]
```

- QComboBox with editable mode
- Pre-populated with favorites: BTC/USDT, ETH/USDT, ADA/USDT
- Can type custom pairs
- Custom pairs added to favorites automatically (max 10 items)

#### C. Settings Load/Save
- `_load_preferences()`: Restores saved values on app startup
  - Strategy name
  - Timeframe
  - Pairs from favorites
  - All set in BacktestPage.__init__

- `_save_preferences_to_settings()`: Saves current inputs
  - Called before each backtest run
  - Updates all preferences
  - Writes to disk immediately
  - Auto-adds new favorites to list

#### D. Preset Button Handler
- `_on_timerange_preset()`: Handles preset button clicks
  - Calculates timerange from preset
  - Updates input field
  - Saves preference for next session

---

## Workflow

### First Run
1. Open app → BacktestPage
2. All inputs have defaults: timeframe="5m", pairs=[BTC/USDT, ETH/USDT, ADA/USDT]
3. Click "30d" preset → timerange fills automatically
4. Select pair from dropdown or type custom
5. Run backtest
6. Settings auto-saved

### Subsequent Runs
1. Open app → BacktestPage
2. **All inputs restored** from previous session:
   - Strategy: "MultiMa_v3"
   - Timeframe: "1h"
   - Pairs: "BTC/USDT ETH/USDT"
3. Just modify what's needed and run again

### After App Restart
1. Close app (preferences saved)
2. Reopen app
3. Go to BacktestPage
4. **All values pre-filled**:
   ```
   Strategy: [MultiMa_v3 ↓]
   Timeframe: [1h]
   Timerange: [custom or preset filled]
   Pairs: [BTC/USDT ETH/USDT ↓]
   ```
5. Ready to run immediately

---

## Technical Details

### File Structure
```
app/core/models/settings_models.py
  ├─ BacktestPreferences (new)
  └─ AppSettings (extended)

app/core/utils/date_utils.py (new)
  └─ calculate_timerange_preset()

app/ui/pages/backtest_page.py (enhanced)
  ├─ Timerange preset buttons
  ├─ Pairs dropdown (QComboBox)
  ├─ _load_preferences()
  ├─ _save_preferences_to_settings()
  └─ _on_timerange_preset()
```

### Settings File Location
```
~/.freqtrade_gui/settings.json
{
  "venv_path": "...",
  "python_executable": "...",
  ...
  "backtest_preferences": {
    "last_strategy": "MultiMa_v3",
    "default_timeframe": "5m",
    "default_pairs": "BTC/USDT ETH/USDT",
    "paired_favorites": ["BTC/USDT", "ETH/USDT", "ADA/USDT"],
    "last_timerange_preset": "30d"
  }
}
```

### Key Features
✅ **Persistent Storage**: Settings auto-saved after each run  
✅ **Auto-Populate**: Presets restore on app startup  
✅ **Date Calculation**: All 6 presets convert to proper YYYYMMDD-YYYYMMDD format  
✅ **Favorites Management**: Auto-grows with new pairs (capped at 10)  
✅ **Backwards Compatible**: Old settings files still work (new fields get defaults)  
✅ **No New Dependencies**: Uses only stdlib (datetime) + existing Pydantic  

---

## Testing

### 1. Preset Buttons
```
1. Click "7d" 
   → Timerange = 7 days ago to today (e.g., "20260408-20260415")
   
2. Click "120d"
   → Timerange = 120 days ago to today (e.g., "20251147-20260415")
   
3. Manual edit
   → Custom timerange still works (e.g., "20240101-20241231")
```

### 2. Pairs Dropdown
```
1. Open pairs dropdown
   → Shows [BTC/USDT, ETH/USDT, ADA/USDT]
   
2. Type "SOL/USDT"
   → Can type custom pairs
   
3. Run backtest with "SOL/USDT"
   → On next run, "SOL/USDT" appears in dropdown
```

### 3. Persistence Across Restart
```
1. Set: strategy="MultiMa_v3", timeframe="1h", pairs="BTC/USDT"
2. Run backtest
3. Close app: ps aux | grep python  → kill the app
4. Check settings file:
   cat ~/.freqtrade_gui/settings.json | grep backtest_preferences
   → Shows all values saved
5. Reopen app: python main.py
6. Go to Backtest tab
   → All values restored
```

### 4. First Run (No Saved Preferences)
```
1. Delete settings file: rm ~/.freqtrade_gui/settings.json
2. Open app → BacktestPage
   → Defaults appear:
      - timeframe: "5m"
      - pairs: [BTC/USDT, ETH/USDT, ADA/USDT]
      - last_timerange_preset: "30d"
```

### 5. Edge Cases
```
- Corrupt settings file
  → App falls back to defaults gracefully
  
- Missing saved strategy (deleted from user_data)
  → Strategy field shows as plain text, still works
  
- Add custom pairs repeatedly
  → Capped at 10 items, prevents list bloat
```

---

## Commit

**Commit: `b1e31e0`** - Add timerange presets and settings persistence

Changes:
- `app/core/models/settings_models.py`: +BacktestPreferences model
- `app/core/utils/date_utils.py`: +calculate_timerange_preset function
- `app/ui/pages/backtest_page.py`: +preset buttons, pairs dropdown, persistence

Total: 134 lines added, 8 lines modified

---

## Next Improvements (Future)

- Manage pairs favorites (add/remove button)
- Backtest history tab (view past results)
- Quick run button (use last settings without UI)
- Export/import preset configs
- Timeframe presets as well (1m, 5m, 1h, 4h, 1d)

