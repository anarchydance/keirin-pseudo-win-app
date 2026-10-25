import base64
import json
import math
import re
from collections import defaultdict
from typing import Any

import pandas as pd
import streamlit as st

st.set_page_config(page_title="競輪 擬似単勝オッズ", page_icon="🚴", layout="centered")

TARGET_RANKS = [2, 5, 6, 7, 9]


def decode_payload(encoded: str) -> dict[str, Any] | None:
    if not encoded:
        return None
    try:
        # URL-safe and regular Base64 are both accepted.
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        try:
            raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", "").replace("倍", "")
        if not text or text in {"-", "—", "–", "発売なし", "欠測", "N/A", "null"}:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def normalize_records(payload: Any) -> tuple[list[dict[str, Any]], list[int], dict[str, Any]]:
    """Accepts records in the form {first, second, third, odds} or a list of such records."""
    metadata: dict[str, Any] = {}
    records_raw: Any = payload
    car_numbers: list[int] = []
    if isinstance(payload, dict):
        metadata = payload
        records_raw = payload.get("records", payload.get("odds", payload.get("data", [])))
        try:
            car_numbers = sorted({int(x) for x in payload.get("car_numbers", []) if 1 <= int(x) <= 9})
        except Exception:
            car_numbers = []
    if not isinstance(records_raw, list):
        return [], car_numbers, metadata

    dedup: dict[tuple[int, int, int], dict[str, Any]] = {}
    for row in records_raw:
        if not isinstance(row, dict):
            continue
        try:
            first = int(row.get("first", row.get("car1", row.get("a"))))
            second = int(row.get("second", row.get("car2", row.get("b"))))
            third = int(row.get("third", row.get("car3", row.get("c"))))
        except (TypeError, ValueError):
            continue
        odds = to_float(row.get("odds", row.get("value", row.get("price"))))
        if not all(1 <= x <= 9 for x in (first, second, third)):
            continue
        if len({first, second, third}) != 3 or odds is None:
            continue
        dedup[(first, second, third)] = {
            "first": first,
            "second": second,
            "third": third,
            "odds": odds,
        }
    records = list(dedup.values())
    if not car_numbers:
        seen = {x for r in records for x in (r["first"], r["second"], r["third"])}
        if seen:
            # Keirin car numbers are consecutive from 1 in normal races.
            car_numbers = list(range(1, max(seen) + 1))
    return records, car_numbers, metadata


def parse_text(text: str) -> tuple[list[dict[str, Any]], list[int]]:
    """Parse lines such as '1-2-3 12.3', '1,2,3,12.3', or JSON records."""
    raw = (text or "").strip()
    if not raw:
        return [], []
    try:
        obj = json.loads(raw)
        records, cars, _ = normalize_records(obj)
        if records:
            return records, cars
    except Exception:
        pass

    result: dict[tuple[int, int, int], dict[str, Any]] = {}
    patterns = [
        re.compile(r"(?<!\d)([1-9])\s*[-‐‑‒–—−－ー→>]\s*([1-9])\s*[-‐‑‒–—−－ー→>]\s*([1-9])(?!\d)\s*[:：,，\s]+([0-9][0-9,]*(?:\.\d+)?)"),
        re.compile(r"(?<!\d)([1-9])\s*[,，\t ]\s*([1-9])\s*[,，\t ]\s*([1-9])\s*[,，\t ]\s*([0-9][0-9,]*(?:\.\d+)?)(?!\d)"),
    ]
    for line in raw.splitlines():
        line = line.strip()
        for pattern in patterns:
            for match in pattern.finditer(line):
                first, second, third = map(int, match.group(1, 2, 3))
                odds = to_float(match.group(4))
                if odds is not None and len({first, second, third}) == 3:
                    result[(first, second, third)] = {
                        "first": first,
                        "second": second,
                        "third": third,
                        "odds": odds,
                    }
    records = list(result.values())
    seen = {x for r in records for x in (r["first"], r["second"], r["third"])}
    cars = list(range(1, max(seen) + 1)) if seen else []
    return records, cars


def calculate(records: list[dict[str, Any]], car_numbers: list[int]) -> tuple[pd.DataFrame, dict[int, int], int]:
    sums = defaultdict(float)
    counts = defaultdict(int)
    for row in records:
        odds = row["odds"]
        if odds > 0:
            sums[row["first"]] += 1.0 / odds
            counts[row["first"]] += 1

    cars = sorted(set(car_numbers or []))
    if not cars:
        cars = sorted(sums)
    total_support = sum(sums[c] for c in cars)
    expected_per_car = max((len(cars) - 1) * (len(cars) - 2), 0)
    rows = []
    for car in cars:
        support = sums[car]
        pseudo_odds = 1.0 / support if support > 0 else None
        share = (support / total_support * 100.0) if total_support > 0 else 0.0
        rows.append({
            "車番": car,
            "擬似単勝オッズ": pseudo_odds,
            "支持率目安(%)": share,
            "有効組み合わせ数": counts[car],
            "想定組み合わせ数": expected_per_car,
            "取得率(%)": (counts[car] / expected_per_car * 100.0) if expected_per_car else 0.0,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["擬似単勝オッズ", "車番"], na_position="last").reset_index(drop=True)
        df.insert(0, "人気順位", range(1, len(df) + 1))
    return df, dict(counts), expected_per_car


def fmt_odds(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.2f}倍"


st.title("🚴 競輪・擬似単勝オッズ")
st.caption("三連単オッズから、各車番の1着支持の強さを推定します。")

query_payload = None
try:
    query_payload = st.query_params.get("payload", None)
except Exception:
    query_payload = None

payload = decode_payload(query_payload) if query_payload else None
records: list[dict[str, Any]] = []
car_numbers: list[int] = []
metadata: dict[str, Any] = {}
source_kind = "manual"

if payload:
    records, car_numbers, metadata = normalize_records(payload)
    source_kind = "bookmarklet"

with st.expander("計算方法", expanded=False):
    st.markdown(
        "**車番ごとの擬似単勝オッズ** ＝ その車番を1着に固定した三連単の各オッズの逆数を合計し、その合計の逆数を取った値。\n\n"
        "**支持率の目安** ＝ 車番ごとの逆数合計を、全車番の逆数合計に対する割合にした値。\n\n"
        "これは実際の単勝オッズ・1着確率ではなく、三連単オッズから作る比較用の推定値です。オッズが0.0、発売なし、未取得の組み合わせは計算から除外します。"
    )

if payload and records:
    st.success(f"ブックマークレットから {len(records)} 組の三連単オッズを受け取りました。")
    if metadata.get("pageTitle"):
        st.write(f"**取得元:** {metadata['pageTitle']}")
    if metadata.get("sourceUrl"):
        st.caption(f"取得元ページ: {metadata['sourceUrl']}")
else:
    st.subheader("オッズデータの取り込み")
    st.markdown(
        "KEIRIN.JPの三連単オッズ画面でブックマークレットを実行すると、データをこのアプリへ送る設計です。\n\n"
        "うまく読み取れない場合は、下の入力欄に `1-2-3 12.3` の形式で貼り付けても計算できます。1行につき1組です。"
    )
    manual_text = st.text_area(
        "三連単オッズ（手動貼り付け・動作確認用）",
        height=180,
        placeholder="1-2-3 12.3\n1-2-4 25.6\n1-3-2 18.4",
        key="manual_odds_text",
    )
    if st.button("計算する", type="primary", use_container_width=True):
        records, car_numbers = parse_text(manual_text)
        source_kind = "manual"
        if records:
            st.session_state["manual_records"] = records
            st.session_state["manual_cars"] = car_numbers
        else:
            st.session_state.pop("manual_records", None)
            st.error("組み合わせとオッズを読み取れませんでした。例と同じ形式で入力してください。")
    if not records and st.session_state.get("manual_records"):
        records = st.session_state["manual_records"]
        car_numbers = st.session_state.get("manual_cars", [])
        source_kind = "manual"

if records:
    # If the payload missed a car number, infer the usual consecutive numbering.
    if not car_numbers:
        seen = {x for r in records for x in (r["first"], r["second"], r["third"])}
        car_numbers = list(range(1, max(seen) + 1)) if seen else []

    df, counts, expected_per_car = calculate(records, car_numbers)
    if df.empty:
        st.error("計算できるオッズがありません。")
        st.stop()

    total_expected = len(car_numbers) * expected_per_car
    total_valid = len(records)
    st.divider()
    st.subheader("指定人気の一覧")
    target_rows = []
    for rank in TARGET_RANKS:
        hit = df[df["人気順位"] == rank]
        if hit.empty:
            target_rows.append({"指定人気": f"{rank}番人気", "車番": "該当なし", "擬似単勝オッズ": "—", "支持率目安": "—"})
        else:
            row = hit.iloc[0]
            target_rows.append({
                "指定人気": f"{rank}番人気",
                "車番": f"{int(row['車番'])}番車",
                "擬似単勝オッズ": fmt_odds(row["擬似単勝オッズ"]),
                "支持率目安": f"{row['支持率目安(%)']:.2f}%",
            })
    target_df = pd.DataFrame(target_rows)
    st.dataframe(target_df, hide_index=True, use_container_width=True)

    st.subheader("全車番の順位")
    display_df = df.copy()
    display_df["擬似単勝オッズ"] = display_df["擬似単勝オッズ"].map(fmt_odds)
    display_df["支持率目安(%)"] = display_df["支持率目安(%)"].map(lambda x: f"{x:.2f}%")
    display_df["取得率(%)"] = display_df["取得率(%)"].map(lambda x: f"{x:.0f}%")
    display_df = display_df.rename(columns={"有効組み合わせ数": "有効点数", "想定組み合わせ数": "想定点数", "取得率(%)": "取得率"})
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    min_coverage = float(df["取得率(%)"].min()) if not df.empty else 0.0
    if min_coverage < 90:
        st.warning(
            f"一部の組み合わせが未取得または発売なしのため、最も低い取得率は {min_coverage:.0f}% です。"
            "取得状況が車番ごとに異なると、擬似単勝オッズや人気順位に偏りが出る可能性があります。"
        )
    st.caption(f"計算対象: {len(car_numbers)}車立て／取得した有効組み合わせ {total_valid}組。三連単オッズは変動するため、取得時点の値です。")

    csv_df = df.copy()
    csv = csv_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("全車番の計算結果をCSV保存", data=csv, file_name="keirin_pseudo_win_odds.csv", mime="text/csv", use_container_width=True)
else:
    st.info("まだオッズデータがありません。まずKEIRIN.JPで三連単オッズ画面を開き、ブックマークレットを実行してください。")

st.divider()
st.caption("このツールはオッズ比較用です。推定値は的中や利益を保証するものではありません。")
