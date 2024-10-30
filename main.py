import pandas as pd
import requests
import aiohttp
import asyncio
import discord
from discord.ext import tasks
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import time
import json
import os
from dotenv import load_dotenv
from discord import app_commands
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

# Configuration
class Config:
    BASE_URL = 'https://fapi.binance.com'
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
    MAX_RETRIES = 3
    MAX_MESSAGE_LENGTH = 4000
    UPDATE_INTERVAL = 15  # minutes
    TOP_N_COINS = 10
    
    # Styling
    COLORS = {
        'background': (25, 25, 25),  # Dark theme
        'text': (255, 255, 255),
        'positive': (46, 204, 113),  # Green
        'negative': (231, 76, 60),   # Red
        'neutral': (149, 165, 166)   # Gray
    }

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

# Set up the Discord client
intents = discord.Intents.default()
intents.message_content = True
client = Bot()

# Function to get the list of all coins available in Binance USDT-M Futures
async def get_futures_symbols():
    for attempt in range(Config.MAX_RETRIES):
        try:
            endpoint = '/fapi/v1/exchangeInfo'
            async with aiohttp.ClientSession() as session:
                async with session.get(Config.BASE_URL + endpoint) as response:
                    data = await response.json()
                    futures_symbols = [symbol['symbol'] for symbol in data['symbols'] if symbol['quoteAsset'] == 'USDT']
                    return futures_symbols
        except Exception as e:
            print(f"Error getting symbols, retrying... (attempt {attempt + 1}/{Config.MAX_RETRIES})")
            print(f"Error: {e}")
            time.sleep(2)  # Backoff before retrying
    return []

# Function to fetch candlestick data
async def fetch_candlestick_data(session, symbol, interval, limit=1):
    for attempt in range(Config.MAX_RETRIES):
        try:
            endpoint = '/fapi/v1/klines'
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit  # Fetch only the most recent candle
            }
            async with session.get(Config.BASE_URL + endpoint, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"Request error for {symbol}: {e}, retrying... (attempt {attempt + 1}/{Config.MAX_RETRIES})")
            time.sleep(2)  # Backoff before retrying
    return None

# Function to calculate percentage change with zero division check
def calculate_percent_change(open_price, close_price):
    try:
        return ((float(close_price) - float(open_price)) / float(open_price)) * 100
    except ZeroDivisionError:
        return 0

# Function to calculate the current percentage change for multiple timeframes
async def calculate_timeframe_changes(symbol, session):
    # Fetch the most recent candlestick for each timeframe
    fifteen_min_data = await fetch_candlestick_data(session, symbol, '15m')
    one_hour_data = await fetch_candlestick_data(session, symbol, '1h')
    four_hour_data = await fetch_candlestick_data(session, symbol, '4h')
    one_day_data = await fetch_candlestick_data(session, symbol, '1d')

    changes = {}

    if fifteen_min_data and len(fifteen_min_data) >= 1:  # Ensure we have at least one candle
        open_15m = float(fifteen_min_data[-1][1])  # Current 15m open
        close_15m = float(fifteen_min_data[-1][4])  # Current 15m close
        changes['change_15m_percent'] = calculate_percent_change(open_15m, close_15m)

    if one_hour_data and len(one_hour_data) >= 1:  # Ensure we have at least one candle
        open_1h = float(one_hour_data[-1][1])  # Current 1h open
        close_1h = float(one_hour_data[-1][4])  # Current 1h close
        changes['change_1h_percent'] = calculate_percent_change(open_1h, close_1h)

    if four_hour_data and len(four_hour_data) >= 1:  # Ensure we have at least one candle
        open_4h = float(four_hour_data[-1][1])  # Current 4h open
        close_4h = float(four_hour_data[-1][4])  # Current 4h close
        changes['change_4h_percent'] = calculate_percent_change(open_4h, close_4h)

    if one_day_data and len(one_day_data) >= 1:  # Ensure we have at least one candle
        open_1d = float(one_day_data[-1][1])  # Current 1d open
        close_1d = float(one_day_data[-1][4])  # Current 1d close
        changes['change_1d_percent'] = calculate_percent_change(open_1d, close_1d)

    return changes

# Function to analyze each coin
async def analyze_coin(symbol, session):
    one_hour_data = await fetch_candlestick_data(session, symbol, '1h')
    if one_hour_data:
        current_1h = one_hour_data[-1]
        current_price = float(current_1h[4])
        
        # Calculate current percentage changes for 15m, 1h, 4h, and 1d
        timeframe_changes = await calculate_timeframe_changes(symbol, session)

        return {
            'symbol': symbol,
            'current_price': current_price,
            'change_15m_percent': timeframe_changes.get('change_15m_percent', 0),
            'change_1h_percent': timeframe_changes.get('change_1h_percent', 0),
            'change_4h_percent': timeframe_changes.get('change_4h_percent', 0),
            'change_1d_percent': timeframe_changes.get('change_1d_percent', 0),
        }
    return None

# Function to analyze all coins asynchronously
async def analyze_coins(symbols):
    async with aiohttp.ClientSession() as session:
        tasks = [analyze_coin(symbol, session) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]

# Function to pad strings for proper indentation
def pad_string(text, width):
    return str(text).ljust(width)

# Function to create and save a table image using Pillow
def create_table_image(data, title, filename="output.png"):
    # Enhanced image styling with better alignment
    padding = 20
    row_height = 45
    col_padding = 15
    
    # Column configurations
    columns = [
        {"name": "Symbol", "width": 120, "align": "left"},
        {"name": "Price (USDT)", "width": 150, "align": "right"},
        {"name": "15m (%)", "width": 120, "align": "right"},
        {"name": "1h (%)", "width": 120, "align": "right"},
        {"name": "4h (%)", "width": 120, "align": "right"},
        {"name": "1d (%)", "width": 120, "align": "right"}
    ]
    
    # Calculate image dimensions
    img_width = sum(col["width"] for col in columns) + (padding * 2)
    img_height = (len(data) + 2) * row_height + (padding * 2)  # +2 for header and title
    
    # Create image
    img = Image.new('RGB', (img_width, img_height), Config.COLORS['background'])
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to use modern fonts
        title_font = ImageFont.truetype("Roboto-Bold.ttf", 24)
        header_font = ImageFont.truetype("Roboto-Medium.ttf", 20)
        font = ImageFont.truetype("Roboto-Regular.ttf", 18)
    except:
        # Fallback to default font
        title_font = ImageFont.truetype("arial.ttf", 24)
        header_font = ImageFont.truetype("arial.ttf", 20)
        font = ImageFont.truetype("arial.ttf", 18)

    # Add title and timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text((padding, padding), title, fill=Config.COLORS['text'], font=title_font)
    timestamp_width = draw.textlength(timestamp, font=font)
    draw.text((img_width - padding - timestamp_width, padding), 
              timestamp, 
              fill=Config.COLORS['neutral'], 
              font=font)

    # Draw header line
    header_y = padding + row_height
    draw.line([(padding, header_y), (img_width - padding, header_y)], 
              fill=Config.COLORS['neutral'], 
              width=1)

    # Draw column headers
    x_pos = padding
    header_y = header_y + 10
    for col in columns:
        text = col["name"]
        if col["align"] == "right":
            text_width = draw.textlength(text, font=header_font)
            text_x = x_pos + col["width"] - text_width - col_padding
        else:
            text_x = x_pos + col_padding
            
        draw.text((text_x, header_y), 
                  text, 
                  fill=Config.COLORS['text'], 
                  font=header_font)
        x_pos += col["width"]

    # Draw data rows
    for i, row in enumerate(data):
        y_pos = header_y + row_height + (i * row_height)
        x_pos = padding
        
        # Draw alternating row backgrounds
        if i % 2 == 0:
            draw.rectangle(
                [(padding, y_pos), (img_width - padding, y_pos + row_height)],
                fill=(30, 30, 30)  # Slightly lighter than background
            )

        # Draw each column in the row
        values = [
            row['symbol'],
            f"{row['current_price']:.2f}",
            f"{row['change_15m_percent']:.2f}%",
            f"{row['change_1h_percent']:.2f}%",
            f"{row['change_4h_percent']:.2f}%",
            f"{row['change_1d_percent']:.2f}%"
        ]

        for col, value in zip(columns, values):
            # Determine text color based on percentage values
            text_color = Config.COLORS['text']
            if '%' in value:
                if float(value.strip('%')) > 0:
                    text_color = Config.COLORS['positive']
                elif float(value.strip('%')) < 0:
                    text_color = Config.COLORS['negative']

            # Align text based on column configuration
            if col["align"] == "right":
                text_width = draw.textlength(value, font=font)
                text_x = x_pos + col["width"] - text_width - col_padding
            else:
                text_x = x_pos + col_padding

            draw.text((text_x, y_pos + 10), 
                     value, 
                     fill=text_color, 
                     font=font)
            x_pos += col["width"]

    # Draw bottom border
    draw.line([(padding, img_height - padding), (img_width - padding, img_height - padding)], 
              fill=Config.COLORS['neutral'], 
              width=1)

    # Save image with better quality
    img.save(filename, quality=95, dpi=(300, 300))

# Task to run the script initially and every 15 minutes
@tasks.loop(minutes=Config.UPDATE_INTERVAL)
async def run_script():
    try:
        channel = client.get_channel(Config.DISCORD_CHANNEL_ID)
        if channel is None:
            print("Error: Could not find Discord channel")
            return

        # Send status message
        status_msg = await channel.send("🔄 Fetching latest market data...")

        symbols = await get_futures_symbols()
        if not symbols:
            await status_msg.edit(content="❌ Error: Could not fetch market symbols")
            return

        df_pumping_coins = await analyze_coins(symbols)
        if not df_pumping_coins:
            await status_msg.edit(content="ℹ️ No significant market movements detected")
            return

        # Separate and sort coins
        increasing_coins = sorted([coin for coin in df_pumping_coins if coin['change_15m_percent'] > 0],
                                key=lambda x: x['change_15m_percent'], 
                                reverse=True)[:Config.TOP_N_COINS]
        
        decreasing_coins = sorted([coin for coin in df_pumping_coins if coin['change_15m_percent'] < 0],
                                key=lambda x: x['change_15m_percent'])[:Config.TOP_N_COINS]

        # Create and send images
        create_table_image(increasing_coins, "📈 Top 10 Increasing Coins", "increasing_coins.png")
        create_table_image(decreasing_coins, "📉 Top 10 Decreasing Coins", "decreasing_coins.png")

        await status_msg.delete()
        await channel.send("🎯 Market Analysis Report", 
                          files=[discord.File("increasing_coins.png"),
                                discord.File("decreasing_coins.png")])

    except Exception as e:
        print(f"Error in run_script: {e}")
        if channel:
            await channel.send(f"❌ An error occurred while processing market data: {str(e)}")

# Discord event listener for when the bot is ready
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    run_script.start()  # Start the loop for every 15 minutes

# Run the bot
client.run(Config.DISCORD_BOT_TOKEN)

@client.tree.command(name="analyze", description="Get current market analysis")
async def analyze(interaction: discord.Interaction):
    await interaction.response.defer()
    await run_analysis(interaction)

@client.tree.command(name="watchlist", description="Add or view your watchlist")
async def watchlist(interaction: discord.Interaction, action: str, symbol: str = None):
    # Watchlist management logic
    pass

async def analyze_volume_patterns(symbol, session):
    klines = await fetch_candlestick_data(session, symbol, '1h', limit=24)
    
    if not klines:
        return None

    volumes = [float(k[5]) for k in klines]
    avg_volume = sum(volumes) / len(volumes)
    current_volume = volumes[-1]
    
    return {
        'current_volume': current_volume,
        'volume_change': ((current_volume - avg_volume) / avg_volume) * 100,
        'is_high_volume': current_volume > (avg_volume * 1.5)
    }

class TradingSignals:
    def generate_signals(self, technical_data, volume_data):
        signals = {
            'strength': 'STRONG' if volume_data['is_high_volume'] else 'NORMAL',
            'action': 'NONE',
            'confidence': 0
        }
        
        # Signal logic based on multiple indicators
        if technical_data['rsi'] < 30 and volume_data['is_high_volume']:
            signals['action'] = 'BUY'
            signals['confidence'] = 80
        elif technical_data['rsi'] > 70 and volume_data['is_high_volume']:
            signals['action'] = 'SELL'
            signals['confidence'] = 80
            
        return signals

class PerformanceTracker:
    def __init__(self):
        self.db = {}  # Consider using a proper database

    async def track_prediction(self, symbol, prediction, actual):
        accuracy = self.calculate_accuracy(prediction, actual)
        self.db[symbol] = self.db.get(symbol, []) + [{
            'timestamp': datetime.now(),
            'prediction': prediction,
            'actual': actual,
            'accuracy': accuracy
        }]

    def get_performance_stats(self, symbol=None):
        # Calculate success rate, average accuracy, etc.
        pass

class CryptoBot:
    def __init__(self):
        self.performance_tracker = PerformanceTracker()
        self.market_analyzer = MarketAnalyzer()
        # ... other initializations ...

    async def track_signal_performance(self, symbol: str, signal_data: Dict, timeframe: str = '1h'):
        """
        Track the performance of trading signals
        """
        try:
            # Store initial prediction with current price and action
            prediction = {
                'action': signal_data['action'],
                'price': signal_data['current_price'],
                'confidence': signal_data['confidence'],
                'timestamp': datetime.now().isoformat()
            }

            # Wait for the specified timeframe to check result
            if timeframe == '1h':
                wait_time = 3600  # 1 hour in seconds
            elif timeframe == '4h':
                wait_time = 14400  # 4 hours in seconds
            else:
                wait_time = 3600  # default to 1 hour

            # Schedule the performance check
            await asyncio.sleep(wait_time)
            
            # Get actual result
            current_data = await self.fetch_market_data(symbol)
            actual = {
                'price': current_data['current_price'],
                'timestamp': datetime.now().isoformat()
            }

            # Track the prediction result
            await self.performance_tracker.track_prediction(symbol, prediction, actual)

            return True

        except Exception as e:
            print(f"Error tracking performance: {e}")
            return False

    async def generate_performance_report(self, symbol: Optional[str] = None) -> Dict:
        """
        Generate detailed performance report
        """
        stats = self.performance_tracker.get_performance_stats(symbol)
        recent_predictions = []

        if symbol:
            recent_predictions = self.performance_tracker.get_recent_predictions(symbol)

        # Create visualization
        if recent_predictions:
            self.create_performance_visualization(recent_predictions, symbol)

        return {
            'statistics': stats,
            'recent_predictions': recent_predictions,
            'visualization': 'performance_chart.png' if recent_predictions else None
        }

    def create_performance_visualization(self, predictions: List[Dict], symbol: str):
        """
        Create visualization of performance data
        """
        df = pd.DataFrame(predictions)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['accuracy'], marker='o')
        plt.title(f'Prediction Accuracy Over Time - {symbol}')
        plt.xlabel('Time')
        plt.ylabel('Accuracy (%)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('performance_chart.png')
        plt.close()

    @client.tree.command(name="performance", description="Get performance statistics")
    async def get_performance(interaction: discord.Interaction, symbol: Optional[str] = None):
        """Discord command to get performance stats"""
        await interaction.response.defer()

        report = await self.generate_performance_report(symbol)
        
        # Create embed message
        embed = discord.Embed(
            title=f"Performance Report {symbol if symbol else 'Overall'}",
            color=discord.Color.blue()
        )

        # Add statistics
        stats = report['statistics']
        embed.add_field(
            name="Statistics",
            value=f"""
                Total Predictions: {stats['total_predictions']}
                Successful Predictions: {stats['successful_predictions']}
                Average Accuracy: {stats['average_accuracy']:.2f}%
                Success Rate: {stats['success_rate']:.2f}%
            """,
            inline=False
        )

        # Add recent predictions if available
        if report['recent_predictions']:
            recent = report['recent_predictions'][0]  # Most recent prediction
            embed.add_field(
                name="Latest Prediction",
                value=f"""
                    Action: {recent['prediction']['action']}
                    Confidence: {recent['prediction']['confidence']}%
                    Accuracy: {recent['accuracy']}%
                """,
                inline=False
            )

        # Send response
        files = []
        if report['visualization']:
            files.append(discord.File('performance_chart.png'))
            embed.set_image(url="attachment://performance_chart.png")

        await interaction.followup.send(embed=embed, files=files)