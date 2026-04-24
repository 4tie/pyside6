# Requirements Document

## Introduction

The backtest Summary tab in the Results Browser currently renders all ~23 fields as a plain flat list of label/value rows with no visual hierarchy, no color coding, and no grouping. This feature enhances the Summary tab to be visually rich, logically organized, and immediately scannable — using the existing `StatCard` widget, theme color tokens, and PySide6 layout primitives. No new dependencies are introduced.

## Glossary

- **Summary_Tab**: The "📄 Summary" tab inside the Results Browser detail panel, built by `_build_summary()` in `ResultsPage`.
- **Section**: A visually distinct group of related fields within the Summary_Tab, rendered with a header label and a bordered card container.
- **Metric_Card**: An instance of the existing `StatCard` widget displaying a single KPI with an accent bar, label, and value.
- **Color_Coding**: Applying `theme.GREEN` to positive/favorable values and `theme.RED` to negative/unfavorable values in displayed text.
- **Section_Header**: A styled `QLabel` rendered above each Section to identify its category.
- **KPI_Row**: The top area of the Summary_Tab containing a horizontal grid of Metric_Cards for the most important performance indicators.
- **Results_Page**: The `ResultsPage` class in `app/ui/pages/results_page.py`.
- **Theme**: The color and typography constants defined in `app/ui/theme.py`.

---

## Requirements

### Requirement 1: Sectioned Layout with Visual Grouping

**User Story:** As a trader reviewing backtest results, I want the summary fields grouped into logical sections with clear headers, so that I can quickly navigate to the category of information I need without scanning a flat list.

#### Acceptance Criteria

1. THE Summary_Tab SHALL organize all displayed fields into at minimum four named Sections: "Overview", "Performance", "Trade Statistics", and "Risk Metrics".
2. WHEN the Summary_Tab is rendered, THE Summary_Tab SHALL display each Section with a Section_Header label styled using `theme.TEXT_SECONDARY` at font size 11px, font weight 600, and uppercase lettering.
3. WHEN the Summary_Tab is rendered, THE Summary_Tab SHALL wrap each Section's fields in a card container with background `theme.BG_SURFACE`, border `theme.BG_BORDER`, and border-radius of 8px.
4. THE Summary_Tab SHALL place the following fields in the "Overview" Section: Strategy, Timeframe, Timerange, Backtest Start, Backtest End, Pairs, Run ID, Saved At.
5. THE Summary_Tab SHALL place the following fields in the "Performance" Section: Starting Balance, Final Balance, Total Profit %, Total Profit Abs, Profit Factor, Expectancy.
6. THE Summary_Tab SHALL place the following fields in the "Trade Statistics" Section: Total Trades, Wins, Losses, Win Rate.
7. THE Summary_Tab SHALL place the following fields in the "Risk Metrics" Section: Max Drawdown %, Max Drawdown Abs, Sharpe Ratio, Sortino Ratio, Calmar Ratio.

---

### Requirement 2: KPI Card Row

**User Story:** As a trader, I want the most important performance indicators displayed as prominent metric cards at the top of the summary, so that I can assess the run's quality at a glance without reading through all sections.

#### Acceptance Criteria

1. WHEN the Summary_Tab is rendered, THE Summary_Tab SHALL display a KPI_Row of Metric_Cards above the Sections containing: Total Profit %, Win Rate, Total Trades, Max Drawdown %, Sharpe Ratio, and Profit Factor.
2. THE KPI_Row SHALL use the existing `StatCard` widget for each Metric_Card.
3. WHEN Total Profit % is zero or positive, THE Summary_Tab SHALL render the Total Profit % Metric_Card with accent color `theme.GREEN`.
4. WHEN Total Profit % is negative, THE Summary_Tab SHALL render the Total Profit % Metric_Card with accent color `theme.RED`.
5. WHEN Max Drawdown % exceeds 20.0, THE Summary_Tab SHALL render the Max Drawdown % Metric_Card with accent color `theme.RED`.
6. WHEN Max Drawdown % is 20.0 or below, THE Summary_Tab SHALL render the Max Drawdown % Metric_Card with accent color `theme.YELLOW`.
7. THE KPI_Row SHALL lay out Metric_Cards horizontally with equal stretch so they fill the available width.
8. WHEN the run data contains no value for a KPI field, THE Summary_Tab SHALL display "—" in the corresponding Metric_Card.

---

### Requirement 3: Color-Coded Field Values

**User Story:** As a trader, I want profit, drawdown, and ratio values color-coded green or red based on whether they are favorable or unfavorable, so that I can instantly identify strong and weak areas of a backtest without interpreting raw numbers.

#### Acceptance Criteria

1. WHEN a profit or return value (Total Profit %, Total Profit Abs, Expectancy) is greater than zero, THE Summary_Tab SHALL render that value's text in color `theme.GREEN`.
2. WHEN a profit or return value (Total Profit %, Total Profit Abs, Expectancy) is less than zero, THE Summary_Tab SHALL render that value's text in color `theme.RED`.
3. WHEN a profit or return value is exactly zero, THE Summary_Tab SHALL render that value's text in color `theme.TEXT_PRIMARY`.
4. WHEN Win Rate is 50.0% or above, THE Summary_Tab SHALL render the Win Rate value text in color `theme.GREEN`.
5. WHEN Win Rate is below 50.0%, THE Summary_Tab SHALL render the Win Rate value text in color `theme.RED`.
6. WHEN Sharpe Ratio is 1.0 or above, THE Summary_Tab SHALL render the Sharpe Ratio value text in color `theme.GREEN`.
7. WHEN Sharpe Ratio is below 1.0 and above zero, THE Summary_Tab SHALL render the Sharpe Ratio value text in color `theme.YELLOW`.
8. WHEN Sharpe Ratio is zero or below, THE Summary_Tab SHALL render the Sharpe Ratio value text in color `theme.RED`.
9. WHEN Profit Factor is 1.0 or above, THE Summary_Tab SHALL render the Profit Factor value text in color `theme.GREEN`.
10. WHEN Profit Factor is below 1.0, THE Summary_Tab SHALL render the Profit Factor value text in color `theme.RED`.
11. THE Summary_Tab SHALL render all non-numeric metadata fields (Strategy, Timeframe, Timerange, Run ID, Saved At, Pairs) in color `theme.TEXT_PRIMARY` without color-coding.

---

### Requirement 4: Two-Column Field Layout Within Sections

**User Story:** As a trader, I want fields within each section displayed in a two-column grid rather than a single column, so that more information is visible without scrolling.

#### Acceptance Criteria

1. WHEN a Section contains two or more fields, THE Summary_Tab SHALL arrange those fields in a two-column grid layout within the Section card.
2. WHEN a Section contains an odd number of fields, THE Summary_Tab SHALL leave the last cell in the grid empty rather than stretching the final field across both columns.
3. THE Summary_Tab SHALL render each field as a label/value pair where the label is styled with `theme.TEXT_SECONDARY` at font size 11px and the value is styled with `theme.TEXT_PRIMARY` at font size 13px, font weight 500.
4. THE Summary_Tab SHALL apply a minimum column width of 200px to each column in the two-column grid.

---

### Requirement 5: Pairs Display

**User Story:** As a trader, I want the traded pairs list displayed in a readable wrapped format rather than a single long comma-separated string, so that I can see all pairs without horizontal scrolling.

#### Acceptance Criteria

1. WHEN the run data contains one or more pairs, THE Summary_Tab SHALL display each pair as a separate inline badge-style label within the Overview Section.
2. THE Summary_Tab SHALL render pair badges with background `theme.ACCENT_DIM`, text color `theme.ACCENT`, border-radius 10px, and padding of 2px horizontal and 8px vertical.
3. WHEN the run data contains zero pairs, THE Summary_Tab SHALL display "—" in place of the pairs badges.
4. THE Summary_Tab SHALL wrap pair badges onto multiple lines when the total width of badges exceeds the available container width.

---

### Requirement 6: Balance Delta Indicator

**User Story:** As a trader, I want to see the absolute and percentage change between starting and final balance displayed alongside the balance values, so that I can immediately understand the net result without mental arithmetic.

#### Acceptance Criteria

1. WHEN Final Balance is greater than Starting Balance, THE Summary_Tab SHALL display a delta label showing the absolute difference prefixed with "+" in color `theme.GREEN` adjacent to the Final Balance value.
2. WHEN Final Balance is less than Starting Balance, THE Summary_Tab SHALL display a delta label showing the absolute difference prefixed with "−" in color `theme.RED` adjacent to the Final Balance value.
3. WHEN Final Balance equals Starting Balance, THE Summary_Tab SHALL display no delta label adjacent to the Final Balance value.
4. THE Summary_Tab SHALL format the delta value to two decimal places followed by the currency unit "USDT".

---

### Requirement 7: Rebuild on Run Selection

**User Story:** As a trader, I want the Summary_Tab to fully refresh its content whenever I select a different run in the run list, so that the displayed data always matches the selected run.

#### Acceptance Criteria

1. WHEN a new run is selected in the run list, THE Results_Page SHALL call `_build_summary` with the newly selected run's data.
2. WHEN `_build_summary` is called, THE Summary_Tab SHALL remove all previously rendered widgets before rendering the new content.
3. WHEN `_build_summary` is called with a run dict that is missing one or more expected fields, THE Summary_Tab SHALL display "—" for each missing field without raising an exception.
4. IF an exception occurs during `_build_summary`, THEN THE Results_Page SHALL log the exception at warning level using `_log.warning` and leave the Summary_Tab in a cleared state.
