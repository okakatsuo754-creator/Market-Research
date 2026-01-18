import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

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
headers_list = ["国名", "カテゴリ", "取引種別", "アイテム名", "価格", "備考"]

if len(raw_data) > 1:
    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
    if "取引種別" not in df.columns:
        df["取引種別"] = "販売"
    df["価格"] = pd.to_numeric(df["価格"], errors='coerce').fillna(0).astype(int)
else:
    df = pd.DataFrame(columns=headers_list)

mc_categories = ["建築ブロック", "植物・食料", "鉱石・インゴット", "モブドロップ", "エンチャント/装備", "ポーション", "その他"]

st.title("国運営：貿易・市場調査システム")

tab1, tab2 = st.tabs(["📊 市場データ表示", "⚙️ データの編集・削除"])

# --- サイドバー：新規登録 ---
st.sidebar.header("📥 新規データ登録")

# 1. 国名の選択 (フォームの外に出すことで動的な連動を可能にする)
existing_countries = sorted(df["国名"].unique().tolist()) if not df.empty else []
country_option = st.sidebar.selectbox("国を選択", ["(新規入力)"] + existing_countries)
new_country_name = ""
if country_option == "(新規入力)":
    new_country_name = st.sidebar.text_input("新しい国名を入力")

# 2. カテゴリの選択 (これによってアイテムの選択肢を変える)
selected_category = st.sidebar.selectbox("カテゴリを選択", mc_categories)

# 3. 選択されたカテゴリに属するアイテムのみを抽出
if not df.empty:
    filtered_items = sorted(df[df["カテゴリ"] == selected_category]["アイテム名"].unique().tolist())
else:
    filtered_items = []

item_option = st.sidebar.selectbox(f"{selected_category} 内のアイテムを選択", ["(新規入力)"] + filtered_items)
new_item_name = ""
if item_option == "(新規入力)":
    new_item_name = st.sidebar.text_input("新しいアイテム名を入力")

# 実際の登録用フォーム
with st.sidebar.form("input_form", clear_on_submit=True):
    trade_type = st.radio("取引種別", ["販売", "買取"], horizontal=True)
    price = st.number_input("価格 (€)", min_value=0, step=1)
    note = st.text_area("備考")
    
    # 送信ボタン
    submit = st.form_submit_button("データベースへ保存")
    
    if submit:
        final_country = new_country_name if country_option == "(新規入力)" else country_option
        final_item = new_item_name if item_option == "(新規入力)" else item_option
        
        if final_country and final_item:
            sheet.append_row([final_country, selected_category, trade_type, final_item, price, note])
            st.sidebar.success(f"{final_item} を登録しました！")
            st.rerun()
        else:
            st.error("国名とアイテム名は必須です。")
            
st.sidebar.divider()
st.sidebar.header(":package: 一括データ登録")
uploaded_file = st.sidebar.file_uploader("JSONファイルをアップロード", type="json")

if uploaded_file is not None:
    try:
        data_to_import = json.load(uploaded_file)
        new_rows = []
        
        # JSON構造をスプレッドシート形式にフラット化
        # 構造: { 国名: { カテゴリ: { "アイテム名 (種別)": 価格 } } }
        for country, categories in data_to_import.items():
            for category, items in categories.items():
                for item_key, price in items.items():
                    # 種別の判別とアイテム名のクリーンアップ
                    trade_type = "買取" if "(買取)" in item_key else "販売"
                    clean_item = item_key.replace(" (販売)", "").replace(" (買取)", "")
                    
                    # スプレッドシートの列順: [国名, カテゴリ, 取引種別, アイテム名, 価格, 備考]
                    new_rows.append([country, category, trade_type, clean_item, price, "一括登録"])
        
        if st.sidebar.button(f"{len(new_rows)}件を一括保存"):
            sheet.append_rows(new_rows)
            st.sidebar.success("一括登録が完了しました！")
            st.rerun()
            
    except Exception as e:
        st.sidebar.error(f"ファイル読み込みエラー: {e}")

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