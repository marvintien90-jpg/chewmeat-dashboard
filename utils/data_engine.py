"""
嗑肉石鍋 數位總部 — 資料引擎模組
解決各表單店名不統一問題（例：「台一店」vs「台一旗艦店」vs「台一」）。
使用模糊比對自動對齊，降低人工維護成本。
"""
from __future__ import annotations

import pandas as pd
from fuzzywuzzy import fuzz, process


def fuzzy_match_store(
    input_name: str,
    canonical_list: list[str],
    score_threshold: int = 75,
) -> tuple[str | None, int]:
    """
    將輸入店名與標準店名清單做模糊比對。
    - input_name: 待比對的店名（可能拼法不一）
    - canonical_list: 標準店名清單（來自主要資料表）
    - score_threshold: 相似度門檻（0-100，預設 75）
    回傳 (最佳比對店名 或 None, 相似度分數)
    """
    if not input_name or not canonical_list:
        return None, 0

    best, score = process.extractOne(
        input_name, canonical_list,
        scorer=fuzz.token_sort_ratio,
    )
    if score >= score_threshold:
        return best, score
    return None, score


def normalize_store_names(
    df: pd.DataFrame,
    store_col: str,
    canonical_list: list[str],
    score_threshold: int = 75,
    new_col: str = "標準店名",
) -> pd.DataFrame:
    """
    對 DataFrame 中的店名欄位批次標準化。
    新增「標準店名」欄，比對失敗時保留原始店名。
    並附加「比對分數」欄，方便人工審核低信心比對結果。
    """
    df = df.copy()
    matched_names = []
    matched_scores = []

    for name in df[store_col]:
        best, score = fuzzy_match_store(str(name), canonical_list, score_threshold)
        matched_names.append(best if best else name)
        matched_scores.append(score)

    df[new_col] = matched_names
    df["比對分數"] = matched_scores
    return df


def fuzzy_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_on: str,
    right_on: str,
    score_threshold: int = 75,
    how: str = "left",
) -> pd.DataFrame:
    """
    以模糊比對店名作為 JOIN Key，合併兩個 DataFrame。
    適用於：將客評 CSV 的門店名稱對應到營收表的標準店名。

    - left/right: 兩個 DataFrame
    - left_on/right_on: 各自的店名欄位名稱
    - score_threshold: 相似度門檻（建議 70-85）
    - how: join 方式（left / inner / outer）
    """
    canonical_list = right[right_on].dropna().unique().tolist()

    left_copy = normalize_store_names(
        left, left_on, canonical_list, score_threshold, new_col="_matched_key"
    )
    right_copy = right.copy()
    right_copy["_matched_key"] = right_copy[right_on]

    merged = left_copy.merge(right_copy, on="_matched_key", how=how, suffixes=("", "_right"))
    merged = merged.drop(columns=["_matched_key", "比對分數"], errors="ignore")
    return merged


def build_store_alias_table(
    alias_names: list[str],
    canonical_list: list[str],
    score_threshold: int = 75,
) -> pd.DataFrame:
    """
    產生「別名對照表」，供人工審核或匯出備查。
    回傳 DataFrame：別名 | 標準店名 | 相似度分數 | 需人工確認
    """
    rows = []
    for alias in alias_names:
        best, score = fuzzy_match_store(alias, canonical_list, score_threshold)
        rows.append({
            "原始名稱": alias,
            "建議標準店名": best if best else "未找到對應",
            "相似度": score,
            "需人工確認": score < score_threshold or best is None,
        })
    return pd.DataFrame(rows)
