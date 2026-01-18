import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- Googleシート接続設定 ---
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {}
    for key in st.secrets.keys():
        val = st.secrets[key]
        if isinstance(val, str) and "\\n" in val:
            val = val.replace("\\n", "\n")
        creds_dict[key] = val

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("Market Research")
        return spreadsheet.get_worksheet(0)
    except Exception as e:
        st.error(f"接続失敗: {e}")
        return None

# アプリの初期設定
st.set_page_config(page_title="貿易管理システム", layout="wide")
sheet = connect_google_sheet()

# --- データの読み込み ---
raw_data = sheet.get_all_values()
# 新しい列構成
headers_list = ["国名", "カテゴリ", "取引種別", "アイテム名", "価格", "備考"]

if len(raw_data) > 1:
    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
    # 列が足りない場合の補完ロジック
    if "取引種別" not in df.columns:
        df["取引種別"] = "販売"
    # 価格を数値型に変換
    df["価格"] = pd.to_numeric(df["価格"], errors='coerce').fillna(0).astype(int)
else:
    df = pd.DataFrame(columns=headers_list)

# カテゴリ定義
mc_categories = ["建築ブロック", "植物・食料", "鉱石・インゴット", "モブドロップ", "エンチャント/装備", "ポーション", "その他"]

st.title("国運営：貿易・市場調査システム")

# タブ分け
tab1, tab2 = st.tabs(["📊 市場データ表示", "⚙️ データの編集・削除"])

# --- サイドバー：新規登録 ---
st.sidebar.header("📥 新規データ登録")
with st.sidebar.form("input_form", clear_on_submit=True):
    # 1. 国名の選択/入力
    existing_countries = sorted(df["国名"].unique().tolist()) if not df.empty else []
    country_option = st.selectbox("国を選択", ["(新規入力)"] + existing_countries)
    new_country_name = st.text_input("新しい国名（新規のみ）")
    final_country = new_country_name if country_option == "(新規入力)" else country_option
    
    # 2. カテゴリと取引種別
    col_cat, col_type = st.columns(2)
    with col_cat:
        category = st.selectbox("カテゴリ", mc_categories)
    with col_type:
        trade_type = st.radio("取引種別", ["販売", "買取"], horizontal=True)
    
    # 3. アイテム名の選択/入力
    existing_items = sorted(df["アイテム名"].unique().tolist()) if not df.empty else []
    item_option = st.selectbox("アイテムを選択", ["(新規入力)"] + existing_items)
    new_item_name = st.text_input("新しいアイテム名（新規のみ）")
    final_item = new_item_name if item_option == "(新規入力)" else item_option
    
    # 4. 価格と備考
    price = st.number_input("価格 (€)", min_value=0, step=1)
    note = st.text_area("備考")
    
    if st.form_submit_button("データベースへ保存"):
        if final_country and final_item:
            # スプレッドシートの列順序に合わせて保存
            sheet.append_row([final_country, category, trade_type, final_item, price, note])
            st.sidebar.success(f"{final_item} の情報を登録しました！")
            st.rerun()

# --- タブ1：表示・検索・比較 ---
with tab1:
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        view_type = st.selectbox("表示するデータ", ["すべて", "販売のみ", "買取のみ"])
    with col_f2:
        filter_cat = st.multiselect("カテゴリで絞り込み", mc_categories)
    with col_f3:
        search_item = st.text_input("アイテム名検索", "")

    display_df = df.copy()
    if view_type == "販売のみ":
        display_df = display_df[display_df["取引種別"] == "販売"]
    elif view_type == "買取のみ":
        display_df = display_df[display_df["取引種別"] == "買取"]
    
    if filter_cat:
        display_df = display_df[display_df["カテゴリ"].isin(filter_cat)]
    if search_item:
        display_df = display_df[display_df["アイテム名"].str.contains(search_item, na=False)]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.divider()
        st.subheader("⚖️ 相場比較（アイテム別）")
        target_item = st.selectbox("比較するアイテムを選択", sorted(df["アイテム名"].unique()))
        compare_df = df[df["アイテム名"] == target_item].sort_values("価格")
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.write(f"🛒 **{target_item} 販売価格**")
            sell_data = compare_df[compare_df["取引種別"] == "販売"]
            if not sell_data.empty:
                st.bar_chart(sell_data.set_index("国名")["価格"])
            else: st.info("販売データなし")

        with col_chart2:
            st.write(f"💰 **{target_item} 買取価格**")
            buy_data = compare_df[compare_df["取引種別"] == "買取"]
            if not buy_data.empty:
                st.bar_chart(buy_data.set_index("国名")["価格"])
            else: st.info("買取データなし")

# --- タブ2：編集・削除 ---
with tab2:
    st.subheader("🛠️ 登録データの修正・削除")
    if df.empty:
        st.write("データがありません。")
    else:
        df_with_id = df.copy()
        # スプレッドシートの行番号(2行目開始)をIDとして保持
        df_with_id["ID"] = range(2, len(df) + 2) 
        
        edit_target = st.selectbox(
            "編集・削除するデータを選択してください",
            options=df_with_id.to_dict('records'),
            format_func=lambda x: f"[{x['取引種別']}] {x['国名']} | {x['アイテム名']} ({x['価格']}G)"
        )

        if edit_target:
            row_num = edit_target["ID"]
            col_edit, col_del = st.columns([2, 1])
            
            with col_edit:
                st.write("### データの編集")
                with st.form(f"edit_form_{row_num}"):
                    e_country = st.text_input("国名", value=edit_target["国名"])
                    e_cat = st.selectbox("カテゴリ", mc_categories, index=mc_categories.index(edit_target["カテゴリ"]) if edit_target["カテゴリ"] in mc_categories else 0)
                    e_type = st.radio("取引種別", ["販売", "買取"], index=0 if edit_target["取引種別"] == "販売" else 1, horizontal=True)
                    e_item = st.text_input("アイテム名", value=edit_target["アイテム名"])
                    e_price = st.number_input("価格", min_value=0, value=int(edit_target["価格"]))
                    e_note = st.text_area("備考", value=edit_target["備考"])
                    
                    if st.form_submit_button("変更を保存"):
                        # 新しい列構成 [国名, カテゴリ, 取引種別, アイテム名, 価格, 備考] で更新
                        updated_values = [[e_country, e_cat, e_type, e_item, e_price, e_note]]
                        sheet.update(range_name=f"A{row_num}:F{row_num}", values=updated_values)
                        st.success("更新しました！")
                        st.rerun()

            with col_del:
                st.write("### データの削除")
                st.warning("この操作は取り消せません。")
                if st.button("このデータを完全に削除", type="primary"):
                    sheet.delete_rows(row_num)
                    st.error("削除しました。")
                    st.rerun()