import pandas as pd
import numpy as np
from scipy.stats import norm
import requests
from datetime import datetime, timedelta
import time
from fake_useragent import UserAgent

class BlackScholesCalculator:
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
    def __init__(self, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.session = None
    
    def get_session(self):
        """Create session with rotating user agents"""
        if self.session is None:
            self.session = requests.Session()
        
        try:
            ua = UserAgent()
            user_agent = ua.random
        except:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        
        headers = {
            'User-Agent': user_agent,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        self.session.headers.update(headers)
        return self.session
    
    def fetch_nse_option_chain(self, symbol="NIFTY", max_retries=5):
        """Aggressive retry strategy for NSE"""
        
        for attempt in range(max_retries):
            try:
                session = self.get_session()
                
                # Step 1: Get homepage (essential for cookies)
                session.get('https://www.nseindia.com', timeout=10)
                time.sleep(1 + attempt * 0.5)  # Progressive delay
                
                # Step 2: Get option chain page
                session.get('https://www.nseindia.com/option-chain', timeout=10)
                time.sleep(1 + attempt * 0.5)
                
                # Step 3: Fetch API
                url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
                response = session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    # Validate data structure
                    if 'records' in data and 'data' in data['records']:
                        return data
                    else:
                        raise Exception("Invalid data structure received")
                
                elif response.status_code == 403:
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        wait_time = (2 ** attempt) + (attempt * 2)
                        print(f"Attempt {attempt + 1} failed, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        # Reset session
                        self.session = None
                        continue
                    else:
                        raise Exception(f"NSE blocked after {max_retries} attempts. Professional solution needed.")
                
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 3 + (attempt * 2)
                    print(f"Timeout, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    self.session = None
                    continue
                else:
                    raise Exception("Connection timeout - NSE may be down or blocking cloud IPs")
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 + (attempt * 1.5)
                    print(f"Error: {str(e)}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    self.session = None
                    continue
                else:
                    raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
        
        raise Exception("All retry attempts exhausted")
    
    def get_futures_ltp_from_multiple_sources(self, symbol="NIFTY"):
        """Fetch spot price"""
        
        # Yahoo Finance
        try:
            symbol_map = {
                "NIFTY": "^NSEI",
                "BANKNIFTY": "^NSEBANK",
                "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
                "MIDCPNIFTY": "NIFTY_MIDCAP_50.NS"
            }
            
            yahoo_symbol = symbol_map.get(symbol)
            if yahoo_symbol:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                response = requests.get(url, timeout=10)
                data = response.json()
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price), "Yahoo Finance"
        except:
            pass
        
        # Groww
        try:
            symbol_map = {
                "NIFTY": "nifty-50",
                "BANKNIFTY": "nifty-bank",
                "FINNIFTY": "nifty-financial-services",
                "MIDCPNIFTY": "nifty-midcap-50"
            }
            
            groww_symbol = symbol_map.get(symbol)
            if groww_symbol:
                url = f"https://groww.in/v1/api/charting_service/v2/chart/exchange/NSE/segment/CASH/symbol/{groww_symbol}/latest"
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                data = response.json()
                if 'ltp' in data:
                    return float(data['ltp']), "Groww.in"
        except:
            pass
        
        return None, None
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation - PRODUCTION VERSION (No synthetic data)"""
        
        # Fetch real data only
        data = self.fetch_nse_option_chain(symbol)
        
        # Get futures price
        futures_ltp, fetch_method = self.get_futures_ltp_from_multiple_sources(symbol)
        
        if futures_ltp is None:
            try:
                futures_ltp = float(data['records']['underlyingValue'])
                fetch_method = "NSE Underlying"
            except:
                raise Exception("Unable to fetch underlying price from any source")
        
        # Get expiry
        expiry_dates = data['records']['expiryDates']
        if expiry_index >= len(expiry_dates):
            expiry_index = 0
        selected_expiry = expiry_dates[expiry_index]
        
        # Parse records
        records = data['records']['data']
        if not records:
            raise Exception("No option chain data available")
        
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
        
        if not option_data:
            raise Exception(f"No data for expiry {selected_expiry}")
        
        df = pd.DataFrame(option_data)
        
        # Filter strikes
        df = df[
            (df['Strike'] >= futures_ltp - strikes_range * 100) &
            (df['Strike'] <= futures_ltp + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in selected range")
        
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
```

**Add to requirements.txt:**
```
fake-useragent
