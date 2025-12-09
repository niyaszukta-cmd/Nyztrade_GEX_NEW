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
    """GEX/DEX Calculator using DhanHQ v2.0.4"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
        
        if client_id and access_token:
            try:
                # DhanHQ v2.0 initialization (old stable method)
                self.dhan = dhanhq(client_id, access_token)
                print(f"✅ DhanHQ v2.0.4 initialized | Client: {client_id}")
            except Exception as e:
                print(f"❌ DhanHQ init failed: {e}")
                raise Exception(f"Failed to initialize DhanHQ: {str(e)}")
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price using market data"""
        if not self.dhan:
            raise Exception("DhanHQ not initialized")
        
        try:
            security_map = {"NIFTY": "13", "BANKNIFTY": "25", "FINNIFTY": "27", "MIDCPNIFTY": "29"}
            security_id = security_map.get(symbol, "13")
            
            # Try to get LTP from market data
            try:
                response = self.dhan.marketfeed.get_quotes(
                    security_id=security_id,
                    exchange_segment=self.dhan.NSE
                )
                if response and 'data' in response:
                    ltp = response['data'].get('LTP')
                    if ltp:
                        return float(ltp)
            except:
                pass
            
            # Fallback to default values
            defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
            return defaults.get(symbol, 24500)
                
        except Exception as e:
            print(f"⚠️ Price fetch warning: {e}")
            defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
            return defaults.get(symbol, 24500)
    
    def get_option_chain_data(self, symbol="NIFTY", expiry_index=0):
        """Get option chain data"""
        if not self.dhan:
            raise Exception("DhanHQ not initialized")
        
        try:
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            # Get expiry dates
            try:
                expiry_response = self.dhan.get_expiry_list(
                    security_id=security_id,
                    exchange_segment=self.dhan.NSE_FNO
                )
            except:
                # Try alternate method
                expiry_response = self.dhan.expiry_list(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I"
                )
            
            if not expiry_response or 'data' not in expiry_response:
                raise Exception("Failed to get expiry list from DhanHQ")
            
            expiries = expiry_response['data']
            if not expiries or len(expiries) == 0:
                raise Exception("No expiries available")
            
            # Select expiry
            if expiry_index >= len(expiries):
                expiry_index = 0
            
            # Get expiry date
            if isinstance(expiries[expiry_index], dict):
                selected_expiry = expiries[expiry_index].get('expiry_date', expiries[expiry_index].get('expiry'))
            else:
                selected_expiry = str(expiries[expiry_index])
            
            print(f"📅 Selected expiry: {selected_expiry}")
            
            # Get option chain
            try:
                option_response = self.dhan.get_option_chain(
                    security_id=security_id,
                    exchange_segment=self.dhan.NSE_FNO,
                    expiry=selected_expiry
                )
            except:
                # Try alternate method
                option_response = self.dhan.option_chain(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I",
                    expiry=selected_expiry
                )
            
            if not option_response or 'data' not in option_response:
                raise Exception("Failed to get option chain from DhanHQ")
            
            return option_response['data'], expiries, selected_expiry
                
        except Exception as e:
            raise Exception(f"DhanHQ API Error: {str(e)}")
    
    def parse_option_data(self, option_data, underlying_price):
        """Parse DhanHQ option data"""
        strikes_dict = {}
        
        for opt in option_data:
            try:
                strike = float(opt.get('strike_price', opt.get('strikePrice', 0)))
                if strike == 0:
                    continue
                
                if strike not in strikes_dict:
                    strikes_dict[strike] = {
                        'Strike': strike,
                        'Call_OI': 0, 'Call_IV': 0.15, 'Call_LTP': 0, 'Call_Volume': 0,
                        'Put_OI': 0, 'Put_IV': 0.15, 'Put_LTP': 0, 'Put_Volume': 0
                    }
                
                opt_type = str(opt.get('option_type', opt.get('optionType', ''))).upper()
                
                if opt_type in ['CALL', 'CE']:
                    strikes_dict[strike]['Call_OI'] = int(opt.get('open_interest', opt.get('openInterest', 0)))
                    iv = opt.get('iv', opt.get('impliedVolatility', 15))
                    strikes_dict[strike]['Call_IV'] = float(iv) / 100 if iv else 0.15
                    strikes_dict[strike]['Call_LTP'] = float(opt.get('ltp', opt.get('lastPrice', 0)))
                    strikes_dict[strike]['Call_Volume'] = int(opt.get('volume', opt.get('totalTradedVolume', 0)))
                
                elif opt_type in ['PUT', 'PE']:
                    strikes_dict[strike]['Put_OI'] = int(opt.get('open_interest', opt.get('openInterest', 0)))
                    iv = opt.get('iv', opt.get('impliedVolatility', 15))
                    strikes_dict[strike]['Put_IV'] = float(iv) / 100 if iv else 0.15
                    strikes_dict[strike]['Put_LTP'] = float(opt.get('ltp', opt.get('lastPrice', 0)))
                    strikes_dict[strike]['Put_Volume'] = int(opt.get('volume', opt.get('totalTradedVolume', 0)))
                    
            except Exception as e:
                continue
        
        return list(strikes_dict.values())
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation function"""
        
        print(f"🔄 Fetching {symbol} from DhanHQ v2.0.4...")
        
        # Get underlying price
        underlying_price = self.get_underlying_price(symbol)
        print(f"💰 Underlying price: {underlying_price}")
        
        # Get option chain
        option_data, expiries, selected_expiry = self.get_option_chain_data(symbol, expiry_index)
        print(f"📊 Retrieved {len(option_data)} option contracts")
        
        # Parse option data
        parsed_data = self.parse_option_data(option_data, underlying_price)
        
        if not parsed_data:
            raise Exception("No option data available after parsing")
        
        df = pd.DataFrame(parsed_data)
        
        # Filter strikes around current price
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in selected range")
        
        print(f"✅ Filtered to {len(df)} strikes")
        
        # Calculate time to expiry
        try:
            expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
        except:
            try:
                expiry_date = datetime.strptime(selected_expiry, '%d-%b-%Y')
            except:
                try:
                    expiry_date = datetime.strptime(selected_expiry, '%d%b%Y')
                except:
                    expiry_date = datetime.now() + timedelta(days=7)
        
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        print(f"📅 Days to expiry: {days_to_expiry}")
        
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
        
        # Calculate GEX and DEX
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
        
        print(f"✅ Calculation complete | ATM: {atm_info['atm_strike']}")
        
        return df, underlying_price, "DhanHQ API v2.0.4", atm_info

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
        gex_bias = "STRONG BULLISH"
    elif gex_near_total < -50:
        gex_bias = "VOLATILE"
    else:
        gex_bias = "NEUTRAL"
    
    dex_near_total = near_strikes['Net_DEX_B'].sum()
    dex_bias = "BULLISH" if dex_near_total > 0 else "BEARISH"
    
    combined = f"{gex_bias} + {dex_bias}"
    
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
                'type': 'Flip Zone'
            })
    
    return flip_zones
