def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=10, expiry_index=0):
    """Fetch option chain and calculate GEX/DEX - Streamlit optimized"""
    try:
        url = f"{self.option_chain_url}?symbol={symbol}"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data: Status {response.status_code}")
        
        data = response.json()
        
        # Better error handling for records
        if 'records' not in data:
            raise Exception(f"Invalid API response structure. Keys available: {list(data.keys())}")
        
        records = data['records']
        
        # Safely get values with defaults
        spot_price = records.get('underlyingValue', None)
        if spot_price is None or spot_price == 0:
            raise Exception("Unable to fetch underlying price from NSE")
        
        expiry_dates = records.get('expiryDates', [])
        if not expiry_dates:
            raise Exception("No expiry dates found in option chain")
        
        # Validate expiry_index
        if expiry_index >= len(expiry_dates):
            expiry_index = 0
        
        selected_expiry = expiry_dates[expiry_index]
        time_to_expiry, days_to_expiry = self.calculate_time_to_expiry(selected_expiry)
        
        # Get futures price (simplified for speed)
        futures_ltp = spot_price * 1.002  # Approximate
        
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
        else:  # NIFTY
            contract_size = 25
            strike_interval = 50
        
        # Process strikes - with better error handling
        option_data = records.get('data', [])
        if not option_data:
            raise Exception("No option chain data found")
        
        all_strikes = []
        processed_strikes = set()
        atm_strike = None
        min_atm_diff = float('inf')
        atm_call_premium = 0
        atm_put_premium = 0
        
        for item in option_data:
            try:
                # Verify expiry matches
                if item.get('expiryDate') != selected_expiry:
                    continue
                
                strike = item.get('strikePrice')
                if not strike or strike == 0 or strike in processed_strikes:
                    continue
                
                processed_strikes.add(strike)
                
                # Check if strike is within range
                strike_distance = abs(strike - futures_ltp) / strike_interval
                if strike_distance > strikes_range:
                    continue
                
                # Safely extract CE and PE data
                ce = item.get('CE', {})
                pe = item.get('PE', {})
                
                # Extract with defaults
                call_oi = ce.get('openInterest', 0)
                put_oi = pe.get('openInterest', 0)
                call_oi_change = ce.get('changeinOpenInterest', 0)
                put_oi_change = pe.get('changeinOpenInterest', 0)
                call_volume = ce.get('totalTradedVolume', 0)
                put_volume = pe.get('totalTradedVolume', 0)
                call_iv = ce.get('impliedVolatility', 0)
                put_iv = pe.get('impliedVolatility', 0)
                call_ltp = ce.get('lastPrice', 0)
                put_ltp = ce.get('lastPrice', 0)
                
                # Find ATM
                strike_diff = abs(strike - futures_ltp)
                if strike_diff < min_atm_diff:
                    min_atm_diff = strike_diff
                    atm_strike = strike
                    atm_call_premium = call_ltp
                    atm_put_premium = put_ltp
                
                # Convert IV to decimal (handle edge cases)
                call_iv_decimal = max(call_iv / 100, 0.10) if call_iv > 0 else 0.15
                put_iv_decimal = max(put_iv / 100, 0.10) if put_iv > 0 else 0.15
                
                # Calculate Greeks with validation
                if time_to_expiry <= 0 or futures_ltp <= 0 or strike <= 0:
                    continue
                
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
                
                # Calculate GEX/DEX (Note: Market makers are SHORT options, so signs flip)
                call_gex = -(call_oi * call_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                put_gex = (put_oi * put_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                
                call_dex = -(call_oi * call_delta * futures_ltp * contract_size) / 1_000_000_000
                put_dex = -(put_oi * put_delta * futures_ltp * contract_size) / 1_000_000_000
                
                call_flow_gex = -(call_oi_change * call_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                put_flow_gex = (put_oi_change * put_gamma * futures_ltp * futures_ltp * contract_size) / 1_000_000_000
                
                call_flow_dex = -(call_oi_change * call_delta * futures_ltp * contract_size) / 1_000_000_000
                put_flow_dex = -(put_oi_change * put_delta * futures_ltp * contract_size) / 1_000_000_000
                
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
                
            except Exception as strike_error:
                # Skip problematic strikes silently
                continue
        
        if not all_strikes:
            raise Exception(f"No valid strikes found within range {strikes_range} of {futures_ltp:.2f}")
        
        # Create DataFrame
        df = pd.DataFrame(all_strikes)
        df = df.sort_values('Strike').reset_index(drop=True)
        
        # Add billion columns
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
        if atm_strike is None:
            atm_strike = int(round(futures_ltp / strike_interval) * strike_interval)
        
        atm_straddle_premium = atm_call_premium + atm_put_premium
        
        atm_info = {
            'atm_strike': atm_strike,
            'atm_call_premium': atm_call_premium,
            'atm_put_premium': atm_put_premium,
            'atm_straddle_premium': atm_straddle_premium
        }
        
        return df, futures_ltp, "NSE Live", atm_info
        
    except requests.exceptions.RequestException as req_err:
        raise Exception(f"Network error: {str(req_err)}")
    except KeyError as key_err:
        raise Exception(f"Data parsing error - missing key: {str(key_err)}")
    except Exception as e:
        raise Exception(f"GEX calculation error: {str(e)}")
