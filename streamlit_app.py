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
# DHAN CREDENTIALS - FIXED VERSION
# ============================================================================

try:
    # Try to get credentials from secrets
    if "dhan_client_id" in st.secrets and "dhan_access_token" in st.secrets:
        DHAN_CLIENT_ID = st.secrets["dhan_client_id"]
        DHAN_ACCESS_TOKEN = st.secrets["dhan_access_token"]
        
        # Debug info in sidebar
        st.sidebar.success("✅ DhanHQ API Connected")
        st.sidebar.caption(f"Client ID: {DHAN_CLIENT_ID[:4]}***")
    else:
        raise KeyError("Credentials not found")
        
except Exception as e:
    DHAN_CLIENT_ID = None
    DHAN_ACCESS_TOKEN = None
    st.sidebar.error("❌ DhanHQ Not Connected")
    st.sidebar.caption(str(e))

# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.header("⚙️ Dashboard Settings")

symbol = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])
strikes_range = st.sidebar.slider("Strikes Range", 5, 20, 12)
expiry_index = st.sidebar.selectbox("Expiry", [0, 1, 2], format_func=lambda x: ["Current Weekly", "Next Weekly", "Monthly"][x])

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, strikes_range, expiry_index, client_id, access_token):
    if not CALCULATOR_AVAILABLE:
        return None, None, None, None, f"Calculator not available: {IMPORT_ERROR}"
    
    if not client_id or not access_token:
        return None, None, None, None, "DhanHQ credentials not configured in Streamlit Secrets"
    
    try:
        calculator = EnhancedGEXDEXCalculator(
            client_id=client_id,
            access_token=access_token
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
    df, futures_ltp, fetch_method, atm_info, error = fetch_data(
        symbol, strikes_range, expiry_index, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
    )

if error:
    st.error(f"❌ Error: {error}")
    
    if "not configured" in error or "not initialized" in error:
        st.warning("""
        **DhanHQ API Setup Required:**
        
        1. Go to: ☰ Menu → Manage app → Settings → Secrets
        2. Add your DhanHQ credentials:
```toml
        dhan_client_id = "YOUR_CLIENT_ID"
        dhan_access_token = "YOUR_API_SECRET"
```
        
        3. Get credentials from: https://www.dhan.co/ → API Management
        4. Save and wait 2 minutes for restart
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
        st.info(f"**DEX:** {flow_metrics['dex_near_bias']}")
    
    with col3:
        st.info(f"**Combined:** {flow_metrics['combined_bias']}")
        
except:
    flow_metrics = None

# ============================================================================
# CHARTS
# ============================================================================

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 GEX Profile", "📈 DEX Profile", "📋 Data"])

with tab1:
    st.subheader(f"{symbol} Gamma Exposure")
    
    fig = go.Figure()
    colors = ['green' if x > 0 else 'red' for x in df['Net_GEX_B']]
    
    fig.add_trace(go.Bar(y=df['Strike'], x=df['Net_GEX_B'], orientation='h', marker_color=colors))
    fig.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    fig.update_layout(height=600, xaxis_title="Net GEX (B)", yaxis_title="Strike")
    
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader(f"{symbol} Delta Exposure")
    
    fig2 = go.Figure()
    colors2 = ['green' if x > 0 else 'red' for x in df['Net_DEX_B']]
    
    fig2.add_trace(go.Bar(y=df['Strike'], x=df['Net_DEX_B'], orientation='h', marker_color=colors2))
    fig2.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    fig2.update_layout(height=600, xaxis_title="Net DEX (B)", yaxis_title="Strike")
    
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.dataframe(df[['Strike', 'Call_OI', 'Put_OI', 'Net_GEX_B', 'Net_DEX_B']], height=400)

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

ist_time = get_ist_time()

with col1:
    st.info(f"⏰ {ist_time.strftime('%H:%M:%S')} IST")
with col2:
    st.info(f"📊 {symbol}")
with col3:
    st.success(f"✅ {fetch_method}")

st.markdown("**💡 NYZTrade YouTube | Powered by DhanHQ**")
