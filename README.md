# Cryptocurrency Trading Analysis Bot

This bot is a crypto trading analysis assistant for Discord, specifically designed to track Binance USDT-M futures. It uses Python and the Discord API to provide real-time market insights, track volume patterns, generate trading signals, and evaluate performance.

## Features

- **Real-Time Market Monitoring**: Retrieves and analyzes cryptocurrency price and volume data from Binance USDT-M futures markets.
- **Multi-Timeframe Analysis**: Calculates percentage changes across multiple timeframes (15m, 1h, 4h, 1d) for selected symbols.
- **Top Movers**: Sends regular updates with images highlighting the top gainers and losers.
- **Volume Pattern Analysis**: Detects high-volume patterns that indicate significant trading activities.
- **Trading Signal Generation**: Provides buy/sell signals based on custom criteria, such as RSI and volume patterns.
- **Performance Tracking**: Tracks prediction accuracy over time and generates performance reports with visualizations.
- **User Commands**: Offers various commands (`analyze`, `watchlist`, and `performance`) for users to interact with the bot and access tailored market insights.

## Configuration

To run the bot, set up a `.env` file with the following configurations:
- `DISCORD_BOT_TOKEN`: Token for your Discord bot.
- `DISCORD_CHANNEL_ID`: Channel ID where the bot will post updates.

## Code Overview

### 1. [`Config` Class](main.py#L13)
Stores bot configuration, including API endpoints, retry limits, styling parameters, and update intervals.

### 2. [`get_futures_symbols()`](main.py#L28)
Fetches a list of USDT-margined futures symbols from Binance, with retries for robust data fetching.

### 3. [`fetch_candlestick_data()`](main.py#L47)
Fetches candlestick (OHLC) data for a specified symbol and interval, essential for calculating price movements over timeframes.

### 4. [`calculate_timeframe_changes()`](main.py#L65)
Calculates percentage changes in price for various timeframes, such as 15 minutes, 1 hour, 4 hours, and 1 day.

### 5. [`analyze_coin()`](main.py#L87)
Retrieves and calculates key metrics for each symbol, including price, 15m, 1h, 4h, and 1d price changes.

### 6. [`create_table_image()`](main.py#L110)
Generates images showing top gainers and losers, including price and percentage change data, with improved visual styling for readability.

### 7. [`run_script` Task](main.py#L202)
Scheduled to run every 15 minutes, this function:
- Retrieves symbols and analyzes coins.
- Generates and sends images of the top 10 coins (both gainers and losers) in the Discord channel.

### 8. Commands
- **[`/analyze`](main.py#L250)**: Retrieves the latest market data and runs analysis.
- **[`/watchlist`](main.py#L256)**: Allows users to manage their watchlist.
- **[`/performance`](main.py#L329)**: Generates and displays performance stats of trading signals, including recent accuracy.

### 9. [`PerformanceTracker` Class](main.py#L300)
Handles tracking and storing the accuracy of predictions to evaluate bot performance over time.

### 10. [`CryptoBot` Class](main.py#L365)
Manages the bot’s main functions, including tracking trading signal performance, generating reports, and creating visualizations.

## Bot Flow

1. **Start and Initialization**: The bot is initialized, connects to Discord, and syncs commands.
2. **Scheduled Task ([`run_script`](main.py#L202))**: Every 15 minutes, it:
   - Fetches and analyzes market data.
   - Sorts top movers and creates visual reports as images.
   - Sends these reports to a specified Discord channel.
3. **User Interactions**:
   - Users can trigger commands to get instant market analysis, add symbols to their watchlist, or retrieve performance stats.
4. **Performance Tracking**: Logs and evaluates the accuracy of each trading signal for future performance improvements.
5. **Image Generation**: Market data is visually represented to improve readability, showing critical details in organized tables with appropriate color-coding.

## Requirements

- Python 3.7+
- Libraries: `pandas`, `aiohttp`, `discord.py`, `Pillow`, `dotenv`
- Discord bot token and Binance API access

## Setup and Run

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
