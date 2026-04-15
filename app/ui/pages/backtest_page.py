from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QMessageBox, QGroupBox,
    QCheckBox, QFormLayout, QTabWidget
)

from app.app_state.settings_state import SettingsState
from app.core.services.backtest_service import BacktestService
from app.core.services.backtest_results_service import BacktestResultsService
from app.core.services.settings_service import SettingsService
from app.core.services.process_service import ProcessService
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget


class BacktestPage(QWidget):
    """Page for running backtest jobs."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.backtest_service = BacktestService(self.settings_service)
        self.process_service = ProcessService()
        self.last_export_path: Optional[str] = None

        self.init_ui()
        self._connect_signals()
        self._refresh_strategies()

    def init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()

        # Left panel: Parameters
        params_layout = QVBoxLayout()

        # Strategy selection
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.setEditable(True)
        strategy_layout.addWidget(self.strategy_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_strategies)
        strategy_layout.addWidget(refresh_btn)

        params_layout.addLayout(strategy_layout)

        # Basic parameters
        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_input = QLineEdit()
        self.timeframe_input.setPlaceholderText("5m, 1h, 4h, 1d, etc.")
        self.timeframe_input.setText("5m")
        timeframe_layout.addWidget(self.timeframe_input)
        params_layout.addLayout(timeframe_layout)

        timerange_layout = QHBoxLayout()
        timerange_layout.addWidget(QLabel("Timerange (optional):"))
        self.timerange_input = QLineEdit()
        self.timerange_input.setPlaceholderText("20240101-20241231")
        timerange_layout.addWidget(self.timerange_input)
        params_layout.addLayout(timerange_layout)

        pairs_layout = QHBoxLayout()
        pairs_layout.addWidget(QLabel("Pairs (space-separated):"))
        self.pairs_input = QLineEdit()
        self.pairs_input.setPlaceholderText("BTC/USDT ETH/USDT ADA/USDT")
        pairs_layout.addWidget(self.pairs_input)
        params_layout.addLayout(pairs_layout)

        # Advanced options (collapsible)
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QFormLayout()

        self.dry_run_wallet = QDoubleSpinBox()
        self.dry_run_wallet.setMinimum(0)
        self.dry_run_wallet.setMaximum(999999)
        self.dry_run_wallet.setValue(80.0)
        self.dry_run_wallet.setToolTip("Dry run starting wallet balance")
        advanced_layout.addRow("Dry Run Wallet:", self.dry_run_wallet)

        self.max_open_trades = QSpinBox()
        self.max_open_trades.setMinimum(1)
        self.max_open_trades.setMaximum(999)
        self.max_open_trades.setValue(2)
        self.max_open_trades.setToolTip("Maximum number of open trades")
        advanced_layout.addRow("Max Open Trades:", self.max_open_trades)

        self.stake_currency = QLineEdit()
        self.stake_currency.setPlaceholderText("USDT, BNB, etc. (optional)")
        advanced_layout.addRow("Stake Currency:", self.stake_currency)

        self.stake_amount = QDoubleSpinBox()
        self.stake_amount.setMinimum(0)
        self.stake_amount.setMaximum(999999)
        self.stake_amount.setToolTip("Stake amount per trade (optional)")
        advanced_layout.addRow("Stake Amount:", self.stake_amount)

        advanced_group.setLayout(advanced_layout)
        advanced_group.setCheckable(False)
        params_layout.addWidget(advanced_group)

        # Export label
        self.export_label = QLabel("Export: -")
        self.export_label.setStyleSheet(
            "padding: 8px; background-color: #f0f0f0; border-radius: 4px; font-family: Courier;"
        )
        params_layout.addWidget(self.export_label)

        # Run/Stop buttons
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Backtest")
        self.run_button.clicked.connect(self._run_backtest)
        button_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.process_service.stop_process)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        params_layout.addLayout(button_layout)

        params_layout.addStretch()

        # Right panel: Output + Results
        output_layout = QVBoxLayout()

        tabs = QTabWidget()

        self.terminal = TerminalWidget()
        tabs.addTab(self.terminal, "Terminal Output")

        self.results_widget = BacktestResultsWidget()
        tabs.addTab(self.results_widget, "Results")

        output_layout.addWidget(tabs)

        # Main horizontal layout
        h_layout = QHBoxLayout()
        h_layout.addLayout(params_layout, 1)
        h_layout.addLayout(output_layout, 2)

        main_layout.addLayout(h_layout)
        self.setLayout(main_layout)

    def _connect_signals(self):
        """Connect settings signals."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)

    def _refresh_strategies(self):
        """Refresh available strategies."""
        strategies = self.backtest_service.get_available_strategies()
        self.strategy_combo.clear()
        self.strategy_combo.addItems(strategies)

    def _on_settings_changed(self, settings):
        """Called when settings change."""
        self._refresh_strategies()

    def _run_backtest(self):
        """Run backtest with selected parameters."""
        strategy = self.strategy_combo.currentText().strip()
        timeframe = self.timeframe_input.text().strip()
        timerange = self.timerange_input.text().strip() or None
        pairs = [p.strip() for p in self.pairs_input.text().split() if p.strip()]

        # Validate inputs
        if not strategy:
            QMessageBox.warning(self, "Missing Input", "Please enter a strategy name.")
            return
        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return

        # Build command
        try:
            stake_currency = self.stake_currency.text().strip() or None
            stake_amount = self.stake_amount.value() if self.stake_amount.value() > 0 else None
            dry_run_wallet = self.dry_run_wallet.value() if self.dry_run_wallet.value() > 0 else None
            max_open_trades = self.max_open_trades.value()

            cmd = self.backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
                stake_currency=stake_currency,
                stake_amount=stake_amount,
                max_open_trades=max_open_trades,
                dry_run_wallet=dry_run_wallet,
            )

            self.last_export_path = cmd.export_zip

        except (ValueError, FileNotFoundError) as e:
            QMessageBox.critical(self, "Backtest Setup Failed", str(e))
            return

        # Clear terminal and show command
        self.terminal.clear_output()
        cmd_str = f"{cmd.program} {' '.join(cmd.args)}"
        self.terminal.append_output(f"$ {cmd_str}\n")
        self.terminal.append_output(
            f"Strategy: {cmd.strategy_file}\n"
            f"Config: {cmd.config_file}\n"
            f"Export: {cmd.export_zip}\n\n"
        )

        # Update export label
        self.export_label.setText(f"Export: {cmd.export_zip}")

        # Mark as running before executing
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.terminal.append_output("[Process started]\n\n")

        # Execute command with callbacks
        try:
            self.process_service.execute_command(
                command=[cmd.program] + cmd.args,
                on_output=self.terminal.append_output,
                on_error=self.terminal.append_error,
                on_finished=self._on_process_finished_internal,
                working_directory=cmd.cwd,
            )
        except Exception as e:
            QMessageBox.critical(self, "Process Error", str(e))
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _on_process_started(self):
        """Called when process starts - now handled internally."""
        pass

    def _on_process_finished_internal(self, exit_code: int):
        """Called when process finishes."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.terminal.append_output(f"\n[Process finished] exit_code={exit_code}\n")

        # Try to parse and display results
        if exit_code == 0 and self.last_export_path:
            self._try_load_results()

    def _try_load_results(self):
        """Try to load and display backtest results."""
        if not self.last_export_path or not Path(self.last_export_path).exists():
            self.terminal.append_error("\nWarning: Export zip file not found at expected path.\n")
            return

        try:
            self.terminal.append_output("\nParsing backtest results...\n")
            results = BacktestResultsService.parse_backtest_zip(self.last_export_path)

            if results:
                self.results_widget.display_results(results)
                self.terminal.append_output("✓ Results loaded successfully!\n")

                # Switch to results tab
                parent_tabs = self.results_widget.parent()
                if hasattr(parent_tabs, 'setCurrentIndex'):
                    parent_tabs.setCurrentIndex(1)  # Switch to Results tab

        except Exception as e:
            error_msg = f"Failed to parse backtest results: {e}\n"
            self.terminal.append_error(error_msg)
