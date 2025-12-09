import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

# Try importing calculator
try:
    from gex_calculator import EnhancedGEXDEXCalculator, calculate_dual_gex_dex_flow, detect_gamma_flip_zones
    CALCULATOR_AVAILABLE = True
except Exception as e:
    CALCULATOR_AVAILABLE = False
    IMPORT_ERROR = str(e)

# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_password():
    """Returns True if user has entered correct password"""
    
    def password_entered():
        username = st.session_state["username"].strip().lower()
        password = st.session_state["password"]
        
        users = {
            "demo": "demo123",
            "premium": "premium123",
            "niyas": "nyztrade123"
        }
        
        if username in users and password == users[username]:
            st.session_state["password_correct"] = True
            st.session_state["authenticated_user"] = username
            del st.session_state["password"]
            return
        
        st.session_state["password_correct"] = False
        st.session_state["authenticated_user"] = None
    
    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 NYZTrade Dashboard Login")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.text_input("Username", key="username", placeholder="Enter username")
            st.text_input("Password", type="password", key="password", placeholder="Enter password")
            st.button("Login", on_click=password_entered, use_container_width=True)
            
            st.markdown("---")
            st.info("""
            **Demo Credentials:**
            - Free: `demo` / `demo123`
            - Premium: `premium` / `premium123`
            """)
        
        return False
    
    elif not st.session_state["password_correct"]:
        st.markdown("## 🔐 NYZTrade Dashboard Login")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.error("😕 Incorrect username or password")
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered, use_container_width=True)
        
        return False
    
    return True

def get_user_tier():
    if "authenticated_user" not in st.session_state:
        return "guest"
    username = st.session_state["authenticated_user"]
    premium_users = ["premium", "niyas"]
    return "premium" if username in premium_users else "basic"

def get_ist_time():
    """Get IST time"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="NYZTrade - GEX Dashboard",
    page_icon="📊",
    layout="wide"
)

if not check_password():
    st.stop()

user_tier = get_user_tier()

# ============================================================================
# CSS
# ============================================================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
    }
    .countdown-timer {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        text-align: center;
        font-size: 1.2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================

st.markdown('<p class="main-header">📊 NYZTrade - Advanced GEX + DEX Analysis</p>', unsafe_allow_html=True)
st.markdown("**Real-time Gamma & Delta Exposure Analysis for Indian Markets**")

if user_tier == "premium":
    st.sidebar.success("👑 **Premium Member**")
else:
    st.sidebar.info(f"🆓 **Free Member**")

if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.header("⚙️ Dashboard Settings")

symbol = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])
strikes_range = st.sidebar.slider("Strikes Range", 5, 20, 12)
expiry_index = st.sidebar.selectbox("Expiry", [0, 1, 2], format_func=lambda x: ["Current Weekly", "Next Weekly", "Monthly"][x])

st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Auto-Refresh")

if user_tier == "premium":
    auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh", value=False)
    if auto_refresh:
        refresh_interval = st.sidebar.slider("Interval (seconds)", 30, 300, 60, 30)
        
        if 'countdown_start' not in st.session_state:
            st.session_state.countdown_start = time.time()
        
        elapsed = time.time() - st.session_state.countdown_start
        remaining = max(0, refresh_interval - int(elapsed))
        
        countdown_placeholder = st.sidebar.empty()
        countdown_placeholder.markdown(f'<div class="countdown-timer">⏱️ Next refresh: {remaining}s</div>', unsafe_allow_html=True)
else:
    st.sidebar.info("🔒 Auto-refresh: Premium only")
    auto_refresh = False
    refresh_interval = 60

if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear()
    if 'countdown_start' in st.session_state:
        st.session_state.countdown_start = time.time()
    st.rerun()

# ============================================================================
# DATA FETCHING
# ============================================================================

# Get DhanHQ credentials from Streamlit Secrets
DHAN_CLIENT_ID = st.secrets.get("dhan_client_id", None)
DHAN_ACCESS_TOKEN = st.secrets.get("dhan_access_token", None)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, strikes_range, expiry_index):
    if not CALCULATOR_AVAILABLE:
        return None, None, None, None, f"Calculator not available: {IMPORT_ERROR}"
    
    try:
        calculator = EnhancedGEXDEXCalculator(
            client_id=DHAN_CLIENT_ID,
            access_token=DHAN_ACCESS_TOKEN
        )
        df, futures_ltp, fetch_method, atm_info = calculator.fetch_and_calculate_gex_dex(
            symbol=symbol,
            strikes_range=strikes_range,
            expiry_index=expiry_index
        )
        return df, futures_ltp, fetch_method, atm_info, None
    except Exception as e:
        return None, None, None, None, str(e)

# ============================================================================
# MAIN
# ============================================================================

st.markdown("---")

with st.spinner(f"🔄 Fetching {symbol} data from DhanHQ..."):
    df, futures_ltp, fetch_method, atm_info, error = fetch_data(symbol, strikes_range, expiry_index)

if error:
    st.error(f"❌ Error: {error}")
    
    if "DhanHQ not initialized" in error:
        st.warning("""
        **DhanHQ API Setup Required:**
        
        1. Go to Streamlit Cloud → Your App → Settings → Secrets
        2. Add your DhanHQ credentials:
```toml
        dhan_client_id = "YOUR_CLIENT_ID"
        dhan_access_token = "YOUR_ACCESS_TOKEN"
```
        
        3. Get credentials from: https://www.dhan.co/ → API Management
        """)
    
    st.stop()

if df is None:
    st.error("❌ Failed to fetch data")
    st.stop()

# ============================================================================
# KEY METRICS
# ============================================================================

st.subheader("📊 Key Metrics")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    total_gex = float(df['Net_GEX_B'].sum())
    st.metric("Total Net GEX", f"{total_gex:.4f}B", delta="Bullish" if total_gex > 0 else "Volatile")

with col2:
    call_gex = float(df['Call_GEX'].sum())
    st.metric("Call GEX", f"{call_gex:.4f}B")

with col3:
    put_gex = float(df['Put_GEX'].sum())
    st.metric("Put GEX", f"{put_gex:.4f}B")

with col4:
    st.metric("Futures LTP", f"Rs {futures_ltp:,.2f}")

with col5:
    if atm_info:
        st.metric("ATM Straddle", f"Rs {atm_info['atm_straddle_premium']:.2f}")

# ============================================================================
# FLOW METRICS
# ============================================================================

try:
    flow_metrics = calculate_dual_gex_dex_flow(df, futures_ltp)
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        gex_bias = flow_metrics['gex_near_bias']
        if "BULLISH" in gex_bias:
            st.markdown(f'<div class="success-box"><b>GEX:</b> {gex_bias}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="warning-box"><b>GEX:</b> {gex_bias}</div>', unsafe_allow_html=True)
    
    with col2:
        dex_bias = flow_metrics['dex_near_bias']
        st.info(f"**DEX Bias:** {dex_bias}")
    
    with col3:
        combined_bias = flow_metrics['combined_bias']
        st.info(f"**Combined:** {combined_bias}")
        
except Exception as e:
    flow_metrics = None

# ============================================================================
# GAMMA FLIP
# ============================================================================

try:
    gamma_flip_zones = detect_gamma_flip_zones(df)
    if gamma_flip_zones:
        st.warning(f"⚡ **{len(gamma_flip_zones)} Gamma Flip Zone(s) Detected!**")
except:
    gamma_flip_zones = []

# ============================================================================
# CHARTS
# ============================================================================

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 GEX Profile", "📈 DEX Profile", "🎯 Hedging Pressure", "📋 Data", "💡 Strategies"])

with tab1:
    st.subheader(f"{symbol} Gamma Exposure")
    
    fig = go.Figure()
    colors = ['green' if x > 0 else 'red' for x in df['Net_GEX_B']]
    
    fig.add_trace(go.Bar(
        y=df['Strike'],
        x=df['Net_GEX_B'],
        orientation='h',
        marker_color=colors,
        name='Net GEX'
    ))
    
    fig.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    fig.update_layout(height=600, xaxis_title="Net GEX (Billions)", yaxis_title="Strike")
    
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader(f"{symbol} Delta Exposure")
    
    fig2 = go.Figure()
    dex_colors = ['green' if x > 0 else 'red' for x in df['Net_DEX_B']]
    
    fig2.add_trace(go.Bar(
        y=df['Strike'],
        x=df['Net_DEX_B'],
        orientation='h',
        marker_color=dex_colors,
        name='Net DEX'
    ))
    
    fig2.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    fig2.update_layout(height=600, xaxis_title="Net DEX (Billions)", yaxis_title="Strike")
    
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader(f"{symbol} Hedging Pressure")
    
    fig3 = go.Figure()
    
    fig3.add_trace(go.Bar(
        y=df['Strike'],
        x=df['Hedging_Pressure'],
        orientation='h',
        marker=dict(color=df['Hedging_Pressure'], colorscale='RdYlGn', showscale=True),
        name='Hedging Pressure'
    ))
    
    fig3.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    fig3.update_layout(height=600, xaxis_title="Pressure (%)", yaxis_title="Strike")
    
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    st.subheader("Strike Analysis")
    
    display_cols = ['Strike', 'Call_OI', 'Put_OI', 'Net_GEX_B', 'Net_DEX_B', 'Hedging_Pressure']
    st.dataframe(df[display_cols], use_container_width=True, height=400)
    
    csv = df.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, f"NYZTrade_{symbol}_{get_ist_time().strftime('%Y%m%d')}.csv", "text/csv")

with tab5:
    st.subheader("💡 Trading Strategies")
    
    if flow_metrics and atm_info:
        gex_val = flow_metrics['gex_near_total']
        dex_val = flow_metrics['dex_near_total']
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("GEX Flow", f"{gex_val:.2f}")
        with col2:
            st.metric("DEX Flow", f"{dex_val:.2f}")
        
        st.markdown("---")
        
        if gex_val > 50:
            st.success("### 🟢 Strong Positive GEX")
            st.text(f"""
Iron Condor:
  Sell {symbol} {int(futures_ltp)} CE/PE
  Buy {symbol} {int(futures_ltp + 200)} CE/{int(futures_ltp - 200)} PE
Risk: MODERATE
            """)
        elif gex_val < -50:
            st.error("### 🔴 Negative GEX")
            st.text(f"""
Long Straddle:
  Buy {symbol} {atm_info['atm_strike']} CE + PE
Cost: Rs {atm_info['atm_straddle_premium']:.2f}
Risk: HIGH
            """)
        else:
            st.warning("### ⚖️ Neutral - Wait for clarity")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

ist_time = get_ist_time()

with col1:
    st.info(f"⏰ {ist_time.strftime('%H:%M:%S')} IST")
with col2:
    st.info(f"📅 {ist_time.strftime('%d %b %Y')}")
with col3:
    st.info(f"📊 {symbol}")
with col4:
    st.success(f"✅ {fetch_method}")

st.markdown("**💡 NYZTrade YouTube | Powered by DhanHQ**")

# ============================================================================
# AUTO-REFRESH
# ============================================================================

if auto_refresh and user_tier == "premium":
    elapsed = time.time() - st.session_state.countdown_start
    if elapsed >= refresh_interval:
        st.session_state.countdown_start = time.time()
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()
