import streamlit as st
import json
import base64
import pandas as pd

st.set_page_config(page_title="擬似単勝オッズアプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")

st.markdown("---")
st.subheader("📊 データ入力")
st.markdown("KEIRIN.JPのオッズ画面でブックマークレットを実行し、コピーしたデータを下の枠内に貼り付けてください。")

pasted_data = st.text_area("ここにデータをペースト（貼り付け）", value="", height=100)

if not pasted_data.strip():
    st.info("💡 ブックマークレットで取得したデータをここに貼り付けてください。")
    st.stop()

try:
    normalized = pasted_data.strip().replace("-", "+").replace("_", "/")
    padded = normalized + "=" * (-len(normalized) % 4)
    json_bytes = base64.b64decode(padded)
    payload = json.loads(json_bytes.decode("utf-8"))
    
    records = payload.get("records", [])
    cars = payload.get("car_numbers", [])
    
    if not records:
        st.error("有効なオッズデータが見つかりませんでした。")
        st.stop()
        
except Exception as e:
    st.error(f"データの読み込みに失敗しました（データ形式が正しくありません）: {e}")
    st.stop()

st.success(f"データ読込成功！ （総データ数: {len(records)} 組）")

# --- 擬似単勝オッズの計算ロジック ---
pseudo_odds_map = {}

for car in cars:
    car_records = [r for r in records if r["first"] == car]
    if not car_records:
        continue
    
    inv_sum = sum(1.0 / r["odds"] for r in car_records if r["odds"] > 0)
    if inv_sum > 0:
        pseudo_odds_map[car] = round(1.0 / inv_sum, 1)

if not pseudo_odds_map:
    st.warning("計算できるデータがありませんでした。")
    st.stop()

# 人気順位の算出
sorted_cars = sorted(pseudo_odds_map.items(), key=lambda x: x[1])
rank_map = {car: idx for idx, (car, odds) in enumerate(sorted_cars, 1)}

# 支持率の目安
inv_totals = {car: 1.0 / odds for car, odds in pseudo_odds_map.items()}
total_inv = sum(inv_totals.values())
support_rates = {car: (inv / total_inv) * 100 for car, inv in inv_totals.items()}

# --- 指定順位の抽出 ---
target_ranks = [2, 5, 6, 7, 9]
rank_to_car = {rank: car for car, rank in rank_map.items()}

st.markdown("### 🎯 指定人気順位の車番")

result_data = []
for r_target in target_ranks:
    car = rank_to_car.get(r_target)
    if car is not None:
        result_data.append({
            "人気順位": f"{r_target}番人気",
            "車番": f"{car}番車",
            "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
            "支持率目安": f"{support_rates[car]:.1f}%"
        })
    else:
        result_data.append({
            "人気順位": f"{r_target}番人気",
            "車番": "該当なし",
            "擬似単勝オッズ": "---",
            "支持率目安": "---"
        })

df_target = pd.DataFrame(result_data)
st.table(df_target)

# --- 全車番の一覧 ---
st.markdown("### 📋 全車番の擬似単勝オッズ一覧")
full_data = []
for car, rank in sorted(rank_map.items(), key=lambda x: x[1]):
    full_data.append({
        "順位": f"{rank}位",
        "車番": f"{car}番車",
        "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
        "支持率目安": f"{support_rates[car]:.1f}%"
    })

df_full = pd.DataFrame(full_data)
st.dataframe(df_full, use_container_width=True, hide_index=True)
