import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("KEIRIN.JPのオッズ画面のテキストを貼り付けるだけで、全組を完璧に解析・計算します！")

st.markdown("---")
st.subheader("📊 オッズテキストの貼り付け")
st.markdown("""
**【使い方】**
1. KEIRIN.JPの三連単オッズ画面を開く。
2. 画面上のテキストをすべて選択してコピーする。
3. 下の入力欄にそのままペースト（貼り付け）する。
""")

pasted_text = st.text_area("オッズテキストをここに貼り付け", value="", height=180, placeholder="ここにコピーしたテキストを貼り付けてください...")

if not pasted_text.strip():
    st.info("💡 上のテキストエリアにオッズ画面のテキストを貼り付けてください。")
    st.stop()

# --- 完全順序解析ロジック ---
# 1. テキスト内に出現する車番（1〜9）を自動検出
detected_cars = sorted(list(set([int(m) for m in re.findall(r'\b([1-9])\b', pasted_text) if 1 <= int(m) <= 9])))
# 通常は1〜9の9車立て（または7車など）
cars = [c for c in range(1, 10) if str(c) in pasted_text]
if len(cars) < 3:
    cars = [1, 2, 3, 4, 5, 6, 7, 8, 9] # フォールバック

# 3連単の標準的な並び順（昇順）で組み合わせを生成する関数
def get_combinations(first_car, all_cars):
    combs = []
    other_cars = [c for c in all_cars if c != first_car]
    for c2 in other_cars:
        for c3 in other_cars:
            if c2 != c3:
                combs.append((first_car, c2, c3))
    return combs

# 2. テキストから「小数点を含むオッズ数値」を順番通りにすべて抽出
all_odds_raw = re.findall(r'(\d{1,5}\.\d+)', pasted_text)

records = []
odds_idx = 0

# 3. 各1着車番ごとに、正しい組み合わせの順番でオッズを順番に割り当て
for first_car in cars:
    combs = get_combinations(first_car, cars)
    for c1, c2, c3 in combs:
        if odds_idx < len(all_odds_raw):
            try:
                odds_val = float(all_odds_raw[odds_idx])
                # 異常値（売っていない組合せの9999.9等）を除外
                if 1.0 <= odds_val < 99998:
                    records.append({"first": c1, "second": c2, "third": c3, "odds": odds_val})
            except ValueError:
                pass
            odds_idx += 1

# 重複除去
unique_records = {}
for r in records:
    key = f"{r['first']}-{r['second']}-{r['third']}"
    unique_records[key] = r

final_records = list(unique_records.values())

if not final_records:
    st.error("オッズデータを自動検出できませんでした。テキスト全体が正しくコピーされているか確認してください。")
    st.stop()

st.success(f"データ解析成功！ （検出データ: {len(final_records)} 組 / 出走車番: {len(cars)}台）")

# --- 擬似単勝オッズ計算 ---
pseudo_odds_map = {}

for car in cars:
    car_records = [r for r in final_records if r["first"] == car]
    if not car_records:
        continue
    
    inv_sum = sum(1.0 / r["odds"] for r in car_records if r["odds"] > 0)
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

# --- 2. 全車番一覧の表示 ---
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
