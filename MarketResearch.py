import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- Googleシート接続設定 ---
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Market Research")
    return spreadsheet.get_worksheet(0)

# アプリの初期設定
st.set_page_config(page_title="貿易管理システム", layout="wide")
sheet = connect_google_sheet()

# --- データの読み込み ---
# スプレッドシートの全データを取得（編集・削除のために行番号を意識する必要がある）
raw_data = sheet.get_all_values()
if len(raw_data) > 1:
    headers = raw_data[0]
    df = pd.DataFrame(raw_data[1:], columns=headers)
    # 価格を数値型に変換
    df["価格"] = pd.to_numeric(df["価格"], errors='coerce').fillna(0).astype(int)
else:
    df = pd.DataFrame(columns=["国名", "カテゴリ", "アイテム名", "価格", "備考"])

# マイクラ向けカテゴリ
mc_categories = ["建築ブロック", "植物・食料", "鉱石・インゴット", "モブドロップ", "エンチャント/装備", "ポーション", "その他"]

st.title("国運営：貿易・市場調査システム")

# タブ分け
tab1, tab2 = st.tabs(["📊 市場データ表示", "⚙️ データの編集・削除"])

# --- サイドバー：新規登録 ---
st.sidebar.header("📥 新規商品登録")
with st.sidebar.form("input_form", clear_on_submit=True):
    existing_countries = sorted(df["国名"].unique().tolist()) if not df.empty else []
    country_option = st.selectbox("販売国を選択", ["(新規入力)"] + existing_countries)
    new_country_name = st.text_input("新しい国名（新規の場合のみ）")
    selected_country = new_country_name if country_option == "(新規入力)" else country_option
    
    category = st.selectbox("カテゴリ", mc_categories)
    item_name = st.text_input("アイテム名")
    price = st.number_input("単価", min_value=0, step=1)
    note = st.text_area("備考")
    
    if st.form_submit_button("データベースへ保存"):
        if selected_country and item_name:
            sheet.append_row([selected_country, category, item_name, price, note])
            st.sidebar.success("登録完了！")
            st.rerun()

# --- タブ1：表示・検索・比較 ---
with tab1:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_cat = st.multiselect("カテゴリで絞り込み", mc_categories, key="filter_cat")
    with col_f2:
        search_item = st.text_input("アイテム名検索", "", key="search_item")

    display_df = df.copy()
    if filter_cat:
        display_df = display_df[display_df["カテゴリ"].isin(filter_cat)]
    if search_item:
        display_df = display_df[display_df["アイテム名"].str.contains(search_item, na=False)]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.divider()
        st.subheader("⚖️ アイテム価格比較")
        target_item = st.selectbox("比較するアイテムを選択", sorted(df["アイテム名"].unique()))
        compare_df = df[df["アイテム名"] == target_item].sort_values("価格")
        st.bar_chart(compare_df.set_index("国名")["価格"])
        st.table(compare_df)

# --- タブ2：編集・削除 ---
with tab2:
    st.subheader("🛠️ 登録データの修正・削除")
    if df.empty:
        st.write("データがありません。")
    else:
        # 編集対象の選択（行番号を特定するためにindexを保持）
        df_with_id = df.copy()
        df_with_id["ID"] = range(2, len(df) + 2)  # スプレッドシートの行番号(2行目開始)
        
        edit_target = st.selectbox(
            "編集・削除するアイテムを選択してください",
            options=df_with_id.to_dict('records'),
            format_func=lambda x: f"[{x['国名']}] {x['アイテム名']} - {x['価格']}G"
        )

        if edit_target:
            row_num = edit_target["ID"]
            
            col_edit, col_del = st.columns([2, 1])
            
            with col_edit:
                st.write("### データの編集")
                with st.form(f"edit_form_{row_num}"):
                    e_country = st.text_input("国名", value=edit_target["国名"])
                    e_cat = st.selectbox("カテゴリ", mc_categories, index=mc_categories.index(edit_target["カテゴリ"]) if edit_target["カテゴリ"] in mc_categories else 0)
                    e_item = st.text_input("アイテム名", value=edit_target["アイテム名"])
                    e_price = st.number_input("単価", min_value=0, value=int(edit_target["価格"]))
                    e_note = st.text_area("備考", value=edit_target["備考"])
                    
                    if st.form_submit_button("変更を保存"):
                        # スプレッドシートの特定の行を更新
                        sheet.update(range_name=f"A{row_num}:E{row_num}", values=[[e_country, e_cat, e_item, e_price, e_note]])
                        st.success("更新しました！")
                        st.rerun()

            with col_del:
                st.write("### データの削除")
                st.warning("削除すると元に戻せません。")
                if st.button("このアイテムを完全に削除", type="primary"):
                    sheet.delete_rows(row_num)
                    st.error("削除しました。")
                    st.rerun()