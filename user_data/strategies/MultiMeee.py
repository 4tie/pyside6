# MultiMa Strategy V2
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/

import json
import os
from functools import reduce

import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IntParameter, IStrategy
from pandas import DataFrame


def load_config_params():
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "config_MultiMeee.json"
    )
    default_params = {
        "buy_ma_count": 5,
        "buy_ma_gap": 13,
        "sell_ma_count": 14,
        "sell_ma_gap": 66,
        "minimal_roi": {"0": 0.523, "1553": 0.123, "2332": 0.076, "3169": 0},
        "stoploss": -0.345,
        "trailing_stop": False,
        "trailing_stop_positive_offset": 0.0,
        "trailing_only_offset_is_reached": False,
        "timeframe": "4h",
        "count_max": 20,
        "gap_max": 100,
    }
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return {
                "buy_ma_count": config.get(
                    "buy_ma_count", default_params["buy_ma_count"]
                ),
                "buy_ma_gap": config.get("buy_ma_gap", default_params["buy_ma_gap"]),
                "sell_ma_count": config.get(
                    "sell_ma_count", default_params["sell_ma_count"]
                ),
                "sell_ma_gap": config.get("sell_ma_gap", default_params["sell_ma_gap"]),
                "minimal_roi": config.get("minimal_roi", default_params["minimal_roi"]),
                "stoploss": config.get("stoploss", default_params["stoploss"]),
                "trailing_stop": config.get(
                    "trailing_stop", default_params["trailing_stop"]
                ),
                "trailing_stop_positive_offset": config.get(
                    "trailing_stop_positive_offset",
                    default_params["trailing_stop_positive_offset"],
                ),
                "trailing_only_offset_is_reached": config.get(
                    "trailing_only_offset_is_reached",
                    default_params["trailing_only_offset_is_reached"],
                ),
                "timeframe": config.get("timeframe", default_params["timeframe"]),
                "count_max": config.get("count_max", default_params["count_max"]),
                "gap_max": config.get("gap_max", default_params["gap_max"]),
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return default_params


CONFIG_PARAMS = load_config_params()


class MultiMeee(IStrategy):
    INTERFACE_VERSION: int = CONFIG_PARAMS.get("INTERFACE_VERSION", 3)
    buy_params = {
        "buy_ma_count": CONFIG_PARAMS.get("buy_ma_count", 5),
        "buy_ma_gap": CONFIG_PARAMS.get("buy_ma_gap", 13),
    }

    sell_params = {
        "sell_ma_count": CONFIG_PARAMS.get("sell_ma_count", 14),
        "sell_ma_gap": CONFIG_PARAMS.get("sell_ma_gap", 66),
    }

    minimal_roi = CONFIG_PARAMS.get(
        "minimal_roi", {"0": 0.523, "1553": 0.123, "2332": 0.076, "3169": 0}
    )

    stoploss = CONFIG_PARAMS.get("stoploss", -0.345)

    trailing_stop = CONFIG_PARAMS.get("trailing_stop", False)
    trailing_stop_positive = None
    trailing_stop_positive_offset = CONFIG_PARAMS.get(
        "trailing_stop_positive_offset", 0.0
    )
    trailing_only_offset_is_reached = CONFIG_PARAMS.get(
        "trailing_only_offset_is_reached", False
    )

    timeframe = CONFIG_PARAMS.get("timeframe", "4h")

    count_max = CONFIG_PARAMS.get("count_max", 20)
    gap_max = CONFIG_PARAMS.get("gap_max", 100)

    buy_ma_count = IntParameter(
        1, count_max, default=CONFIG_PARAMS.get("buy_ma_count", 5), space="buy"
    )
    buy_ma_gap = IntParameter(
        1, gap_max, default=CONFIG_PARAMS.get("buy_ma_gap", 13), space="buy"
    )

    sell_ma_count = IntParameter(
        1, count_max, default=CONFIG_PARAMS.get("sell_ma_count", 14), space="sell"
    )
    sell_ma_gap = IntParameter(
        1, gap_max, default=CONFIG_PARAMS.get("sell_ma_gap", 66), space="sell"
    )

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