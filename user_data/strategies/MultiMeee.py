# MultiMa Strategy V2
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/

from functools import reduce

import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IntParameter, IStrategy
from pandas import DataFrame



class MultiMeee(IStrategy):
    INTERFACE_VERSION: int = 3
    buy_params = {
        "buy_ma_count": 5,
        "buy_ma_gap": 13,
    }

    sell_params = {
        "sell_ma_count": 14,
        "sell_ma_gap": 66,
    }

    minimal_roi = {"0": 0.523, "1553": 0.123, "2332": 0.076, "3169": 0}

    stoploss = -0.345

    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    timeframe = "4h"

    count_max = 20
    gap_max = 100

    buy_ma_count = IntParameter(1, count_max, default=5, space="buy")
    buy_ma_gap = IntParameter(1, gap_max, default=13, space="buy")

    sell_ma_count = IntParameter(1, count_max, default=14, space="sell")
    sell_ma_gap = IntParameter(1, gap_max, default=66, space="sell")

    @staticmethod
    def _tema_column_name(period: int) -> str:
        return f"tema_{int(period)}"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        needed_periods = set()

        for ma_count in range(self.buy_ma_count.value + 1):
            needed_periods.add(ma_count * self.buy_ma_gap.value)

        for ma_count in range(self.sell_ma_count.value + 1):
            needed_periods.add(ma_count * self.sell_ma_gap.value)

        new_cols = {}
        for period in needed_periods:
            if period > 1:
                col_name = self._tema_column_name(period)
                if col_name not in dataframe.columns:
                    new_cols[col_name] = ta.TEMA(dataframe, timeperiod=int(period))

        if new_cols:
            dataframe = pd.concat(
                [dataframe, DataFrame(new_cols, index=dataframe.index)], axis=1
            )

        print(" ", metadata["pair"], end="\t\r")
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(self.buy_ma_count.value):
            key_period = ma_count * self.buy_ma_gap.value
            past_key_period = (ma_count - 1) * self.buy_ma_gap.value

            if past_key_period > 1:
                key = self._tema_column_name(key_period)
                past_key = self._tema_column_name(past_key_period)

                if key in dataframe.columns and past_key in dataframe.columns:
                    conditions.append(dataframe[key] < dataframe[past_key])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(self.sell_ma_count.value):
            key_period = ma_count * self.sell_ma_gap.value
            past_key_period = (ma_count - 1) * self.sell_ma_gap.value

            if past_key_period > 1:
                key = self._tema_column_name(key_period)
                past_key = self._tema_column_name(past_key_period)

                if key in dataframe.columns and past_key in dataframe.columns:
                    conditions.append(dataframe[key] > dataframe[past_key])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_long"] = 1
        return dataframe