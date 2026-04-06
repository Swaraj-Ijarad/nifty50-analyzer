import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

st.set_page_config(layout="wide")

st.title("📊 NIFTY 50 Pro Analyzer")

# -------------------------
# LIVE NIFTY 50 (NSE CSV)
# -------------------------
@st.cache_data(ttl=86400)
def get_nifty50():
    url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"

    try:
        df = pd.read_csv(url, storage_options={"User-Agent": "Mozilla/5.0"})

        symbols = df["Symbol"].tolist()
        names = df["Company Name"].tolist()

        stocks = [s + ".NS" for s in symbols]
        company_map = dict(zip(stocks, names))

        return stocks, company_map

    except Exception:
        fallback_stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        fallback_map = {s: s for s in fallback_stocks}

        return fallback_stocks, fallback_map
stocks, company_names = get_nifty50()

# -------------------------
# SESSION STATE
# -------------------------
if "stock" not in st.session_state:
    st.session_state.stock = stocks[0]

# -------------------------
# SIDEBAR + SEARCH
# -------------------------
st.sidebar.title("📈 NIFTY 50")

st.sidebar.markdown("## 📈 NIFTY 50")

search = st.sidebar.text_input("🔍 Search stock")

filtered = [s for s in stocks if search.upper() in s] if search else stocks

for s in filtered:
    name = company_names.get(s, s)

    if s == st.session_state.stock:
        st.sidebar.markdown(f"👉 **{name}**")
    else:
        if st.sidebar.button(name):
            st.session_state.stock = s
selected_stock = st.session_state.stock

# -------------------------
# FETCH DATA
# -------------------------
data = yf.download(selected_stock, period="6mo", progress=False)

# 🔥 HANDLE EMPTY DATA (VERY IMPORTANT)
if data is None or data.empty:
    st.error("⚠️ Data not available right now. Please try another stock.")
    st.stop()

if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

data = data.dropna()

if len(data) < 2:
    st.warning("⚠️ Not enough data to analyze this stock.")
    st.stop()

# -------------------------
# PRICE + OHLC
# -------------------------
latest = data.iloc[-1]
prev = data.iloc[-2]

price = float(latest["Close"])
percent = ((price - prev["Close"]) / prev["Close"]) * 100

open_p = float(latest["Open"])
high_p = float(latest["High"])
low_p = float(latest["Low"])
close_p = float(latest["Close"])

# -------------------------
# RETURNS
# -------------------------
returns = data["Close"].pct_change().dropna()

volatility = float(returns.std() * np.sqrt(252))
avg_return = float(returns.mean() * 252)
risk_return = avg_return / volatility if volatility != 0 else 0

# -------------------------
# RSI
# -------------------------
delta = data["Close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)

rs = gain.rolling(14).mean() / loss.rolling(14).mean()
rsi = 100 - (100 / (1 + rs))

latest_rsi = float(rsi.dropna().iloc[-1])

# -------------------------
# MOVING AVERAGES
# -------------------------
data["MA20"] = data["Close"].rolling(20).mean()
data["MA50"] = data["Close"].rolling(50).mean()

ma20 = data["MA20"].iloc[-1]
ma50 = data["MA50"].iloc[-1]

signal = "🟢 BUY" if ma20 > ma50 else "🔴 SELL"

# -------------------------
# DECISION
# -------------------------
if risk_return > 1 and latest_rsi < 60:
    decision = "🔥 Strong Buy"
elif risk_return > 0.5:
    decision = "👍 Buy"
elif risk_return < 0:
    decision = "❌ Avoid"
else:
    decision = "⚖️ Hold"

trend = "📈 Uptrend" if price > data["Close"].iloc[0] else "📉 Downtrend"

# -------------------------
# LAYOUT
# -------------------------
left, right = st.columns([3,1])

# -------------------------
# LEFT PANEL
# -------------------------
with left:

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Price", f"₹{price:.2f}", f"{percent:.2f}%")
    col2.metric("Volatility", f"{volatility:.2f}")
    col3.metric("Return", f"{avg_return:.2f}")
    col4.metric("RSI", f"{latest_rsi:.2f}")

    st.markdown(f"### {selected_stock} | {signal} | {decision} | {trend}")

    st.markdown(
        f"**Open:** ₹{open_p:.2f} | **High:** ₹{high_p:.2f} | "
        f"**Low:** ₹{low_p:.2f} | **Close:** ₹{close_p:.2f}"
    )

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"]
    ))

    fig.add_trace(go.Scatter(x=data.index, y=data["MA20"], name="MA20"))
    fig.add_trace(go.Scatter(x=data.index, y=data["MA50"], name="MA50"))

    fig.update_layout(template="plotly_dark", title=selected_stock)

    st.plotly_chart(fig, use_container_width=True)

# -------------------------
# RIGHT PANEL (GAINERS/LOSERS FIXED)
# -------------------------
with right:

    st.subheader("🔥 Top Movers (Today)")

    movers = []

    for stock in stocks:
        try:
            d = yf.download(stock, period="5d", interval="1d", progress=False)

            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)

            d = d.dropna()

            closes = d["Close"].dropna()

            if len(closes) < 2:
                continue

            prev_close = float(closes.iloc[-2])
            latest_close = float(closes.iloc[-1])

            change = (latest_close - prev_close) / prev_close

            movers.append([stock, latest_close, change])

        except:
            continue

    df_movers = pd.DataFrame(movers, columns=["Stock", "Price", "Change"])

    if not df_movers.empty:
        df_movers = df_movers.sort_values(by="Change", ascending=False)

        st.markdown("### 🚀 Gainers")
        st.dataframe(df_movers.head(5), use_container_width=True)

        st.markdown("### 🔻 Losers")
        st.dataframe(df_movers.tail(5), use_container_width=True)

# -------------------------
# RANKING
# -------------------------
st.subheader("📊 Ranking (3M Performance)")

ranking = []

for stock in stocks:
    try:
        d = yf.download(stock, period="3mo", progress=False)

        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)

        d = d.dropna()

        if len(d) < 2:
            continue

        start = float(d["Close"].iloc[0])
        end = float(d["Close"].iloc[-1])

        change = (end - start) / start

        ranking.append([stock, change])

    except:
        continue

df_rank = pd.DataFrame(ranking, columns=["Stock", "Return"])

if not df_rank.empty:
    df_rank = df_rank.sort_values(by="Return", ascending=False)
    st.dataframe(df_rank)

# -------------------------
# TIME
# -------------------------
st.caption(f"Updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
