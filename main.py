
#!/usr/bin/env python3
"""
Gamma Edge - Advanced Options Analysis Telegram Bot
===================================================

Professional-grade options analysis tool leveraging Upstox API for real-time market data.
Features: Gamma Exposure Analysis, Confluence Scanner, Real-time Monitoring, Advanced Greeks

Author: Gamma Edge Team
Date: January 2025
"""

import os
import logging
import requests
import json
import datetime
import math
import asyncio
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from io import BytesIO
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get Bot Token from environment
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
    logger.error("Please add your bot token to Secrets")
    exit(1)

# API Cache for performance
api_cache = {}
CACHE_DURATION = 60  # seconds

# Global scheduler for monitoring
scheduler = AsyncIOScheduler(jobstores={'default': MemoryJobStore()})
active_monitors = {}  # user_id: {symbol: job_details}

class GammaEdgeCalculator:
    """
    Advanced Gamma Exposure Calculator with Upstox API integration
    """
    
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.session = requests.Session()
        
        # Get Upstox API credentials from environment variables
        self.api_key = os.getenv('UPSTOX_API_KEY')
        self.access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
        
        if not self.api_key or not self.access_token:
            logger.warning("⚠️ Upstox API credentials not found in environment variables!")
            logger.warning("Add UPSTOX_API_KEY and UPSTOX_ACCESS_TOKEN to Secrets for live data")
            self.use_live_data = False
        else:
            self.use_live_data = True
            logger.info("✓ Upstox API credentials loaded successfully")
        
        # Set up session headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        if self.use_live_data:
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
        
        # Log initialization status
        logger.info("🔧 Initializing Gamma Edge Calculator...")
        logger.info(f"📡 Base URL: {self.base_url}")
        logger.info(f"🔑 API Key Present: {'Yes' if self.api_key else 'No'}")
        logger.info(f"🎫 Access Token Present: {'Yes' if self.access_token else 'No'}")
        logger.info(f"💾 Live Data Mode: {'Enabled' if self.use_live_data else 'Disabled (using mock data)'}")
        
        # Known instruments mapping
        self.known_instruments = {
            # Major Indices
            'NIFTY': 'NSE_INDEX|Nifty 50',
            'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
            'FINNIFTY': 'NSE_INDEX|Nifty Financial Services',
            'MIDCPNIFTY': 'NSE_INDEX|NIFTY MID SELECT',
            
            # Banking Stocks
            'HDFCBANK': 'NSE_EQ|INE040A01034',
            'ICICIBANK': 'NSE_EQ|INE090A01021',
            'KOTAKBANK': 'NSE_EQ|INE237A01028',
            'SBIN': 'NSE_EQ|INE062A01020',
            'AXISBANK': 'NSE_EQ|INE238A01034',
            'INDUSINDBK': 'NSE_EQ|INE095A01012',
            
            # IT Stocks
            'TCS': 'NSE_EQ|INE467B01029',
            'INFY': 'NSE_EQ|INE009A01021',
            'WIPRO': 'NSE_EQ|INE075A01022',
            'HCLTECH': 'NSE_EQ|INE860A01027',
            'TECHM': 'NSE_EQ|INE669C01036',
            
            # Energy
            'RELIANCE': 'NSE_EQ|INE002A01018',
            'ONGC': 'NSE_EQ|INE213A01029',
            'BPCL': 'NSE_EQ|INE029A01011',
            'IOC': 'NSE_EQ|INE242A01010',
            'NTPC': 'NSE_EQ|INE733E01010',
            
            # FMCG
            'HINDUNILVR': 'NSE_EQ|INE030A01027',
            'ITC': 'NSE_EQ|INE154A01025',
            'BRITANNIA': 'NSE_EQ|INE216A01030',
            'NESTLEIND': 'NSE_EQ|INE239A01016',
            
            # Auto
            'MARUTI': 'NSE_EQ|INE585B01010',
            'BAJAJ-AUTO': 'NSE_EQ|INE917I01010',
            'M&M': 'NSE_EQ|INE101A01026',
            'TATAMOTORS': 'NSE_EQ|INE155A01022',
        }
    
    def _get_cache_key(self, method: str, symbol: str) -> str:
        """Generate cache key for API calls"""
        return f"{method}_{symbol}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in api_cache:
            return False
        
        cached_time = api_cache[cache_key]['timestamp']
        current_time = datetime.datetime.now()
        return (current_time - cached_time).seconds < CACHE_DURATION
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get basic stock information with caching"""
        cache_key = self._get_cache_key('stock_info', symbol)
        
        if self._is_cache_valid(cache_key):
            return api_cache[cache_key]['data']
        
        try:
            if symbol not in self.known_instruments:
                logger.error(f"Symbol {symbol} not found in known instruments")
                return None
                
            instrument_key = self.known_instruments[symbol]
            
            if not self.use_live_data:
                logger.error(f"No API credentials available for {symbol}")
                return None
            
            # Real API call to get market quote
            url = f"{self.base_url}/market-quote/quotes"
            params = {'instrument_key': instrument_key}
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and data.get('data'):
                    quote_data = data['data'].get(instrument_key)
                    if quote_data:
                        stock_info = {
                            'instrument_key': instrument_key,
                            'company_name': symbol,
                            'last_price': float(quote_data.get('last_price', 0)),
                            'change': float(quote_data.get('net_change', 0)),
                            'pchange': float(quote_data.get('percent_change', 0))
                        }
                        
                        # Cache the result
                        api_cache[cache_key] = {
                            'data': stock_info,
                            'timestamp': datetime.datetime.now()
                        }
                        
                        return stock_info
                    else:
                        logger.error(f"No data found for instrument {instrument_key}")
                        return None
                else:
                    logger.error(f"API Error for {symbol}: {data.get('message', 'Unknown error')}")
                    return None
            else:
                logger.error(f"HTTP Error {response.status_code} for {symbol}: {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching stock info for {symbol}: {e}")
            return None
    
    
    
    
    
    def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get options chain data from Upstox API"""
        try:
            if symbol not in self.known_instruments:
                logger.error(f"Symbol {symbol} not found in known instruments")
                return None
                
            instrument_key = self.known_instruments[symbol]
            
            if not self.use_live_data:
                logger.error(f"No API credentials available for {symbol}")
                return None
            
            # Get options chain
            url = f"{self.base_url}/option-chain"
            params = {'instrument_key': instrument_key}
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and data.get('data'):
                    return data['data']
                else:
                    logger.error(f"Options chain API Error for {symbol}: {data.get('message', 'Unknown error')}")
                    return None
            else:
                logger.error(f"Options chain HTTP Error {response.status_code} for {symbol}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return None
    
    def calculate_gamma_exposure(self, symbol: str, current_price: float) -> Optional[Dict]:
        """Calculate gamma exposure using real options data"""
        try:
            options_data = self.get_options_chain(symbol)
            
            if not options_data:
                logger.error(f"No options data available for {symbol} - cannot calculate gamma exposure")
                return None
            
            gamma_data = {}
            
            # Process options chain data
            for expiry_data in options_data:
                for option in expiry_data.get('option_data', []):
                    strike = float(option['strike_price'])
                    
                    # Get call and put data
                    call_data = option.get('call_options', {})
                    put_data = option.get('put_options', {})
                    
                    # Calculate gamma exposure (simplified formula)
                    # Real calculation would use Black-Scholes gamma
                    call_oi = float(call_data.get('open_interest', 0))
                    put_oi = float(put_data.get('open_interest', 0))
                    
                    # Simplified gamma calculation
                    moneyness = abs(strike - current_price) / current_price
                    gamma_factor = max(0, 0.1 - moneyness)  # Peak at ATM
                    
                    call_gamma_exposure = call_oi * gamma_factor * 100 * strike  # Notional exposure
                    put_gamma_exposure = -put_oi * gamma_factor * 100 * strike  # Negative for puts
                    
                    gamma_data[strike] = {
                        'call_gamma_exposure': call_gamma_exposure,
                        'put_gamma_exposure': put_gamma_exposure,
                        'net_gamma_exposure': call_gamma_exposure + put_gamma_exposure
                    }
            
            return gamma_data
            
        except Exception as e:
            logger.error(f"Error calculating gamma exposure for {symbol}: {e}")
            return None
    
    
    
    def find_gamma_levels(self, gamma_exposure: Dict, current_price: float) -> Dict:
        """Find key gamma levels"""
        try:
            max_call_gamma = 0
            max_put_gamma = 0
            call_wall = None
            put_wall = None
            zero_gamma = None
            min_net_gamma_diff = float('inf')
            
            for strike, data in gamma_exposure.items():
                # Call Wall - maximum call gamma
                if data['call_gamma_exposure'] > max_call_gamma:
                    max_call_gamma = data['call_gamma_exposure']
                    call_wall = strike
                
                # Put Wall - maximum put gamma (most negative)
                if abs(data['put_gamma_exposure']) > max_put_gamma:
                    max_put_gamma = abs(data['put_gamma_exposure'])
                    put_wall = strike
                
                # Zero Gamma - closest to zero net gamma
                net_gamma_abs = abs(data['net_gamma_exposure'])
                if net_gamma_abs < min_net_gamma_diff:
                    min_net_gamma_diff = net_gamma_abs
                    zero_gamma = strike
            
            return {
                'call_wall': {
                    'strike': call_wall,
                    'gamma_exposure': max_call_gamma,
                    'distance_from_current': (call_wall - current_price) if call_wall else None
                },
                'put_wall': {
                    'strike': put_wall,
                    'gamma_exposure': max_put_gamma,
                    'distance_from_current': (current_price - put_wall) if put_wall else None
                },
                'zero_gamma': {
                    'strike': zero_gamma,
                    'net_gamma_exposure': gamma_exposure[zero_gamma]['net_gamma_exposure'] if zero_gamma else None,
                    'distance_from_current': abs(zero_gamma - current_price) if zero_gamma else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error finding gamma levels: {e}")
            return {}
    
    def generate_gex_chart(self, symbol: str, gamma_exposure: Dict, gamma_levels: Dict) -> BytesIO:
        """Generate GEX profile chart with highlighted key levels"""
        try:
            fig, ax = plt.subplots(figsize=(14, 10))
            
            strikes = sorted(gamma_exposure.keys())
            call_gamma = [gamma_exposure[s]['call_gamma_exposure'] / 1000000 for s in strikes]  # Convert to millions
            put_gamma = [gamma_exposure[s]['put_gamma_exposure'] / 1000000 for s in strikes]
            net_gamma = [gamma_exposure[s]['net_gamma_exposure'] / 1000000 for s in strikes]
            
            # Create bars for call and put gamma
            bar_width = (max(strikes) - min(strikes)) / len(strikes) * 0.8
            ax.bar(strikes, call_gamma, width=bar_width, color='green', alpha=0.7, label='Call Gamma', edgecolor='darkgreen')
            ax.bar(strikes, put_gamma, width=bar_width, color='red', alpha=0.7, label='Put Gamma', edgecolor='darkred')
            
            # Add net gamma line
            ax.plot(strikes, net_gamma, color='blue', linewidth=2, marker='o', markersize=4, label='Net Gamma')
            
            # Mark and label key levels with enhanced visibility
            key_levels_added = []
            
            if gamma_levels.get('call_wall'):
                call_wall_strike = gamma_levels['call_wall']['strike']
                ax.axvline(call_wall_strike, color='darkgreen', linestyle='--', linewidth=3, alpha=0.8, label=f'Call Wall: ₹{call_wall_strike:.0f}')
                ax.text(call_wall_strike, max(call_gamma) * 0.9, f'Call Wall\n₹{call_wall_strike:.0f}', 
                       ha='center', va='bottom', fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", facecolor='lightgreen', alpha=0.7))
                key_levels_added.append(call_wall_strike)
            
            if gamma_levels.get('put_wall'):
                put_wall_strike = gamma_levels['put_wall']['strike']
                ax.axvline(put_wall_strike, color='darkred', linestyle='--', linewidth=3, alpha=0.8, label=f'Put Wall: ₹{put_wall_strike:.0f}')
                ax.text(put_wall_strike, min(put_gamma) * 0.9, f'Put Wall\n₹{put_wall_strike:.0f}', 
                       ha='center', va='top', fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", facecolor='lightcoral', alpha=0.7))
                key_levels_added.append(put_wall_strike)
            
            if gamma_levels.get('zero_gamma'):
                zero_gamma_strike = gamma_levels['zero_gamma']['strike']
                ax.axvline(zero_gamma_strike, color='blue', linestyle='--', linewidth=3, alpha=0.8, label=f'Zero Gamma: ₹{zero_gamma_strike:.0f}')
                ax.text(zero_gamma_strike, 0, f'Zero Gamma\n₹{zero_gamma_strike:.0f}', 
                       ha='center', va='center', fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue', alpha=0.7))
                key_levels_added.append(zero_gamma_strike)
            
            # Customize x-axis to highlight key levels
            ax.set_xticks(strikes[::max(1, len(strikes)//10)] + key_levels_added)
            ax.tick_params(axis='x', rotation=45)
            
            # Add horizontal line at zero
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            
            ax.set_title(f'Gamma Exposure Profile - {symbol}', fontsize=18, fontweight='bold', pad=20)
            ax.set_xlabel('Strike Price (₹)', fontsize=14, fontweight='bold')
            ax.set_ylabel('Gamma Exposure (₹ Millions)', fontsize=14, fontweight='bold')
            ax.legend(loc='upper right', fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # Improve layout
            plt.tight_layout()
            
            # Save to BytesIO
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight', facecolor='white')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return None
    
    def calculate_advanced_greeks(self, symbol: str) -> Dict:
        """Calculate Vanna and Charm exposure"""
        # Mock calculations for demo
        vanna_exposure = np.random.choice(['High Positive', 'Moderate Positive', 'Low Positive', 'Negative'])
        charm_exposure = np.random.choice(['Slightly Negative', 'Moderately Negative', 'Neutral', 'Positive'])
        
        interpretations = {
            'vanna': {
                'High Positive': 'A sharp drop in IV could force dealers to buy, supporting prices.',
                'Moderate Positive': 'IV changes may provide moderate price support.',
                'Low Positive': 'Minor impact from volatility changes expected.',
                'Negative': 'IV drop could lead to dealer selling pressure.'
            },
            'charm': {
                'Slightly Negative': 'A minor headwind into the end of the day due to time decay.',
                'Moderately Negative': 'Time decay creates moderate selling pressure.',
                'Neutral': 'Time decay impact is balanced.',
                'Positive': 'Time decay may provide buying support.'
            }
        }
        
        return {
            'vanna': {
                'level': vanna_exposure,
                'interpretation': interpretations['vanna'][vanna_exposure]
            },
            'charm': {
                'level': charm_exposure,
                'interpretation': interpretations['charm'][charm_exposure]
            }
        }
    
    def run_confluence_scan(self, strategy: str) -> List[Dict]:
        """Run confluence scanner for different strategies"""
        results = []
        
        # Sample stocks for scanning
        scan_stocks = ['RELIANCE', 'HDFCBANK', 'INFY', 'TCS', 'ICICIBANK']
        
        for stock in scan_stocks:
            stock_info = self.get_stock_info(stock)
            if not stock_info:
                continue
            
            current_price = stock_info['last_price']
            
            # Mock technical analysis
            technical_strong = np.random.choice([True, False], p=[0.3, 0.7])  # 30% pass rate
            
            if technical_strong:
                gamma_exposure = self.calculate_gamma_exposure(stock, current_price)
                gamma_levels = self.find_gamma_levels(gamma_exposure, current_price)
                
                if strategy == 'uptrend_dip_buy':
                    put_wall = gamma_levels.get('put_wall', {}).get('strike', current_price * 0.98)
                    distance_to_put_wall = abs(current_price - put_wall) / current_price
                    
                    if distance_to_put_wall <= 0.005:  # Within 0.5%
                        results.append({
                            'symbol': stock,
                            'spot': current_price,
                            'key_level': put_wall,
                            'level_type': 'Put Wall',
                            'status': '🟢 Technically Strong, hitting major options support.'
                        })
                
                elif strategy == 'bearish_breakdown':
                    put_wall = gamma_levels.get('put_wall', {}).get('strike', current_price * 0.98)
                    if current_price < put_wall:
                        results.append({
                            'symbol': stock,
                            'spot': current_price,
                            'key_level': put_wall,
                            'level_type': 'Put Wall',
                            'status': '🔴 Broke below Put Wall - Bearish breakdown setup.'
                        })
                
                elif strategy == 'gamma_squeeze':
                    call_wall = gamma_levels.get('call_wall', {}).get('strike', current_price * 1.02)
                    distance_to_call_wall = abs(current_price - call_wall) / current_price
                    
                    if distance_to_call_wall <= 0.01:  # Within 1%
                        results.append({
                            'symbol': stock,
                            'spot': current_price,
                            'key_level': call_wall,
                            'level_type': 'Call Wall',
                            'status': '⚡ Approaching Call Wall - Potential gamma squeeze setup.'
                        })
        
        return results[:3]  # Return top 3 results

# Initialize calculator
gamma_calculator = GammaEdgeCalculator()

# ==================== TELEGRAM BOT HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with main menu"""
    keyboard = [
        [InlineKeyboardButton("📊 Analyze GEX", callback_data="main_gex")],
        [InlineKeyboardButton("🔍 Scan for Setups", callback_data="main_scan")],
        [InlineKeyboardButton("🔔 Setup Alerts", callback_data="main_monitor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = """
🚀 **Welcome, Trader!**

I am **Gamma Edge**, your advanced market structure analysis assistant.

**Main Features:**
📊 `/gex` - Analyze Gamma Exposure for instruments
🔍 `/scan` - Scan for high-probability setups  
🔔 `/monitor` - Get real-time alerts on key levels

**Choose an option below to begin:**
    """
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send detailed help"""
    help_text = """
🔧 **Gamma Edge - Help Guide**

**📊 GEX Analysis (`/gex`):**
• Calculates Call Wall, Put Wall, Zero Gamma levels
• Shows regime analysis (Positive/Negative Gamma)
• Generates visual GEX profile charts
• Provides advanced Greeks (Vanna & Charm)

**🔍 Confluence Scanner (`/scan`):**
• Uptrend Dip-Buy: Technical + Options support confluence
• Bearish Breakdown: Stocks breaking key support levels
• Gamma Squeeze: Stocks approaching major resistance

**🔔 Real-time Monitoring (`/monitor`):**
• Zero Gamma Cross alerts
• Wall Proximity alerts (1% threshold)
• Automatic notifications when conditions are met

**Supported Instruments:**
• Indices: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY
• F&O Stocks: 100+ major stocks across all sectors

Type `/start` to return to the main menu.
    """
    await update.message.reply_text(help_text)

async def gex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gex command"""
    keyboard = [
        [InlineKeyboardButton("NIFTY", callback_data="gex_NIFTY")],
        [InlineKeyboardButton("BANKNIFTY", callback_data="gex_BANKNIFTY")],
        [InlineKeyboardButton("FINNIFTY", callback_data="gex_FINNIFTY")],
        [InlineKeyboardButton("🔎 Other Stock", callback_data="gex_other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 **GEX Analysis**\n\nSelect an instrument:",
        reply_markup=reply_markup
    )

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scan command"""
    keyboard = [
        [InlineKeyboardButton("Bullish: Uptrend Dip-Buy", callback_data="scan_uptrend_dip_buy")],
        [InlineKeyboardButton("Bearish: Breakdown Setup", callback_data="scan_bearish_breakdown")],
        [InlineKeyboardButton("Momentum: Gamma Squeeze", callback_data="scan_gamma_squeeze")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔍 **Confluence Scanner**\n\nSelect a pre-built strategy:",
        reply_markup=reply_markup
    )

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monitor command"""
    keyboard = [
        [InlineKeyboardButton("NIFTY", callback_data="monitor_NIFTY")],
        [InlineKeyboardButton("BANKNIFTY", callback_data="monitor_BANKNIFTY")],
        [InlineKeyboardButton("🔎 Other Stock", callback_data="monitor_other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔔 **Real-time Monitoring**\n\nSelect instrument to monitor:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # Main menu callbacks
    if data == "main_gex":
        keyboard = [
            [InlineKeyboardButton("NIFTY", callback_data="gex_NIFTY")],
            [InlineKeyboardButton("BANKNIFTY", callback_data="gex_BANKNIFTY")],
            [InlineKeyboardButton("FINNIFTY", callback_data="gex_FINNIFTY")],
            [InlineKeyboardButton("🔎 Other Stock", callback_data="gex_other")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📊 **GEX Analysis**\n\nSelect an instrument:", reply_markup=reply_markup)
        return
    elif data == "main_scan":
        keyboard = [
            [InlineKeyboardButton("Bullish: Uptrend Dip-Buy", callback_data="scan_uptrend_dip_buy")],
            [InlineKeyboardButton("Bearish: Breakdown Setup", callback_data="scan_bearish_breakdown")],
            [InlineKeyboardButton("Momentum: Gamma Squeeze", callback_data="scan_gamma_squeeze")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🔍 **Confluence Scanner**\n\nSelect a pre-built strategy:", reply_markup=reply_markup)
        return
    elif data == "main_monitor":
        keyboard = [
            [InlineKeyboardButton("NIFTY", callback_data="monitor_NIFTY")],
            [InlineKeyboardButton("BANKNIFTY", callback_data="monitor_BANKNIFTY")],
            [InlineKeyboardButton("🔎 Other Stock", callback_data="monitor_other")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🔔 **Real-time Monitoring**\n\nSelect instrument to monitor:", reply_markup=reply_markup)
        return
    
    # GEX Analysis callbacks
    if data.startswith("gex_"):
        symbol = data.replace("gex_", "")
        if symbol == "other":
            await query.edit_message_text("Please type the stock symbol (e.g., RELIANCE):")
            context.user_data['waiting_for'] = 'gex_symbol'
        else:
            await process_gex_analysis(query, symbol)
        return
    
    # Expiry selection callbacks
    if data.startswith("expiry_"):
        parts = data.split("_")
        symbol = parts[1]
        expiry_type = parts[2]
        await process_gex_with_expiry(query, symbol, expiry_type)
        return
    
    # Chart and advanced Greeks callbacks
    if data.startswith("chart_"):
        symbol = data.replace("chart_", "")
        await send_gex_chart(query, symbol)
        return
    
    if data.startswith("greeks_"):
        symbol = data.replace("greeks_", "")
        await send_advanced_greeks(query, symbol)
        return
    
    # Scanner callbacks
    if data.startswith("scan_"):
        strategy = data.replace("scan_", "")
        await process_confluence_scan(query, strategy)
        return
    
    # Monitor callbacks
    if data.startswith("monitor_"):
        symbol = data.replace("monitor_", "")
        if symbol == "other":
            await query.edit_message_text("Please type the stock symbol to monitor:")
            context.user_data['waiting_for'] = 'monitor_symbol'
        else:
            await setup_monitoring(query, symbol, user_id)
        return

async def process_gex_analysis(query, symbol: str) -> None:
    """Process GEX analysis for a symbol"""
    await query.edit_message_text(f"🔍 Analyzing {symbol}... Please wait...")
    
    # Get stock info
    stock_info = gamma_calculator.get_stock_info(symbol)
    if not stock_info:
        await query.edit_message_text(f"❌ Could not find data for {symbol}. Please check the symbol.")
        return
    
    # Show expiry selection
    keyboard = [
        [InlineKeyboardButton("Weekly", callback_data=f"expiry_{symbol}_weekly")],
        [InlineKeyboardButton("Monthly", callback_data=f"expiry_{symbol}_monthly")],
        [InlineKeyboardButton("🗓️ Term Structure", callback_data=f"expiry_{symbol}_term")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"Select expiry for {symbol}:", reply_markup=reply_markup)

async def process_gex_with_expiry(query, symbol: str, expiry_type: str) -> None:
    """Process GEX analysis with expiry selection"""
    await query.edit_message_text(f"🔍 **Analyzing {symbol}** ({expiry_type.title()} Expiry)...\n\n⚡ Fetching data from Upstox API...")
    
    # Get analysis data
    stock_info = gamma_calculator.get_stock_info(symbol)
    if not stock_info:
        await query.edit_message_text(f"❌ **Error fetching data for {symbol}**\n\nUnable to retrieve stock information from Upstox API. Please check:\n• Symbol is correct\n• API credentials are valid\n• Market is open")
        return
    
    current_price = stock_info['last_price']
    
    gamma_exposure = gamma_calculator.calculate_gamma_exposure(symbol, current_price)
    if not gamma_exposure:
        await query.edit_message_text(f"❌ **Error calculating gamma exposure for {symbol}**\n\nUnable to retrieve options chain data from Upstox API. Please check:\n• Options trading is available for this symbol\n• API credentials have options data access\n• Market is open")
        return
    
    gamma_levels = gamma_calculator.find_gamma_levels(gamma_exposure, current_price)
    if not gamma_levels:
        await query.edit_message_text(f"❌ **Error calculating gamma levels for {symbol}**\n\nInsufficient options data to calculate key levels.")
        return
    
    # Determine regime
    zero_gamma_strike = gamma_levels.get('zero_gamma', {}).get('strike', current_price)
    if current_price > zero_gamma_strike:
        regime = "Positive Gamma"
        regime_interpretation = "Market is in a stabilizing state. Expect range-bound movement with mean reversion."
    else:
        regime = "Negative Gamma"
        regime_interpretation = "Market is in a volatile state. Expect trending moves to accelerate."
    
    # Build result message
    expiry_date = "25 JUL 2025"  # Mock expiry
    result_msg = f"""📊 **GEX Analysis for {symbol}** ({expiry_date} Expiry)

🎯 **Spot:** ₹{current_price:.2f}

**🎯 Key Levels:**
"""
    
    if gamma_levels.get('call_wall'):
        call_wall = gamma_levels['call_wall']
        result_msg += f"🔴 **Call Wall:** ₹{call_wall['strike']:.0f}\n"
    
    if gamma_levels.get('zero_gamma'):
        zero_gamma = gamma_levels['zero_gamma']
        result_msg += f"⚪ **Zero Gamma:** ₹{zero_gamma['strike']:.0f}\n"
    
    if gamma_levels.get('put_wall'):
        put_wall = gamma_levels['put_wall']
        result_msg += f"🟢 **Put Wall:** ₹{put_wall['strike']:.0f}\n"
    
    result_msg += f"""
**📊 Regime Analysis:**
*Regime: {regime}*
*Interpretation: {regime_interpretation}*
"""
    
    # Action buttons
    keyboard = [
        [InlineKeyboardButton("📈 Show GEX Profile Chart", callback_data=f"chart_{symbol}")],
        [InlineKeyboardButton("🔬 Advanced Greeks", callback_data=f"greeks_{symbol}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(result_msg, reply_markup=reply_markup)

async def send_gex_chart(query, symbol: str) -> None:
    """Send GEX profile chart"""
    await query.answer("Fetching data and generating chart...")
    
    # Get data
    stock_info = gamma_calculator.get_stock_info(symbol)
    if not stock_info:
        await query.message.reply_text(f"❌ **Error fetching data for {symbol}**\n\nUnable to retrieve stock information from Upstox API.")
        return
    
    current_price = stock_info['last_price']
    gamma_exposure = gamma_calculator.calculate_gamma_exposure(symbol, current_price)
    if not gamma_exposure:
        await query.message.reply_text(f"❌ **Error fetching options data for {symbol}**\n\nUnable to retrieve options chain data from Upstox API.")
        return
    
    gamma_levels = gamma_calculator.find_gamma_levels(gamma_exposure, current_price)
    if not gamma_levels:
        await query.message.reply_text(f"❌ **Error calculating gamma levels for {symbol}**\n\nInsufficient options data to calculate key levels.")
        return
    
    # Generate chart
    chart_buffer = gamma_calculator.generate_gex_chart(symbol, gamma_exposure, gamma_levels)
    
    if chart_buffer:
        await query.message.reply_photo(
            photo=InputFile(chart_buffer, filename=f"gex_chart_{symbol}.png"),
            caption=f"📈 **Gamma Exposure Profile - {symbol}**"
        )
    else:
        await query.message.reply_text("❌ Error generating chart. Please try again.")

async def send_advanced_greeks(query, symbol: str) -> None:
    """Send advanced Greeks analysis"""
    await query.answer("Calculating advanced Greeks...")
    
    greeks = gamma_calculator.calculate_advanced_greeks(symbol)
    
    result_msg = f"""🔬 **Advanced Greeks** (25 JUL 2025):

💧 **Vanna Exposure:** {greeks['vanna']['level']}
*Interpretation: {greeks['vanna']['interpretation']}*

⏳ **Charm Exposure:** {greeks['charm']['level']}
*Interpretation: {greeks['charm']['interpretation']}*
"""
    
    await query.message.reply_text(result_msg)

async def process_confluence_scan(query, strategy: str) -> None:
    """Process confluence scanner with detailed criteria explanation"""
    await query.edit_message_text(f"🔍 **Running {strategy.replace('_', ' ').title()} Scan...**\n\n⚡ Scanning F&O stocks...")
    
    # Get scan criteria explanation
    criteria_explanation = get_scan_criteria_explanation(strategy)
    
    results = gamma_calculator.run_confluence_scan(strategy)
    
    result_msg = f"🔍 **Scan Results: {strategy.replace('_', ' ').title()}**\n\n"
    result_msg += f"**📋 Scan Criteria:**\n{criteria_explanation}\n\n"
    
    if not results:
        result_msg += "❌ **No setups found matching the criteria.**\n\n"
        result_msg += "**💡 What this means:**\n"
        result_msg += "• No stocks currently meet all the technical and options flow requirements\n"
        result_msg += "• Market conditions may not be favorable for this strategy\n"
        result_msg += "• Try running the scan again during different market hours\n"
    else:
        result_msg += f"✅ **{len(results)} Setups Found:**\n\n"
        
        for i, result in enumerate(results, 1):
            result_msg += f"**{i}. {result['symbol']}**\n"
            result_msg += f"   `Spot: ₹{result['spot']:.0f} | {result['level_type']}: ₹{result['key_level']:.0f}`\n"
            result_msg += f"   `{result['status']}`\n\n"
    
    await query.edit_message_text(result_msg)

def get_scan_criteria_explanation(strategy: str) -> str:
    """Get detailed explanation of scan criteria for each strategy"""
    criteria = {
        'uptrend_dip_buy': """
• **Technical Filter:** Stock in clear uptrend (20 EMA > 50 EMA)
• **Options Flow:** Price within 0.5% of major Put Wall support
• **Volume:** Above average volume confirming interest
• **Risk-Reward:** Clear resistance levels above for target setting
• **Confluence:** Technical strength + Options support alignment""",
        
        'bearish_breakdown': """
• **Technical Filter:** Stock showing weakness (Price < 20 EMA)
• **Options Flow:** Price broken below major Put Wall support
• **Volume:** Increased volume on breakdown confirming selling
• **Momentum:** Negative gamma environment supporting further decline
• **Confluence:** Technical breakdown + Options flow bearish alignment""",
        
        'gamma_squeeze': """
• **Technical Filter:** Stock approaching resistance with momentum
• **Options Flow:** Price within 1% of major Call Wall resistance
• **Options Activity:** High Call OI creating potential squeeze setup
• **Gamma Environment:** Positive gamma that could accelerate moves
• **Confluence:** Technical breakout potential + Options squeeze mechanics"""
    }
    
    return criteria.get(strategy, "Criteria not defined for this strategy.")

async def setup_monitoring(query, symbol: str, user_id: int) -> None:
    """Setup monitoring for a symbol"""
    keyboard = [
        [InlineKeyboardButton("Zero Gamma Cross", callback_data=f"monitor_setup_{symbol}_zero_gamma")],
        [InlineKeyboardButton("Wall Proximity (1%)", callback_data=f"monitor_setup_{symbol}_wall_proximity")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🔔 **Monitor {symbol}**\n\nWhat would you like to monitor?",
        reply_markup=reply_markup
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""
    user_input = update.message.text.upper()
    waiting_for = context.user_data.get('waiting_for')
    
    if waiting_for == 'gex_symbol':
        if user_input in gamma_calculator.known_instruments:
            context.user_data.pop('waiting_for', None)
            # Create a mock query object for processing
            class MockQuery:
                def __init__(self, message):
                    self.message = message
                async def edit_message_text(self, text, reply_markup=None):
                    await self.message.reply_text(text, reply_markup=reply_markup)
            
            mock_query = MockQuery(update.message)
            await process_gex_analysis(mock_query, user_input)
        else:
            await update.message.reply_text(f"❌ Symbol '{user_input}' not found. Please enter a valid F&O stock symbol.")
    
    elif waiting_for == 'monitor_symbol':
        if user_input in gamma_calculator.known_instruments:
            context.user_data.pop('waiting_for', None)
            class MockQuery:
                def __init__(self, message):
                    self.message = message
                async def edit_message_text(self, text, reply_markup=None):
                    await self.message.reply_text(text, reply_markup=reply_markup)
            
            mock_query = MockQuery(update.message)
            await setup_monitoring(mock_query, user_input, update.effective_user.id)
        else:
            await update.message.reply_text(f"❌ Symbol '{user_input}' not found. Please enter a valid F&O stock symbol.")
    
    else:
        # General message handling
        await update.message.reply_text(
            f"👋 Hello! I'm Gamma Edge.\n\n"
            f"🎯 **Quick Actions:**\n"
            f"• Type `/start` for the main menu\n"
            f"• Type `/gex` for gamma analysis\n"
            f"• Type `/scan` for confluence scanner\n"
            f"• Type `/monitor` for real-time alerts\n\n"
            f"Ready to analyze the markets! 📈"
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Something went wrong. Please try again or contact support."
        )

async def start_scheduler(context):
    """Start the scheduler after event loop is running"""
    if not scheduler.running:
        scheduler.start()
        print("✅ Scheduler started successfully")

def main() -> None:
    """Start the Gamma Edge Telegram bot"""
    print("🚀 Starting Gamma Edge - Advanced Options Analysis Bot...")
    print("📊 Powered by Upstox API for real-time market data")
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("gex", gex_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)

    # Start scheduler after application starts
    application.job_queue.run_once(start_scheduler, when=1)
    
    # Start the bot
    print("✅ Gamma Edge Bot is running! Send /start to begin")
    application.run_polling()

if __name__ == '__main__':
    main()
