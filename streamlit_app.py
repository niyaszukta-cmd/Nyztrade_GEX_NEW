import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

try:
    from gex_calculator import EnhancedGEXDEXCalculator, calculate_dual_gex_dex_flow, detect_gamma_flip_zones
    CALCULATOR_AVAILABLE = True
except Exception as e:
    CALCULATOR_AVAILABLE = False
    IMPORT_ERROR = str(e)

def check_password():
    def password_entered():
        username = st.session_state["username"].strip().lower()
        password = st.session_state["password"]
        users = {"demo": "demo123", "premium": "premium123", "niyas": "nyztrade123"}
        
        if username in users and password == users[username]:
            st.session_state["password_correct"] = True
            st.session_state["authenticated_user"] = username
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 NYZTrade Login")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered, use_container_width=True)
            st.info("Demo: `demo` / `demo123` | Premium: `premium` / `premium123`")
        return False
    elif not st.session_state["password_correct"]:
        st.error("Incorrect credentials")
        return False
    return True

def get_user_tier():
    username = st.session_state.get("authenticated_user", "guest")
    return "premium" if username in ["premium", "niyas"] else "basic"

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

st.set_page_config(page_title="NYZTrade GEX", page_icon="📊", layout="wide")

if not check_password():
    st.stop()

user_tier = get_user_tier()

st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#1f77b4;text-align:center">📊 NYZTrade - GEX + DEX Analysis</p>', unsafe_allow_html=True)
st.markdown("**Real-time Gamma & Delta Exposure for Indian Markets**")

if user_tier == "premium":
    st.sidebar.success("👑 Premium")
else:
    st.sidebar.info("🆓 Free")

if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================================================
# DEBUG SECRETS - THIS WILL SHOW US WHAT'S WRONG
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Debug Info")

# Show all available secrets keys
try:
    all_keys = list(st.secrets.keys())
    st.sidebar.success(f"✅ Secrets found: {len(all_keys)}")
    st.sidebar.caption(f"Keys: {all_keys}")
except Exception as e:
    st.sidebar.error(f"❌ No secrets: {e}")
    all_keys = []

# Try to get DhanHQ credentials
DHAN_CLIENT_ID = None
DHAN_ACCESS_TOKEN = None

# Method 1: Direct access
try:
    if "dhan_client_id" in st.secrets:
        DHAN_CLIENT_ID = st.secrets["dhan_client_id"]
        st.sidebar.success(f"✅ Client ID: {DHAN_CLIENT_ID[:4]}***")
    else:
        st.sidebar.warning("⚠️ dhan_client_id not in secrets")
except Exception as e:
    st.sidebar.error(f"❌ Client ID error: {e}")

try:
    if "dhan_access_token" in st.secrets:
        DHAN_ACCESS_TOKEN = st.secrets["dhan_access_token"]
        st.sidebar.success(f"✅ Access Token: {DHAN_ACCESS_TOKEN[:8]}***")
    else:
        st.sidebar.warning("⚠️ dhan_access_token not in secrets")
except Exception as e:
    st.sidebar.error(f"❌ Access Token error: {e}")

# Final status
if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
    st.sidebar.success("✅ DhanHQ Ready!")
else:
    st.sidebar.error("❌ DhanHQ credentials missing")
    st.error("### ❌ DhanHQ credentials not found in secrets")
    
    st.warning("""
    **How to fix:**
    
    1. Click ☰ (menu) → Manage app → Settings → Secrets
    2. Paste this EXACTLY:
```
    [passwords]
    demo = "demo123"
    premium = "premium123"
    premium_users = ["premium", "niyas"]
    
    dhan_client_id = "022705a2"
    dhan_access_token = "a9e88db4-17ae-4e2e-ba26-211ba1b62ccd"
```
    
    3. Click Save
    4. Wait 2 minutes
    5. Refresh this page
    """)
    st.stop()

# ============================================================================
# MAIN APP
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Settings")
symbol = st.sidebar.selectbox("Index", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])
strikes_range = st.sidebar.slider("Strikes Range", 5, 20, 12)
expiry_index = st.sidebar.selectbox("Expiry", [0, 1, 2], format_func=lambda x: ["Current", "Next", "Monthly"][x])

if st.sidebar.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, strikes_range, expiry_index, client_id, access_token):
    if not CALCULATOR_AVAILABLE:
        return None, None, None, None, f"Calculator error: {IMPORT_ERROR}"
    if not client_id or not access_token:
        return None, None, None, None, "DhanHQ credentials not configured"
    
    try:
        calc = EnhancedGEXDEXCalculator(client_id=client_id, access_token=access_token)
        return (*calc.fetch_and_calculate_gex_dex(symbol, strikes_range, expiry_index), None)
    except Exception as e:
        return None, None, None, None, str(e)

st.markdown("---")

with st.spinner(f"🔄 Fetching {symbol}..."):
    df, ltp, method, atm_info, error = fetch_data(symbol, strikes_range, expiry_index, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

if error:
    st.error(f"❌ {error}")
    st.stop()

if df is None:
    st.error("Failed to fetch data")
    st.stop()

st.subheader("📊 Key Metrics")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Net GEX", f"{df['Net_GEX_B'].sum():.4f}B")
with col2:
    st.metric("Call GEX", f"{df['Call_GEX'].sum():.4f}B")
with col3:
    st.metric("Put GEX", f"{df['Put_GEX'].sum():.4f}B")
with col4:
    st.metric("Futures", f"₹{ltp:,.2f}")
with col5:
    if atm_info:
        st.metric("ATM Straddle", f"₹{atm_info['atm_straddle_premium']:.2f}")

try:
    flow = calculate_dual_gex_dex_flow(df, ltp)
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"**GEX:** {flow['gex_near_bias']}")
    with c2:
        st.info(f"**DEX:** {flow['dex_near_bias']}")
    with c3:
        st.info(f"**Combined:** {flow['combined_bias']}")
except:
    pass

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📊 GEX", "📈 DEX", "📋 Data"])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df['Strike'], x=df['Net_GEX_B'], orientation='h', 
                         marker_color=['green' if x > 0 else 'red' for x in df['Net_GEX_B']]))
    fig.add_hline(y=ltp, line_dash="dash", line_color="blue", line_width=3)
    fig.update_layout(height=600, xaxis_title="Net GEX (B)", yaxis_title="Strike")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(y=df['Strike'], x=df['Net_DEX_B'], orientation='h',
                          marker_color=['green' if x > 0 else 'red' for x in df['Net_DEX_B']]))
    fig2.add_hline(y=ltp, line_dash="dash", line_color="blue", line_width=3)
    fig2.update_layout(height=600, xaxis_title="Net DEX (B)", yaxis_title="Strike")
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.dataframe(df[['Strike', 'Call_OI', 'Put_OI', 'Net_GEX_B', 'Net_DEX_B']], height=400)

st.markdown("---")
col1, col2, col3 = st.columns(3)
ist = get_ist_time()
with col1:
    st.info(f"⏰ {ist.strftime('%H:%M:%S')} IST")
with col2:
    st.info(f"📊 {symbol}")
with col3:
    st.success(f"✅ {method}")

st.markdown("**💡 NYZTrade YouTube | Powered by DhanHQ v2.1.0**")
