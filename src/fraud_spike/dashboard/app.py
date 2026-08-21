import streamlit as st
import redis, json, pandas as pd
from streamlit_autorefresh import st_autorefresh
from fraud_spike.config import settings
import plotly.express as px

st.set_page_config(page_title="Fraud Spike Monitor", layout="wide", page_icon="🚨")
st.title("🚨 Fraud Spike Detector — Live Feed")

# Unique Feature: Dynamic Adaptive Risk Settings display
st.sidebar.header("⚙️ Active Policies")
st.sidebar.info("Model: fraud_spike_lgbm")
st.sidebar.metric("Live Threshold", "0.50 (Adaptive)")

st_autorefresh(interval=1500, key="refresh")

r = redis.Redis.from_url(settings.redis_url, decode_responses=True)

if 'last_id' not in st.session_state:
    st.session_state.last_id = '0'
if 'rows' not in st.session_state:
    st.session_state.rows = []

try:
    entries = r.xread({'flagged_stream': st.session_state.last_id}, count=50, block=100)
    if entries:
        for _, messages in entries:
            for msg_id, fields in messages:
                data = json.loads(fields['data'])
                # Flatten for display
                flat_row = {
                    'TransactionID': data['txn'].get('TransactionID', 'Unknown'),
                    'TransactionAmt': data['txn'].get('TransactionAmt', 0.0),
                    'Score': round(data['score'], 4),
                    'Top Reason': data['reasons'][0]['feature'] if data['reasons'] else 'N/A'
                }
                st.session_state.rows.append(flat_row)
                st.session_state.last_id = msg_id
except Exception as e:
    st.error(f"Redis connection error: {e}")

col1, col2 = st.columns(2)
col1.metric("Flagged this session", len(st.session_state.rows))

if st.session_state.rows:
    df = pd.DataFrame(st.session_state.rows[-50:])
    
    st.subheader("Recent Flagged Transactions")
    st.dataframe(df, use_container_width=True)
    
    # Unique Feature: Real-time fraud volume graph
    st.subheader("📈 Real-time Spike Analysis")
    fig = px.scatter(df, x=df.index, y="Score", size="TransactionAmt", 
                     color="Score", title="Fraud Scores & Amount Scatter",
                     color_continuous_scale="Reds")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Waiting for real-time flagged transactions...")
