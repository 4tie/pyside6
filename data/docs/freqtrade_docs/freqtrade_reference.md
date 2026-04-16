# Freqtrade Reference

## Key Commands

```bash
# Backtesting
python -m freqtrade backtesting \
  --strategy MyStrategy \
  --timeframe 5m \
  --timerange 20240101-20241231 \
  --config user_data/config.json \
  --user-data-dir user_data \
  --export trades

# Download data
python -m freqtrade download-data \
  --pairs BTC/USDT ETH/USDT \
  --timeframes 5m 1h \
  --config user_data/config.json \
  --user-data-dir user_data

# List strategies
python -m freqtrade list-strategies --user-data-dir user_data

# Version
python -m freqtrade --version
```

## Backtest Result JSON Structure

```
strategy/
  {StrategyName}/
    results_per_pair: [{pair, trades, wins, losses, profit_total_abs, ...}]
    total_trades: int
    wins: int
    losses: int
    profit_total_abs: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    calmar: float
    trades: [{pair, open_date, close_date, open_rate, close_rate, profit_abs, profit_ratio, trade_duration, exit_reason}]
```

## Config Fields (config.json)

```json
{
  "stake_currency": "USDT",
  "stake_amount": 100,
  "max_open_trades": 3,
  "dry_run": true,
  "exchange": { "name": "binance" },
  "pairs": ["BTC/USDT", "ETH/USDT"]
}
```

## Export Zip Structure

```
backtest_results/{strategy}/{timestamp}.zip
  └── {timestamp}_backtest_results.json
```

## Timerange Format

```
YYYYMMDD-YYYYMMDD   e.g. 20240101-20241231
YYYYMMDD-            e.g. 20240101- (open end)
```
