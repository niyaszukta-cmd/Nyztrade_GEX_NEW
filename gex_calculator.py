import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
from dhanhq import DhanContext, dhanhq

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
    """GEX/DEX Calculator using DhanHQ v2.1.0 with DhanContext"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
        
        if client_id and access_token:
            try:
                # NEW DhanHQ v2.1.0 initialization method
                dhan_context = DhanContext(client_id, access_token)
                self.dhan = dhanhq(dhan_context)
                print(f"✅ DhanHQ v2.1.0 initialized | Client: {client_id}")
            except Exception as e:
                print(f"⚠️ DhanHQ init error: {e}")
                raise Exception(f"Failed to initialize DhanHQ: {str(e)}")
    
    def get_option_chain_from_dhan(self, symbol="NIFTY"):
        """Fetch option chain using DhanHQ v2.1.0"""
        
        if not self.dhan:
            raise Exception("DhanHQ not initialized")
        
        try:
            # Security IDs for indices
            security_map = {
                "NIFTY": 13,
                "BANKNIFTY": 25,
                "FINNIFTY": 27,
                "MIDCPNIFTY": 29
            }
            
            security_id = security_map.get(symbol, 13)
            
            # Get current expiry using expiry_list
            expiry_response = self.dhan.expiry_list(
                under_security_id=security_id,
                under_exchange_segment="IDX_I"
            )
            
            if not expiry_response or 'data' not in expiry_response:
                raise Exception("Failed to get expiry list")
            
            expiries = expiry_response['data']
            if not expiries:
                raise Exception("No expiries available")
            
            # Get option chain for first expiry
            current_expiry = expiries[0]['expiry_date']
            
            option_response = self.dhan.option_chain(
                under_security_id=security_id,
                under_exchange_segment="IDX_I",
                expiry=current_expiry
            )
            
            if option_response and 'data' in option_response:
                return option_response['data'], expiries
            else:
                raise Exception(f"Invalid option chain response")
                
        except Exception as e:
            raise Exception(f"DhanHQ API Error: {str(e)}")
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get underlying index price using market quote"""
        
        if not self.dhan:
            raise Exception("DhanHQ not initialized")
        
        try:
            security_map = {
                "NIFTY": 13,
                "BANKNIFTY": 25,
                "FINNIFTY": 27,
                "MIDCPNIFTY": 29
            }
            
            security_id = security_map.get(symbol, 13)
            
            # Use ohlc_data for getting LTP
            securities = {"IDX_I": [security_id]}
            
            response = self.dhan.ohlc_data(securities=securities)
            
            if response and 'data' in response and 'IDX_I' in response['data']:
                idx_data = response['data']['IDX_I']
                if idx_data and str(security_id) in idx_data:
                    ltp = idx_data[str(security_id)].get('last_price', None)
                    if ltp:
                        return float(ltp)
            
            raise Exception("Failed to get LTP from market data")
                
        except Exception as e:
            raise Exception(f"Price fetch error: {str(e)}")
    
    def parse_dhan_data(self, dhan_data, expiries, underlying_price, expiry_index=0):
        """Convert DhanHQ v2.1.0 data to our format"""
        
        if not expiries or expiry_index >= len(expiries):
            expiry_index = 0
        
        selected_expiry = expiries[expiry_index]['expiry_date']
        
        # Filter data for selected expiry
        strikes_dict = {}
        
        for opt in dhan_data:
            strike = float(opt.get('strike_price', 0))
            if strike == 0:
                continue
            
            if strike not in strikes_dict:
                strikes_dict[strike] = {
                    'Strike': strike,
                    'Call_OI': 0, 'Call_IV': 0.15, 'Call_LTP': 0, 'Call_Volume': 0,
                    'Put_OI': 0, 'Put_IV': 0.15, 'Put_LTP': 0, 'Put_Volume': 0
                }
            
            opt_type = opt.get('option_type', '').upper()
            
            if opt_type == 'CALL' or opt_type == 'CE':
                strikes_dict[strike]['Call_OI'] = int(opt.get('open_interest', 0))
                strikes_dict[strike]['Call_IV'] = float(opt.get('implied_volatility', 15)) / 100 if opt.get('implied_volatility') else 0.15
                strikes_dict[strike]['Call_LTP'] = float(opt.get('ltp', 0))
                strikes_dict[strike]['Call_Volume'] = int(opt.get('volume', 0))
            
            elif opt_type == 'PUT' or opt_type == 'PE':
                strikes_dict[strike]['Put_OI'] = int(opt.get('open_interest', 0))
                strikes_dict[strike]['Put_IV'] = float(opt.get('implied_volatility', 15)) / 100 if opt.get('implied_volatility') else 0.15
                strikes_dict[strike]['Put_LTP'] = float(opt.get('ltp', 0))
                strikes_dict[strike]['Put_Volume'] = int(opt.get('volume', 0))
        
        option_data = list(strikes_dict.values())
        
        return option_data, selected_expiry, expiries
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation function using DhanHQ v2.1.0"""
        
        print(f"🔄 Fetching {symbol} from DhanHQ v2.1.0...")
        
        # Fetch data
        dhan_data, expiries = self.get_option_chain_from_dhan(symbol)
        underlying_price = self.get_underlying_price(symbol)
        
        print(f"✅ Data received | Price: {underlying_price} | Expiries: {len(expiries)}")
        
        # Parse data
        option_data, selected_expiry, expiries = self.parse_dhan_data(
            dhan_data, expiries, underlying_price, expiry_index
        )
        
        if not option_data:
            raise Exception("No option data available")
        
        df = pd.DataFrame(option_data)
        
        # Filter strikes
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in range")
        
        # Time to expiry
        try:
            expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
        except:
            try:
                expiry_date = datetime.strptime(selected_expiry, '%d-%b-%Y')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
        
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        # Calculate Greeks
        df['Call_Gamma'] = df.apply(
            lambda r: self.bs_calc.calculate_gamma(
                underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)
            ), axis=1
        )
        
        df['Put_Gamma'] = df.apply(
            lambda r: self.bs_calc.calculate_gamma(
                underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)
            ), axis=1
        )
        
        df['Call_Delta'] = df.apply(
            lambda r: self.bs_calc.calculate_delta(
                underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'
            ), axis=1
        )
        
        df['Put_Delta'] = df.apply(
            lambda r: self.bs_calc.calculate_delta(
                underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'
            ), axis=1
        )
        
        # GEX and DEX calculations
        df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * underlying_price * underlying_price * 0.01
        df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * underlying_price * underlying_price * 0.01 * -1
        df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
        df['Net_GEX_B'] = df['Net_GEX'] / 1e9
        
        df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * underlying_price * 0.01
        df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * underlying_price * 0.01
        df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
        df['Net_DEX_B'] = df['Net_DEX'] / 1e9
        
        # Hedging pressure
        total_gex = df['Net_GEX'].abs().sum()
        df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex * 100) if total_gex > 0 else 0
        df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
        
        # ATM info
        atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
        atm_row = df[df['Strike'] == atm_strike].iloc[0]
        
        atm_info = {
            'atm_strike': int(atm_strike),
            'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
        }
        
        print(f"✅ Complete | Strikes: {len(df)} | ATM: {atm_info['atm_strike']}")
        
        return df, underlying_price, "DhanHQ v2.1.0", atm_info

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

