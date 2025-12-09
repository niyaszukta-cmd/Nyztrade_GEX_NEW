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
    """Enhanced GEX and DEX calculator with multiple data sources"""
    
    def __init__(self, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
    
    def fetch_from_alternative_api(self, symbol="NIFTY"):
        """Fetch from alternative source - nse-data-api (Render deployment)"""
        try:
            # Using public NSE data API
            url = f"https://nse-data-api.onrender.com/api/option-chain?symbol={symbol}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                return response.json(), "Alternative API"
            else:
                raise Exception(f"Alternative API returned {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Alternative API failed: {str(e)}")
    
    def fetch_from_opstra_style(self, symbol="NIFTY"):
        """Try opstra-style proxy"""
        try:
            session = requests.Session()
            
            # More aggressive headers
            headers = {
                'authority': 'www.nseindia.com',
                'method': 'GET',
                'scheme': 'https',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            session.headers.update(headers)
            
            # Multi-step access
            session.get('https://www.nseindia.com', timeout=10)
            time.sleep(0.5)
            session.get('https://www.nseindia.com/get-quotes/derivatives?symbol=NIFTY', timeout=10)
            time.sleep(0.5)
            
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            response = session.get(url, timeout=15)
            
            if response.status_code == 200:
                return response.json(), "NSE Direct (Opstra Method)"
            else:
                raise Exception(f"NSE Direct returned {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Opstra method failed: {str(e)}")
    
    def fetch_nse_option_chain(self, symbol="NIFTY"):
        """Fetch with fallback methods"""
        
        errors = []
        
        # Method 1: Try alternative API first (most reliable on cloud)
        try:
            data, method = self.fetch_from_alternative_api(symbol)
            return data
        except Exception as e:
            errors.append(f"Alternative API: {str(e)}")
        
        # Method 2: Try opstra-style access
        try:
            data, method = self.fetch_from_opstra_style(symbol)
            return data
        except Exception as e:
            errors.append(f"Opstra method: {str(e)}")
        
        # If all methods fail
        error_msg = "All data sources failed:\n" + "\n".join(errors)
        error_msg += "\n\nNSE is blocking cloud server IPs. Solutions:\n"
        error_msg += "1. Try after 10-15 minutes\n"
        error_msg += "2. Use during market hours (9:15 AM - 3:30 PM IST)\n"
        error_msg += "3. Contact NYZTrade for premium data feed access"
        
        raise Exception(error_msg)
    
    def get_futures_ltp_from_multiple_sources(self, symbol="NIFTY"):
        """Try multiple sources for futures price"""
        
        # Method 1: Groww
        try:
            symbol_map = {
                "NIFTY": "nifty-50",
                "BANKNIFTY": "nifty-bank",
                "FINNIFTY": "nifty-financial-services",
                "MIDCPNIFTY": "nifty-midcap-50"
            }
            
            groww_symbol = symbol_map.get(symbol, "nifty-50")
            url = f"https://groww.in/v1/api/charting_service/v2/chart/exchange/NSE/segment/CASH/symbol/{groww_symbol}/latest"
            
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            data = response.json()
            
            if 'ltp' in data:
                return float(data['ltp']), "Groww.in"
        except:
            pass
        
        # Method 2: Try Yahoo Finance
        try:
            symbol_map = {
                "NIFTY": "^NSEI",
                "BANKNIFTY": "^NSEBANK",
                "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
                "MIDCPNIFTY": "NIFTY_MIDCAP_50.NS"
            }
            
            yahoo_symbol = symbol_map.get(symbol, "^NSEI")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            
            response = requests.get(url, timeout=5)
            data = response.json()
            
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return float(price), "Yahoo Finance"
        except:
            pass
        
        return None, None
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main function with robust error handling"""
        
        # Fetch option chain
        data = self.fetch_nse_option_chain(symbol)
        
        # Get futures price
        futures_ltp, fetch_method = self.get_futures_ltp_from_multiple_sources(symbol)
        
        if futures_ltp is None:
            try:
                futures_ltp = float(data['records']['underlyingValue'])
                fetch_method = "NSE Underlying"
            except:
                records = data['records']['data']
                if records:
                    futures_ltp = records[len(records)//2].get('strikePrice', 25000)
                    fetch_method = "ATM Strike"
        
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
                futures_ltp, row['Strike'], T, self.risk_free_rate, row['Call_IV']
            ) if row['Call_IV'] > 0 else 0, axis=1
        )
        
        df['Put_Gamma'] = df.apply(
            lambda row: self.bs_calc.calculate_gamma(
                futures_ltp, row['Strike'], T, self.risk_free_rate, row['Put_IV']
            ) if row['Put_IV'] > 0 else 0, axis=1
        )
        
        df['Call_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                futures_ltp, row['Strike'], T, self.risk_free_rate, row['Call_IV'], 'call'
            ) if row['Call_IV'] > 0 else 0, axis=1
        )
        
        df['Put_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                futures_ltp, row['Strike'], T, self.risk_free_rate, row['Put_IV'], 'put'
            ) if row['Put_IV'] > 0 else 0, axis=1
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
