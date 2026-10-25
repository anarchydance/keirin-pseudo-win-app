import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("KEIRIN.JPの三連単オッズ画面のテキストをコピペするだけで自動計算！")

st.markdown("---")
st.subheader("📊 オッズテキストの貼り付け")
st.markdown("""
**【使い方】**
1. KEIRIN.JPの三連単オッズ画面を開く。
2. 画面上のテキストを**長押しで全選択（すべて選択）**して**コピー**する。
3. 下の入力欄にそのまま**ペースト（貼り付け）**する。
""")

pasted_text = st.text_area("オッズテキストをここに貼り付け", value="", height=150, placeholder="画面のテキストをすべてコピーしてここに貼ってください...")

if not pasted_text.strip():
    st.info("💡 上のテキストエリアにKEIRIN.JPのオッズテキストを貼り付けてください。")
    st.stop()

# --- テキスト解析処理 ---
lines = [line.strip() for line in pasted_text.splitlines() if line.strip()]

records = []
current_first = None

# テキストを行ごとに解析
for i, line in enumerate(lines):
    # 1着の見出し（「1番車」「1着」などの検出）
    m_first = re.search(r'^([1-9])\s*(?:番車|着)?$', line)
    if m_first and ("番車" in line or "全選択" in line or (i + 1 < len(lines) and "番車" in lines[i+1])):
        current_first = int(m_first.group(1))
        continue

    # 1-2-3 12.3 や 1-2 3.4 などのパターン抽出
    # 車番組合せ + オッズの正規表現
    m_comb = re.search(r'([1-9])\s*[-=＝→>]\s*([1-9])\s*[-=＝→>]\s*([1-9])\s+([0-9]+(?:\.[0-9]+)?)', line)
    if m_comb:
        c1, c2, c3, odds_str = int(m_comb.group(1)), int(m_comb.group(2)), int(m_comb.group(3)), float(m_comb.group(4))
        if len({c1, c2, c3}) == 3 and odds_str > 0:
            records.append({"first": c1, "second": c2, "third": c3, "odds": odds_str})
        continue

    # テーブル形式（2着車番、3着車番、オッズが連なる形式）の汎用解析
    # 数字とオッズ（例: 2 3 15.4）
    parts = line.split()
    if len(parts) >= 2:
        try:
            # 2着 3着 オッズ の形
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                c2, c3 = int(parts[0]), int(parts[1])
                odds_val = float(parts[2].replace(",", "").replace("倍", ""))
                if current_first and len({current_first, c2, c3}) == 3 and odds_val > 0:
                    records.append({"first": current_first, "second": c2, "third": c3, "odds": odds_val})
            # 2着/3着 オッズ の形
            elif len(parts) == 2 and parts[0].isdigit():
                odds_val = float(parts[1].replace(",", "").replace("倍", ""))
                # 直前や文脈から補正
                pass
        except ValueError:
            pass

# 重複除去
unique_records = {}
for r in records:
    key = f"{r['first']}-{r['second']}-{r['third']}"
    unique_records[key] = r

final_records = list(unique_records.values())

if not final_records:
    st.error("オッズデータを自動検出できませんでした。KEIRIN.JPの三連単オッズ画面全体のテキストをそのままコピーして貼り付けてみてください。")
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
