import pandas as pd
import numpy as np
from scipy.stats import norm
import requests
from datetime import datetime, timedelta

class BlackScholesCalculator:
    """Calculate Greeks using Black-Scholes model"""
    
    @staticmethod
    def calculate_gamma(S, K, T, r, sigma):
        """Calculate gamma (rate of change of delta)"""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        return gamma
    
    @staticmethod
    def calculate_delta(S, K, T, r, sigma, option_type='call'):
        """Calculate delta"""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        
        return delta

class EnhancedGEXDEXCalculator:
    """Enhanced GEX and DEX calculator for NSE options"""
    
    def __init__(self, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
    
    def fetch_nse_option_chain(self, symbol="NIFTY"):
        """Fetch option chain from NSE"""
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
    
    def get_futures_ltp_from_groww(self, symbol="NIFTY"):
        """Fetch futures price from Groww.in"""
        try:
            symbol_map = {
                "NIFTY": "nifty-50",
                "BANKNIFTY": "nifty-bank",
                "FINNIFTY": "nifty-financial-services",
                "MIDCPNIFTY": "nifty-midcap-50"
            }
            
            groww_symbol = symbol_map.get(symbol, "nifty-50")
            url = f"https://groww.in/v1/api/charting_service/v2/chart/exchange/NSE/segment/CASH/symbol/{groww_symbol}/latest"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            if 'ltp' in data:
                return float(data['ltp']), "Groww.in API"
        except:
            pass
        
        return None, None
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main function to fetch data and calculate GEX/DEX"""
        
        # Fetch option chain
        data = self.fetch_nse_option_chain(symbol)
        
        # Get futures price
        futures_ltp, fetch_method = self.get_futures_ltp_from_groww(symbol)
        
        if futures_ltp is None:
            # Fallback to ATM strike
            records = data['records']['data']
            if records:
                futures_ltp = records[0].get('strikePrice', 25000)
                fetch_method = "ATM Strike (Fallback)"
        
        # Get expiry dates
        expiry_dates = data['records']['expiryDates']
        selected_expiry = expiry_dates[expiry_index]
        
        # Parse option chain
        records = data['records']['data']
        
        option_data = []
        for record in records:
            if record.get('expiryDate') != selected_expiry:
                continue
            
            strike = record['strikePrice']
            
            # Call data
            ce_data = record.get('CE', {})
            call_oi = ce_data.get('openInterest', 0)
            call_iv = ce_data.get('impliedVolatility', 0) / 100
            call_ltp = ce_data.get('lastPrice', 0)
            call_volume = ce_data.get('totalTradedVolume', 0)
            
            # Put data
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
        
        # Filter strikes around current price
        df = df[
            (df['Strike'] >= futures_ltp - strikes_range * 100) &
            (df['Strike'] <= futures_ltp + strikes_range * 100)
        ].copy()
        
        # Calculate time to expiry
        expiry_date = datetime.strptime(selected_expiry, '%d-%b-%Y')
        days_to_expiry = (expiry_date - datetime.now()).days
        T = max(days_to_expiry / 365.0, 0.01)
        
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
        
        # Calculate GEX and DEX
        df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * futures_ltp * futures_ltp * 0.01
        df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * futures_ltp * futures_ltp * 0.01 * -1
        df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
        df['Net_GEX_B'] = df['Net_GEX'] / 1e9
        
        df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * futures_ltp * 0.01
        df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * futures_ltp * 0.01
        df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
        df['Net_DEX_B'] = df['Net_DEX'] / 1e9
        
        # Calculate hedging pressure
        total_gex = df['Net_GEX'].abs().sum()
        if total_gex > 0:
            df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex) * 100
        else:
            df['Hedging_Pressure'] = 0
        
        # Total volume
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
    """Calculate GEX and DEX flow metrics"""
    
    df_sorted = df.sort_values('Strike').copy()
    atm_idx = (df_sorted['Strike'] - futures_ltp).abs().idxmin()
    atm_position = df_sorted.index.get_loc(atm_idx)
    
    # Get 5 strikes above and below
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
    
    # DEX flow
    dex_near_total = near_strikes['Net_DEX_B'].sum()
    
    if dex_near_total > 0:
        dex_bias = "BULLISH"
    else:
        dex_bias = "BEARISH"
    
    # Combined
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
    """Detect gamma flip zones"""
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
