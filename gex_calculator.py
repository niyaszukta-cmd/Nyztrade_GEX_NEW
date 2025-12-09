import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
from dhanhq import dhanhq

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
    """GEX/DEX Calculator using DhanHQ API"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
        
        if client_id and access_token:
            try:
                self.dhan = dhanhq(client_id, access_token)
            except Exception as e:
                print(f"Warning: DhanHQ initialization failed: {e}")
    
    def get_security_id(self, symbol, segment="IDX_I"):
        """Get Dhan security ID for index"""
        security_map = {
            "NIFTY": "13",      # NIFTY 50
            "BANKNIFTY": "25",  # BANK NIFTY
            "FINNIFTY": "27",   # FIN NIFTY
            "MIDCPNIFTY": "29"  # MIDCP NIFTY
        }
        return security_map.get(symbol, "13")
    
    def fetch_option_chain_dhan(self, symbol="NIFTY"):
        """Fetch option chain using DhanHQ API"""
        
        if not self.dhan:
            raise Exception("DhanHQ not initialized. Please provide Client ID and Access Token.")
        
        try:
            # Get security ID
            security_id = self.get_security_id(symbol)
            
            # Get LTP for underlying
            ltp_response = self.dhan.get_ltp_data(
                exchange_segment=dhanhq.IDX,
                security_id=security_id
            )
            
            if ltp_response['status'] == 'success':
                underlying_price = ltp_response['data']['LTP']
            else:
                raise Exception("Failed to fetch underlying price")
            
            # Get option chain
            # Note: DhanHQ provides expiry-wise option data
            option_chain_response = self.dhan.get_option_chain(
                exchange_segment=dhanhq.IDX,
                security_id=security_id
            )
            
            if option_chain_response['status'] != 'success':
                raise Exception("Failed to fetch option chain")
            
            return option_chain_response['data'], underlying_price, "DhanHQ API"
            
        except Exception as e:
            raise Exception(f"DhanHQ API Error: {str(e)}")
    
    def fetch_option_chain_marketdata(self, symbol="NIFTY"):
        """Fetch using DhanHQ Market Data Feed (Free - no login required)"""
        
        try:
            # DhanHQ provides free market data feed
            # This doesn't require authentication
            from dhanhq import marketfeed
            
            # Get instrument list
            instruments = marketfeed.get_option_chain(symbol)
            
            # Get LTP for underlying
            underlying_ltp = marketfeed.get_ltp(symbol)
            
            return instruments, underlying_ltp, "DhanHQ Market Feed"
            
        except Exception as e:
            raise Exception(f"Market Feed Error: {str(e)}")
    
    def parse_dhan_option_data(self, dhan_data, underlying_price, expiry_index=0):
        """Convert DhanHQ data to our format"""
        
        # Get unique expiries
        expiries = sorted(list(set([opt['expiry_date'] for opt in dhan_data])))
        
        if expiry_index >= len(expiries):
            expiry_index = 0
        
        selected_expiry = expiries[expiry_index]
        
        # Filter by expiry
        expiry_data = [opt for opt in dhan_data if opt['expiry_date'] == selected_expiry]
        
        # Group by strike
        strikes_data = {}
        
        for opt in expiry_data:
            strike = opt['strike_price']
            
            if strike not in strikes_data:
                strikes_data[strike] = {
                    'Strike': strike,
                    'Call_OI': 0,
                    'Call_IV': 0,
                    'Call_LTP': 0,
                    'Call_Volume': 0,
                    'Put_OI': 0,
                    'Put_IV': 0,
                    'Put_LTP': 0,
                    'Put_Volume': 0
                }
            
            if opt['option_type'] == 'CALL':
                strikes_data[strike]['Call_OI'] = opt.get('open_interest', 0)
                strikes_data[strike]['Call_IV'] = opt.get('implied_volatility', 15) / 100
                strikes_data[strike]['Call_LTP'] = opt.get('ltp', 0)
                strikes_data[strike]['Call_Volume'] = opt.get('volume', 0)
            
            elif opt['option_type'] == 'PUT':
                strikes_data[strike]['Put_OI'] = opt.get('open_interest', 0)
                strikes_data[strike]['Put_IV'] = opt.get('implied_volatility', 15) / 100
                strikes_data[strike]['Put_LTP'] = opt.get('ltp', 0)
                strikes_data[strike]['Put_Volume'] = opt.get('volume', 0)
        
        option_data = list(strikes_data.values())
        
        return option_data, selected_expiry, expiries
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation using DhanHQ"""
        
        # Try authenticated API first, then fall back to market feed
        try:
            if self.dhan:
                dhan_data, underlying_price, fetch_method = self.fetch_option_chain_dhan(symbol)
            else:
                dhan_data, underlying_price, fetch_method = self.fetch_option_chain_marketdata(symbol)
        except Exception as e:
            raise Exception(f"Failed to fetch data from DhanHQ: {str(e)}")
        
        # Parse data
        option_data, selected_expiry, expiries = self.parse_dhan_option_data(
            dhan_data, underlying_price, expiry_index
        )
        
        if not option_data:
            raise Exception("No option data available")
        
        df = pd.DataFrame(option_data)
        
        # Filter strikes around current price
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in selected range")
        
        # Calculate time to expiry
        expiry_date = datetime.strptime(selected_expiry, '%d-%b-%Y')
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        # Calculate Greeks
        df['Call_Gamma'] = df.apply(
            lambda row: self.bs_calc.calculate_gamma(
                underlying_price, row['Strike'], T, self.risk_free_rate, max(row['Call_IV'], 0.01)
            ), axis=1
        )
        
        df['Put_Gamma'] = df.apply(
            lambda row: self.bs_calc.calculate_gamma(
                underlying_price, row['Strike'], T, self.risk_free_rate, max(row['Put_IV'], 0.01)
            ), axis=1
        )
        
        df['Call_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                underlying_price, row['Strike'], T, self.risk_free_rate, max(row['Call_IV'], 0.01), 'call'
            ), axis=1
        )
        
        df['Put_Delta'] = df.apply(
            lambda row: self.bs_calc.calculate_delta(
                underlying_price, row['Strike'], T, self.risk_free_rate, max(row['Put_IV'], 0.01), 'put'
            ), axis=1
        )
        
        # Calculate GEX and DEX
        df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * underlying_price * underlying_price * 0.01
        df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * underlying_price * underlying_price * 0.01 * -1
        df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
        df['Net_GEX_B'] = df['Net_GEX'] / 1e9
        
        df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * underlying_price * 0.01
        df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * underlying_price * 0.01
        df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
        df['Net_DEX_B'] = df['Net_DEX'] / 1e9
        
        # Calculate hedging pressure
        total_gex = df['Net_GEX'].abs().sum()
        if total_gex > 0:
            df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex) * 100
        else:
            df['Hedging_Pressure'] = 0
        
        df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
        
        # ATM info
        atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
        atm_row = df[df['Strike'] == atm_strike].iloc[0]
        
        atm_info = {
            'atm_strike': int(atm_strike),
            'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
        }
        
        return df, underlying_price, fetch_method, atm_info

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
