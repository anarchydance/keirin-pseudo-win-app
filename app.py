import streamlit as st
import re
import pandas as pd
import math

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("オッズ画面のテキストから擬似単勝とワイド9点の資金配分を自動計算します！")

st.markdown("---")

# --- 出走車番数の選択 ---
col_car1, col_car2 = st.columns([1, 1])
with col_car1:
    car_count_mode = st.radio("出走車番の数を選択", [9, 8, 7], index=1, horizontal=True)

st.subheader("📊 オッズテキストの貼り付け")
pasted_text = st.text_area("オッズテキストをここに貼り付け", value="", height=140, placeholder="ここにコピーしたテキストを貼り付けてください...")

if not pasted_text.strip():
    st.info("💡 上のテキストエリアにオッズ画面のテキストを貼り付けてください。")
    st.stop()

cars = list(range(1, car_count_mode + 1))

def get_combinations(first_car, all_cars):
    combs = []
    other_cars = [c for c in all_cars if c != first_car]
    for c2 in other_cars:
        for c3 in other_cars:
            if c2 != c3:
                combs.append((first_car, c2, c3))
    return combs

all_odds_raw = re.findall(r'(\d{1,5}\.\d+)', pasted_text)

records = []
odds_idx = 0

for first_car in cars:
    combs = get_combinations(first_car, cars)
    for c1, c2, c3 in combs:
        if odds_idx < len(all_odds_raw):
            try:
                odds_val = float(all_odds_raw[odds_idx])
                records.append({"first": c1, "second": c2, "third": c3, "odds": odds_val})
            except ValueError:
                pass
            odds_idx += 1

if not records:
    st.error("オッズデータを自動検出できませんでした。テキスト全体が正しくコピーされているか確認してください。")
    st.stop()

st.success(f"データ解析成功！ （検出データ: {len(records)} 組 / 設定: {car_count_mode}車立て）")

# --- 擬似単勝オッズ計算 ---
pseudo_odds_map = {}
for car in cars:
    car_records = [r for r in records if r["first"] == car]
    if not car_records:
        continue
    valid_odds = [r["odds"] for r in car_records if 0 < r["odds"] < 9998]
    if valid_odds:
        inv_sum = sum(1.0 / odds for odds in valid_odds)
        if inv_sum > 0:
            pseudo_odds_map[car] = round(1.0 / inv_sum, 1)

if not pseudo_odds_map:
    st.warning("計算できるデータがありませんでした。")
    st.stop()

# 人気順位・支持率の計算
sorted_cars = sorted(pseudo_odds_map.items(), key=lambda x: x[1])
rank_map = {car: idx for idx, (car, odds) in enumerate(sorted_cars, 1)}

inv_totals = {car: 1.0 / odds for car, odds in pseudo_odds_map.items()}
total_inv = sum(inv_totals.values())
support_rates = {car: (inv / total_inv) * 100 for car, inv in inv_totals.items()}

# --- 1. 指定人気順位の表示 (2, 5, 6, 7, 9番人気) ---
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

# --- 2. ワイド9点 資金配分シミュレーター ---
st.markdown("---")
st.markdown("### 💰 ワイド9点 資金配分計算")
st.caption("2人気・5人気・6人気・7人気・9人気（6人気-9人気除外の9点）の資金配分")

total_budget = st.number_input("全体購入金額 (円)", min_value=900, max_value=100000, value=3000, step=100)

# ワイド9点のペアリスト（人気順位ペア）
wide_pairs = [
    (2, 5), (2, 6), (2, 7), (2, 9),
    (5, 6), (5, 7), (5, 9),
    (6, 7),
    (7, 9)
    # (6, 9) は除外
]

allocations = []
valid_pairs = []

for r1, r2 in wide_pairs:
    c1 = rank_to_car.get(r1)
    c2 = rank_to_car.get(r2)
    if c1 is not None and c2 is not None:
        # 擬似単勝の支持率の積からワイド推定オッズ（近似）を算出
        p1 = support_rates.get(c1, 0) / 100.0
        p2 = support_rates.get(c2, 0) / 100.0
        est_prob = p1 * p2 * 3.0 # ワイドの重複調整係数
        est_odds = max(1.1, round(1.0 / est_prob, 1)) if est_prob > 0 else 10.0
        
        valid_pairs.append({
            "pair_str": f"{c1} - {c2}",
            "ranks_str": f"{r1}人気 - {r2}人気",
            "est_odds": est_odds
        })

if valid_pairs:
    # 各オッズの逆数和（合成オッズ用）
    inv_odds_sum = sum(1.0 / item["est_odds"] for item in valid_pairs)
    
    alloc_table = []
    total_calc_spend = 0
    
    for item in valid_pairs:
        # 資金配分の基本計算 (100円単位で四捨五入/繰り上げ)
        raw_alloc = (total_budget / item["est_odds"]) / inv_odds_sum
        alloc_100 = max(100, int(round(raw_alloc / 100.0) * 100))
        est_return = int(alloc_100 * item["est_odds"])
        
        total_calc_spend += alloc_100
        alloc_table.append({
            "買い目 (車番)": item["pair_str"],
            "組み合わせ": item["ranks_str"],
            "推定オッズ": f"{item['est_odds']:.1f}倍",
            "購入金額": f"{alloc_100:,}円",
            "的中時想定払戻": f"{est_return:,}円"
        })
    
    df_alloc = pd.DataFrame(alloc_table)
    st.table(df_alloc)
    st.info(f"💡 合計購入確定額: **{total_calc_spend:,}円** （各点数最低100円以上・100円単位自動調整済み）")

# --- 3. 全車番一覧 ---
st.markdown("---")
st.markdown("### 📋 全車番の擬似単勝オッズ一覧")
full_data = []
for car, rank in sorted(rank_map.items(), key=lambda x: x[1]):
    full_data.append({
        "順位": f"{rank}位",
        "車番": f"{car}番车",
        "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
        "支持率目安": f"{support_rates[car]:.1f}%"
    })

df_full = pd.DataFrame(full_data)
st.dataframe(df_full, use_container_width=True, hide_index=True)
