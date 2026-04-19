"""
US Market Theme & Breadth Tracker — Full Featured Web App
Live data from Yahoo Finance + Finviz
Features: Sectors, Themes, Breadth, Finviz Industries, Stage 2 Scanner,
          Sector Rotation, 52W Heatmap, RS Rating, Watchlist, Alerts, History
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re
import io
import json

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="US Market Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #0a0e1a; }
h1,h2,h3 { font-family: 'DM Sans', sans-serif; font-weight: 700; }

.main-header {
    background: linear-gradient(135deg, #0d1b2a 0%, #1a2744 50%, #0d1b2a 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 20px;
}
.main-title { font-size: 26px; font-weight: 700; color: #e8f4fd; margin:0; letter-spacing:-0.5px; }
.main-subtitle { font-size: 12px; color: #6b8cad; margin-top:4px; font-family:'DM Mono',monospace; }

.section-header {
    font-size: 12px; font-weight: 600; color: #6b8cad;
    text-transform: uppercase; letter-spacing: 1.5px;
    border-bottom: 1px solid #1e2d3d;
    padding-bottom: 8px; margin-bottom: 14px;
}
.update-badge {
    font-family:'DM Mono',monospace; font-size:11px; color:#4a6741;
    background:#0d1f0d; border:1px solid #1a3d1a; border-radius:4px;
    padding:2px 8px; display:inline-block;
}
.alert-box {
    background:#1a0d0d; border:1px solid #5c1a1a; border-radius:8px;
    padding:10px 14px; margin:4px 0; font-size:13px; color:#e8b4b4;
}
.alert-box-green {
    background:#0d1a0d; border:1px solid #1a5c1a; border-radius:8px;
    padding:10px 14px; margin:4px 0; font-size:13px; color:#b4e8b4;
}
.stTabs [data-baseweb="tab-list"] {
    background:#111827; border-radius:8px; padding:4px; gap:2px;
}
.stTabs [data-baseweb="tab"] { color:#6b8cad; font-weight:500; border-radius:6px; }
.stTabs [aria-selected="true"] { background:#1e3a5f !important; color:#e8f4fd !important; }
.stage2-badge {
    background:#0d2010; border:1px solid #27ae60; border-radius:6px;
    padding:2px 8px; font-size:11px; color:#27ae60;
    font-family:'DM Mono',monospace; font-weight:600;
}
</style>
""", unsafe_allow_html=True)

# ── Instrument lists ──────────────────────────────────────────────────────────
SECTORS = [
    ("Technology","XLK"),("Communication Svcs","XLC"),("Consumer Disc.","XLY"),
    ("Financials","XLF"),("Health Care","XLV"),("Industrials","XLI"),
    ("Energy","XLE"),("Consumer Staples","XLP"),("Utilities","XLU"),
    ("Real Estate","XLRE"),("Materials","XLB"),
]
THEMES = [
    ("Gold Miners","GDX"),("Silver Miners","SIL"),("Copper Miners","COPX"),
    ("Lithium/Battery","LIT"),("Steel","SLX"),("Nuclear Energy","NLR"),
    ("Uranium","URA"),("Clean Energy","ICLN"),("Solar","TAN"),
    ("AI","BOTZ"),("AI Infrastructure","GRID"),("Cybersecurity","HACK"),
    ("Cloud Computing","SKYY"),("Semiconductors","SOXX"),("Software","IGV"),
    ("Robotics","ROBO"),("Space","ARKX"),("Quantum Computing","QTUM"),
    ("Genomics","ARKG"),("Medical Devices","IHI"),("Biotech","XBI"),
    ("Defence & Aerospace","ITA"),("India","INDA"),("Europe","EZU"),
    ("Japan","EWJ"),("China Internet","KWEB"),("Bitcoin/Crypto","BITO"),
    ("Bitcoin Miners","WGMI"),("Long Term Treasuries","TLT"),
    ("Short Term Treasuries","SHY"),("Inflation/TIPS","TIP"),
    ("US Dollar","UUP"),("Dividend Growth","DGRO"),("Low Volatility","USMV"),
    ("Growth Stocks","VUG"),("Oil & Gas","XOP"),("Transports","IYT"),
    ("Home Construction","XHB"),("Retail","XRT"),("Airlines","JETS"),
    ("Casinos/Gaming","BJK"),("Telecom","IYZ"),("Fintech","FINX"),
    ("Social Media","SOCL"),("Emerging Mkts Tech","EMQQ"),("Commodities","PDBC"),
]
BREADTH = [("S&P 500","SPY"),("Nasdaq 100","QQQ"),("Russell 2000","IWM")]
HEADERS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language":"en-US,en;q=0.9",
}

# ── Session state init ────────────────────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["AAPL","NVDA","MSFT","TSLA"]
if "history" not in st.session_state:
    st.session_state.history = {}
if "stage2_results" not in st.session_state:
    st.session_state.stage2_results = None
if "stage2_timestamp" not in st.session_state:
    st.session_state.stage2_timestamp = None
if "setup_scan_results" not in st.session_state:
    st.session_state.setup_scan_results = None

# ── Helper functions ──────────────────────────────────────────────────────────
def safe_pct(new, old):
    if old and old != 0: return round((new-old)/abs(old)*100, 2)
    return None

def ema_calc(prices, period):
    if len(prices) < period: return None
    k = 2/(period+1); val = sum(prices[:period])/period
    for p in prices[period:]: val = p*k + val*(1-k)
    return round(val, 2)

def sma_calc(prices, period):
    if len(prices) < period: return None
    return round(sum(prices[-period:])/period, 2)

def rs_rating(ticker_ret_1y, spy_ret_1y):
    """Simplified RS rating 1-99 vs S&P 500."""
    if ticker_ret_1y is None or spy_ret_1y is None: return None
    diff = ticker_ret_1y - spy_ret_1y
    # Map diff to 1-99 scale (rough approximation)
    rating = 50 + diff * 0.5
    return max(1, min(99, round(rating)))

def to_finviz_url(name):
    code = re.sub(r'[^a-z0-9]','',name.lower())
    return f"https://finviz.com/screener.ashx?f=ind_{code}&v=211"

def fmt_pct(val):
    if val is None: return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"

def fmt_large(val):
    if not val: return "—"
    if val >= 1e12: return f"${val/1e12:.1f}T"
    if val >= 1e9:  return f"${val/1e9:.1f}B"
    if val >= 1e6:  return f"${val/1e6:.0f}M"
    return f"${val:,.0f}"

# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def fetch_ticker(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 5: return None
        prices = [float(x) for x in hist["Close"]]
        vols   = [float(x) for x in hist["Volume"]]
        price  = round(prices[-1], 2)
        high52 = round(max(prices), 2)
        low52  = round(min(prices), 2)
        try:
            info    = tk.fast_info
            company = getattr(info,"company_name", ticker) or ticker
            mktcap  = getattr(info,"market_cap", 0) or 0
        except Exception:
            company = ticker; mktcap = 0
        return {
            "price":    price,
            "company":  company,
            "mktcap":   mktcap,
            "ret_1d":   safe_pct(price, prices[-2])  if len(prices)>=2  else None,
            "ret_1w":   safe_pct(price, prices[-6])  if len(prices)>=6  else None,
            "ret_1m":   safe_pct(price, prices[-22]) if len(prices)>=22 else None,
            "ret_3m":   safe_pct(price, prices[-66]) if len(prices)>=66 else None,
            "ret_1y":   safe_pct(price, prices[0]),
            "high_52w": high52,
            "low_52w":  low52,
            "pct_off":  round((price-high52)/high52*100, 2),
            "avg_vol":  int(sum(vols[-50:])/50),
            "ema10":    ema_calc(prices, 10),
            "sma20":    sma_calc(prices, 20),
            "sma50":    sma_calc(prices, 50),
            "sma150":   sma_calc(prices, 150),
            "sma200":   sma_calc(prices, 200),
        }
    except Exception:
        return None

@st.cache_data(ttl=900)
def fetch_spy_ret():
    d = fetch_ticker("SPY")
    return d["ret_1y"] if d else 0

@st.cache_data(ttl=900)
def fetch_finviz():
    try:
        url = "https://finviz.com/groups.ashx?g=industry&v=140&o=name&st=d1"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.content, "html.parser")
        table = None
        for sel in [{"class":"groups_table"},{"id":"groups-table"}]:
            table = soup.find("table", sel)
            if table: break
        if not table:
            for t in soup.find_all("table"):
                if "Biotechnology" in t.get_text() and "Steel" in t.get_text():
                    table = t; break
        if not table: return pd.DataFrame()

        SMAP = {
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
            try: return float(s)/100
            except: return None

        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells or len(cells) < 5: continue
            name = cells[1].get_text(strip=True) if len(cells)>1 else ""
            if not name or name in ("Name","Industry",""): continue
            n = len(cells)
            r1w=to_f(cells[2].get_text()) if n>2 else None
            r1m=to_f(cells[3].get_text()) if n>3 else None
            r3m=to_f(cells[4].get_text()) if n>4 else None
            r6m=to_f(cells[5].get_text()) if n>5 else None
            r1y=to_f(cells[6].get_text()) if n>6 else None
            r1d=to_f(cells[10].get_text()) if n>10 else None
            comp=(r1w or 0)+(r1m or 0)+(r3m or 0)
            rows.append({"Industry":name,"Sector":SMAP.get(name,"Other"),
                         "1D %":r1d,"1W %":r1w,"1M %":r1m,"3M %":r3m,
                         "6M %":r6m,"1Y %":r1y,"Composite":comp})

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Composite",ascending=False).reset_index(drop=True)
            df.index += 1; df.index.name = "Rank"
        return df
    except Exception:
        return pd.DataFrame()

def build_etf_df(pairs):
    spy_ret = fetch_spy_ret()
    rows = []
    for name, ticker in pairs:
        d = fetch_ticker(ticker)
        if d:
            rs = rs_rating(d["ret_1y"], spy_ret)
            comp = (d["ret_1w"] or 0)+(d["ret_1m"] or 0)+(d["ret_3m"] or 0)
            rows.append({"Name":name,"Ticker":ticker,"Price":d["price"],
                         "1D %":d["ret_1d"],"1W %":d["ret_1w"],
                         "1M %":d["ret_1m"],"3M %":d["ret_3m"],"1Y %":d["ret_1y"],
                         "% off High":d["pct_off"],"RS Rating":rs,"Composite":comp})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Composite",ascending=False).reset_index(drop=True)
        df.index += 1; df.index.name = "Rank"
    return df

def get_industry_tickers(industry_name, max_pages=20):
    """Get stock tickers for an industry from Finviz screener.
    Mirrors Excel stage2_weekend.py exactly — up to 20 pages (400 stocks/industry).
    Uses href quote.ashx?t= filter to get ONLY real ticker links."""
    code = re.sub(r'[^a-z0-9]','',industry_name.lower())
    tickers = []
    for page in range(1, max_pages+1):
        start = (page-1)*20+1
        url = f"https://finviz.com/screener.ashx?v=111&f=ind_{code}&r={start}&o=ticker"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                break
            page_tickers = []
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=re.compile(r'quote\.ashx\?t=')):
                t = a.get_text(strip=True)
                if t and 1<=len(t)<=6 and re.match(r'^[A-Z][A-Z0-9.]*$',t):
                    page_tickers.append(t)
            if not page_tickers: break
            tickers.extend(page_tickers)
            if len(page_tickers) < 20: break
            time.sleep(0.3)
        except Exception:
            break
    return list(dict.fromkeys(tickers))

def check_stage2(ticker, min_price=8.0, min_vol=100000):
    """
    Check Stage 2 criteria — mirrors stage2_weekend.py (Excel) exactly:
      - Price >= min_price
      - 50-day avg volume >= min_vol
      - Price > MA50 > MA150 > MA200
    Uses period=1y, requires >= 200 days of data.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 200:
            return None

        prices  = [float(x) for x in hist["Close"]]
        volumes = [float(x) for x in hist["Volume"]]
        price   = prices[-1]
        avg_vol = sum(volumes[-50:]) / 50  # 50-day avg volume — same as Excel

        if price < min_price:   return None
        if avg_vol < min_vol:   return None

        # Moving averages — identical calculation to Excel
        ma50  = sum(prices[-50:])  / 50
        ma150 = sum(prices[-150:]) / 150
        ma200 = sum(prices[-200:]) / 200

        if not (price > ma50 > ma150 > ma200):
            return None

        # Returns — same formula as Excel
        high_52w = max(prices)
        low_52w  = min(prices)
        ret_1d = ((price / prices[-2]) - 1) * 100 if len(prices) >= 2 else None
        ret_1w = ((price / prices[-6]) - 1) * 100 if len(prices) >= 6 else None
        ret_1y = safe_pct(price, prices[0])

        spy_ret = fetch_spy_ret()
        rs = rs_rating(ret_1y, spy_ret)

        # Company info — use "name" attribute same as Excel fast_info.name
        try:
            info    = tk.fast_info
            company = getattr(info, "name", ticker) or ticker
            mktcap  = getattr(info, "market_cap", 0) or 0
        except Exception:
            company = ticker
            mktcap  = 0

        return {
            "Ticker":  ticker,
            "Company": company,
            "Price":   round(price, 2),
            "MA50":    round(ma50, 2),
            "MA150":   round(ma150, 2),
            "MA200":   round(ma200, 2),
            "1D %":    round(ret_1d, 2) if ret_1d is not None else None,
            "1W %":    round(ret_1w, 2) if ret_1w is not None else None,
            "% off 52W High": round((price - high_52w) / high_52w * 100, 1),
            "% from 52W Low": round((price - low_52w)  / low_52w  * 100, 1),
            "RS Rating": rs,
            "Avg Vol":   int(avg_vol),
            "Mkt Cap":   mktcap,
        }
    except Exception:
        return None

# ── Download helper ───────────────────────────────────────────────────────────
def to_excel_bytes(dfs_dict):
    """Convert dict of {sheetname: df} to Excel bytes for download."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=sheet[:31])
    return buf.getvalue()

# ── Chart helpers ─────────────────────────────────────────────────────────────
DARK = dict(paper_bgcolor="#111827",plot_bgcolor="#111827",
            font=dict(color="#aab8c2",family="DM Mono"))

def bar_chart(df, col, title, n=15, height=420):
    sub = df.dropna(subset=[col]).copy()
    top = sub.sort_values(col,ascending=False).head(n)
    bot = sub.sort_values(col,ascending=True).head(5)
    combined = pd.concat([bot,top]).drop_duplicates().sort_values(col,ascending=True)
    name_col = "Industry" if "Industry" in combined.columns else "Name"
    vals = combined[col]*100 if combined[col].abs().max()<2 else combined[col]
    colors = ["#27ae60" if v>=0 else "#e74c3c" for v in vals]
    fig = go.Figure(go.Bar(
        x=vals, y=combined[name_col], orientation="h",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in vals],
        textposition="outside", textfont=dict(size=9,color="#aab8c2"),
    ))
    fig.update_layout(**DARK, title=dict(text=title,font=dict(color="#e8f4fd",size=13)),
                      xaxis=dict(gridcolor="#1e2d3d",zerolinecolor="#2d3f50",ticksuffix="%"),
                      yaxis=dict(gridcolor="#1e2d3d",tickfont=dict(size=9)),
                      height=height, margin=dict(l=10,r=70,t=40,b=10), showlegend=False)
    return fig

def scatter_rotation(df):
    """Sector rotation scatter: 1M vs 3M."""
    sub = df.dropna(subset=["1M %","3M %"]).copy()
    name_col = "Industry" if "Industry" in sub.columns else "Name"
    x = sub["3M %"]*100 if sub["3M %"].abs().max()<2 else sub["3M %"]
    y = sub["1M %"]*100 if sub["1M %"].abs().max()<2 else sub["1M %"]
    colors = []
    quadrants = []
    for xi, yi in zip(x, y):
        if xi>0 and yi>0:   colors.append("#27ae60"); quadrants.append("Leading")
        elif xi<0 and yi>0: colors.append("#3498db"); quadrants.append("Improving")
        elif xi>0 and yi<0: colors.append("#e67e22"); quadrants.append("Fading")
        else:                colors.append("#e74c3c"); quadrants.append("Lagging")

    fig = go.Figure()
    fig.add_shape(type="line",x0=0,x1=0,y0=y.min()-2,y1=y.max()+2,
                  line=dict(color="#2d3f50",width=1,dash="dot"))
    fig.add_shape(type="line",x0=x.min()-2,x1=x.max()+2,y0=0,y1=0,
                  line=dict(color="#2d3f50",width=1,dash="dot"))

    for q, color in [("Leading","#27ae60"),("Improving","#3498db"),
                     ("Fading","#e67e22"),("Lagging","#e74c3c")]:
        mask = [qi==q for qi in quadrants]
        if not any(mask): continue
        fig.add_trace(go.Scatter(
            x=x[mask], y=y[mask],
            mode="markers+text",
            text=sub[name_col][mask],
            textposition="top center",
            textfont=dict(size=8,color="#aab8c2"),
            marker=dict(size=10,color=color,opacity=0.85,
                        line=dict(width=1,color="#1e2d3d")),
            name=q, hovertemplate=f"<b>%{{text}}</b><br>3M: %{{x:.1f}}%<br>1M: %{{y:.1f}}%<extra></extra>"
        ))

    # Quadrant labels
    for txt, x_pos, y_pos in [
        ("▲ LEADING",    x.max()*0.7, y.max()*0.85),
        ("↗ IMPROVING",  x.min()*0.7, y.max()*0.85),
        ("↘ FADING",     x.max()*0.7, y.min()*0.85),
        ("▼ LAGGING",    x.min()*0.7, y.min()*0.85),
    ]:
        fig.add_annotation(x=x_pos,y=y_pos,text=txt,
                           font=dict(size=10,color="#2d3f50"),showarrow=False)

    fig.update_layout(**DARK,
        title=dict(text="Sector Rotation — 3M (x) vs 1M (y)",
                   font=dict(color="#e8f4fd",size=13)),
        xaxis=dict(title="3M Performance %",gridcolor="#1a2535",
                   zerolinecolor="#2d3f50",ticksuffix="%"),
        yaxis=dict(title="1M Performance %",gridcolor="#1a2535",
                   zerolinecolor="#2d3f50",ticksuffix="%"),
        height=500, margin=dict(l=60,r=20,t=50,b=50),
        showlegend=True,
        legend=dict(bgcolor="#111827",bordercolor="#1e2d3d",borderwidth=1)
    )
    return fig

def heatmap_52w(df):
    """52W High/Low heatmap."""
    sub = df.dropna(subset=["% off High"]).copy()
    name_col = "Industry" if "Industry" in sub.columns else "Name"
    vals = sub["% off High"]*100 if sub["% off High"].abs().max()<2 else sub["% off High"]
    sub = sub.copy(); sub["val"] = vals
    sub = sub.sort_values("val", ascending=False)

    fig = go.Figure(go.Bar(
        x=sub[name_col], y=sub["val"],
        marker=dict(
            color=sub["val"],
            colorscale=[[0,"#e74c3c"],[0.5,"#e67e22"],[0.8,"#f1c40f"],[1,"#27ae60"]],
            cmin=-50, cmax=0,
            colorbar=dict(title="% off High",ticksuffix="%",
                          thickness=12,len=0.6)
        ),
        text=[f"{v:.1f}%" for v in sub["val"]],
        textposition="outside", textfont=dict(size=8,color="#aab8c2"),
    ))
    fig.update_layout(**DARK,
        title=dict(text="% off 52-Week High",font=dict(color="#e8f4fd",size=13)),
        xaxis=dict(tickangle=-45,tickfont=dict(size=8),gridcolor="#1a2535"),
        yaxis=dict(gridcolor="#1a2535",ticksuffix="%",title=""),
        height=420, margin=dict(l=20,r=20,t=50,b=120), showlegend=False
    )
    return fig

def fmt_df_pct(df, pct_cols, multiplier=1):
    """Format dataframe percentage columns for display."""
    display = df.copy()
    for col in pct_cols:
        if col in display.columns:
            display[col] = display[col].apply(
                lambda x: f"{x*multiplier:+.2f}%" if pd.notna(x) and x is not None else "—"
            )
    return display

# ── Alerts checker ────────────────────────────────────────────────────────────
def check_alerts(df_themes, df_sectors, df_fv):
    alerts = []
    # Theme composite crossovers
    if not df_themes.empty:
        for _, r in df_themes.iterrows():
            comp = r.get("Composite", 0)
            name = r.get("Name","")
            if comp > 10:
                alerts.append(("🚀", f"{name} — composite score extremely strong: {comp:+.1f}%", "green"))
            elif comp < -10:
                alerts.append(("⚠️", f"{name} — composite score very weak: {comp:+.1f}%", "red"))

    # Breadth alerts
    if not df_sectors.empty:
        bullish = sum(1 for _, r in df_sectors.iterrows()
                      if r.get("1M %") and r.get("1M %") > 0)
        total = len(df_sectors)
        pct = round(bullish/total*100) if total else 0
        if pct >= 70:
            alerts.append(("✅", f"Broad market bullish — {bullish}/{total} sectors positive 1M", "green"))
        elif pct <= 30:
            alerts.append(("🔴", f"Market breadth weak — only {bullish}/{total} sectors positive 1M", "red"))

    # Finviz: extreme movers
    if not df_fv.empty:
        top = df_fv.dropna(subset=["1D %"]).sort_values("1D %",ascending=False).head(3)
        bot = df_fv.dropna(subset=["1D %"]).sort_values("1D %").head(3)
        for _, r in top.iterrows():
            if r["1D %"] and r["1D %"]*100 > 2:
                alerts.append(("🔥", f"{r['Industry']} industry up {r['1D %']*100:+.2f}% today", "green"))
        for _, r in bot.iterrows():
            if r["1D %"] and r["1D %"]*100 < -2:
                alerts.append(("💧", f"{r['Industry']} industry down {r['1D %']*100:+.2f}% today", "red"))

    return alerts[:12]  # cap at 12


# ── SETUP SCANNER HELPER FUNCTIONS ────────────────────────────────────────────

def check_setup_scans(ticker, vol_thresh=1.5, pivot_thresh=0.8, lookback=20):
    """
    Run three scans on a ticker:
    Scan 1 — Low Volatility:  last 2 days both have (High-Low)/Close < vol_thresh%
    Scan 2 — Pivot Area:      last 2 days highs within pivot_thresh% of each other
    Scan 3 — Inside Day:      last day High < prev day High AND last day Low > prev day Low
    Returns dict with scan results + OHLCV for charting, or None if no scan passes.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 5:
            return None

        hist = hist.tail(lookback)
        opens  = list(hist["Open"])
        highs  = list(hist["High"])
        lows   = list(hist["Low"])
        closes = list(hist["Close"])
        dates  = list(hist.index)
        vols   = list(hist["Volume"])

        if len(closes) < 3:
            return None

        # Use last 2 completed days
        d1_o, d1_h, d1_l, d1_c = opens[-2], highs[-2], lows[-2], closes[-2]
        d2_o, d2_h, d2_l, d2_c = opens[-1], highs[-1], lows[-1], closes[-1]

        # Scan 1: daily range (High-Low)/Close < vol_thresh% for BOTH days
        range_d1 = (d1_h - d1_l) / d1_c * 100
        range_d2 = (d2_h - d2_l) / d2_c * 100
        scan1 = range_d1 < vol_thresh and range_d2 < vol_thresh

        # Scan 2: two last day highs within pivot_thresh% of each other
        high_diff = abs(d1_h - d2_h) / max(d1_h, d2_h) * 100
        scan2 = high_diff < pivot_thresh

        # Scan 3: inside day — last day's range is entirely within previous day's range
        scan3 = (d2_h < d1_h) and (d2_l > d1_l)

        # Only return if at least one scan passes
        if not (scan1 or scan2 or scan3):
            return None

        return {
            "ticker":    ticker,
            "scan1":     scan1,
            "scan2":     scan2,
            "scan3":     scan3,
            "range_d1":  round(range_d1, 2),
            "range_d2":  round(range_d2, 2),
            "high_diff": round(high_diff, 2),
            "inside_margin": round((d1_h - d2_h) / d1_h * 100, 2),
            "price":     round(closes[-1], 2),
            "pivot_high": round(max(d1_h, d2_h), 2),
            "prev_high":  round(d1_h, 2),
            "prev_low":   round(d1_l, 2),
            # OHLCV for mini chart
            "dates":  dates,
            "opens":  opens,
            "highs":  highs,
            "lows":   lows,
            "closes": closes,
            "vols":   vols,
        }
    except Exception:
        return None


def mini_candle_chart(result, industry="", rs=None, vol_thresh=1.5, pivot_thresh=0.8):
    """Compact 20-day candlestick chart with volume bars and scan annotations."""
    dates  = result["dates"]
    opens  = result["opens"]
    highs  = result["highs"]
    lows   = result["lows"]
    closes = result["closes"]
    vols   = result["vols"]
    ticker = result["ticker"]
    pivot  = result["pivot_high"]

    colors = ["rgba(39,174,96,0.85)" if c >= o else "rgba(231,76,60,0.85)"
              for c, o in zip(closes, opens)]
    vol_colors = ["rgba(39,174,96,0.35)" if c >= o else "rgba(231,76,60,0.35)"
                  for c, o in zip(closes, opens)]

    fig = go.Figure()

    # Volume bars (background layer)
    fig.add_trace(go.Bar(
        x=dates, y=vols,
        marker_color=vol_colors,
        name="Volume", yaxis="y2", showlegend=False,
    ))

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=dates, open=opens, high=highs, low=lows, close=closes,
        name="Price",
        increasing=dict(line=dict(color="#27ae60", width=1.5),
                        fillcolor="rgba(39,174,96,0.8)"),
        decreasing=dict(line=dict(color="#e74c3c", width=1.5),
                        fillcolor="rgba(231,76,60,0.8)"),
    ))

    # Pivot high dashed line
    fig.add_shape(type="line",
                  x0=dates[max(0, len(dates)-5)], x1=dates[-1],
                  y0=pivot, y1=pivot,
                  line=dict(color="#f39c12", width=1.5, dash="dash"))
    fig.add_annotation(
        x=dates[-1], y=pivot,
        text=f" ${pivot:.2f}",
        showarrow=False,
        font=dict(color="#f39c12", size=9),
        xanchor="left",
    )

    # Inside day box — highlight range of previous day
    if result.get("scan3") and len(dates) >= 2:
        fig.add_shape(type="rect",
                      x0=dates[-2], x1=dates[-1],
                      y0=result["prev_low"], y1=result["prev_high"],
                      fillcolor="rgba(52,152,219,0.08)",
                      line=dict(color="rgba(52,152,219,0.4)", width=1, dash="dot"))

    # Highlight last 2 bars
    if len(dates) >= 2:
        fig.add_vrect(
            x0=dates[-2], x1=dates[-1],
            fillcolor="rgba(255,255,255,0.03)",
            line=dict(color="rgba(255,255,255,0.15)", width=1),
        )

    # Build title with scan badges
    badges = []
    if result["scan1"]: badges.append(f"<span style='color:#3498db'>●LowVol</span>")
    if result["scan2"]: badges.append(f"<span style='color:#f39c12'>●Pivot</span>")
    if result["scan3"]: badges.append(f"<span style='color:#9b59b6'>●Inside</span>")
    badge_str = "  ".join(badges)

    rs_str  = f"  RS:{rs}" if rs else ""
    ind_str = f"<br><span style='color:#4a6080;font-size:9px'>{industry}</span>" if industry else ""
    title   = f"<b style='color:#e8f4fd'>{ticker}</b>  <span style='color:#aab8c2'>${result['price']:.2f}</span>  {badge_str}{rs_str}{ind_str}"

    fig.update_layout(
        paper_bgcolor="#111827",
        plot_bgcolor="#0a0f1a",
        font=dict(color="#aab8c2", family="DM Mono", size=8),
        title=dict(text=title, font=dict(color="#e8f4fd", size=11), x=0, y=0.98),
        xaxis=dict(
            gridcolor="#151e2d", showgrid=False,
            rangeslider=dict(visible=False),
            tickformat="%d %b", tickfont=dict(size=7),
            showticklabels=True,
        ),
        yaxis=dict(
            gridcolor="#151e2d", tickprefix="$", side="right",
            tickfont=dict(size=8), showgrid=True,
        ),
        yaxis2=dict(
            domain=[0, 0.18], showticklabels=False, showgrid=False,
            overlaying=None,
        ),
        height=290,
        margin=dict(l=4, r=55, t=45, b=20),
        showlegend=False,
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📋 Watchlist")
    wl_input = st.text_input("Add ticker:", placeholder="e.g. AAPL")
    if st.button("Add") and wl_input:
        t = wl_input.strip().upper()
        if t not in st.session_state.watchlist:
            st.session_state.watchlist.append(t)

    if st.session_state.watchlist:
        remove = st.selectbox("Remove:", ["—"]+st.session_state.watchlist)
        if st.button("Remove") and remove != "—":
            st.session_state.watchlist.remove(remove)

        st.markdown("---")
        spy_ret = fetch_spy_ret()
        for ticker in st.session_state.watchlist:
            d = fetch_ticker(ticker)
            if d:
                rs = rs_rating(d["ret_1y"], spy_ret)
                chg = d["ret_1d"] or 0
                color = "#27ae60" if chg >= 0 else "#e74c3c"
                sign  = "+" if chg >= 0 else ""
                st.markdown(
                    f"<div style='padding:8px;border-bottom:1px solid #1e2d3d'>"
                    f"<span style='color:#e8f4fd;font-weight:700'>{ticker}</span> "
                    f"<span style='color:{color};font-family:DM Mono;font-size:12px'>"
                    f"${d['price']:.2f} ({sign}{chg:.2f}%)</span><br>"
                    f"<span style='color:#6b8cad;font-size:11px'>RS: {rs or '—'} | "
                    f"1M: {fmt_pct(d['ret_1m'])} | MA50: ${d['sma50'] or 0:.2f}</span></div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(f"<div style='color:#6b8cad;padding:4px'>{ticker} — no data</div>",
                            unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    min_price = st.slider("Stage 2 Min Price ($)", 1, 50, 8)
    min_vol   = st.slider("Stage 2 Min Avg Vol (K)", 50, 500, 100) * 1000
    top_n     = st.slider("Top N Industries for Stage 2", 10, 60, 40)

    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()

# ── Main header ───────────────────────────────────────────────────────────────
now = datetime.now().strftime("%d %b %Y  %H:%M")
st.markdown(f"""
<div class="main-header">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div class="main-title">🇺🇸 US Market Theme & Breadth Tracker</div>
      <div class="main-subtitle">Yahoo Finance + Finviz · 15-min delayed · Auto-refresh every 15 min</div>
    </div>
    <div class="update-badge">⬤ LIVE · {now}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load core data ────────────────────────────────────────────────────────────
with st.spinner("Loading market data..."):
    df_sec = build_etf_df(SECTORS)
    df_th  = build_etf_df(THEMES)
    df_fv  = fetch_finviz()

# ── Alerts bar ────────────────────────────────────────────────────────────────
alerts = check_alerts(df_th, df_sec, df_fv)
if alerts:
    with st.expander(f"🔔 {len(alerts)} Alerts", expanded=False):
        for icon, msg, kind in alerts:
            cls = "alert-box-green" if kind=="green" else "alert-box"
            st.markdown(f'<div class="{cls}">{icon} {msg}</div>', unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Sectors",
    "🔥 Themes",
    "🧭 Breadth",
    "🏭 Industries",
    "📈 Stage 2",
    "🎯 Setup Scanner",
    "🔄 Rotation",
    "📉 52W Map",
    "📅 History",
])
tab_sec, tab_th, tab_br, tab_fv, tab_s2, tab_scan, tab_rot, tab_hw, tab_hist = tabs

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SECTORS
# ══════════════════════════════════════════════════════════════════════════════
with tab_sec:
    if not df_sec.empty:
        c1, c2 = st.columns([3,2])
        with c1:
            st.markdown('<div class="section-header">S&P 500 Sectors</div>',unsafe_allow_html=True)
            display = df_sec.copy()
            for col in ["1D %","1W %","1M %","3M %","1Y %","Composite"]:
                display[col] = display[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
            display["Price"] = display["Price"].apply(lambda x: f"${x:.2f}")
            display["% off High"] = display["% off High"].apply(lambda x: f"{x:+.1f}%")
            st.dataframe(display[["Name","Ticker","Price","1D %","1W %","1M %","3M %","1Y %","% off High","RS Rating","Composite"]],
                         use_container_width=True, height=420)
            # Download
            dl = df_sec.copy()
            st.download_button("📥 Download Excel", to_excel_bytes({"Sectors":dl}),
                               "sectors.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            period = st.selectbox("Period",["1M %","1W %","1D %","3M %","1Y %"],key="sec_p")
            st.plotly_chart(bar_chart(df_sec,period,f"Sectors — {period}",n=11,height=420),
                            use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THEMES
# ══════════════════════════════════════════════════════════════════════════════
with tab_th:
    if not df_th.empty:
        # Summary row
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="section-header">🚀 Top 5 Today</div>',unsafe_allow_html=True)
            top5 = df_th.dropna(subset=["1D %"]).sort_values("1D %",ascending=False).head(5)
            for _,r in top5.iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
                    f"border-bottom:1px solid #1e2d3d'>"
                    f"<span style='color:#e8f4fd;font-size:12px'>{r['Name']}</span>"
                    f"<span style='color:#27ae60;font-weight:700;font-family:DM Mono;font-size:12px'>"
                    f"+{r['1D %']:.2f}%</span></div>",unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="section-header">📉 Bottom 5 Today</div>',unsafe_allow_html=True)
            bot5 = df_th.dropna(subset=["1D %"]).sort_values("1D %").head(5)
            for _,r in bot5.iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
                    f"border-bottom:1px solid #1e2d3d'>"
                    f"<span style='color:#e8f4fd;font-size:12px'>{r['Name']}</span>"
                    f"<span style='color:#e74c3c;font-weight:700;font-family:DM Mono;font-size:12px'>"
                    f"{r['1D %']:.2f}%</span></div>",unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="section-header">🏆 Top Composite</div>',unsafe_allow_html=True)
            for _,r in df_th.head(5).iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
                    f"border-bottom:1px solid #1e2d3d'>"
                    f"<span style='color:#e8f4fd;font-size:12px'>{r['Name']}</span>"
                    f"<span style='color:#f39c12;font-weight:700;font-family:DM Mono;font-size:12px'>"
                    f"{r['Composite']:+.1f}%</span></div>",unsafe_allow_html=True)

        st.markdown("<br>",unsafe_allow_html=True)
        c1, c2 = st.columns([2,3])
        with c1:
            period = st.selectbox("Period",["1M %","1W %","1D %","3M %","1Y %","Composite"],key="th_p")
            st.plotly_chart(bar_chart(df_th,period,f"Themes — {period}",n=12,height=520),
                            use_container_width=True)
        with c2:
            st.markdown('<div class="section-header">All Themes — Ranked by Composite</div>',unsafe_allow_html=True)
            display = df_th.copy()
            for col in ["1D %","1W %","1M %","3M %","1Y %","Composite"]:
                display[col] = display[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
            display["Price"] = display["Price"].apply(lambda x: f"${x:.2f}")
            display["% off High"] = display["% off High"].apply(lambda x: f"{x:+.1f}%")
            st.dataframe(display[["Name","Ticker","Price","1D %","1W %","1M %","3M %","1Y %","% off High","RS Rating","Composite"]],
                         use_container_width=True, height=520)

        st.download_button("📥 Download Excel", to_excel_bytes({"Themes":df_th}),
                           "themes.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BREADTH
# ══════════════════════════════════════════════════════════════════════════════
with tab_br:
    st.markdown('<div class="section-header">Breadth Monitor — EMA10 vs SMA20</div>',unsafe_allow_html=True)
    rows = []
    with st.spinner("Loading breadth data..."):
        for name,ticker in BREADTH+SECTORS:
            d = fetch_ticker(ticker)
            if d:
                p,e10,s20,s50,s200 = d["price"],d["ema10"],d["sma20"],d["sma50"],d["sma200"]
                pe = p>e10 if e10 else False
                es = e10>s20 if (e10 and s20) else False
                ps = p>s20 if s20 else False
                if pe and es and ps: sig="✅ BULLISH"
                elif pe or ps:       sig="🟡 MIXED"
                else:                sig="🔴 BEARISH"
                rows.append({"Name":name,"Ticker":ticker,
                             "Price":f"${p:.2f}",
                             "EMA10":f"${e10:.2f}" if e10 else "—",
                             "SMA20":f"${s20:.2f}" if s20 else "—",
                             "SMA50":f"${s50:.2f}" if s50 else "—",
                             "SMA200":f"${s200:.2f}" if s200 else "—",
                             "P>EMA10":"✅" if pe else "❌",
                             "EMA10>SMA20":"✅" if es else "❌",
                             "Signal":sig,
                             "_bull":pe and es and ps})

    if rows:
        df_br = pd.DataFrame(rows)
        bull = df_br["_bull"].sum(); total=len(df_br)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Bullish",f"{bull}/{total}",f"{round(bull/total*100)}%")
        c2.metric("Mixed",str((df_br["Signal"]=="🟡 MIXED").sum()))
        c3.metric("Bearish",str((df_br["Signal"]=="🔴 BEARISH").sum()))
        c4.metric("Market Pulse","🟢 Risk On" if bull/total>0.6 else "🔴 Risk Off" if bull/total<0.4 else "🟡 Neutral")
        st.dataframe(df_br.drop(columns=["_bull"]),use_container_width=True,height=500)
        st.download_button("📥 Download Excel",
                           to_excel_bytes({"Breadth":df_br.drop(columns=["_bull"])}),
                           "breadth.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — FINVIZ INDUSTRIES
# ══════════════════════════════════════════════════════════════════════════════
with tab_fv:
    if df_fv.empty:
        st.warning("Could not load Finviz data. Try again in a few minutes.")
    else:
        st.markdown(f'<div class="section-header">{len(df_fv)} Industries — Ranked by Composite</div>',
                    unsafe_allow_html=True)
        c1,c2 = st.columns([3,2])
        with c1:
            sectors = ["All"]+sorted(df_fv["Sector"].dropna().unique().tolist())
            sel = st.selectbox("Sector filter",sectors,key="fv_s")
            df_show = df_fv if sel=="All" else df_fv[df_fv["Sector"]==sel]
            display = df_show.copy()
            for col in ["1D %","1W %","1M %","3M %","6M %","1Y %","Composite"]:
                display[col]=display[col].apply(lambda x:f"{x*100:+.2f}%" if pd.notna(x) else "—")
            display["🔗"]=df_show["Industry"].apply(to_finviz_url)
            st.dataframe(display[["Industry","Sector","1D %","1W %","1M %","3M %","6M %","1Y %","Composite","🔗"]],
                         use_container_width=True, height=580,
                         column_config={"🔗":st.column_config.LinkColumn("Finviz →",display_text="Open")})
            st.download_button("📥 Download Excel",to_excel_bytes({"Finviz Industries":df_show}),
                               "finviz_industries.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            period = st.selectbox("Period",["Composite","1D %","1W %","1M %","3M %","1Y %"],key="fv_p")
            df_chart = df_show.copy()
            top = df_chart.dropna(subset=[period]).sort_values(period,ascending=False).head(15)
            bot = df_chart.dropna(subset=[period]).sort_values(period).head(5)
            combined = pd.concat([bot,top]).drop_duplicates().sort_values(period,ascending=True)
            vals = combined[period]*100 if combined[period].abs().max()<2 else combined[period]
            colors=["#27ae60" if v>=0 else "#e74c3c" for v in vals]
            fig=go.Figure(go.Bar(x=vals,y=combined["Industry"],orientation="h",
                                 marker_color=colors,
                                 text=[f"{v:+.2f}%" for v in vals],
                                 textposition="outside",textfont=dict(size=8,color="#aab8c2")))
            fig.update_layout(**DARK,title=dict(text=f"Top 15 + Bottom 5 — {period}",
                                                font=dict(color="#e8f4fd",size=12)),
                              xaxis=dict(gridcolor="#1e2d3d",ticksuffix="%"),
                              yaxis=dict(tickfont=dict(size=8)),
                              height=600,margin=dict(l=10,r=70,t=40,b=10),showlegend=False)
            st.plotly_chart(fig,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — STAGE 2
# ══════════════════════════════════════════════════════════════════════════════
with tab_s2:
    st.markdown('<div class="section-header">Stage 2 Stocks — Price > MA50 > MA150 > MA200</div>',
                unsafe_allow_html=True)

    # Check if we have cached results < 24h old
    has_results = (st.session_state.stage2_results is not None and
                   st.session_state.stage2_timestamp is not None and
                   datetime.now() - st.session_state.stage2_timestamp < timedelta(hours=24))

    if has_results:
        ts = st.session_state.stage2_timestamp.strftime("%d %b %Y %H:%M")
        st.markdown(f'<div class="update-badge">Last scan: {ts}</div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1:
        st.info(f"⏱️ Scans top {top_n} industries × ~30-50 stocks each. Takes **10-20 minutes**. "
                f"Results cached for 24 hours. Best run on weekends.")
    with col2:
        run_scan = st.button("🔍 Run Stage 2 Scan", type="primary",
                             disabled=False)

    if run_scan:
        if df_fv.empty:
            st.error("Load Finviz data first — go to Industries tab")
        else:
            top_industries = df_fv.head(top_n)[["Industry","Sector","Composite"]].values.tolist()
            progress = st.progress(0)
            status   = st.empty()
            all_results = []
            total_checked = 0

            for i, (industry, sector, score) in enumerate(top_industries):
                status.markdown(f"**Scanning [{i+1}/{top_n}]:** {industry}...")
                progress.progress((i+1)/top_n)

                tickers = get_industry_tickers(industry, max_pages=4)
                for ticker in tickers:
                    total_checked += 1
                    stock = check_stage2(ticker, min_price, min_vol)
                    if stock:
                        stock["Industry"] = industry
                        stock["Sector"]   = sector
                        stock["Ind Score"]= round(score*100, 2)
                        all_results.append(stock)
                    time.sleep(0.1)

            progress.progress(1.0)
            status.markdown(f"✅ **Done!** Found **{len(all_results)}** Stage 2 stocks from {total_checked} checked.")
            st.session_state.stage2_results   = all_results
            st.session_state.stage2_timestamp = datetime.now()

    if st.session_state.stage2_results:
        df_s2 = pd.DataFrame(st.session_state.stage2_results)
        df_s2 = df_s2.sort_values(["Ind Score","% off 52W High"],ascending=[False,False])
        df_s2 = df_s2.reset_index(drop=True); df_s2.index+=1; df_s2.index.name="Rank"

        # Summary metrics
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Stage 2 Stocks",len(df_s2))
        c2.metric("Industries",df_s2["Industry"].nunique())
        c3.metric("Avg RS Rating",round(df_s2["RS Rating"].dropna().mean()))
        c4.metric("Near 52W High (<10%)",int((df_s2["% off 52W High"]>-10).sum()))

        # Filters
        c1,c2,c3 = st.columns(3)
        with c1:
            ind_filter = st.selectbox("Industry",["All"]+sorted(df_s2["Industry"].unique().tolist()))
        with c2:
            rs_min = st.slider("Min RS Rating",1,99,50,key="s2_rs")
        with c3:
            high_filter = st.slider("Max % off 52W High",-50,0,-30,key="s2_high")

        df_show = df_s2.copy()
        if ind_filter != "All":
            df_show = df_show[df_show["Industry"]==ind_filter]
        df_show = df_show[df_show["RS Rating"].fillna(0)>=rs_min]
        df_show = df_show[df_show["% off 52W High"]>=high_filter]

        st.markdown(f"**Showing {len(df_show)} stocks**",unsafe_allow_html=True)

        # Format for display
        display = df_show.copy()
        for col in ["1D %","1W %"]:
            if col in display.columns:
                display[col]=display[col].apply(lambda x:f"{x:+.2f}%" if pd.notna(x) else "—")
        for col in ["% off 52W High","% from 52W Low"]:
            if col in display.columns:
                display[col]=display[col].apply(lambda x:f"{x:+.1f}%")
        display["Price"]=display["Price"].apply(lambda x:f"${x:.2f}")
        display["MA50"]=display["MA50"].apply(lambda x:f"${x:.2f}")
        display["MA150"]=display["MA150"].apply(lambda x:f"${x:.2f}")
        display["MA200"]=display["MA200"].apply(lambda x:f"${x:.2f}")
        display["Avg Vol"]=display["Avg Vol"].apply(lambda x:f"{x/1e6:.1f}M" if x>=1e6 else f"{x/1e3:.0f}K")
        display["Mkt Cap"]=display["Mkt Cap"].apply(fmt_large)

        st.dataframe(display,use_container_width=True,height=550)

        st.download_button("📥 Download Stage 2 Excel",
                           to_excel_bytes({"Stage 2 Stocks":df_show,"All Results":df_s2}),
                           "stage2_stocks.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Top industries bar chart
        top_inds = df_s2.groupby("Industry").size().sort_values(ascending=False).head(15)
        fig = go.Figure(go.Bar(
            x=top_inds.values, y=top_inds.index, orientation="h",
            marker_color="#27ae60",
            text=top_inds.values, textposition="outside",
        ))
        fig.update_layout(**DARK,title=dict(text="Stage 2 Stocks by Industry",
                                            font=dict(color="#e8f4fd",size=13)),
                          xaxis=dict(gridcolor="#1e2d3d",title="# Stocks"),
                          yaxis=dict(tickfont=dict(size=9)),
                          height=400,margin=dict(l=10,r=40,t=40,b=10),showlegend=False)
        st.plotly_chart(fig,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — SETUP SCANNER
# ══════════════════════════════════════════════════════════════════════════════
with tab_scan:
    st.markdown(
        '<div class="section-header">🎯 Setup Scanner — Low Volatility · Pivot · Inside Day</div>',
        unsafe_allow_html=True
    )

    # Scan descriptions
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div style='background:#0d1520;border:1px solid #1e3a6e;border-radius:8px;padding:12px;font-size:12px'>
        <b style='color:#3498db'>📘 Scan 1 — Low Volatility</b><br><br>
        Both last 2 days have daily range<br>
        (High − Low) / Close &lt; threshold<br><br>
        <span style='color:#6b8cad'>Stock is coiling — energy building</span>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div style='background:#0d1520;border:1px solid #6e5a1e;border-radius:8px;padding:12px;font-size:12px'>
        <b style='color:#f39c12'>📘 Scan 2 — Pivot Area</b><br><br>
        Last 2 days highs within<br>
        threshold % of each other<br><br>
        <span style='color:#6b8cad'>Clear resistance level being tested</span>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div style='background:#0d1520;border:1px solid #5a1e6e;border-radius:8px;padding:12px;font-size:12px'>
        <b style='color:#9b59b6'>📘 Scan 3 — Inside Day</b><br><br>
        Last day High &lt; prev High<br>
        AND last day Low &gt; prev Low<br><br>
        <span style='color:#6b8cad'>Full range contained — compression</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.stage2_results is None:
        st.warning("⚠️ Run the **Stage 2 Scan** first (📈 Stage 2 tab) — Setup Scanner filters those results.")
    else:
        df_s2_base = pd.DataFrame(st.session_state.stage2_results)
        n_stocks = len(df_s2_base)

        # Settings
        cs1, cs2, cs3, cs4 = st.columns(4)
        with cs1: vol_thresh   = st.slider("Scan 1: Max daily range %", 0.5, 3.0, 1.5, 0.1, key="sc_vol")
        with cs2: pivot_thresh = st.slider("Scan 2: Max high diff %",   0.1, 2.0, 0.8, 0.1, key="sc_piv")
        with cs3: charts_per_row = st.selectbox("Charts per row", [2, 3, 4], index=1, key="sc_cols")
        with cs4: st.markdown(f"<br><span style='color:#6b8cad;font-size:12px'>{n_stocks} Stage 2 stocks to scan</span>", unsafe_allow_html=True)

        if st.button("🔍 Run Setup Scans", type="primary", key="run_setup"):
            tickers = df_s2_base["Ticker"].tolist()
            progress = st.progress(0)
            status   = st.empty()
            scan_results = []

            for i, ticker in enumerate(tickers):
                progress.progress((i + 1) / len(tickers))
                status.markdown(f"Scanning **{ticker}** ({i+1}/{len(tickers)})...")
                r = check_setup_scans(ticker, vol_thresh, pivot_thresh)
                if r:
                    s2_row = df_s2_base[df_s2_base["Ticker"] == ticker]
                    if not s2_row.empty:
                        r["Company"]  = s2_row.iloc[0].get("Company", ticker)
                        r["Industry"] = s2_row.iloc[0].get("Industry", "")
                        r["Sector"]   = s2_row.iloc[0].get("Sector", "")
                        r["RS Rating"]= s2_row.iloc[0].get("RS Rating", None)
                        r["MA50"]     = s2_row.iloc[0].get("MA50", None)
                        r["Ind Score"]= s2_row.iloc[0].get("Ind Score", 0)
                    scan_results.append(r)
                time.sleep(0.08)

            progress.progress(1.0)
            status.empty()
            st.session_state.setup_scan_results = scan_results
            total = len(scan_results)
            both  = sum(1 for r in scan_results if r["scan1"] and r["scan2"])
            s3    = sum(1 for r in scan_results if r["scan3"])
            st.success(f"✅ Found **{total}** setups — {both} pass both S1+S2, {s3} inside days")

        # ── Display results ───────────────────────────────────────────────────
        if st.session_state.setup_scan_results:
            results = st.session_state.setup_scan_results

            # ── Summary metrics ───────────────────────────────────────────
            n_s1 = sum(1 for r in results if r["scan1"])
            n_s2 = sum(1 for r in results if r["scan2"])
            n_s3 = sum(1 for r in results if r["scan3"])
            n_12 = sum(1 for r in results if r["scan1"] and r["scan2"])
            n_13 = sum(1 for r in results if r["scan1"] and r["scan3"])
            n_23 = sum(1 for r in results if r["scan2"] and r["scan3"])
            n_all= sum(1 for r in results if r["scan1"] and r["scan2"] and r["scan3"])

            c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
            c1.metric("🔵 S1",      n_s1,  "Low Vol")
            c2.metric("🟡 S2",      n_s2,  "Pivot")
            c3.metric("🟣 S3",      n_s3,  "Inside")
            c4.metric("S1+S2",      n_12)
            c5.metric("S1+S3",      n_13)
            c6.metric("S2+S3",      n_23)
            c7.metric("🏆 All 3",   n_all, "Best")

            st.markdown("---")

            # ── Scan filter UI ────────────────────────────────────────────
            st.markdown(
                "<div style='color:#e8f4fd;font-weight:600;font-size:13px;"
                "margin-bottom:10px'>🎛️ Filter — choose which scans to include:</div>",
                unsafe_allow_html=True
            )

            fc1, fc2, fc3, fc4, fc5 = st.columns([2,2,2,2,3])
            with fc1:
                use_s1 = st.checkbox("🔵 Scan 1 — Low Vol",   value=True,  key="f_s1")
            with fc2:
                use_s2 = st.checkbox("🟡 Scan 2 — Pivot",     value=True,  key="f_s2")
            with fc3:
                use_s3 = st.checkbox("🟣 Scan 3 — Inside Day", value=True, key="f_s3")
            with fc4:
                logic = st.radio("Logic", ["OR — any selected", "AND — all selected"],
                                 key="f_logic", horizontal=False)
            with fc5:
                st.markdown(
                    "<div style='background:#0d1520;border:1px solid #1e3a5f;"
                    "border-radius:6px;padding:8px 12px;font-size:11px;color:#6b8cad'>"
                    "<b>OR</b> = show stocks passing <i>at least one</i> selected scan<br>"
                    "<b>AND</b> = show stocks passing <i>all</i> selected scans"
                    "</div>",
                    unsafe_allow_html=True
                )

            use_and = "AND" in logic
            selected = []
            if use_s1: selected.append("scan1")
            if use_s2: selected.append("scan2")
            if use_s3: selected.append("scan3")

            if not selected:
                st.warning("Select at least one scan above.")
            else:
                # Filter results based on selected scans and logic
                if use_and:
                    # AND: stock must pass ALL selected scans
                    filtered = [r for r in results if all(r.get(s) for s in selected)]
                    filter_desc = " AND ".join([
                        "Low Vol" if s=="scan1" else "Pivot" if s=="scan2" else "Inside Day"
                        for s in selected
                    ])
                else:
                    # OR: stock must pass AT LEAST ONE selected scan
                    filtered = [r for r in results if any(r.get(s) for s in selected)]
                    filter_desc = " OR ".join([
                        "Low Vol" if s=="scan1" else "Pivot" if s=="scan2" else "Inside Day"
                        for s in selected
                    ])

                # Sort: RS Rating desc, then closest to 52W high
                filtered_sorted = sorted(
                    filtered,
                    key=lambda x: (-(x.get("RS Rating") or 0), x.get("high_diff") or 99)
                )

                st.markdown("<br>", unsafe_allow_html=True)

                # Result header
                mode_color = "#27ae60" if use_and else "#3498db"
                st.markdown(
                    f"<div style='background:#0a0e1a;border-left:4px solid {mode_color};"
                    f"padding:10px 16px;border-radius:0 6px 6px 0;margin-bottom:12px'>"
                    f"<span style='color:{mode_color};font-weight:700;font-size:14px'>"
                    f"{'🏆' if use_and else '🔍'} {filter_desc}</span>"
                    f"<span style='color:#6b8cad;font-size:12px;margin-left:12px'>"
                    f"{'Must pass all selected scans' if use_and else 'Passes at least one selected scan'}"
                    f"</span>"
                    f"<span style='background:{mode_color}22;color:{mode_color};"
                    f"font-family:DM Mono;font-size:13px;font-weight:700;"
                    f"padding:3px 10px;border-radius:4px;float:right'>"
                    f"{len(filtered_sorted)} stocks</span></div>",
                    unsafe_allow_html=True
                )

                if not filtered_sorted:
                    st.info("No stocks match the current filter. Try OR logic or select more scans.")
                else:
                    # Download
                    rows_dl = []
                    for r in filtered_sorted:
                        rows_dl.append({
                            "Ticker":r["ticker"],"Company":r.get("Company",""),
                            "Industry":r.get("Industry",""),"Sector":r.get("Sector",""),
                            "Price":r["price"],"Pivot High":r["pivot_high"],
                            "RS Rating":r.get("RS Rating",""),"MA50":r.get("MA50",""),
                            "Day1 Range %":r["range_d1"],"Day2 Range %":r["range_d2"],
                            "High Diff %":r["high_diff"],
                            "Inside Margin %":r.get("inside_margin",""),
                            "S1 LowVol":"✅" if r["scan1"] else "❌",
                            "S2 Pivot": "✅" if r["scan2"] else "❌",
                            "S3 Inside":"✅" if r["scan3"] else "❌",
                        })
                    df_dl = pd.DataFrame(rows_dl)
                    st.download_button(
                        f"📥 Download {len(filtered_sorted)} stocks (Excel)",
                        to_excel_bytes({"Filtered Results": df_dl, "All Scan Results": pd.DataFrame([
                            {"Ticker":r["ticker"],"S1":r["scan1"],"S2":r["scan2"],"S3":r["scan3"]}
                            for r in results
                        ])}),
                        "setup_scan_filtered.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_filtered"
                    )

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Charts grid
                    cols = st.columns(charts_per_row)
                    for i, r in enumerate(filtered_sorted):
                        with cols[i % charts_per_row]:
                            rs  = r.get("RS Rating")
                            ind = r.get("Industry", "")
                            fig = mini_candle_chart(r, industry=ind, rs=rs,
                                                   vol_thresh=vol_thresh,
                                                   pivot_thresh=pivot_thresh)
                            st.plotly_chart(fig, use_container_width=True)

                            tv_url = f"https://www.tradingview.com/chart/?symbol={r['ticker']}"
                            s1_txt = f"<span style='color:#3498db'>S1:{r['range_d1']:.1f}/{r['range_d2']:.1f}%</span>" if r["scan1"] else ""
                            s2_txt = f"<span style='color:#f39c12'>S2:Δ{r['high_diff']:.2f}%</span>" if r["scan2"] else ""
                            s3_txt = f"<span style='color:#9b59b6'>S3:inside</span>" if r["scan3"] else ""
                            ma50   = r.get("MA50")
                            ma_txt = f"<span style='color:#6b8cad'>MA50:${ma50:.2f}</span>" if ma50 else ""
                            st.markdown(
                                f"<div style='font-family:DM Mono;font-size:10px;padding:2px 0 8px 0;"
                                f"display:flex;gap:8px;flex-wrap:wrap;align-items:center'>"
                                f"{s1_txt} {s2_txt} {s3_txt} {ma_txt}"
                                f"<a href='{tv_url}' target='_blank' style='color:#1a73e8;"
                                f"text-decoration:none;margin-left:auto'>📈 TV</a>"
                                f"</div>",
                                unsafe_allow_html=True
                            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — SECTOR ROTATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_rot:
    st.markdown('<div class="section-header">Sector Rotation — 3M vs 1M Performance</div>',
                unsafe_allow_html=True)

    view = st.radio("View",["Sectors","Themes","Finviz Industries"],horizontal=True)
    df_rot = {"Sectors":df_sec,"Themes":df_th,"Finviz Industries":df_fv}[view]

    if not df_rot.empty:
        st.plotly_chart(scatter_rotation(df_rot),use_container_width=True)
        st.markdown("""
        <div style='color:#6b8cad;font-size:12px;padding:8px'>
        <b style='color:#27ae60'>▲ LEADING</b> — both 3M and 1M positive (upper right) &nbsp;|&nbsp;
        <b style='color:#3498db'>↗ IMPROVING</b> — 3M negative but 1M turning positive (upper left) &nbsp;|&nbsp;
        <b style='color:#e67e22'>↘ FADING</b> — 3M positive but 1M turning negative (lower right) &nbsp;|&nbsp;
        <b style='color:#e74c3c'>▼ LAGGING</b> — both negative (lower left)
        </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — 52W HEATMAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_hw:
    st.markdown('<div class="section-header">52-Week High/Low Heatmap</div>',unsafe_allow_html=True)

    view2 = st.radio("View",["Sectors","Themes"],horizontal=True,key="hw_view")
    df_hw = {"Sectors":df_sec,"Themes":df_th}[view2]

    if not df_hw.empty:
        st.plotly_chart(heatmap_52w(df_hw),use_container_width=True)

        # Also show table
        display = df_hw.copy()
        display = display[["Name","Ticker","Price","% off High","1D %","1M %","RS Rating"]].copy()
        display["Price"] = display["Price"].apply(lambda x:f"${x:.2f}")
        display["% off High"]=display["% off High"].apply(lambda x:f"{x:+.1f}%")
        for col in ["1D %","1M %"]:
            display[col]=display[col].apply(lambda x:f"{x:+.2f}%" if pd.notna(x) else "—")
        display = display.sort_values("% off High",ascending=False)
        st.dataframe(display,use_container_width=True,height=350)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.markdown('<div class="section-header">Historical Snapshots — Compare Rankings Over Time</div>',
                unsafe_allow_html=True)

    # Save current snapshot
    if st.button("💾 Save Today's Snapshot"):
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not df_th.empty:
            snap = df_th[["Name","1D %","1W %","1M %","3M %","Composite"]].copy()
            snap.columns = [c if c=="Name" else f"{c} ({today})" for c in snap.columns]
            st.session_state.history[today] = df_th[["Name","Composite"]].set_index("Name")["Composite"].to_dict()
            st.success(f"Snapshot saved for {today}")

    if len(st.session_state.history) >= 2:
        dates = sorted(st.session_state.history.keys())
        c1,c2 = st.columns(2)
        with c1: d1 = st.selectbox("Compare from", dates, index=0)
        with c2: d2 = st.selectbox("Compare to",   dates, index=len(dates)-1)

        s1 = st.session_state.history[d1]
        s2 = st.session_state.history[d2]
        common = set(s1.keys()) & set(s2.keys())
        changes = []
        for name in common:
            diff = (s2[name] - s1[name]) * 100
            changes.append({"Theme":name,
                            f"Score {d1[:10]}":f"{s1[name]*100:+.1f}%",
                            f"Score {d2[:10]}":f"{s2[name]*100:+.1f}%",
                            "Change":f"{diff:+.1f}%",
                            "_diff":diff})
        if changes:
            df_chg = pd.DataFrame(changes).sort_values("_diff",ascending=False)
            st.dataframe(df_chg.drop(columns=["_diff"]),use_container_width=True,height=500)
            st.download_button("📥 Download Comparison",
                               to_excel_bytes({"Comparison":df_chg.drop(columns=["_diff"])}),
                               "history_comparison.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Save at least 2 snapshots to compare rankings over time. "
                "Come back tomorrow and save another to see what changed!")
        if st.session_state.history:
            st.markdown(f"**Saved snapshots:** {', '.join(st.session_state.history.keys())}")
