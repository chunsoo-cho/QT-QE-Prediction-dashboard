import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import pandas_datareader as pdr

# ---------------------------------------------------------
# 1. 페이지 설정 및 제목
# ---------------------------------------------------------
st.set_page_config(page_title="Market Strategic Dashboard", layout="wide")
st.title("📊 시장 전략 대시보드 (Market Strategy Dashboard)")
st.markdown("---")

# ---------------------------------------------------------
# 2. 데이터 수집 함수 (캐싱 적용으로 속도 향상)
# ---------------------------------------------------------
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_market_data():
    with st.spinner('최신 시장 데이터를 불러오는 중입니다...'):
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365*2)

        # FRED 데이터
        fred_tickers = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'SOFR', 'IORB', 'T10Y2Y']
        try:
            df_fred = pdr.get_data_fred(fred_tickers, start_date, end_date)
        except:
            st.error("FRED 데이터 수집 실패. 잠시 후 다시 시도해주세요.")
            return None

        # Yahoo Finance 데이터
        yf_tickers = ['^GSPC', '^VIX', '^MOVE']
        df_yf = yf.download(yf_tickers, start=start_date, end=end_date, progress=False)['Close']

        # 데이터 병합 및 전처리
        df = pd.concat([df_fred, df_yf], axis=1)
        df = df.resample('D').mean().fillna(method='ffill').dropna()
        
        # 지표 계산
        # Net Liquidity (단위: 조 달러)
        df['Net_Liquidity'] = (df['WALCL']/1000000) - (df['WTREGEN']/1000) - (df['RRPONTSYD']/1000)
        # System Health (Spread)
        df['Rate_Spread'] = df['SOFR'] - df['IORB']
        # MA
        df['Liq_MA20'] = df['Net_Liquidity'].rolling(window=20).mean()
        
        return df

df = get_market_data()

if df is not None:
    last = df.iloc[-1]
    prev = df.iloc[-5] # 5일 전 비교

    # ---------------------------------------------------------
    # 3. 대시보드 UI 구성
    # ---------------------------------------------------------

    # [Part A] 유동성 (Liquidity)
    st.header("1. ⛽ 시장 유동성 (Fuel)")
    st.info("💡 **설명:** 연준(Fed)이 시장에 공급한 '진짜 현금'의 양입니다. 이 선이 올라가야 주식이 오를 힘이 생깁니다.")
    
    col1, col2, col3 = st.columns(3)
    liq_diff = last['Net_Liquidity'] - prev['Net_Liquidity']
    col1.metric("순유동성 (Net Liquidity)", f"${last['Net_Liquidity']:.3f} T", f"{liq_diff:.3f} T")
    col2.metric("TGA (정부 지갑)", f"${last['WTREGEN']/1000:.3f} T")
    col3.metric("RRP (연준 파킹)", f"${last['RRPONTSYD']/1000:.3f} T")

    fig_liq = make_subplots(specs=[[{"secondary_y": True}]])
    fig_liq.add_trace(go.Scatter(x=df.index, y=df['Net_Liquidity'], name="유동성", line=dict(color='#00ff00', width=2), fill='tozeroy', opacity=0.1), secondary_y=False)
    fig_liq.add_trace(go.Scatter(x=df.index, y=df['^GSPC'], name="S&P500", line=dict(color='white', width=1)), secondary_y=True)
    fig_liq.update_layout(title="유동성 vs S&P500", height=400, template="plotly_dark")
    st.plotly_chart(fig_liq, use_container_width=True)

    st.markdown("---")

    # [Part B] 건전성 (Health)
    st.header("2. 🏥 금융 시스템 건전성 (Health)")
    
    # 🟢 일반인용 설명 추가
    with st.expander("❓ 이게 무슨 지표인가요? (클릭해서 보기)", expanded=True):
        st.markdown("""
        * **무엇을 보나요?**: 은행들끼리 돈을 빌릴 때의 금리(SOFR)가 정상인지 봅니다.
        * **쉽게 말하면**: 사람의 '혈압'과 같습니다. 
        * **위험 신호**: 막대그래프가 **빨간 점선(0.05%)**을 뚫고 올라가면 **'돈맥경화(자금 경색)'**가 왔다는 뜻입니다. 이때는 주식을 다 팔고 도망쳐야 합니다.
        """)

    spread_val = last['Rate_Spread']
    status_msg = "정상 (Normal) ✅"
    status_color = "off"
    if spread_val >= 0.05:
        status_msg = "🚨 위험 (CRITICAL) - 현금화 필요"
        status_color = "inverse"
    elif spread_val > 0:
        status_msg = "주의 (Warning) ⚠️"
        status_color = "normal"
        
    st.metric("SOFR - IORB 스프레드", f"{spread_val:.3f} %", delta_color=status_color, help="0.05% 이상이면 위험")
    st.caption(f"현재 상태: **{status_msg}**")

    # 색상 로직
    colors = np.where(df['Rate_Spread'] >= 0.05, 'red', np.where(df['Rate_Spread'] > 0, 'yellow', 'green'))
    
    fig_health = go.Figure()
    fig_health.add_trace(go.Bar(x=df.index, y=df['Rate_Spread'], marker_color=colors, name="Spread"))
    fig_health.add_hline(y=0.05, line_dash="dot", line_color="red", annotation_text="위험 기준선(0.05%)")
    fig_health.update_layout(title="시스템 스트레스 지수", height=300, template="plotly_dark")
    st.plotly_chart(fig_health, use_container_width=True)

    st.markdown("---")

    # [Part C] 투자 심리 (Sentiment)
    st.header("3. 😨 투자 심리 (Sentiment)")

    # 🟢 일반인용 설명 추가
    with st.expander("❓ 이게 무슨 지표인가요? (클릭해서 보기)", expanded=True):
        st.markdown("""
        * **무엇을 보나요?**: 시장 참여자들이 얼마나 겁을 먹었는지(VIX) 봅니다.
        * **쉽게 말하면**: **'공포 지수'**입니다. 
        * **판단 기준**:
            * **20 이하**: 시장이 평온합니다. (매수/홀딩)
            * **30 이상**: 패닉 상태입니다. (시스템이 정상이면 오히려 저점 매수 기회)
        """)

    vix_val = last['^VIX']
    move_val = last['^MOVE']
    
    col_c1, col_c2 = st.columns(2)
    col_c1.metric("VIX (주식 공포)", f"{vix_val:.2f}")
    col_c2.metric("MOVE (채권 공포)", f"{move_val:.2f}")

    fig_sent = make_subplots(specs=[[{"secondary_y": True}]])
    fig_sent.add_trace(go.Scatter(x=df.index, y=df['^VIX'], name="VIX", line=dict(color='orange')), secondary_y=False)
    fig_sent.add_trace(go.Scatter(x=df.index, y=df['^MOVE'], name="MOVE", line=dict(color='cyan', dash='dot')), secondary_y=True)
    fig_sent.add_hline(y=20, line_dash="dot", line_color="white", annotation_text="심리적 경계선")
    fig_sent.update_layout(title="공포 지수 추이 (VIX vs MOVE)", height=350, template="plotly_dark")
    st.plotly_chart(fig_sent, use_container_width=True)

    # ---------------------------------------------------------
    # 4. AI 최종 제안
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🤖 AI 전략 제안")
    
    final_action = "🚀 관망 / 홀딩 (Hold)"
    reason = "특이 사항 없음"
    
    if spread_val >= 0.05:
        final_action = "🚨 [비상] 전량 현금화 (System Risk)"
        reason = "금융 시스템 내 자금 경색 감지됨"
        st.error(f"결론: {final_action}")
        st.error(f"이유: {reason}")
    elif vix_val >= 25 and liq_diff > 0:
        final_action = "💎 [기회] 공포에 매수 (Buy the Dip)"
        reason = "유동성은 좋은데 심리만 위축됨 (펀더멘털 양호)"
        st.success(f"결론: {final_action}")
        st.info(f"이유: {reason}")
    else:
        st.info(f"결론: **{final_action}**")
