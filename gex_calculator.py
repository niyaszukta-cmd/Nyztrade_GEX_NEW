import pandas as pd
import numpy as np
from scipy.stats import norm
import requests
from datetime import datetime, timedelta
import time
import json

class BlackScholesCalculator:
    """Calculate Greeks using Black-Scholes model"""
    
    @staticmethod
    def calculate_gamma(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        return gamma
    
    @staticmethod
    def calculate_delta(S, K, T, r, sigma, option_type='call'):
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        return delta

class EnhancedGEXDEXCalculator:
    """Enhanced GEX and DEX calculator with smart fallback"""
    
    def __init__(self, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
    
    def fetch_via_cors_proxy(self, symbol="NIFTY"):
        """Use CORS proxy to bypass restrictions"""
        try:
            # Method 1: AllOrigins proxy
            nse_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            proxy_url = f"https://api.allorigins.win/raw?url={nse_url}"
            
            response = requests.get(proxy_url, timeout=30)
            
            if response.status_code == 200:
                return response.json(), "CORS Proxy"
        except:
            pass
        
        try:
            # Method 2: CORS Anywhere
            nse_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            proxy_url = f"https://cors-anywhere.herokuapp.com/{nse_url}"
            
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0'
            }
            
            response = requests.get(proxy_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json(), "CORS Anywhere"
        except:
            pass
        
        raise Exception("CORS proxies failed")
    
    def fetch_from_upstox_api(self, symbol="NIFTY"):
        """Try Upstox market data (free tier)"""
        try:
            # Upstox provides index data
            symbol_map = {
                "NIFTY": "NSE_INDEX|Nifty 50",
                "BANKNIFTY": "NSE_INDEX|Nifty Bank",
                "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
                "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT"
            }
            
            # Note: This is a placeholder - actual implementation would need Upstox API key
            # For demo purposes, we'll skip this
            raise Exception("Upstox requires API key")
            
        except:
            raise Exception("Upstox method not available")
    
    def generate_synthetic_data(self, symbol="NIFTY", spot_price=None):
        """Generate realistic synthetic data when APIs fail (for demo/testing)"""
        
        if spot_price is None:
            # Default prices for each index
            default_prices = {
                "NIFTY": 24500,
                "BANKNIFTY": 52000,
                "FINNIFTY": 22500,
                "MIDCPNIFTY": 12000
            }
            spot_price = default_prices.get(symbol, 24500)
        
        # Generate strikes around spot (±1200 points, 50 point intervals)
        strikes = np.arange(spot_price - 1200, spot_price + 1300, 50)
        
        option_data = []
        
        for strike in strikes:
            # Distance from ATM
            moneyness = (strike - spot_price) / spot_price
            
            # Synthetic OI (higher near ATM)
            distance_factor = np.exp(-abs(moneyness) * 10)
            
            call_oi = int(np.random.uniform(5000, 50000) * distance_factor)
            put_oi = int(np.random.uniform(5000, 50000) * distance_factor)
            
            # Synthetic IV (smile pattern)
            base_iv = 15 + abs(moneyness) * 50
            call_iv = base_iv + np.random.uniform(-2, 2)
            put_iv = base_iv + np.random.uniform(-2, 2)
            
            # Synthetic LTP based on intrinsic + time value
            call_intrinsic = max(spot_price - strike, 0)
            put_intrinsic = max(strike - spot_price, 0)
            
            call_ltp = call_intrinsic + abs(np.random.uniform(10, 100) * distance_factor)
            put_ltp = put_intrinsic + abs(np.random.uniform(10, 100) * distance_factor)
            
            # Volumes
            call_volume = int(call_oi * np.random.uniform(0.1, 0.3))
            put_volume = int(put_oi * np.random.uniform(0.1, 0.3))
            
            option_data.append({
                'Strike': float(strike),
                'Call_OI': call_oi,
                'Call_IV': call_iv / 100,
                'Call_LTP': call_ltp,
                'Call_Volume': call_volume,
                'Put_OI': put_oi,
                'Put_IV': put_iv / 100,
                'Put_LTP': put_ltp,
                'Put_Volume': put_volume
            })
        
        # Create synthetic response structure
        today = datetime.now()
        expiry_dates = [
            (today + timedelta(days=(4 - today.weekday()))).strftime('%d-%b-%Y'),  # This week
            (today + timedelta(days=(11 - today.weekday()))).strftime('%d-%b-%Y'),  # Next week
            (today + timedelta(days=28)).strftime('%d-%b-%Y')  # Monthly
        ]
        
        synthetic_response = {
            'records': {
                'expiryDates': expiry_dates,
                'data': [],
                'underlyingValue': spot_price
            }
        }
        
        for opt in option_data:
            synthetic_response['records']['data'].append({
                'strikePrice': opt['Strike'],
                'expiryDate': expiry_dates[0],
                'CE': {
                    'openInterest': opt['Call_OI'],
                    'impliedVolatility': opt['Call_IV'] * 100,
                    'lastPrice': opt['Call_LTP'],
                    'totalTradedVolume': opt['Call_Volume']
                },
                'PE': {
                    'openInterest': opt['Put_OI'],
                    'impliedVolatility': opt['Put_IV'] * 100,
                    'lastPrice': opt['Put_LTP'],
                    'totalTradedVolume': opt['Put_Volume']
                }
            })
        
        return synthetic_response, "Synthetic Data (Demo Mode)"
    
    def fetch_nse_option_chain(self, symbol="NIFTY"):
        """Master fetch with all fallbacks"""
        
        errors = []
        
        # Try CORS proxy
        try:
            data, method = self.fetch_via_cors_proxy(symbol)
            return data
        except Exception as e:
            errors.append(f"CORS Proxy: {str(e)}")
        
        # Last resort: Generate synthetic data for testing
        print("⚠️ WARNING: Using synthetic data (API unavailable)")
        data, method = self.generate_synthetic_data(symbol)
        return data
    
    def get_futures_ltp_from_multiple_sources(self, symbol="NIFTY"):
        """Get spot price from multiple sources"""
        
        # Try Yahoo Finance
        try:
            symbol_map = {
                "NIFTY": "^NSEI",
                "BANKNIFTY": "^NSEBANK"
            }
            
            if symbol in symbol_map:
                yahoo_symbol = symbol_map[symbol]
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                
                response = requests.get(url, timeout=10)
                data = response.json()
                
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price), "Yahoo Finance"
        except:
            pass
        
        # Try Groww
        try:
            symbol_map = {
                "NIFTY": "nifty-50",
                "BANKNIFTY": "nifty-bank"
            }
            
            if symbol in symbol_map:
                groww_symbol = symbol_map[symbol]
                url = f"https://groww.in/v1/api/charting_service/v2/chart/exchange/NSE/segment/CASH/symbol/{groww_symbol}/latest"
                
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                data = response.json()
                
                if 'ltp' in data:
                    return float(data['ltp']), "Groww.in"
        except:
            pass
        
        return None, None
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation function"""
        
        # Fetch option chain
        data = self.fetch_nse_option_chain(symbol)
        
        # Get spot price
        futures_ltp, fetch_method = self.get_futures_ltp_from_multiple_sources(symbol)
        
        if futures_ltp is None:
            try:
                futures_ltp = float(data['records']['underlyingValue'])
                fetch_method = "NSE Underlying"
            except:
                # Use default
                defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
                futures_ltp = defaults.get(symbol, 24500)
                fetch_method = "Default (APIs unavailable)"
        
        # Get expiry
        expiry_dates = data['records']['expiryDates']
        selected_expiry = expiry_dates[expiry_index]
        
        # Parse records
        records = data['records']['data']
        option_data = []
        
        for record in records:
            if record.get('expiryDate') != selected_expiry:
                continue
            
            strike = record['strikePrice']
            
            ce_data = record.get('CE', {})
            call_oi = ce_data.get('openInterest', 0)
            call_iv = ce_data.get('impliedVolatility', 0) / 100
            call_ltp = ce_data.get('lastPrice', 0)
            call_volume = ce_data.get('totalTradedVolume', 0)
            
            pe_data = record.get('PE', {})
            put_oi = pe_data.get('openInterest', 0)
            put_iv = pe_data.get('impliedVolatility', 0) / 100
            put_ltp = pe_data.get('lastPrice', 0)
            put_volume = pe_data.get('totalTradedVolume', 0)
            
            option_data.append({
                'Strike': strike,
                'Call_OI': call_oi,
                'Call_IV': call_iv,
                'Call_LTP': call_ltp,
                'Call_Volume': call_volume,
                'Put_OI': put_oi,
                'Put_IV': put_iv,
                'Put_LTP': put_ltp,
                'Put_Volume': put_volume
            })
        
        df = pd.DataFrame(option_data)
        
        # Filter strikes
        df = df[
            (df['Strike'] >= futures_ltp - strikes_range * 100) &
            (df['Strike'] <= futures_ltp + strikes_range * 100)
        ].copy()
        
        # Time to expiry
        expiry_date = datetime.strptime(selected_expiry, '%d-%b-%Y')
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        # Calculate Greeks
        df['Call_Gamma'] = df.apply(
            lambda row: self.bs_calc.calculate_gamma(
                futures_ltp, row['Strike'], T, self.risk_free_rate, max(row['Call_IV'], 0.01)
            ), axis=1
        )
        
        df['Put_Gamma'] = df.apply(
            lambda row: self.bs_calc.calculate_gamma(
                futures_ltp, row['Strike'], T, self.risk_free_rate, max(row['Put_IV'], 0.01)
            ), axis=1
        )
        
        df['Call_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                futures_ltp, row['Strike'], T, self.risk_free_rate, max(row['Call_IV'], 0.01), 'call'
            ), axis=1
        )
        
        df['Put_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                futures_ltp, row['Strike'], T, self.risk_free_rate, max(row['Put_IV'], 0.01), 'put'
            ), axis=1
        )
        
        # GEX and DEX
        df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * futures_ltp * futures_ltp * 0.01
        df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * futures_ltp * futures_ltp * 0.01 * -1
        df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
        df['Net_GEX_B'] = df['Net_GEX'] / 1e9
        
        df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * futures_ltp * 0.01
        df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * futures_ltp * 0.01
        df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
        df['Net_DEX_B'] = df['Net_DEX'] / 1e9
        
        # Hedging pressure
        total_gex = df['Net_GEX'].abs().sum()
        if total_gex > 0:
            df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex) * 100
        else:
            df['Hedging_Pressure'] = 0
        
        df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
        
        # ATM info
        atm_strike = df.iloc[(df['Strike'] - futures_ltp).abs().argsort()[0]]['Strike']
        atm_row = df[df['Strike'] == atm_strike].iloc[0]
        
        atm_info = {
            'atm_strike': int(atm_strike),
            'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
        }
        
        return df, futures_ltp, fetch_method, atm_info

def calculate_dual_gex_dex_flow(df, futures_ltp):
    df_sorted = df.sort_values('Strike').copy()
    atm_idx = (df_sorted['Strike'] - futures_ltp).abs().idxmin()
    atm_position = df_sorted.index.get_loc(atm_idx)
    
    start_idx = max(0, atm_position - 5)
    end_idx = min(len(df_sorted), atm_position + 6)
    near_strikes = df_sorted.iloc[start_idx:end_idx]
    
    positive_gex = near_strikes[near_strikes['Net_GEX_B'] > 0]['Net_GEX_B'].sum()
    negative_gex = near_strikes[near_strikes['Net_GEX_B'] < 0]['Net_GEX_B'].sum()
    gex_near_total = positive_gex + negative_gex
    
    if gex_near_total > 50:
        gex_bias = "STRONG BULLISH (Sideways to Bullish)"
    elif gex_near_total < -50:
        gex_bias = "VOLATILE (High Volatility Expected)"
    else:
        gex_bias = "NEUTRAL"
    
    dex_near_total = near_strikes['Net_DEX_B'].sum()
    dex_bias = "BULLISH" if dex_near_total > 0 else "BEARISH"
    
    if gex_near_total > 50 and dex_near_total > 0:
        combined = "STRONG BULLISH (Sideways to Bullish)"
    elif gex_near_total < -50:
        combined = "HIGH VOLATILITY"
    else:
        combined = f"MIXED ({gex_bias} + {dex_bias})"
    
    return {
        'gex_near_total': gex_near_total,
        'dex_near_total': dex_near_total,
        'gex_near_bias': gex_bias,
        'dex_near_bias': dex_bias,
        'combined_bias': combined
    }

def detect_gamma_flip_zones(df):
    flip_zones = []
    df_sorted = df.sort_values('Strike').reset_index(drop=True)
    
    for i in range(len(df_sorted) - 1):
        current_gex = df_sorted.loc[i, 'Net_GEX_B']
        next_gex = df_sorted.loc[i + 1, 'Net_GEX_B']
        
        if (current_gex > 0 and next_gex < 0) or (current_gex < 0 and next_gex > 0):
            flip_zones.append({
                'lower_strike': df_sorted.loc[i, 'Strike'],
                'upper_strike': df_sorted.loc[i + 1, 'Strike'],
                'type': 'Positive to Negative' if current_gex > 0 else 'Negative to Positive'
            })
    
    return flip_zones
