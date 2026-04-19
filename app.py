"""
US Market Theme & Breadth Tracker — Streamlit Web App
Live data from Yahoo Finance + Finviz
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="US Market Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
.stApp { background: #0a0e1a; }

h1, h2, h3 { font-family: 'DM Sans', sans-serif; font-weight: 700; }

/* Header */
.main-header {
    background: linear-gradient(135deg, #0d1b2a 0%, #1a2744 50%, #0d1b2a 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 24px 32px;
    margin-bottom: 24px;
}
.main-title {
    font-size: 28px;
    font-weight: 700;
    color: #e8f4fd;
    margin: 0;
    letter-spacing: -0.5px;
}
.main-subtitle {
    font-size: 13px;
    color: #6b8cad;
    margin-top: 4px;
    font-family: 'DM Mono', monospace;
}

/* Metric cards */
.metric-card {
    background: #111827;
    border: 1px solid #1e2d3d;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
}
.metric-label {
    font-size: 11px;
    color: #6b8cad;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
}
.metric-value {
    font-size: 22px;
    font-weight: 700;
    color: #e8f4fd;
    font-family: 'DM Mono', monospace;
    margin-top: 4px;
}

/* Table styling */
.dataframe { font-family: 'DM Mono', monospace !important; font-size: 12px !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111827;
    border-radius: 8px;
    padding: 4px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    color: #6b8cad;
    font-weight: 500;
    border-radius: 6px;
}
.stTabs [aria-selected="true"] {
    background: #1e3a5f !important;
    color: #e8f4fd !important;
}

/* Green/Red colouring */
.pos { color: #27ae60 !important; font-weight: 600; }
.neg { color: #e74c3c !important; font-weight: 600; }

/* Section headers */
.section-header {
    font-size: 13px;
    font-weight: 600;
    color: #6b8cad;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 1px solid #1e2d3d;
    padding-bottom: 8px;
    margin-bottom: 16px;
}

/* Last updated badge */
.update-badge {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: #4a6741;
    background: #0d1f0d;
    border: 1px solid #1a3d1a;
    border-radius: 4px;
    padding: 2px 8px;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# ── Data definitions ──────────────────────────────────────────────────────────
SECTORS = [
    ("Technology", "XLK"), ("Communication Svcs", "XLC"),
    ("Consumer Disc.", "XLY"), ("Financials", "XLF"),
    ("Health Care", "XLV"), ("Industrials", "XLI"),
    ("Energy", "XLE"), ("Consumer Staples", "XLP"),
    ("Utilities", "XLU"), ("Real Estate", "XLRE"),
    ("Materials", "XLB"),
]

THEMES = [
    ("Gold Miners", "GDX"), ("Silver Miners", "SIL"),
    ("Copper Miners", "COPX"), ("Lithium/Battery", "LIT"),
    ("Steel", "SLX"), ("Nuclear Energy", "NLR"),
    ("Uranium", "URA"), ("Clean Energy", "ICLN"),
    ("Solar", "TAN"), ("AI", "BOTZ"),
    ("AI Infrastructure", "GRID"), ("Cybersecurity", "HACK"),
    ("Cloud Computing", "SKYY"), ("Semiconductors", "SOXX"),
    ("Software", "IGV"), ("Robotics", "ROBO"),
    ("Space", "ARKX"), ("Quantum Computing", "QTUM"),
    ("Genomics", "ARKG"), ("Medical Devices", "IHI"),
    ("Biotech", "XBI"), ("Defence & Aerospace", "ITA"),
    ("India", "INDA"), ("Europe", "EZU"),
    ("Japan", "EWJ"), ("China Internet", "KWEB"),
    ("Bitcoin/Crypto", "BITO"), ("Bitcoin Miners", "WGMI"),
    ("Long Term Treasuries", "TLT"), ("Short Term Treasuries", "SHY"),
    ("Inflation/TIPS", "TIP"), ("US Dollar", "UUP"),
    ("Dividend Growth", "DGRO"), ("Low Volatility", "USMV"),
    ("Growth Stocks", "VUG"), ("Oil & Gas", "XOP"),
    ("Transports", "IYT"), ("Home Construction", "XHB"),
    ("Retail", "XRT"), ("Airlines", "JETS"),
    ("Casinos/Gaming", "BJK"), ("Telecom", "IYZ"),
    ("Fintech", "FINX"), ("Social Media", "SOCL"),
    ("Emerging Mkts Tech", "EMQQ"), ("Commodities", "PDBC"),
]

BREADTH = [
    ("S&P 500", "SPY"), ("Nasdaq 100", "QQQ"), ("Russell 2000", "IWM"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Helper functions ──────────────────────────────────────────────────────────
def safe_pct(new, old):
    if old and old != 0:
        return round((new - old) / abs(old) * 100, 2)
    return None

def ema_calc(prices, period):
    if len(prices) < period: return None
    k = 2 / (period + 1)
    val = sum(prices[:period]) / period
    for p in prices[period:]: val = p * k + val * (1 - k)
    return round(val, 2)

def sma_calc(prices, period):
    if len(prices) < period: return None
    return round(sum(prices[-period:]) / period, 2)

def fmt_pct(val, decimals=2):
    if val is None: return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.{decimals}f}%"

def color_val(val):
    """Return HTML-coloured percentage string."""
    if val is None: return "<span style='color:#4a5568'>—</span>"
    color = "#27ae60" if val >= 0 else "#e74c3c"
    sign = "+" if val >= 0 else ""
    return f"<span style='color:{color};font-weight:600'>{sign}{val:.2f}%</span>"

# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)  # cache for 15 minutes
def fetch_ticker(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 5: return None
        prices = [float(x) for x in hist["Close"]]
        price  = round(prices[-1], 2)
        return {
            "price":    price,
            "ret_1d":   safe_pct(price, prices[-2])  if len(prices)>=2  else None,
            "ret_1w":   safe_pct(price, prices[-6])  if len(prices)>=6  else None,
            "ret_1m":   safe_pct(price, prices[-22]) if len(prices)>=22 else None,
            "ret_3m":   safe_pct(price, prices[-66]) if len(prices)>=66 else None,
            "ret_1y":   safe_pct(price, prices[0]),
            "high_52w": round(max(prices), 2),
            "low_52w":  round(min(prices), 2),
            "pct_off_high": round((price - max(prices)) / max(prices) * 100, 2),
            "ema10":  ema_calc(prices, 10),
            "sma20":  sma_calc(prices, 20),
            "sma50":  sma_calc(prices, 50),
            "sma200": sma_calc(prices, 200),
        }
    except Exception:
        return None

@st.cache_data(ttl=900)
def fetch_finviz_industries():
    try:
        url = "https://finviz.com/groups.ashx?g=industry&v=140&o=name&st=d1"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.content, "html.parser")
        table = None
        for sel in [{"class":"groups_table"}, {"id":"groups-table"}]:
            table = soup.find("table", sel)
            if table: break
        if not table:
            for t in soup.find_all("table"):
                if "Biotechnology" in t.get_text() and "Steel" in t.get_text():
                    table = t; break
        if not table: return pd.DataFrame()

        SECTOR_MAP = {
            "Agricultural Inputs":"Basic Materials","Aluminum":"Basic Materials",
            "Building Materials":"Basic Materials","Chemicals":"Basic Materials",
            "Coking Coal":"Basic Materials","Copper":"Basic Materials","Gold":"Basic Materials",
            "Lumber & Wood Production":"Basic Materials","Other Industrial Metals & Mining":"Basic Materials",
            "Other Precious Metals & Mining":"Basic Materials","Paper & Paper Products":"Basic Materials",
            "Silver":"Basic Materials","Specialty Chemicals":"Basic Materials","Steel":"Basic Materials",
            "Uranium":"Basic Materials",
            "Advertising Agencies":"Comm. Services","Broadcasting":"Comm. Services",
            "Electronic Gaming & Multimedia":"Comm. Services","Entertainment":"Comm. Services",
            "Internet Content & Information":"Comm. Services","Publishing":"Comm. Services",
            "Telecom Services":"Comm. Services",
            "Airlines":"Consumer Cyclical","Apparel Manufacturing":"Consumer Cyclical",
            "Apparel Retail":"Consumer Cyclical","Auto & Truck Dealerships":"Consumer Cyclical",
            "Auto Manufacturers":"Consumer Cyclical","Auto Parts":"Consumer Cyclical",
            "Department Stores":"Consumer Cyclical","Footwear & Accessories":"Consumer Cyclical",
            "Gambling":"Consumer Cyclical","Home Improvement Retail":"Consumer Cyclical",
            "Internet Retail":"Consumer Cyclical","Leisure":"Consumer Cyclical",
            "Lodging":"Consumer Cyclical","Luxury Goods":"Consumer Cyclical",
            "Residential Construction":"Consumer Cyclical","Resorts & Casinos":"Consumer Cyclical",
            "Restaurants":"Consumer Cyclical","Specialty Retail":"Consumer Cyclical",
            "Travel Services":"Consumer Cyclical",
            "Beverages - Brewers":"Cons. Defensive","Beverages - Non-Alcoholic":"Cons. Defensive",
            "Beverages - Wineries & Distillers":"Cons. Defensive","Confectioners":"Cons. Defensive",
            "Discount Stores":"Cons. Defensive","Drug Stores":"Cons. Defensive",
            "Farm Products":"Cons. Defensive","Food Distribution":"Cons. Defensive",
            "Grocery Stores":"Cons. Defensive","Household & Personal Products":"Cons. Defensive",
            "Packaged Foods":"Cons. Defensive","Tobacco":"Cons. Defensive",
            "Oil & Gas Drilling":"Energy","Oil & Gas E&P":"Energy",
            "Oil & Gas Equipment & Services":"Energy","Oil & Gas Integrated":"Energy",
            "Oil & Gas Midstream":"Energy","Oil & Gas Refining & Marketing":"Energy",
            "Thermal Coal":"Energy",
            "Asset Management":"Financial","Banks - Diversified":"Financial",
            "Banks - Regional":"Financial","Capital Markets":"Financial",
            "Credit Services":"Financial","Financial Conglomerates":"Financial",
            "Financial Data & Stock Exchanges":"Financial","Insurance - Diversified":"Financial",
            "Insurance - Life":"Financial","Insurance - Property & Casualty":"Financial",
            "Insurance - Reinsurance":"Financial","Insurance - Specialty":"Financial",
            "Mortgage Finance":"Financial",
            "Biotechnology":"Healthcare","Diagnostics & Research":"Healthcare",
            "Drug Manufacturers - General":"Healthcare",
            "Drug Manufacturers - Specialty & Generic":"Healthcare",
            "Health Information Services":"Healthcare","Healthcare Plans":"Healthcare",
            "Medical Care Facilities":"Healthcare","Medical Devices":"Healthcare",
            "Medical Distribution":"Healthcare","Medical Instruments & Supplies":"Healthcare",
            "Pharmaceutical Retailers":"Healthcare",
            "Aerospace & Defense":"Industrials","Agricultural Farm Machinery":"Industrials",
            "Airports & Air Services":"Industrials","Building Products & Equipment":"Industrials",
            "Business Equipment & Supplies":"Industrials","Conglomerates":"Industrials",
            "Consulting Services":"Industrials","Electrical Equipment & Parts":"Industrials",
            "Engineering & Construction":"Industrials","Farm & Heavy Construction Machinery":"Industrials",
            "Industrial Distribution":"Industrials","Infrastructure Operations":"Industrials",
            "Integrated Freight & Logistics":"Industrials","Marine Shipping":"Industrials",
            "Metal Fabrication":"Industrials","Railroads":"Industrials",
            "Specialty Industrial Machinery":"Industrials","Trucking":"Industrials",
            "Waste Management":"Industrials",
            "Real Estate - Development":"Real Estate","Real Estate - Diversified":"Real Estate",
            "Real Estate Services":"Real Estate","REIT - Diversified":"Real Estate",
            "REIT - Healthcare Facilities":"Real Estate","REIT - Hotel & Motel":"Real Estate",
            "REIT - Industrial":"Real Estate","REIT - Mortgage":"Real Estate",
            "REIT - Office":"Real Estate","REIT - Residential":"Real Estate",
            "REIT - Retail":"Real Estate","REIT - Specialty":"Real Estate",
            "Communication Equipment":"Technology","Computer Hardware":"Technology",
            "Consumer Electronics":"Technology","Electronic Components":"Technology",
            "Electronics & Computer Distribution":"Technology",
            "Information Technology Services":"Technology",
            "Scientific & Technical Instruments":"Technology",
            "Semiconductor Equipment & Materials":"Technology","Semiconductors":"Technology",
            "Software - Application":"Technology","Software - Infrastructure":"Technology",
            "Utilities - Diversified":"Utilities","Utilities - Independent Power Producers":"Utilities",
            "Utilities - Regulated Electric":"Utilities","Utilities - Regulated Gas":"Utilities",
            "Utilities - Regulated Water":"Utilities","Utilities - Renewable":"Utilities",
        }

        def to_f(s):
            s = str(s).strip().replace("%","").replace("+","").replace(" ","")
            try: return float(s) / 100
            except: return None

        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells or len(cells) < 5: continue
            name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            if not name or name in ("Name","Industry",""): continue
            n = len(cells)
            ret_1w = to_f(cells[2].get_text()) if n>2 else None
            ret_1m = to_f(cells[3].get_text()) if n>3 else None
            ret_3m = to_f(cells[4].get_text()) if n>4 else None
            ret_6m = to_f(cells[5].get_text()) if n>5 else None
            ret_1y = to_f(cells[6].get_text()) if n>6 else None
            ret_1d = to_f(cells[10].get_text()) if n>10 else None
            comp   = (ret_1w or 0) + (ret_1m or 0) + (ret_3m or 0)
            rows.append({
                "Industry": name,
                "Sector":   SECTOR_MAP.get(name, "Other"),
                "1D %":     ret_1d,
                "1W %":     ret_1w,
                "1M %":     ret_1m,
                "3M %":     ret_3m,
                "6M %":     ret_6m,
                "1Y %":     ret_1y,
                "Composite":comp,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Composite", ascending=False).reset_index(drop=True)
            df.index += 1  # rank starts at 1
            df.index.name = "Rank"
        return df
    except Exception as e:
        return pd.DataFrame()

def build_etf_df(pairs):
    rows = []
    for name, ticker in pairs:
        d = fetch_ticker(ticker)
        if d:
            rows.append({
                "Name": name, "Ticker": ticker,
                "Price": d["price"],
                "1D %": d["ret_1d"], "1W %": d["ret_1w"],
                "1M %": d["ret_1m"], "3M %": d["ret_3m"], "1Y %": d["ret_1y"],
                "% off High": d["pct_off_high"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Composite"] = (
            (df["1W %"].fillna(0) + df["1M %"].fillna(0) + df["3M %"].fillna(0))
        )
        df = df.sort_values("Composite", ascending=False).reset_index(drop=True)
        df.index += 1
        df.index.name = "Rank"
    return df

# ── Chart helpers ─────────────────────────────────────────────────────────────
def bar_chart(df, col, title, n=15, height=400):
    sub = df.dropna(subset=[col]).copy()
    sub = pd.concat([sub.head(n), sub.tail(n)]).drop_duplicates()
    sub = sub.sort_values(col, ascending=True)
    colors = ["#27ae60" if v >= 0 else "#e74c3c" for v in sub[col]]
    name_col = "Industry" if "Industry" in sub.columns else "Name"
    fig = go.Figure(go.Bar(
        x=sub[col] * 100,
        y=sub[name_col],
        orientation="h",
        marker_color=colors,
        text=[f"{v*100:+.2f}%" for v in sub[col]],
        textposition="outside",
        textfont=dict(size=10, color="#aab8c2"),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#e8f4fd", size=14)),
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font=dict(color="#aab8c2", family="DM Mono"),
        xaxis=dict(gridcolor="#1e2d3d", zerolinecolor="#2d3f50", ticksuffix="%"),
        yaxis=dict(gridcolor="#1e2d3d", tickfont=dict(size=10)),
        height=height,
        margin=dict(l=10, r=60, t=40, b=10),
        showlegend=False,
    )
    return fig

def styled_df(df, pct_cols):
    """Format a dataframe with colour-coded percentage columns."""
    def fmt_cell(val, col):
        if pd.isna(val) or val is None: return "—"
        if col in pct_cols:
            v = val * 100 if abs(val) < 1 else val
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.2f}%"
        if col == "Price": return f"${val:.2f}"
        if col == "% off High": return f"{val:+.1f}%"
        return str(val)

    styled = df.copy()
    for col in pct_cols:
        if col in styled.columns:
            styled[col] = styled[col].apply(lambda x: fmt_cell(x, col))

    return styled

# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    # Header
    now = datetime.now().strftime("%d %b %Y  %H:%M")
    st.markdown(f"""
    <div class="main-header">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <div class="main-title">🇺🇸 US Market Theme & Breadth Tracker</div>
                <div class="main-subtitle">Live data · Yahoo Finance + Finviz · Auto-refreshes every 15 min</div>
            </div>
            <div class="update-badge">⬤ LIVE · {now}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 S&P 500 Sectors",
        "🔥 Theme Scorecard",
        "🧭 Breadth Monitor",
        "🏭 Finviz Industries",
    ])

    # ── Tab 1: Sectors ────────────────────────────────────────────────────────
    with tab1:
        with st.spinner("Loading sector data..."):
            df_sec = build_etf_df(SECTORS)

        if not df_sec.empty:
            col1, col2 = st.columns([3, 2])

            with col1:
                st.markdown('<div class="section-header">S&P 500 Sectors — Returns</div>',
                            unsafe_allow_html=True)
                pct_cols = ["1D %","1W %","1M %","3M %","1Y %","% off High","Composite"]

                def highlight_pct(val):
                    if not isinstance(val, str) or val == "—": return ""
                    try:
                        v = float(val.replace("%","").replace("+",""))
                        if v > 0: return "color: #27ae60; font-weight: 600"
                        if v < 0: return "color: #e74c3c; font-weight: 600"
                    except: pass
                    return ""

                display = df_sec[["Name","Ticker","Price","1D %","1W %","1M %","3M %","1Y %","Composite"]].copy()
                for col in ["1D %","1W %","1M %","3M %","1Y %","Composite"]:
                    display[col] = display[col].apply(
                        lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
                    )
                display["Price"] = display["Price"].apply(lambda x: f"${x:.2f}")

                st.dataframe(
                    display,
                    use_container_width=True,
                    height=420,
                )

            with col2:
                period = st.selectbox("Period", ["1M %","1W %","1D %","3M %","1Y %"],
                                      key="sec_period")
                st.plotly_chart(
                    bar_chart(df_sec, period, f"Sectors — {period}", n=11, height=420),
                    use_container_width=True
                )

    # ── Tab 2: Themes ─────────────────────────────────────────────────────────
    with tab2:
        with st.spinner("Loading theme data..."):
            df_th = build_etf_df(THEMES)

        if not df_th.empty:
            # Top/bottom summary
            top5    = df_th.head(5)
            bottom5 = df_th.tail(5)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="section-header">🚀 Top 5 Today (1D)</div>',
                            unsafe_allow_html=True)
                top5_1d = df_th.dropna(subset=["1D %"]).sort_values("1D %", ascending=False).head(5)
                for _, r in top5_1d.iterrows():
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                        f"border-bottom:1px solid #1e2d3d'>"
                        f"<span style='color:#e8f4fd;font-size:13px'>{r['Name']}</span>"
                        f"<span style='color:#27ae60;font-weight:700;font-family:DM Mono'>"
                        f"+{r['1D %']:.2f}%</span></div>",
                        unsafe_allow_html=True
                    )

            with col2:
                st.markdown('<div class="section-header">📉 Bottom 5 Today (1D)</div>',
                            unsafe_allow_html=True)
                bot5_1d = df_th.dropna(subset=["1D %"]).sort_values("1D %").head(5)
                for _, r in bot5_1d.iterrows():
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                        f"border-bottom:1px solid #1e2d3d'>"
                        f"<span style='color:#e8f4fd;font-size:13px'>{r['Name']}</span>"
                        f"<span style='color:#e74c3c;font-weight:700;font-family:DM Mono'>"
                        f"{r['1D %']:.2f}%</span></div>",
                        unsafe_allow_html=True
                    )

            with col3:
                st.markdown('<div class="section-header">🏆 Top Composite (1W+1M+3M)</div>',
                            unsafe_allow_html=True)
                for _, r in top5.iterrows():
                    comp = r["Composite"]
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                        f"border-bottom:1px solid #1e2d3d'>"
                        f"<span style='color:#e8f4fd;font-size:13px'>{r['Name']}</span>"
                        f"<span style='color:#f39c12;font-weight:700;font-family:DM Mono'>"
                        f"{comp:+.1f}%</span></div>",
                        unsafe_allow_html=True
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # Bar chart + full table
            col1, col2 = st.columns([2, 3])
            with col1:
                period = st.selectbox("Period", ["1M %","1W %","1D %","3M %","1Y %","Composite"],
                                      key="th_period")
                st.plotly_chart(
                    bar_chart(df_th, period, f"Top & Bottom Themes — {period}", n=10, height=500),
                    use_container_width=True
                )

            with col2:
                st.markdown('<div class="section-header">All Themes — Ranked by Composite</div>',
                            unsafe_allow_html=True)
                display = df_th[["Name","Ticker","Price","1D %","1W %","1M %","3M %","1Y %","Composite"]].copy()
                for col in ["1D %","1W %","1M %","3M %","1Y %","Composite"]:
                    display[col] = display[col].apply(
                        lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
                    )
                display["Price"] = display["Price"].apply(lambda x: f"${x:.2f}")
                st.dataframe(display, use_container_width=True, height=500)

    # ── Tab 3: Breadth Monitor ────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-header">Market Breadth — EMA10 vs SMA20 Signal</div>',
                    unsafe_allow_html=True)

        instruments = BREADTH + SECTORS
        rows = []
        with st.spinner("Loading breadth data..."):
            for name, ticker in instruments:
                d = fetch_ticker(ticker)
                if d:
                    price  = d["price"]
                    ema10  = d["ema10"]
                    sma20  = d["sma20"]
                    sma50  = d["sma50"]
                    sma200 = d["sma200"]
                    p_e10  = price > ema10  if ema10  else False
                    e_s20  = ema10 > sma20  if (ema10 and sma20) else False
                    p_s20  = price > sma20  if sma20  else False
                    if p_e10 and e_s20 and p_s20: sig = "✅ BULLISH"
                    elif p_e10 or p_s20:           sig = "🟡 MIXED"
                    else:                          sig = "🔴 BEARISH"
                    rows.append({
                        "Name": name, "Ticker": ticker,
                        "Price": f"${price:.2f}",
                        "EMA10": f"${ema10:.2f}" if ema10 else "—",
                        "SMA20": f"${sma20:.2f}" if sma20 else "—",
                        "SMA50": f"${sma50:.2f}" if sma50 else "—",
                        "SMA200": f"${sma200:.2f}" if sma200 else "—",
                        "Price>EMA10": "✅" if p_e10 else "❌",
                        "EMA10>SMA20": "✅" if e_s20 else "❌",
                        "Signal": sig,
                        "_bullish": p_e10 and e_s20 and p_s20,
                    })

        if rows:
            df_br = pd.DataFrame(rows)
            bullish = df_br["_bullish"].sum()
            total   = len(df_br)
            pct     = round(bullish / total * 100)

            c1, c2, c3 = st.columns(3)
            c1.metric("Bullish", f"{bullish}/{total}", f"{pct}% of instruments")
            c2.metric("Mixed",   str((df_br["Signal"]=="🟡 MIXED").sum()))
            c3.metric("Bearish", str((df_br["Signal"]=="🔴 BEARISH").sum()))

            st.dataframe(
                df_br.drop(columns=["_bullish"]),
                use_container_width=True, height=500
            )

    # ── Tab 4: Finviz Industries ──────────────────────────────────────────────
    with tab4:
        with st.spinner("Loading Finviz industry data..."):
            df_fv = fetch_finviz_industries()

        if df_fv.empty:
            st.warning("Could not load Finviz data. Try again in a few minutes.")
        else:
            st.markdown(
                f'<div class="section-header">{len(df_fv)} Industries — Ranked by Composite (1W+1M+3M)</div>',
                unsafe_allow_html=True
            )

            col1, col2 = st.columns([3, 2])

            with col1:
                # Sector filter
                sectors = ["All"] + sorted(df_fv["Sector"].unique().tolist())
                sel_sector = st.selectbox("Filter by sector", sectors, key="fv_sector")
                df_show = df_fv if sel_sector == "All" else df_fv[df_fv["Sector"]==sel_sector]

                # Format display
                display = df_show[["Industry","Sector","1D %","1W %","1M %","3M %","6M %","1Y %","Composite"]].copy()
                for col in ["1D %","1W %","1M %","3M %","6M %","1Y %","Composite"]:
                    display[col] = display[col].apply(
                        lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "—"
                    )

                # Add Finviz link
                def make_link(name):
                    code = re.sub(r'[^a-z0-9]', '', name.lower())
                    return f"https://finviz.com/screener.ashx?f=ind_{code}&v=211"

                display["🔗"] = df_show["Industry"].apply(make_link)

                st.dataframe(
                    display,
                    use_container_width=True,
                    height=600,
                    column_config={
                        "🔗": st.column_config.LinkColumn("Finviz →", display_text="Open")
                    }
                )

            with col2:
                period = st.selectbox(
                    "Period",
                    ["Composite","1D %","1W %","1M %","3M %","1Y %"],
                    key="fv_period"
                )
                df_chart = df_show.copy()
                df_chart[period] = df_chart[period] if period == "Composite" else df_chart[period]

                # Top 15 + bottom 5
                top    = df_chart.dropna(subset=[period]).sort_values(period, ascending=False).head(15)
                bottom = df_chart.dropna(subset=[period]).sort_values(period).head(5)
                combined = pd.concat([bottom, top]).drop_duplicates()
                combined = combined.sort_values(period, ascending=True)

                colors = ["#27ae60" if v >= 0 else "#e74c3c" for v in combined[period]]
                fig = go.Figure(go.Bar(
                    x=combined[period] * 100,
                    y=combined["Industry"],
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v*100:+.2f}%" for v in combined[period]],
                    textposition="outside",
                    textfont=dict(size=9, color="#aab8c2"),
                ))
                fig.update_layout(
                    title=dict(text=f"Top 15 + Bottom 5 — {period}",
                               font=dict(color="#e8f4fd", size=13)),
                    paper_bgcolor="#111827",
                    plot_bgcolor="#111827",
                    font=dict(color="#aab8c2", family="DM Mono"),
                    xaxis=dict(gridcolor="#1e2d3d", zerolinecolor="#2d3f50",
                               ticksuffix="%", title=""),
                    yaxis=dict(gridcolor="#1e2d3d", tickfont=dict(size=9)),
                    height=620,
                    margin=dict(l=10, r=60, t=40, b=10),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

    # Auto-refresh button
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,3])
    with col1:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        st.markdown(
            f'<div class="update-badge">Last: {now}</div>',
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
