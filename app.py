import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="WiFi Inventory（Category=WIFI）", layout="wide")

# -------------------------
# WiFi 新品 PLU 清單（原邏輯；未直接使用，保留）
# -------------------------
WIFI_NEW_PLUS = [
    "05H00018","05H00009","05H00039","05H00038","05H00021","05H00026",
    "05H00048","05H00046","05H00055","05H00054","05H00056","05H00064",
    "05H00065","05H00042","05H00040","05H00004","05H00049","05H00053",
    "05H00002","05H00001","05H00050","05H00006","05H00036","05H00005",
    "05H00007","05H00022"
]

# Model 對應
PLU_TO_MODEL = {
    "05H00018": "R500",
    "05H00009": "R510",
    "05H00039": "R350",
    "05H00038": "R550",
    "05H00021": "R730",
    "05H00026": "R750",
    "05H00048": "R770",
    "05H00046": "T350",
    "05H00055": "Huawei AirEngine 5776-57T",
    "05H00054": "Huawei AirEngine 5573-21",
    "05H00056": "Huawei AirEngine 5576I-X6EH",
    "05H00064": "S5535-S24PN4XE-V2(2.5G PoE+)",
    "05H00065": "Wi-Fi 7 SwitchS5335-L8P4X-QA-V2",
    "05H00042": "ARIXOLINK DQ150G",
    "05H00040": "MeiG 5G SRT830",
    "05H00004": "SINGLE PORT, 802.3AF",
    "05H00049": "UK Power Adapter for Ruckus R720, R730",
    "05H00053": "PoE Adapter",
    "05H00002": "Planet 4 Port Switch",
    "05H00001": "Brocade 12 Port Switch",
    "05H00050": "Ruckus ICX 8200 Compact Switch",
    "05H00006": "R310",
    "05H00036": "R320",
    "05H00005": "T300",
    "05H00007": "T301",
    "05H00022": "MikroTik LtAPLTE6 Kit 4G Router"
}

REUSED_PREFIX = "X-"

# -------------------------
# 新增：Technology / Device Category / Vendor 對應
# -------------------------
PLU_TO_TECH = {
    "05H00018": "Wi‑Fi 5",
    "05H00009": "Wi‑Fi 5",
    "05H00039": "Wi‑Fi 6",
    "05H00038": "Wi‑Fi 6",
    "05H00021": "Wi‑Fi 6",
    "05H00026": "Wi‑Fi 6",
    "05H00048": "Wi‑Fi 7",
    "05H00046": "Wi‑Fi 6",
    "05H00055": "Wi‑Fi 7 (Medium-grade Tri-Band)",
    "05H00054": "Wi‑Fi 7 (Dual-Band)",
    "05H00056": "Wi‑Fi 7",
    "05H00064": "Wi‑Fi 7",
    "05H00065": "Wi‑Fi 7",
    "05H00042": "5G",
    "05H00040": "5G",
    "05H00004": "/",
    "05H00049": "/",
    "05H00053": "Wi‑Fi 7",
    "05H00002": "Wi‑Fi 4/5/6",
    "05H00001": "Wi‑Fi 5 / 6",
    "05H00050": "Wi‑Fi 7",
    "05H00006": "Wi‑Fi 5",
    "05H00036": "Wi‑Fi 5",
    "05H00005": "Wi‑Fi 5",
    "05H00007": "Wi‑Fi 5",
    "05H00022": "4G"
}

PLU_TO_DEVICE_CAT = {
    "05H00018": "Indoor AP",
    "05H00009": "Indoor AP",
    "05H00039": "Indoor AP",
    "05H00038": "Indoor AP",
    "05H00021": "Indoor AP",
    "05H00026": "Indoor AP",
    "05H00048": "Indoor AP",
    "05H00046": "Outdoor AP",
    "05H00055": "Indoor AP",
    "05H00054": "Indoor AP",
    "05H00056": "Outdoor AP",
    "05H00064": "Switch",
    "05H00065": "Switch",
    "05H00042": "Router",
    "05H00040": "Router",
    "05H00004": "POE Injector",
    "05H00049": "Power Adapter",
    "05H00053": "Power Adapter",
    "05H00002": "Switch",
    "05H00001": "Switch",
    "05H00050": "Switch",
    "05H00006": "Indoor AP",
    "05H00036": "Indoor AP",
    "05H00005": "Outdoor AP",
    "05H00007": "Outdoor AP",
    "05H00022": "Router"
}

HUAWEI_PLUS = {"05H00055","05H00054","05H00056","05H00064","05H00065"}

def vendor_of(plu: str) -> str:
    return "Huawei" if plu in HUAWEI_PLUS else "Ruckus"

# -------------------------
# Usage 分組
# -------------------------
BIZ_USE_PLUS = [
    "05H00018","05H00009","05H00039","05H00038","05H00021","05H00026",
    "05H00055","05H00054","05H00056","05H00064",
    "05H00065","05H00042","05H00040","05H00004","05H00049","05H00002"
]

MAINT_USE_PLUS = [
    "05H00006","05H00036","05H00048","05H00005",
    "05H00007","05H00046","05H00053","05H00001","05H00050","05H00022"
]

# -------------------------
# 工具函數
# -------------------------
def load_file(uploaded_file):
    suffix = uploaded_file.name.lower().split('.')[-1]
    if suffix == 'csv':
        df = pd.read_csv(uploaded_file, header=1, dtype=str)
    else:
        df = pd.read_excel(uploaded_file, header=1, engine='openpyxl', dtype=str)
    df = df.dropna(how='all')
    df.columns = [str(c).strip() for c in df.columns]
    return df

def to_number(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

def build_report(df, plu_list, usage_label=None):
    """
    依指定 plu_list 輸出報表。
    若提供 usage_label，會加上 Usage 欄位（For Biz Use / For Maintenance）。
    會附帶三個新欄位：Wi‑Fi Technology / Device Category / Vendor
    """
    col_category = "Category"  # 來源資料中的欄位
    col_plu = "PLU"
    col_main = "MAIN"

    # 安全轉數字
    df[col_main] = to_number(df[col_main])

    # 限定 WIFI 類別（來源 Category == WIFI）
    wifi_df = df[df[col_category].str.upper() == "WIFI"].copy()

    rows = []
    for plu in plu_list:
        model = PLU_TO_MODEL.get(plu, "")
        tech = PLU_TO_TECH.get(plu, "")
        dev_cat = PLU_TO_DEVICE_CAT.get(plu, "")
        vendor = vendor_of(plu)

        new_qty = wifi_df.loc[wifi_df[col_plu] == plu, col_main].sum()
        reused_qty = wifi_df.loc[wifi_df[col_plu] == REUSED_PREFIX + plu, col_main].sum()
        total_qty = new_qty + reused_qty

        row = {
            "PLU": plu,
            "Vendor": vendor,
            "Model": model,
            "Wi‑Fi Technology": tech,
            "Device Category": dev_cat,
            "Reused Stock": int(reused_qty),
            "New Stock": int(new_qty),
            "Total Stock": int(total_qty)
        }
        if usage_label:
            row["Usage"] = usage_label
        rows.append(row)

    out_df = pd.DataFrame(rows)

    # 調整欄位順序（Usage 若不存在會被忽略）
    cols_order = [
        "Usage","PLU","Vendor","Model","Wi‑Fi Technology","Device Category",
        "Reused Stock","New Stock","Total Stock"
    ]
    out_df = out_df[[c for c in cols_order if c in out_df.columns]]
    return out_df

# ---- 模糊查找工具 ----
def _normalize_text(s) -> str:
    """轉小寫並移除非 a-z0-9 的字元（把空白/斜線/連字號等同）。"""
    s = "" if pd.isna(s) else str(s)
    s = s.lower()
    return re.sub(r'[^a-z0-9]+', '', s)

def build_search_blob(df: pd.DataFrame) -> pd.Series:
    """
    逐行把多欄位字串 join 起來，避免 Series 被直接 join 的錯誤。
    這會回傳一個 Series，每列是一段合併後且正規化的字串。
    """
    cols = ["PLU","Vendor","Model","Wi‑Fi Technology","Device Category"]
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series([""] * len(df), index=df.index)

    combined = df[cols].astype(str).agg(' '.join, axis=1).fillna("")
    return combined.apply(_normalize_text)

def fuzzy_filter(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    多關鍵字 AND 模糊查找。忽略大小寫、空白、連字號。
    特別處理 token == 'ap'：僅命中 Device Category 為 Indoor/Outdoor AP（避免誤中 Power Adapter）。
    """
    if df is None or df.empty:
        return df
    if not query or not query.strip():
        return df

    # 準備 search blob（一次建好）
    if "_search_blob" not in df.columns:
        df = df.copy()
        df["_search_blob"] = build_search_blob(df)
    blob = df["_search_blob"]

    tokens = [t for t in re.split(r'\s+', query.strip()) if t]
    mask = pd.Series([True] * len(df), index=df.index)

    for t in tokens:
        norm_t = _normalize_text(t)

        # 特別處理 'ap'（僅匹配 Device Category 的 AP，而非 Adapter）
        if norm_t == "ap" and "Device Category" in df.columns:
            ap_mask = df["Device Category"].fillna("").str.contains(r"\bAP\b", case=False, regex=True)
            mask = mask & ap_mask
        else:
            mask = mask & blob.str.contains(norm_t, na=False)

    return df[mask].drop(columns=["_search_blob"], errors="ignore")

def section_metrics(label, df):
    if df is None or df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"{label} — Total New", 0)
        with col2:
            st.metric(f"{label} — Total Reused", 0)
        with col3:
            st.metric(f"{label} — Total Stock", 0)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"{label} — Total New", int(df["New Stock"].sum()))
    with col2:
        st.metric(f"{label} — Total Reused", int(df["Reused Stock"].sum()))
    with col3:
        st.metric(f"{label} — Total Stock", int(df["Total Stock"].sum()))

# -------------------------
# UI 主流程
# -------------------------
st.title("📶 Wi-Fi Inventory（自動統計｜分 For Biz Use / For Maintenance）")
st.caption("上傳含 Category / PLU / MAIN 的 data source，系統會自動統計 WiFi 設備庫存，並分兩塊輸出。")

uploaded = st.file_uploader("📤 上傳 CSV 或 Excel", type=["csv","xlsx"])

if uploaded:
    df = load_file(uploaded)

    # 1) 原始資料先顯示
    with st.expander("📄 原始資料（前 10 行）", expanded=False):
        st.dataframe(df.head(10), use_container_width=True)

    # 2) 建立分塊統計（包含 Vendor / Wi‑Fi Technology / Device Category）
    biz_df = build_report(df, BIZ_USE_PLUS, usage_label="For Biz Use")
    maint_df = build_report(df, MAINT_USE_PLUS, usage_label="For Maintenance")
    combined_df = pd.concat([biz_df, maint_df], ignore_index=True)

    # 3) 🔎 查找功能整塊 — 放在「原始資料」的下方
    st.markdown("---")
    st.subheader("🔎 即時查找（Vendor / Wi‑Fi Technology / Device Category / Model / PLU）")
    query = st.text_input(
        "輸入關鍵字（可空白分隔多關鍵字，採 AND 條件；忽略大小寫與連字號）",
        placeholder="例如：Huawei、AP、Dual-Band、dualband、Wi‑Fi 7、Router …"
    )

    with st.container():
        if query:
            filtered_df = fuzzy_filter(combined_df, query)
            st.markdown(f"**符合條件：{len(filtered_df)} 筆**")
            st.dataframe(filtered_df, use_container_width=True)
            section_metrics("Search Result", filtered_df)
        else:
            st.caption("提示：支援糢糊查找（忽略大小寫與連字號），如「dualband / dual-band / Dual-Band」都會命中。")

    st.markdown("---")

    # 4) 其餘板塊
    st.subheader("🏢 For Biz Use")
    st.dataframe(biz_df, use_container_width=True)
    section_metrics("For Biz Use", biz_df)

    st.subheader("🛠️ For Maintenance")
    st.dataframe(maint_df, use_container_width=True)
    section_metrics("For Maintenance", maint_df)

    st.subheader("🧾 合併檢視（含 Usage / Vendor / Wi‑Fi Technology / Device Category）")
    st.dataframe(combined_df, use_container_width=True)

    st.markdown("### 📈 全部總計")
    section_metrics("Overall", combined_df)

    # 5) 下載區（含新欄位）
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.download_button(
            "⬇️ 下載 For Biz Use（CSV）",
            biz_df.to_csv(index=False).encode("utf-8-sig"),
            "wifi_report_biz_use.csv",
            "text/csv"
        )
    with col_b:
        st.download_button(
            "⬇️ 下載 For Maintenance（CSV）",
            maint_df.to_csv(index=False).encode("utf-8-sig"),
            "wifi_report_maintenance.csv",
            "text/csv"
        )
    with col_c:
        st.download_button(
            "⬇️ 下載合併版（CSV）",
            combined_df.to_csv(index=False).encode("utf-8-sig"),
            "wifi_report_combined.csv",
            "text/csv"
        )

else:
    st.info("請上傳檔案以產生報表。")
