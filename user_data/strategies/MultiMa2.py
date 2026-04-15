# MultiMa Strategy V2
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/

# --- Do not remove these libs ---
from freqtrade.strategy import IntParameter, IStrategy
from pandas import DataFrame

# --------------------------------

import talib.abstract as ta
from functools import reduce
import pandas as pd


class MultiMa2(IStrategy):
    # 111/2000:     18 trades. 12/4/2 Wins/Draws/Losses. Avg profit   9.72%. Median profit   3.01%. Total profit  733.01234143 USDT (  73.30%). Avg duration 2 days, 18:40:00 min. Objective: 1.67048

    INTERFACE_VERSION: int = 3

    # Buy hyperspace params:
    buy_params = {
        "buy_ma_count": 5,
        "buy_ma_gap": 13,
    }

    # Sell hyperspace params:
    sell_params = {
        "sell_ma_count": 14,
        "sell_ma_gap": 66,
    }

    # ROI table:
    minimal_roi = {
        "0": 0.523,
        "1553": 0.123,
        "2332": 0.076,
        "3169": 0,
    }

    # Stoploss:
    stoploss = -0.345

    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    # Optimal Timeframe
    timeframe = "4h"

    count_max = 20
    gap_max = 100

    buy_ma_count = IntParameter(1, count_max, default=5, space="buy")
    buy_ma_gap = IntParameter(1, gap_max, default=13, space="buy")

    sell_ma_count = IntParameter(1, count_max, default=14, space="sell")
    sell_ma_gap = IntParameter(1, gap_max, default=66, space="sell")

    @staticmethod
    def _tema_col(period: int) -> str:
        return f"tema_{int(period)}"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only compute TEMA periods that will actually be used in entry/exit conditions.
        # Keep the same effective period generation logic, but use string column names
        # so the API/UI can serialize dataframe columns safely.
        needed_periods = set()

        # Buy side: preserve the original loop shape (+1 included)
        for ma_count in range(self.buy_ma_count.value + 1):
            needed_periods.add(ma_count * self.buy_ma_gap.value)

        # Sell side: preserve the original loop shape (+1 included)
        for ma_count in range(self.sell_ma_count.value + 1):
            needed_periods.add(ma_count * self.sell_ma_gap.value)

        new_cols = {}
        for period in needed_periods:
            if period > 1:
                col = self._tema_col(period)
                if col not in dataframe.columns:
                    new_cols[col] = ta.TEMA(dataframe, timeperiod=int(period))

        if new_cols:
            dataframe = pd.concat([dataframe, DataFrame(new_cols, index=dataframe.index)], axis=1)

        print(" ", metadata["pair"], end="\t\r")
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # Preserve the original loop/logic and values.
        # Only column names are changed from integers to strings.
        for ma_count in range(self.buy_ma_count.value):
            key = ma_count * self.buy_ma_gap.value
            past_key = (ma_count - 1) * self.buy_ma_gap.value

            if past_key > 1:
                key_col = self._tema_col(key)
                past_key_col = self._tema_col(past_key)

                if key_col in dataframe.columns and past_key_col in dataframe.columns:
                    conditions.append(dataframe[key_col] < dataframe[past_key_col])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(self.sell_ma_count.value):
            key = ma_count * self.sell_ma_gap.value
            past_key = (ma_count - 1) * self.sell_ma_gap.value

            if past_key > 1:
                key_col = self._tema_col(key)
                past_key_col = self._tema_col(past_key)

                if key_col in dataframe.columns and past_key_col in dataframe.columns:
                    conditions.append(dataframe[key_col] > dataframe[past_key_col])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_long"] = 1

        return dataframe