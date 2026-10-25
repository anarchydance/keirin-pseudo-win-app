import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("KEIRIN.JPのオッズ画面のテキストをコピーして貼り付けるだけで、自動で全組を解析・計算します！")

st.markdown("---")
st.subheader("📊 オッズテキストの貼り付け")
st.markdown("""
**【使い方】**
1. KEIRIN.JPの三連単オッズ画面を開く。
2. 画面上のテキストをすべて選択してコピーする（PCなら `Ctrl+A` または `Cmd+A` で全選択してコピーするのがおすすめ）。
3.下の入力欄にそのままペースト（貼り付け）する。
""")

pasted_text = st.text_area("オッズテキストをここに貼り付け", value="", height=180, placeholder="ここにコピーしたテキストを貼り付けてください...")

if not pasted_text.strip():
    st.info("💡 上のテキストエリアにオッズ画面のテキストを貼り付けてください。")
    st.stop()

# --- 強力なマルチパターン・テキスト解析処理 ---
records = []
lines = [line.strip() for line in pasted_text.splitlines() if line.strip()]

# パターン1: 「1-2-3 12.5」や「1 2 3 12.5」など、1行の中に3つの車番とオッズが含まれる形式
pattern_inline = re.compile(
    r'([1-9])\s*[-=＝→>\s]\s*([1-9])\s*[-=＝→>\s]\s*([1-9])\D+?([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]+)?)'
)

for line in lines:
    match = pattern_inline.search(line)
    if match:
        c1, c2, c3 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        odds_str = match.group(4).replace(",", "").replace("倍", "").strip()
        try:
            odds_val = float(odds_str)
            if len({c1, c2, c3}) == 3 and odds_val > 0:
                records.append({"first": c1, "second": c2, "third": c3, "odds": odds_val})
        except ValueError:
            continue

# フォールバック: 表形式などで数字とオッズが離れて並んでいる場合をスマートにスキャン
if len(records) < 20:
    tokens = []
    for line in lines:
        parts = line.split()
        for p in parts:
            p_clean = p.replace(",", "").replace("倍", "")
            if re.match(r'^[1-9]$', p):
                tokens.append({"type": "car", "val": int(p)})
            elif re.match(r'^\d{1,4}\.\d+$', p_clean) or re.match(r'^\d{1,4}$', p_clean):
                try:
                    v = float(p_clean)
                    if v > 0:
                        tokens.append({"type": "odds", "val": v})
                except ValueError:
                    pass
    
    # 「車番, 車番, 車番, オッズ」の並びを検出
    for idx in range(len(tokens) - 3):
        if (tokens[idx]["type"] == "car" and 
            tokens[idx+1]["type"] == "car" and 
            tokens[idx+2]["type"] == "car" and 
            tokens[idx+3]["type"] == "odds"):
            
            c1 = tokens[idx]["val"]
            c2 = tokens[idx+1]["val"]
            c3 = tokens[idx+2]["val"]
            odds_val = tokens[idx+3]["val"]
            
            if len({c1, c2, c3}) == 3:
                records.append({"first": c1, "second": c2, "third": c3, "odds": odds_val})

# 重複除去
unique_records = {}
for r in records:
    key = f"{r['first']}-{r['second']}-{r['third']}"
    unique_records[key] = r

final_records = list(unique_records.values())

if not final_records:
    st.error("オッズデータを自動検出できませんでした。KEIRIN.JPのオッズ画面のテキスト全体をコピーして再度貼り付けてみてください。")
    st.stop()

# 検出車番の整理
cars = sorted(list(set([r["first"] for r in final_records] + [r["second"] for r in final_records] + [r["third"] for r in final_records])))

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
