import requests
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import warnings
import time
warnings.filterwarnings('ignore')

# ============================================================================
# BLACK-SCHOLES CALCULATOR
# ============================================================================

class BlackScholesCalculator:
    """Calculate accurate gamma and delta using Black-Scholes formula"""
    
    @staticmethod
    def calculate_d1(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        return (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
    
    @staticmethod
    def calculate_gamma(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            n_prime_d1 = norm.pdf(d1)
            gamma = n_prime_d1 / (S * sigma * np.sqrt(T))
            return gamma
        except:
            return 0
    
    @staticmethod
    def calculate_call_delta(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            return norm.cdf(d1)
        except:
            return 0
    
    @staticmethod
    def calculate_put_delta(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            return norm.cdf(d1) - 1
        except:
            return 0

# ============================================================================
# ENHANCED GEX/DEX CALCULATOR WITH ROBUST NSE API
# ============================================================================

class EnhancedGEXDEXCalculator:
    """Advanced GEX + DEX calculations with robust NSE data fetching"""
    
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.option_chain_url = "https://www.nseindia.com/api/option-chain-indices"
        self.risk_free_rate = 0.07
        self.bs_calc = BlackScholesCalculator()
        
        # Enhanced headers to mimic browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nseindia.com/option-chain',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
        }
        
        # Initialize session
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize session by visiting homepage first (required by NSE)"""
        try:
            # Visit homepage to get cookies
            response = self.session.get(self.base_url, timeout=10)
            time.sleep(1)
            
            # Visit option chain page
            oc_page = f"{self.base_url}/option-chain"
            self.session.get(oc_page, timeout=10)
            time.sleep(1)
            
            return True
        except Exception as e:
            print(f"Session initialization warning: {e}")
            return False
    
    def calculate_time_to_expiry(self, expiry_date_str):
        """Calculate time to expiry in years and days"""
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%d-%b-%Y")
            today = datetime.now()
            days_to_expiry = (expiry_date - today).days
            
            if days_to_expiry < 1:
                days_to_expiry = 1
            
            time_to_expiry = days_to_expiry / 365
            return time_to_expiry, days_to_expiry
        except Exception as e:
            print(f"Expiry calculation error: {e}")
            return 7/365, 7
    
    def fetch_nse_option_chain(self, symbol="NIFTY", max_retries=3):
        """Fetch option chain data from NSE with retry logic"""
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Retry attempt {attempt + 1}/{max_retries}")
                    self._initialize_session()
                    time.sleep(2)
                
                url = f"{self.option_chain_url}?symbol={symbol}"
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'records' in data and 'data' in data['records']:
                        print(f"✓ Successfully fetched {symbol} option chain data")
                        return data, None
                    else:
                        error_msg = "Invalid data structure received"
                        print(f"✗ {error_msg}")
                        
                elif response.status_code == 401:
                    error_msg = "Authentication failed - reinitializing session"
                    print(f"✗ {error_msg}")
                    self._initialize_session()
                    
                else:
                    error_msg = f"HTTP {response.status_code}"
                    print(f"✗ {error_msg}")
                
            except requests.exceptions.Timeout:
                error_msg = "Request timeout"
                print(f"✗ {error_msg}")
                
            except requests.exceptions.ConnectionError:
                error_msg = "Connection error"
                print(f"✗ {error_msg}")
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                print(f"✗ {error_msg}")
            
            if attempt < max_retries - 1:
                time.sleep(3)
        
        return None, f"Failed after {max_retries} attempts"
    
    def get_contract_specs(self, symbol):
        """Get contract size and strike interval for symbol"""
        specs = {
            'NIFTY': {'size': 25, 'interval': 50},
            'BANKNIFTY': {'size': 15, 'interval': 100},
            'FINNIFTY': {'size': 40, 'interval': 50},
            'MIDCPNIFTY': {'size': 75, 'interval': 25},
        }
        return specs.get(symbol, {'size': 25, 'interval': 50})
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=10, expiry_index=0):
        """Fetch option chain and calculate GEX/DEX with robust error handling"""
        
        try:
            data, error = self.fetch_nse_option_chain(symbol)
            
            if error or data is None:
                raise Exception(f"Data fetch failed: {error}")
            
            records = data.get('records', {})
            
            if not records:
                raise Exception("No records found in response")
            
            spot_price = records.get('underlyingValue', 0)
            expiry_dates = records.get('expiryDates', [])
            
            if spot_price == 0:
                raise Exception("Invalid spot price")
            
            if not expiry_dates:
                raise Exception("No expiry dates found")
            
            if expiry_index >= len(expiry_dates):
                expiry_index = 0
            
            selected_expiry = expiry_dates[expiry_index]
            time_to_expiry, days_to_expiry = self.calculate_time_to_expiry(selected_expiry)
            
            print(f"Selected Expiry: {selected_expiry} ({days_to_expiry} days)")
            
            futures_ltp = spot_price * (1 + self.risk_free_rate * time_to_expiry)
            
            specs = self.get_contract_specs(symbol)
            contract_size = specs['size']
            strike_interval = specs['interval']
            
            option_data = records.get('data', [])
            
            if not option_data:
                raise Exception("No option data found")
            
            all_strikes = []
            processed_strikes = set()
            
            atm_strike = None
            min_atm_diff = float('inf')
            atm_call_premium = 0
            atm_put_premium = 0
            
            for item in option_data:
                if item.get('expiryDate') != selected_expiry:
                    continue
                
                strike = item.get('strikePrice', 0)
                
                if strike == 0 or strike in processed_strikes:
                    continue
                
                strike_distance = abs(strike - futures_ltp) / strike_interval
                
                if strike_distance > strikes_range:
                    continue
                
                processed_strikes.add(strike)
                
                ce = item.get('CE', {})
                pe = item.get('PE', {})
                
                call_oi = ce.get('openInterest', 0)
                put_oi = pe.get('openInterest', 0)
                call_oi_change = ce.get('changeinOpenInterest', 0)
                put_oi_change = pe.get('changeinOpenInterest', 0)
                call_volume = ce.get('totalTradedVolume', 0)
                put_volume = pe.get('totalTradedVolume', 0)
                call_iv = ce.get('impliedVolatility', 0)
                put_iv = pe.get('impliedVolatility', 0)
                call_ltp = ce.get('lastPrice', 0)
                put_ltp = pe.get('lastPrice', 0)
                
                strike_diff = abs(strike - futures_ltp)
                if strike_diff < min_atm_diff:
                    min_atm_diff = strike_diff
                    atm_strike = strike
                    atm_call_premium = call_ltp
                    atm_put_premium = put_ltp
                
                call_iv_decimal = call_iv / 100 if call_iv > 0 else 0.20
                put_iv_decimal = put_iv / 100 if put_iv > 0 else 0.20
                
                call_gamma = self.bs_calc.calculate_gamma(
                    S=futures_ltp, K=strike, T=time_to_expiry,
                    r=self.risk_free_rate, sigma=call_iv_decimal
                )
                
                put_gamma = self.bs_calc.calculate_gamma(
                    S=futures_ltp, K=strike, T=time_to_expiry,
                    r=self.risk_free_rate, sigma=put_iv_decimal
                )
                
                call_delta = self.bs_calc.calculate_call_delta(
                    S=futures_ltp, K=strike, T=time_to_expiry,
                    r=self.risk_free_rate, sigma=call_iv_decimal
                )
                
                put_delta = self.bs_calc.calculate_put_delta(
                    S=futures_ltp, K=strike, T=time_to_expiry,
                    r=self.risk_free_rate, sigma=put_iv_decimal
                )
                
                call_gex = (call_oi * call_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                put_gex = -(put_oi * put_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                
                call_dex = (call_oi * call_delta * futures_ltp * contract_size) / 1_000_000_000
                put_dex = (put_oi * put_delta * futures_ltp * contract_size) / 1_000_000_000
                
                call_flow_gex = (call_oi_change * call_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                put_flow_gex = -(put_oi_change * put_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                
                call_flow_dex = (call_oi_change * call_delta * futures_ltp * contract_size) / 1_000_000_000
                put_flow_dex = (put_oi_change * put_delta * futures_ltp * contract_size) / 1_000_000_000
                
                all_strikes.append({
                    'Strike': strike,
                    'Call_OI': call_oi,
                    'Put_OI': put_oi,
                    'Call_OI_Change': call_oi_change,
                    'Put_OI_Change': put_oi_change,
                    'Call_Volume': call_volume,
                    'Put_Volume': put_volume,
                    'Call_IV': call_iv,
                    'Put_IV': put_iv,
                    'Call_LTP': call_ltp,
                    'Put_LTP': put_ltp,
                    'Call_Gamma': call_gamma,
                    'Put_Gamma': put_gamma,
                    'Call_Delta': call_delta,
                    'Put_Delta': put_delta,
                    'Call_GEX': call_gex,
                    'Put_GEX': put_gex,
                    'Net_GEX': call_gex + put_gex,
                    'Call_DEX': call_dex,
                    'Put_DEX': put_dex,
                    'Net_DEX': call_dex + put_dex,
                    'Call_Flow_GEX': call_flow_gex,
                    'Put_Flow_GEX': put_flow_gex,
                    'Net_Flow_GEX': call_flow_gex + put_flow_gex,
                    'Call_Flow_DEX': call_flow_dex,
                    'Put_Flow_DEX': put_flow_dex,
                    'Net_Flow_DEX': call_flow_dex + put_flow_dex
                })
            
            if not all_strikes:
                raise Exception("No strikes processed - check strikes_range parameter")
            
            df = pd.DataFrame(all_strikes)
            df = df.sort_values('Strike').reset_index(drop=True)
            
            df['Call_GEX_B'] = df['Call_GEX']
            df['Put_GEX_B'] = df['Put_GEX']
            df['Net_GEX_B'] = df['Net_GEX']
            df['Call_DEX_B'] = df['Call_DEX']
            df['Put_DEX_B'] = df['Put_DEX']
            df['Net_DEX_B'] = df['Net_DEX']
            df['Call_Flow_GEX_B'] = df['Call_Flow_GEX']
            df['Put_Flow_GEX_B'] = df['Put_Flow_GEX']
            df['Net_Flow_GEX_B'] = df['Net_Flow_GEX']
            df['Call_Flow_DEX_B'] = df['Call_Flow_DEX']
            df['Put_Flow_DEX_B'] = df['Put_Flow_DEX']
            df['Net_Flow_DEX_B'] = df['Net_Flow_DEX']
            df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
            
            max_net_gex = df['Net_GEX_B'].abs().max()
            if max_net_gex > 0:
                df['Hedging_Pressure'] = (df['Net_GEX_B'] / max_net_gex) * 100
            else:
                df['Hedging_Pressure'] = 0
            
            atm_straddle_premium = atm_call_premium + atm_put_premium
            
            atm_info = {
                'atm_strike': atm_strike,
                'atm_call_premium': atm_call_premium,
                'atm_put_premium': atm_put_premium,
                'atm_straddle_premium': atm_straddle_premium,
                'spot_price': spot_price,
                'futures_price': futures_ltp,
                'expiry_date': selected_expiry,
                'days_to_expiry': days_to_expiry
            }
            
            print(f"✓ Processed {len(df)} strikes for {symbol}")
            print(f"✓ Futures: {futures_ltp:.2f} | ATM: {atm_strike} | Straddle: {atm_straddle_premium:.2f}")
            
            return df, futures_ltp, "NSE Live API", atm_info
            
        except Exception as e:
            error_msg = f"GEX calculation error: {str(e)}"
            print(f"✗ {error_msg}")
            raise Exception(error_msg)

def calculate_dual_gex_dex_flow(df, futures_ltp):
    """Calculate GEX/DEX flow metrics for near and total strikes"""
    
    df_unique = df.drop_duplicates(subset=['Strike']).sort_values('Strike').reset_index(drop=True)
    
    positive_gex_df = df_unique[df_unique['Net_GEX_B'] > 0].copy()
    positive_gex_df['Distance'] = abs(positive_gex_df['Strike'] - futures_ltp)
    positive_gex_df = positive_gex_df.sort_values('Distance').head(5)
    
    negative_gex_df = df_unique[df_unique['Net_GEX_B'] < 0].copy()
    negative_gex_df['Distance'] = abs(negative_gex_df['Strike'] - futures_ltp)
    negative_gex_df = negative_gex_df.sort_values('Distance').head(5)
    
    gex_near_positive = float(positive_gex_df['Net_GEX_B'].sum()) if len(positive_gex_df) > 0 else 0.0
    gex_near_negative = float(negative_gex_df['Net_GEX_B'].sum()) if len(negative_gex_df) > 0 else 0.0
    gex_near_total = gex_near_positive + gex_near_negative
    
    positive_gex_mask = df_unique['Net_GEX_B'] > 0
    negative_gex_mask = df_unique['Net_GEX_B'] < 0
    
    gex_total_positive = float(df_unique.loc[positive_gex_mask, 'Net_GEX_B'].sum()) if positive_gex_mask.any() else 0.0
    gex_total_negative = float(df_unique.loc[negative_gex_mask, 'Net_GEX_B'].sum()) if negative_gex_mask.any() else 0.0
    gex_total_all = gex_total_positive + gex_total_negative
    
    above_futures = df_unique[df_unique['Strike'] > futures_ltp].head(5)
    below_futures = df_unique[df_unique['Strike'] < futures_ltp].tail(5)
    
    dex_near_positive = float(above_futures['Net_DEX_B'].sum()) if len(above_futures) > 0 else 0.0
    dex_near_negative = float(below_futures['Net_DEX_B'].sum()) if len(below_futures) > 0 else 0.0
    dex_near_total = dex_near_positive + dex_near_negative
    
    positive_dex_mask = df_unique['Net_DEX_B'] > 0
    negative_dex_mask = df_unique['Net_DEX_B'] < 0
    
    dex_total_positive = float(df_unique.loc[positive_dex_mask, 'Net_DEX_B'].sum()) if positive_dex_mask.any() else 0.0
    dex_total_negative = float(df_unique.loc[negative_dex_mask, 'Net_DEX_B'].sum()) if negative_dex_mask.any() else 0.0
    dex_total_all = dex_total_positive + dex_total_negative
    
    def get_gex_bias(flow_value):
        if flow_value > 50:
            return "STRONG BULLISH (Sideways to Bullish)", "green"
        elif flow_value > 0:
            return "BULLISH (Sideways to Bullish)", "lightgreen"
        elif flow_value < -50:
            return "HIGH VOLATILITY (Strong)", "red"
        elif flow_value < 0:
            return "HIGH VOLATILITY", "lightcoral"
        else:
            return "NEUTRAL", "orange"
    
    def get_dex_bias(flow_value):
        if flow_value > 50:
            return "BULLISH", "green"
        elif flow_value < -50:
            return "BEARISH", "red"
        elif flow_value > 0:
            return "Mild Bullish", "lightgreen"
        elif flow_value < 0:
            return "Mild Bearish", "lightcoral"
        else:
            return "NEUTRAL", "orange"
    
    gex_near_bias, gex_near_color = get_gex_bias(gex_near_total)
    gex_total_bias, gex_total_color = get_gex_bias(gex_total_all)
    dex_near_bias, dex_near_color = get_dex_bias(dex_near_total)
    dex_total_bias, dex_total_color = get_dex_bias(dex_total_all)
    
    combined_signal = (gex_near_total + dex_near_total) / 2
    combined_bias, combined_color = get_gex_bias(combined_signal)
    
    return {
        'gex_near_positive': gex_near_positive,
        'gex_near_negative': gex_near_negative,
        'gex_near_total': gex_near_total,
        'gex_near_bias': gex_near_bias,
        'gex_near_color': gex_near_color,
        'gex_total_positive': gex_total_positive,
        'gex_total_negative': gex_total_negative,
        'gex_total_all': gex_total_all,
        'gex_total_bias': gex_total_bias,
        'gex_total_color': gex_total_color,
        'dex_near_positive': dex_near_positive,
        'dex_near_negative': dex_near_negative,
        'dex_near_total': dex_near_total,
        'dex_near_bias': dex_near_bias,
        'dex_near_color': dex_near_color,
        'dex_total_positive': dex_total_positive,
        'dex_total_negative': dex_total_negative,
        'dex_total_all': dex_total_all,
        'dex_total_bias': dex_total_bias,
        'dex_total_color': dex_total_color,
        'combined_signal': combined_signal,
        'combined_bias': combined_bias,
        'combined_color': combined_color,
    }

def detect_gamma_flip_zones(df):
    """Detect gamma flip zones where GEX changes sign"""
    
    gamma_flip_zones = []
    df_sorted = df.sort_values('Strike').reset_index(drop=True)
    
    for i in range(len(df_sorted) - 1):
        current_gex = df_sorted.iloc[i]['Net_GEX_B']
        next_gex = df_sorted.iloc[i + 1]['Net_GEX_B']
        
        if (current_gex > 0 and next_gex < 0) or (current_gex < 0 and next_gex > 0):
            flip_strike_lower = df_sorted.iloc[i]['Strike']
            flip_strike_upper = df_sorted.iloc[i + 1]['Strike']
            
            if abs(current_gex) + abs(next_gex) > 0:
                weight = abs(current_gex) / (abs(current_gex) + abs(next_gex))
                flip_strike = flip_strike_lower + (flip_strike_upper - flip_strike_lower) * weight
            else:
                flip_strike = (flip_strike_lower + flip_strike_upper) / 2
            
            flip_type = "Positive to Negative" if current_gex > 0 else "Negative to Positive"
            
            gamma_flip_zones.append({
                'flip_strike': flip_strike,
                'lower_strike': flip_strike_lower,
                'upper_strike': flip_strike_upper,
                'flip_type': flip_type,
                'lower_gex': current_gex,
                'upper_gex': next_gex
            })
    
    return gamma_flip_zones
