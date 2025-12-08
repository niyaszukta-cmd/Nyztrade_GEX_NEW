import requests
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import warnings
import time
import json
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
# ENHANCED GEX/DEX CALCULATOR
# ============================================================================

class EnhancedGEXDEXCalculator:
    """Advanced GEX + DEX calculations optimized for Streamlit"""
    
    def __init__(self):
        self.session = None
        self.base_url = "https://www.nseindia.com"
        self.option_chain_url = "https://www.nseindia.com/api/option-chain-indices"
        self.risk_free_rate = 0.07
        self.bs_calc = BlackScholesCalculator()
        self._create_session()
    
    def _create_session(self):
        """Create a new session with proper headers"""
        self.session = requests.Session()
        
        # Enhanced headers to mimic real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        })
    
    def _initialize_session(self):
        """Initialize NSE session with proper cookie acquisition"""
        try:
            # Step 1: Visit homepage to get initial cookies
            print("Initializing NSE session...")
            home_response = self.session.get(
                self.base_url,
                timeout=10,
                headers={'Referer': self.base_url}
            )
            
            if home_response.status_code != 200:
                print(f"Homepage returned status: {home_response.status_code}")
                return False
            
            time.sleep(1)
            
            # Step 2: Visit option chain page to establish session
            oc_page_url = f"{self.base_url}/option-chain"
            oc_response = self.session.get(
                oc_page_url,
                timeout=10,
                headers={'Referer': self.base_url}
            )
            
            if oc_response.status_code != 200:
                print(f"Option chain page returned status: {oc_response.status_code}")
                return False
            
            time.sleep(1)
            
            # Step 3: Check if we have necessary cookies
            cookies = self.session.cookies.get_dict()
            print(f"Cookies acquired: {len(cookies)} cookies")
            
            if len(cookies) == 0:
                print("Warning: No cookies received")
                return False
            
            return True
            
        except Exception as e:
            print(f"Session initialization error: {e}")
            return False
    
    def calculate_time_to_expiry(self, expiry_date_str):
        """Calculate time to expiry from date string"""
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%d-%b-%Y")
            today = datetime.now()
            days_to_expiry = (expiry_date - today).days
            time_to_expiry = max(days_to_expiry / 365, 0.001)
            return time_to_expiry, days_to_expiry
        except:
            return 7/365, 7
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=10, expiry_index=0):
        """Fetch option chain and calculate GEX/DEX - Streamlit optimized"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt + 1}/{max_retries}")
                
                # Initialize/reinitialize session
                if attempt == 0 or attempt > 0:
                    self._create_session()
                    session_ok = self._initialize_session()
                    
                    if not session_ok:
                        print("Session initialization failed, retrying...")
                        time.sleep(3)
                        continue
                
                # Build URL
                url = f"{self.option_chain_url}?symbol={symbol}"
                print(f"Fetching: {url}")
                
                # Make API request with proper referer
                response = self.session.get(
                    url,
                    timeout=15,
                    headers={
                        'Referer': f'{self.base_url}/option-chain',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                )
                
                print(f"Response status: {response.status_code}")
                
                if response.status_code == 401:
                    print("Unauthorized - session expired")
                    time.sleep(3)
                    continue
                    
                if response.status_code == 403:
                    print("Forbidden - possible rate limit or IP block")
                    time.sleep(5)
                    continue
                
                if response.status_code != 200:
                    print(f"HTTP {response.status_code}: {response.text[:200]}")
                    time.sleep(3)
                    continue
                
                # Parse response
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON response: {str(e)}")
                    print(f"Response text: {response.text[:500]}")
                    time.sleep(3)
                    continue
                
                # Validate response structure
                print(f"Response keys: {list(data.keys())}")
                
                if 'records' not in data:
                    print(f"ERROR: Response missing 'records' key")
                    print(f"Full response: {json.dumps(data, indent=2)[:1000]}")
                    
                    # Check if it's an error response
                    if 'error' in data:
                        print(f"API Error: {data.get('error')}")
                    
                    time.sleep(3)
                    continue
                
                records = data['records']
                
                if not isinstance(records, dict):
                    print(f"'records' is not a dict: {type(records)}")
                    time.sleep(3)
                    continue
                
                # Extract data
                spot_price = records.get('underlyingValue')
                if not spot_price:
                    print("Missing underlyingValue")
                    print(f"Records keys: {list(records.keys())}")
                    time.sleep(3)
                    continue
                
                expiry_dates = records.get('expiryDates', [])
                if not expiry_dates:
                    raise Exception("No expiry dates available")
                
                selected_expiry = expiry_dates[expiry_index] if expiry_index < len(expiry_dates) else expiry_dates[0]
                time_to_expiry, days_to_expiry = self.calculate_time_to_expiry(selected_expiry)
                
                print(f"Spot: {spot_price}, Expiry: {selected_expiry}, Days: {days_to_expiry}")
                
                # Get futures price
                futures_ltp = spot_price * 1.002
                
                # Contract specs
                if 'BANKNIFTY' in symbol:
                    contract_size = 15
                    strike_interval = 100
                elif 'FINNIFTY' in symbol:
                    contract_size = 40
                    strike_interval = 50
                elif 'MIDCPNIFTY' in symbol:
                    contract_size = 75
                    strike_interval = 25
                else:
                    contract_size = 25
                    strike_interval = 50
                
                # Process strikes
                all_strikes = []
                processed_strikes = set()
                atm_strike = None
                min_atm_diff = float('inf')
                atm_call_premium = 0
                atm_put_premium = 0
                
                option_data = records.get('data', [])
                if not option_data:
                    raise Exception("No option data in records")
                
                print(f"Processing {len(option_data)} option records...")
                
                for item in option_data:
                    if not isinstance(item, dict):
                        continue
                    
                    if selected_expiry and item.get('expiryDate') != selected_expiry:
                        continue
                    
                    strike = item.get('strikePrice', 0)
                    if strike == 0 or strike in processed_strikes:
                        continue
                    
                    processed_strikes.add(strike)
                    
                    strike_distance = abs(strike - futures_ltp) / strike_interval
                    if strike_distance > strikes_range:
                        continue
                    
                    ce = item.get('CE', {}) or {}
                    pe = item.get('PE', {}) or {}
                    
                    call_oi = ce.get('openInterest', 0) or 0
                    put_oi = pe.get('openInterest', 0) or 0
                    call_oi_change = ce.get('changeinOpenInterest', 0) or 0
                    put_oi_change = pe.get('changeinOpenInterest', 0) or 0
                    call_volume = ce.get('totalTradedVolume', 0) or 0
                    put_volume = pe.get('totalTradedVolume', 0) or 0
                    call_iv = ce.get('impliedVolatility', 0) or 0
                    put_iv = pe.get('impliedVolatility', 0) or 0
                    call_ltp = ce.get('lastPrice', 0) or 0
                    put_ltp = pe.get('lastPrice', 0) or 0
                    
                    # Find ATM
                    strike_diff = abs(strike - futures_ltp)
                    if strike_diff < min_atm_diff:
                        min_atm_diff = strike_diff
                        atm_strike = strike
                        atm_call_premium = call_ltp
                        atm_put_premium = put_ltp
                    
                    call_iv_decimal = call_iv / 100 if call_iv > 0 else 0.15
                    put_iv_decimal = put_iv / 100 if put_iv > 0 else 0.15
                    
                    # Calculate Greeks
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
                    
                    # Calculate GEX/DEX
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
                    raise Exception(f"No strikes found within range {strikes_range}")
                
                print(f"Processed {len(all_strikes)} strikes successfully")
                
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
                
                # Hedging pressure
                max_net_gex = df['Net_GEX_B'].abs().max()
                if max_net_gex > 0:
                    df['Hedging_Pressure'] = (df['Net_GEX_B'] / max_net_gex) * 100
                else:
                    df['Hedging_Pressure'] = 0
                
                # ATM info
                atm_straddle_premium = atm_call_premium + atm_put_premium
                
                atm_info = {
                    'atm_strike': atm_strike,
                    'atm_call_premium': atm_call_premium,
                    'atm_put_premium': atm_put_premium,
                    'atm_straddle_premium': atm_straddle_premium
                }
                
                print("✓ GEX/DEX calculation completed successfully")
                return df, futures_ltp, "NSE Live", atm_info
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Failed after {max_retries} attempts: {str(e)}")

# ============================================================================
# FLOW METRICS CALCULATION
# ============================================================================

def calculate_dual_gex_dex_flow(df, futures_ltp):
    """Calculate GEX/DEX flow metrics"""
    if df is None or len(df) == 0:
        raise ValueError("Empty dataframe provided")
    
    df_unique = df.drop_duplicates(subset=['Strike']).sort_values('Strike').reset_index(drop=True)
    
    # GEX Flow
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
    
    # DEX Flow
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
    
    # Bias functions
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

# ============================================================================
# GAMMA FLIP DETECTION
# ============================================================================

def detect_gamma_flip_zones(df):
    """Detect gamma flip zones"""
    if df is None or len(df) == 0:
        return []
    
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
