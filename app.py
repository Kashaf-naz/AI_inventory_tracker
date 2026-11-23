import streamlit as st
import pandas as pd
import os
import difflib
import re
import html
from database import get_connection, save_uploaded_file, save_uploaded_file_bytes
from datetime import datetime
from ai_helper import classify_and_extract, extract_pdf_text, answer_inventory_question, find_manual_passages, extract_pdf_text_ocr, expand_search_words
import base64

def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = get_base64_image("inventory_logo.png")

import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

st.set_page_config(page_title="Home Inventory Tracker", page_icon="📦", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-size: 20px;
    }
    label {
        font-size: 17px !important;
    }
    h1 {
        font-size: 46px !important;
    }
    h3 {
        font-size: 28px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# AUTHENTICATION GATE
# ============================================================
with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config["preauthorized"]
)

if not st.session_state.get("authentication_status"):
    st.markdown(f"""
        <div style="display:flex; justify-content:center; margin-top: 40px;">
            <div style="text-align:center;">
                <img src="data:image/png;base64,{logo_base64}" width="90" style="border-radius: 18px;">
                <div style="font-size: 34px; font-weight: 800; color: #1F3864; margin-top: 10px;">Home Inventory Tracker</div>
                <div style="font-size: 15px; color: #666666; margin-bottom: 20px;">Sign in to manage your home inventory</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "auth_view" not in st.session_state:
        st.session_state.auth_view = "login"

    center_col = st.columns([1, 2, 1])[1]
    with center_col:

        if st.session_state.auth_view == "login":
            st.markdown("### 🔑 Log In")
            authenticator.login()
            if st.session_state.get("authentication_status") is False:
                st.error("Username or password is incorrect.")
            elif st.session_state.get("authentication_status") is None:
                st.info("Please enter your username and password.")

            st.write("")
            link_col1, link_col2 = st.columns([3, 1])
            with link_col1:
                st.write("Don't have an account?")
            with link_col2:
                if st.button("Sign Up", use_container_width=True):
                    st.session_state.auth_view = "signup"
                    st.rerun()

        else:
            st.markdown("### 📝 Sign Up")
            try:
                email, username, name = authenticator.register_user(pre_authorization=False)
                if email:
                    with open("config.yaml", "w") as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success("Account created successfully! Please log in.")
                    st.session_state.auth_view = "login"
            except Exception as e:
                st.error(e)

            st.write("")
            link_col1, link_col2 = st.columns([3, 1])
            with link_col1:
                st.write("Already have an account?")
            with link_col2:
                if st.button("Log In", use_container_width=True):
                    st.session_state.auth_view = "login"
                    st.rerun()

    st.stop()

current_user = st.session_state["username"]

def get_warranty_status(w):
    if pd.isna(w):
        return "No warranty"
    days_left = (pd.to_datetime(w) - datetime.now()).days
    if days_left < 0:
        return "Expired"
    elif days_left <= 30:
        return "Expiring soon (30 days)"
    else:
        return "Has warranty"

# If we reach here, the user IS logged in
st.markdown("""
    <style>

    /* ==========================================================
       SIDEBAR
       ========================================================== */

    [data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #1F3864 0%,
            #162B4F 100%
        );
    }

    [data-testid="stSidebar"] * {
        color: white !important;
    }


    /* ==========================================================
       PROFILE CARD
       ========================================================== */

    .sb-profile {
        text-align: center;
        margin-top: 6px;
        padding: 24px 12px 18px;
        border-radius: 18px;

        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.10);

        transition:
            transform .25s ease,
            background .25s ease,
            box-shadow .25s ease;
    }

    .sb-profile:hover {
        transform: translateY(-3px);

        background: rgba(255, 255, 255, 0.11);

        box-shadow:
            0 10px 24px rgba(0, 0, 0, 0.25);
    }


    /* ==========================================================
       AVATAR
       ========================================================== */

    .sb-avatar {
        width: 84px;
        height: 84px;

        margin: 0 auto 12px;

        border-radius: 50%;

        display: flex;
        align-items: center;
        justify-content: center;

        font-size: 36px;
        font-weight: 800;
        letter-spacing: 1px;

        background: linear-gradient(
            135deg,
            #5B8DEF 0%,
            #7DD3FC 100%
        );

        border: 3px solid rgba(255, 255, 255, 0.85);

        box-shadow:
            0 0 0 6px rgba(125, 211, 252, 0.15),
            0 8px 18px rgba(0, 0, 0, 0.3);

        transition:
            transform .3s ease,
            box-shadow .3s ease;
    }

    .sb-profile:hover .sb-avatar {
        transform: scale(1.07) rotate(-3deg);

        box-shadow:
            0 0 0 8px rgba(125, 211, 252, 0.22),
            0 12px 24px rgba(0, 0, 0, 0.35);
    }


    /* ==========================================================
       USERNAME
       ========================================================== */

    .sb-name {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: .3px;
        margin-bottom: 4px;
    }


    /* ==========================================================
       ONLINE STATUS
       ========================================================== */

    .sb-status {
        display: inline-flex;
        align-items: center;

        gap: 6px;

        font-size: 13px;
        opacity: .85;
    }

    .sb-dot {
        width: 8px;
        height: 8px;

        border-radius: 50%;

        background: #34D399;

        animation: sbPulse 2s infinite;
    }

    @keyframes sbPulse {

        0% {
            box-shadow:
                0 0 0 0 rgba(52, 211, 153, 0.7);
        }

        70% {
            box-shadow:
                0 0 0 7px rgba(52, 211, 153, 0);
        }

        100% {
            box-shadow:
                0 0 0 0 rgba(52, 211, 153, 0);
        }

    }


    /* ==========================================================
       DIVIDER
       ========================================================== */

    .sb-divider {
        height: 1px;

        background: rgba(255, 255, 255, 0.12);

        margin: 20px 4px;
    }


    /* ==========================================================
       BOTTOM BUTTON AREA
       ========================================================== */

    .st-key-sb_bottom {

        position: fixed;

        bottom: 24px;
        left: 20px;

        width: 250px;

        z-index: 100;

        display: flex;
        flex-direction: column;

        gap: .6rem;
    }


    /* ==========================================================
       CHAT ASSISTANT BUTTON
       ========================================================== */

    .st-key-sb_bottom .st-key-open_chat {
        width: 100% !important;
    }

    .st-key-sb_bottom .st-key-open_chat button {

        width: 100% !important;

        padding: 10px 0 !important;

        border-radius: 12px;

        font-weight: 600;

        background: #FFFFFF !important;

        border: 1px solid #FFFFFF !important;

        transition:
            transform .2s ease,
            box-shadow .2s ease,
            background .2s ease,
            border-color .2s ease;
    }


    /* Chat button text */

    .st-key-sb_bottom .st-key-open_chat button * {
        color: #1F3864 !important;

        font-weight: 700;
    }


    /* Chat hover */

    .st-key-sb_bottom .st-key-open_chat button:hover {

        background: #EAF1FF !important;

        border-color: #EAF1FF !important;

        transform: translateY(-2px);

        box-shadow:
            0 6px 14px rgba(0, 0, 0, 0.28);
    }


    /* ==========================================================
       LOGOUT CONTAINER
       ========================================================== */

    .st-key-sb_logout {

        width: 100% !important;

        display: flex !important;

        justify-content: center !important;

        align-items: center !important;

        margin: 0 !important;

        padding: 0 !important;
    }


    /* ==========================================================
       LOGOUT BUTTON
       ========================================================== */

    .st-key-sb_logout button {

        /* Let button size itself around the text */
        width: auto !important;

        min-width: 0 !important;

        /* Equal spacing on all four sides */
        padding: 8px 14px !important;

        margin: 0 !important;

        /* Keep "Log out" on one line */
        white-space: nowrap !important;

        /* Center text */
        text-align: center !important;

        /* Appearance */
        border-radius: 10px !important;

        background: transparent !important;

        border: 1px solid rgba(255, 255, 255, 0.35) !important;

        font-weight: 600 !important;

        transition:
            transform .2s ease,
            box-shadow .2s ease,
            background .2s ease,
            border-color .2s ease;
    }


    /* Logout text */

    .st-key-sb_logout button * {
        color: white !important;

        font-weight: 600 !important;
    }


    /* Logout hover */

    .st-key-sb_logout button:hover {

        background: rgba(255, 255, 255, 0.14) !important;

        border-color: #FFFFFF !important;

        transform: translateY(-2px);

        box-shadow:
            0 6px 14px rgba(0, 0, 0, 0.28);
    }


    /* Logout click */

    .st-key-sb_logout button:active {

        transform: translateY(0) scale(0.98);
    }


    </style>
""", unsafe_allow_html=True)

_display_name = str(st.session_state.get("name") or current_user)
_initial = html.escape(_display_name[:1].upper() or "?")
_name_safe = html.escape(_display_name)

with st.sidebar:
    st.markdown(f"""
        <div class="sb-profile">
            <div class="sb-avatar">{_initial}</div>
            <div class="sb-name">{_name_safe}</div>
            <div class="sb-status"><span class="sb-dot"></span>Online</div>
        </div>
        <div class="sb-divider"></div>
    """, unsafe_allow_html=True)

    with st.container(key="sb_bottom"):

        chat_clicked = st.button(
            "🤖 Chat assistant",
            key="open_chat",
            use_container_width=True
        )

    with st.container(key="sb_logout"):
        authenticator.logout("🚪 Log out", "main")
#--------------------------------------------------------------

st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 4px;">
        <img src="data:image/png;base64,{logo_base64}" width="64" style="border-radius: 14px;">
        <div>
            <div style="font-size: 40px; font-weight: 800; color: #1F3864; line-height: 1.1;">Home Inventory Tracker</div>
            <div style="font-size: 16px; color: #666666;">Keep track of everything you own — purchase, warranties, and history</div>
        </div>
    </div>
""", unsafe_allow_html=True)
st.write("")
st.write("")

# ============================================================
# ADD ITEM DIALOG — pure confirmation form, pre-filled if AI data exists
# ============================================================
@st.dialog("Add a new item", width="large")
def add_item_dialog():
    extracted = st.session_state.get("extracted_data", {})
    has_warranty = st.checkbox("This item has a warranty")

    with st.form("add_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Item name", value=extracted.get("name") or "")
            category = st.text_input("Category (e.g. Appliance, Furniture)", value=extracted.get("category") or "")
            purchase_date_default = pd.to_datetime(extracted.get("purchase_date")) if extracted.get("purchase_date") else pd.Timestamp.today()
            purchase_date = st.date_input("Purchase date", value=purchase_date_default)
            quantity = st.number_input("Quantity", min_value=1, step=1, value=int(extracted.get("quantity") or 1))
        with col2:
            price = st.number_input("Price", min_value=0.0, step=1.0, value=float(extracted.get("price") or 0.0))
            store = st.text_input("Store", value=extracted.get("store") or "")
            if has_warranty:
                warranty_expiry = st.date_input("Warranty expiry")
            else:
                warranty_expiry = None
                st.write("")

        submitted = st.form_submit_button("Save item")
        if submitted:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO items (name, category, purchase_date, price, store, warranty_expiry, quantity, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, category, str(purchase_date), price, store,
                  str(warranty_expiry) if warranty_expiry else None, quantity, current_user))
            conn.commit()
            conn.close()
            st.session_state.pop("extracted_data", None)
            st.toast(f"'{name}' added successfully! ✅")
            st.rerun()

# ============================================================
# ITEM UPDATED CONFIRMATION DIALOG (used by the AI Assistant)
# ============================================================
@st.dialog("Confirm item edit", width="large")
def edit_item_dialog():
    pending = st.session_state.get("ai_pending", {})
    data = pending.get("data", {})
    items_list = pending.get("all_items", [])
    item_names = [i["name"] for i in items_list]

    if not item_names:
        st.error("No items exist yet.")
        return

    if pending.get("matched_id") is not None:
        default_idx = next((i for i, it in enumerate(items_list) if it["id"] == pending["matched_id"]), 0)
    else:
        default_idx = 0
        st.warning("Couldn't confidently match this to one item — please confirm which item below.")

    selected_name = st.selectbox("Which item do you want to edit?", item_names, index=default_idx)
    selected_id = next((i["id"] for i in items_list if i["name"] == selected_name), None)

    conn = get_connection()
    current_df = pd.read_sql_query("SELECT * FROM items WHERE id = ?", conn, params=(selected_id,))
    conn.close()
    current = current_df.iloc[0]

    has_warranty = st.checkbox(
        "This item has a warranty",
        value=bool(data.get("warranty_expiry")) or pd.notna(current["warranty_expiry"])
    )

    with st.form("confirm_edit_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Item name", value=data.get("name") or current["name"])
            new_category = st.text_input("Category", value=data.get("category") or current["category"])
            date_default = data.get("purchase_date") or current["purchase_date"]
            new_purchase_date = st.date_input("Purchase date", value=pd.to_datetime(date_default))
            new_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(data.get("quantity") or current["quantity"]))
        with col2:
            new_price = st.number_input("Price", min_value=0.0, step=1.0, value=float(data.get("price") or current["price"]))
            new_store = st.text_input("Store", value=data.get("store") or current["store"] or "")
            if has_warranty:
                warranty_default = data.get("warranty_expiry") or current["warranty_expiry"]
                new_warranty = st.date_input(
                    "Warranty expiry",
                    value=pd.to_datetime(warranty_default) if warranty_default else pd.Timestamp.today()
                )
            else:
                new_warranty = None

        if st.form_submit_button("💾 Save changes"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE items SET name=?, category=?, purchase_date=?, price=?, store=?, warranty_expiry=?, quantity=?
                WHERE id=?
            """, (new_name, new_category, str(new_purchase_date), new_price, new_store,
                  str(new_warranty) if new_warranty else None, new_quantity, selected_id))
            conn.commit()
            conn.close()
            st.session_state.pop("ai_pending", None)
            st.toast("Item updated! ✅")
            st.rerun()

# ============================================================
# REPAIR CONFIRMATION DIALOG (used by the AI Assistant)
# ============================================================
@st.dialog("Confirm repair record", width="large")
def add_repair_dialog():
    pending = st.session_state.get("ai_pending", {})
    data = pending.get("data", {})
    items_list = pending.get("all_items", [])
    item_names = [i["name"] for i in items_list]

    if not item_names:
        st.error("No items exist yet — add an item first before logging a repair.")
        return

    if pending.get("matched_id") is not None:
        default_idx = next((i for i, it in enumerate(items_list) if it["id"] == pending["matched_id"]), 0)
    else:
        default_idx = 0
        st.warning("Couldn't confidently match this to one item — please confirm which item below.")

    selected_name = st.selectbox("Which item is this repair for?", item_names, index=default_idx)
    selected_id = next((i["id"] for i in items_list if i["name"] == selected_name), None)

    with st.form("confirm_repair_form"):
        col1, col2 = st.columns(2)
        with col1:
            r_date = st.date_input(
                "Repair date",
                value=pd.to_datetime(data.get("repair_date")) if data.get("repair_date") else pd.Timestamp.today()
            )
            description = st.text_input("Description", value=data.get("description") or "")
            cost = st.number_input("Cost", min_value=0.0, step=1.0, value=float(data.get("cost") or 0.0))
        with col2:
            repairer_name = st.text_input("Repairer name", value=data.get("repairer_name") or "")
            repairer_contact = st.text_input("Repairer contact", value=data.get("repairer_contact") or "")
            status_options = ["completed", "scheduled"]
            status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(data.get("status")) if data.get("status") in status_options else 0
            )
        notes = st.text_area("Notes", value=data.get("notes") or "")

        if st.form_submit_button("💾 Save repair"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO repairs (item_id, repair_date, description, cost, repairer_name, repairer_contact, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (selected_id, str(r_date), description, cost, repairer_name, repairer_contact, status, notes))
            repair_id = cursor.lastrowid

            if pending.get("file_bytes") is not None:
                file_path = save_uploaded_file_bytes(pending["file_bytes"], pending["file_name"], selected_id)
                cursor.execute("""
                    INSERT INTO documents (item_id, repair_id, doc_type, file_path, file_name, uploaded_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (selected_id, repair_id, "Receipt", file_path, pending["file_name"],
                      str(pd.Timestamp.today().date()), "Auto-attached from AI Assistant"))

            conn.commit()
            conn.close()
            st.session_state.pop("ai_pending", None)
            st.toast("Repair record saved! 🔧")
            st.rerun()


# ============================================================
# DOCUMENT CONFIRMATION DIALOG (used by the AI Assistant)
# ============================================================
@st.dialog("Confirm document", width="large")
def add_document_dialog():
    pending = st.session_state.get("ai_pending", {})
    data = pending.get("data", {})
    items_list = pending.get("all_items", [])
    item_names = [i["name"] for i in items_list]

    if not item_names:
        st.error("No items exist yet — add an item first before uploading a document.")
        return

    if pending.get("matched_id") is not None:
        default_idx = next((i for i, it in enumerate(items_list) if it["id"] == pending["matched_id"]), 0)
    else:
        default_idx = 0
        st.warning("Couldn't confidently match this to one item — please confirm which item below.")

    selected_name = st.selectbox("Which item is this document for?", item_names, index=default_idx)
    selected_id = next((i["id"] for i in items_list if i["name"] == selected_name), None)

    doc_types = ["Receipt", "Manual", "Photo", "Warranty Card", "Other"]
    doc_type = st.selectbox(
        "Document type",
        doc_types,
        index=doc_types.index(data.get("doc_type")) if data.get("doc_type") in doc_types else 1
    )
    notes = st.text_area("Notes", value=data.get("notes") or "")

    detected_warranty = data.get("warranty_expiry")
    update_warranty = False
    if detected_warranty:
        update_warranty = st.checkbox(f"Also update this item's warranty expiry to {detected_warranty}", value=True)

    if st.button("💾 Save document"):
        if pending.get("file_bytes") is None:
            st.error("No file was attached — please attach a file in the AI Assistant box first.")
        else:
            file_path = save_uploaded_file_bytes(pending["file_bytes"], pending["file_name"], selected_id)

            # Read the whole document (PDFs only) so the chatbot can search it later
            full_text = None
            if pending.get("file_mime") == "application/pdf":
                bar = st.progress(0, text="Reading the manual...")
                full_text = extract_pdf_text_ocr(
                    pending["file_bytes"],
                    progress=lambda i, n: bar.progress(i / n, text=f"Reading page {i} of {n}...")
                )
                bar.empty()

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO documents (item_id, doc_type, file_path, file_name, uploaded_date, notes, extracted_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (selected_id, doc_type, file_path, pending["file_name"], str(pd.Timestamp.today().date()), notes, full_text))
            if update_warranty and detected_warranty:
                cursor.execute("UPDATE items SET warranty_expiry = ? WHERE id = ?", (detected_warranty, selected_id))

            conn.commit()
            conn.close()
            st.session_state.pop("ai_pending", None)
            st.toast(f"'{pending['file_name']}' saved! 📄")
            st.rerun()

# ============================================================
# CHATBOT (opens from the sidebar button, or from the AI Assistant box
# when the user types a question). Defined BEFORE the AI Assistant code
# because run_ai_assistant calls these functions.
# ============================================================
st.markdown("""
    <style>
    /* ---------- Chat window ---------- */
    @keyframes chatFadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    .cb-row {
        display: flex;
        align-items: flex-end;
        gap: 10px;
        margin: 10px 0;
    }
    .cb-row.user { flex-direction: row-reverse; }
    .cb-row.latest { animation: chatFadeIn .4s ease-out; }

    .cb-avatar {
        width: 30px;
        height: 30px;
        min-width: 30px;
        border-radius: 50%;
        background: #EEF2F9;
        border: 1px solid #D6DEEE;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
    }

    /* bubble is only as wide as its text (up to 80% of the window) */
    .cb-bubble {
        max-width: 80%;
        padding: 10px 16px;
        border-radius: 18px 18px 18px 4px;
        background: #FFFFFF;
        border: 1px solid #E3E8F0;
        box-shadow: 0 1px 3px rgba(31, 56, 100, 0.06);
        font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 15.5px;
        line-height: 1.5;
        color: #1F2937;
        overflow-x: auto;
        transition: box-shadow .2s ease, transform .2s ease, border-color .2s ease;
    }
    .cb-row.user .cb-bubble {
        background: #EEF2F9;
        border-color: #D6DEEE;
        border-radius: 18px 18px 4px 18px;
    }
    .cb-bubble:hover {
        box-shadow: 0 6px 16px rgba(31, 56, 100, 0.12);
        transform: translateY(-1px);
        border-color: #C9D3E6;
    }
    .cb-bubble p { margin: 0 0 6px 0; }
    .cb-bubble p:last-child { margin-bottom: 0; }
    .cb-bubble ul, .cb-bubble ol { margin: 4px 0 4px 18px; padding: 0; }
    .cb-bubble table { border-collapse: collapse; margin: 6px 0; font-size: 14px; }
    .cb-bubble th, .cb-bubble td { border: 1px solid #E3E8F0; padding: 4px 10px; text-align: left; }
    .cb-bubble th { background: #F5F7FB; }

    /* quick-question buttons, Clear and Send */
    div[role="dialog"] .stButton button,
    div[role="dialog"] [data-testid="stFormSubmitButton"] button {
        border-radius: 999px;
        border: 1px solid #D6DEEE;
        transition: all .2s ease;
    }
    div[role="dialog"] .stButton button:hover,
    div[role="dialog"] [data-testid="stFormSubmitButton"] button:hover {
        background-color: #1F3864;
        border-color: #1F3864;
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(31, 56, 100, 0.25);
    }
    div[role="dialog"] .stButton button:hover *,
    div[role="dialog"] [data-testid="stFormSubmitButton"] button:hover * {
        color: white !important;
    }
    div[role="dialog"] .stButton button:active,
    div[role="dialog"] [data-testid="stFormSubmitButton"] button:active {
        transform: translateY(0) scale(0.97);
    }

    /* text box: smooth glow when you click into it */
    div[role="dialog"] [data-baseweb="input"] {
        border-radius: 12px;
        transition: box-shadow .2s ease, border-color .2s ease;
    }
    div[role="dialog"] [data-baseweb="input"]:focus-within {
        border-color: #1F3864;
        box-shadow: 0 0 0 3px rgba(31, 56, 100, 0.15);
    }

    /* respect people who turn animations off */
    @media (prefers-reduced-motion: reduce) {
        div[role="dialog"] * { animation: none !important; transition: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

try:
    import markdown as md_lib
except ImportError:
    md_lib = None

def _space_lists(text):
    """Models often skip the blank line before a list; add it so lists render as lists."""
    item = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")
    out, prev = [], ""
    for line in text.split("\n"):
        if item.match(line) and prev.strip() and not item.match(prev):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)

def render_md(text):
    """Turn a chat message into safe HTML for the bubbles (markdown if available)."""
    safe = _space_lists(html.escape(text or "", quote=False))
    if md_lib:
        out = md_lib.markdown(safe, extensions=["tables", "nl2br", "sane_lists"])
    else:
        out = safe.replace("\n", "<br>")
    return out.replace("\n", "")

def process_chat_question(question):
    conn = get_connection()
    chat_items = pd.read_sql_query(
        """SELECT name, category, purchase_date, price, store, warranty_expiry, quantity
           FROM items WHERE status = 'active' AND user_id = ?""",
        conn, params=(current_user,)
    )
    chat_repairs = pd.read_sql_query(
        """SELECT i.name AS item, r.repair_date, r.description, r.cost, r.repairer_name, r.status
           FROM repairs r JOIN items i ON r.item_id = i.id
           WHERE i.user_id = ? AND i.status = 'active'""",
        conn, params=(current_user,)
    )
    chat_docs = pd.read_sql_query(
    """SELECT i.name AS item, d.file_name, d.extracted_text
        FROM documents d JOIN items i ON d.item_id = i.id
        WHERE i.user_id = ? AND i.status = 'active'
            AND d.extracted_text IS NOT NULL AND d.extracted_text != ''""",
    conn, params=(current_user,)
    )
    conn.close()
    extra_words = expand_search_words(question) if not chat_docs.empty else ""
    passages = find_manual_passages(question + " " + extra_words, chat_docs)
    print("DOCS WITH TEXT:", len(chat_docs), "| PASSAGES FOUND:", len(passages))

    with st.spinner("Processing..."):
        answer = answer_inventory_question(
            question, chat_items, chat_repairs, st.session_state.chat_history,
            manual_passages=passages
        )

    st.session_state.chat_history.append(("user", question))
    st.session_state.chat_history.append(("assistant", answer))

@st.dialog("🤖 Home Inventory Assistant", width="large")
def chat_dialog():
    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.caption("Ask about your items, warranties, repairs and spending.")
    with top_right:
        if st.button("🧹 Clear", use_container_width=True):
            st.session_state.chat_history = []

    chat_box = st.container(height=380, border=False)

    suggestions = [
        "Which warranties have expired?",
        "What repairs are scheduled?",
        "What is my total spending?",
    ]
    s_cols = st.columns(len(suggestions))
    for col, text in zip(s_cols, suggestions):
        if col.button(text, key=f"sugg_{text}", use_container_width=True):
            process_chat_question(text)

    with st.form("chat_form", clear_on_submit=True):
        c1, c2 = st.columns([6, 1])
        with c1:
            chat_question = st.text_input(
                "Ask a question",
                placeholder="Type your question here...",
                label_visibility="collapsed"
            )
        with c2:
            chat_send = st.form_submit_button("➤", use_container_width=True)
    if chat_send and chat_question.strip():
        process_chat_question(chat_question.strip())

    with chat_box:
        if not st.session_state.chat_history:
            st.info("👋 Hi! Ask me anything about your home inventory, or tap a quick question below.")
        else:
            last_index = len(st.session_state.chat_history) - 1
            rows = []
            for i, (role, text) in enumerate(st.session_state.chat_history):
                side = "user" if role == "user" else "bot"
                avatar = "👤" if role == "user" else "🤖"
                latest = " latest" if i >= last_index - 1 else ""
                rows.append(
                    f'<div class="cb-row {side}{latest}">'
                    f'<div class="cb-avatar">{avatar}</div>'
                    f'<div class="cb-bubble">{render_md(text)}</div>'
                    f'</div>'
                )
            st.markdown("".join(rows), unsafe_allow_html=True)

# ============================================================
# ONE CENTRAL AI ASSISTANT — auto-processes on upload, or on text submit
# ============================================================
st.markdown("""
    <div style="border-left: 5px solid #FF4B4B; padding: 10px 15px; border-radius: 6px; background-color: rgba(255, 75, 75, 0.08); margin-bottom: 10px;">
        <span style="font-size: 20px; font-weight: 700;">✨ AI Assistant</span><br>
        <span style="font-size: 14px; color: #666666;">Type anything, like adding a purchase or repair or asking a question, or attach a receipt, manual or warranty card — processing starts automatically</span>
    </div>
""", unsafe_allow_html=True)


def find_matching_item_id(matched_name, items_df):
    if not matched_name:
        return None
    m = matched_name.lower()
    for _, r in items_df.iterrows():
        n = r['name'].lower()
        if n in m or m in n:
            return int(r['id'])
    names = [n.lower() for n in items_df['name']]
    close = difflib.get_close_matches(m, names, n=1, cutoff=0.5)
    if close:
        return int(items_df.iloc[names.index(close[0])]['id'])
    return None

def find_item_by_filename(file_name, items_df):
    if not file_name:
        return None
    skip = {"manual", "pdf", "png", "jpg", "jpeg", "warranty", "card", "receipt", "the", "and"}
    file_words = {w for w in re.findall(r"[a-z0-9]+", file_name.lower()) if w not in skip}

    best_id, best_score, tie = None, 0, False
    for _, r in items_df.iterrows():
        item_words = set(re.findall(r"[a-z0-9]+", r['name'].lower()))
        score = len(file_words & item_words)
        if score > best_score:
            best_id, best_score, tie = int(r['id']), score, False
        elif score == best_score and score > 0:
            tie = True
    return best_id if best_score >= 2 and not tie else None

def run_ai_assistant(sentence=None, ai_file=None):
    conn = get_connection()
    all_items_df = pd.read_sql_query(
        "SELECT id, name FROM items WHERE status = 'active' AND user_id = ?", conn, params=(current_user,)
    )
    conn.close()

    img_bytes, img_mime, file_name, pdf_text = None, None, None, None
    raw_bytes = None

    if ai_file is not None:
        file_name = ai_file.name
        raw_bytes = ai_file.getvalue()
        if ai_file.type == "application/pdf":
            pdf_text = extract_pdf_text(raw_bytes)
        else:
            img_bytes = raw_bytes
            img_mime = ai_file.type

    with st.spinner("Understanding..."):
        result = classify_and_extract(
            item_names=all_items_df['name'].tolist(),
            sentence=sentence,
            image_bytes=img_bytes,
            mime_type=img_mime,
            pdf_text=pdf_text,
            file_uploaded=(ai_file is not None),
            file_name=file_name
        )

    if "error" in result:
        st.error(f"AI couldn't process that right now: {result['error']}")
        return

    record_type = result.get("record_type")

    if record_type == "new_item":
        st.session_state["extracted_data"] = result.get("new_item") or {}
        add_item_dialog()

    elif record_type == "query":
        # Questions are answered by the chatbot; an uploaded file must NEVER trigger this
        if ai_file is None and sentence:
            process_chat_question(sentence)
            chat_dialog()
        return

    elif record_type in ("repair", "document", "edit_item"):
        matched_name = result.get("matched_item_name") or ""
        st.session_state["ai_pending"] = {
            "type": record_type,
            "data": result.get(record_type) or {},
            "matched_id": find_matching_item_id(matched_name, all_items_df) or find_item_by_filename(file_name, all_items_df),
            "all_items": all_items_df.to_dict("records"),
            "file_bytes": raw_bytes,
            "file_mime": ai_file.type if ai_file is not None else None,
            "file_name": file_name,
            "extracted_text": pdf_text,
        }
        if record_type == "repair":
            add_repair_dialog()
        elif record_type == "document":
            add_document_dialog()
        else:
            edit_item_dialog()

    else:
        st.warning("Couldn't determine what kind of record this is — please try rephrasing.")

# --- File upload: processes immediately, no button needed ---
if "last_ai_file_id" not in st.session_state:
    st.session_state.last_ai_file_id = None

ai_file = st.file_uploader(
    "Attach a receipt, manual, or warranty card",
    type=["jpg", "jpeg", "png", "pdf"],
    key="ai_file_input"
)
if ai_file is not None:
    file_size_mb = ai_file.size / (1024 * 1024)
    if file_size_mb > 70:
        st.error(f"This file is {file_size_mb:.1f} MB — please upload something under 70 MB. Try compressing the PDF or exporting a smaller version.")
    else:
        file_id = f"{ai_file.name}_{ai_file.size}"
        if file_id != st.session_state.last_ai_file_id:
            st.session_state.last_ai_file_id = file_id
            run_ai_assistant(sentence=None, ai_file=ai_file)

# --- Text input: processes on submit ---
with st.form("ai_text_form", clear_on_submit=True):
    ai_text = st.text_input(
        "Or type a description",
        placeholder="e.g. 'Bought a TV for 650', 'Fixed the sofa leg, paid 30 euros' or 'Which warranties have expired?'",
        key="ai_text_input",
        label_visibility="collapsed"
    )
    text_submit = st.form_submit_button("✨ Process", use_container_width=True, type="primary")
    if text_submit and ai_text.strip():
        run_ai_assistant(sentence=ai_text.strip(), ai_file=None)

st.write("")

# --- Sidebar chat button opens the chat window ---
if chat_clicked:
    chat_dialog()

# ============================================================
# PAGE HEADER + "Add Item" BUTTON (manual add, no AI)
# ============================================================
header_col, button_col = st.columns([5, 0.5])
with header_col:
    st.subheader("Your items")
with button_col:
    if st.button("➕ Add Item", use_container_width=True):
        st.session_state.pop("extracted_data", None)  # ensure a clean manual form
        add_item_dialog()


# ============================================================
# VIEW / SEARCH / FILTER ITEMS
# ============================================================
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM items WHERE status = 'active' AND user_id = ?", conn, params=(current_user,))
conn.close()

# ---------------- Summary dashboard ----------------
total_items = int(df['quantity'].sum()) if not df.empty else 0
total_value = float((df['price'] * df['quantity']).sum()) if not df.empty else 0.0
if not df.empty:
    warranty_statuses = df['warranty_expiry'].apply(get_warranty_status)
    expiring_count = (warranty_statuses == "Expiring soon (30 days)").sum()  # fixed typo
    expired_count = (warranty_statuses == "Expired").sum()
else:
    expiring_count = 0
    expired_count = 0

conn = get_connection()
scheduled_repairs = pd.read_sql_query(
    """SELECT COUNT(*) as cnt
       FROM repairs r
       JOIN items i ON r.item_id = i.id
       WHERE i.status = 'active'
         AND i.user_id = ?
         AND r.status = 'scheduled'""",
    conn,
    params=(current_user,)
).iloc[0]['cnt']
conn.close()

m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Total Items", total_items)
m2.metric("💰 Total Value", f"€{total_value:,.2f}")
m3.metric("⚠️ Warranty Alerts", expiring_count + expired_count,
          help=f"{expiring_count} expiring soon, {expired_count} expired")
m4.metric("🔧 Scheduled Repairs", int(scheduled_repairs))

st.markdown("---")

if df.empty:
    st.info("No items yet — click 'Add Item' above to get started.")
else:
    search_col, cat_col, warranty_col, sort_col = st.columns([2, 1, 1, 1.2])
    with search_col:
        search_term = st.text_input("🔍 Search by name")
    with cat_col:
        categories = ["All"] + sorted(df['category'].dropna().unique().tolist())
        selected_category = st.selectbox("Category", categories)
    with warranty_col:
        warranty_filter = st.selectbox(
            "Warranty",
            ["All", "Has warranty", "No warranty", "Expired", "Expiring soon (30 days)"]
        )
    with sort_col:
        sort_option = st.selectbox(
            "Sort by",
            ["Name (A-Z)", "Price (High to Low)", "Price (Low to High)",
             "Purchase date (Newest)", "Purchase date (Oldest)", "Warranty expiring soonest"]
        )

    filtered_df = df.copy()
    if search_term:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search_term, case=False, na=False)]
    if selected_category != "All":
        filtered_df = filtered_df[filtered_df['category'] == selected_category]
    if warranty_filter != "All":
        filtered_df = filtered_df[filtered_df['warranty_expiry'].apply(get_warranty_status) == warranty_filter]

    if sort_option == "Name (A-Z)":
        filtered_df = filtered_df.sort_values("name")
    elif sort_option == "Price (High to Low)":
        filtered_df = filtered_df.sort_values("price", ascending=False)
    elif sort_option == "Price (Low to High)":
        filtered_df = filtered_df.sort_values("price", ascending=True)
    elif sort_option == "Purchase date (Newest)":
        filtered_df = filtered_df.sort_values("purchase_date", ascending=False)
    elif sort_option == "Purchase date (Oldest)":
        filtered_df = filtered_df.sort_values("purchase_date", ascending=True)
    elif sort_option == "Warranty expiring soonest":
        filtered_df = filtered_df.sort_values("warranty_expiry", ascending=True, na_position="last")

    if filtered_df.empty:
        st.info("No items match your search/filter.")

    items_per_page = 10
    total_items_count = len(filtered_df)
    total_pages = max(1, -(-total_items_count // items_per_page))

    if "current_page" not in st.session_state:
        st.session_state.current_page = 1
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages

    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = filtered_df.iloc[start_idx:end_idx]

    for _, row in page_df.iterrows():
        with st.expander(f"{row['name']} ({row['category']})"):
            edit_key = f"editing_{row['id']}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            if not st.session_state[edit_key]:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Purchase date:** {row['purchase_date']}")
                    purchase = pd.to_datetime(row['purchase_date'])
                    days_owned = (datetime.now() - purchase).days
                    years = days_owned // 365
                    months = (days_owned % 365) // 30
                    st.write(f"**Owned for:** {years} yrs, {months} months")
                    st.write(f"**Price:** {row['price']}")
                    st.write(f"**Store:** {row['store']}")
                with col2:
                    if pd.notna(row['warranty_expiry']):
                        warranty_date = pd.to_datetime(row['warranty_expiry'])
                        days_left = (warranty_date - datetime.now()).days
                        if days_left < 0:
                            warranty_display = f"{row['warranty_expiry']} (Expired!)"
                        else:
                            years_left = days_left // 365
                            months_left = (days_left % 365) // 30
                            if years_left > 0:
                                time_left = f"{years_left} yrs, {months_left} months left"
                            elif months_left > 0:
                                time_left = f"{months_left} months left"
                            else:
                                time_left = f"{days_left} days left"
                            warranty_display = f"{row['warranty_expiry']} ({time_left})"
                    else:
                        warranty_display = "No warranty"
                    st.write(f"**Warranty expiry:** {warranty_display}")
                    st.write(f"**Quantity:** {row['quantity']}")

                # ---------------- Repair history ----------------
                st.markdown("---")
                st.markdown("**🔧 Repair & Maintenance History**")

                conn = get_connection()
                repairs_df = pd.read_sql_query(
                    "SELECT * FROM repairs WHERE item_id = ? ORDER BY repair_date DESC",
                    conn, params=(row['id'],)
                )
                conn.close()

                if repairs_df.empty:
                    st.caption("No repairs logged yet.")
                else:
                    for _, repair in repairs_df.iterrows():
                        with st.container(border=True):
                            complete_key = f"completing_{repair['id']}"
                            if complete_key not in st.session_state:
                                st.session_state[complete_key] = False

                            if not st.session_state[complete_key]:
                                rcol1, rcol2, rcol3, rcol4 = st.columns([2, 2, 1, 0.2])
                                with rcol1:
                                    st.markdown(f"**🗓️ {repair['repair_date']}**")
                                    if pd.notna(repair['description']) and repair['description']:
                                        st.write(repair['description'])
                                with rcol2:
                                    if pd.notna(repair['repairer_name']) and repair['repairer_name']:
                                        st.write(f"👤 {repair['repairer_name']}")
                                    if pd.notna(repair['repairer_contact']) and repair['repairer_contact']:
                                        st.write(f"📞 {repair['repairer_contact']}")
                                with rcol3:
                                    if pd.notna(repair['cost']) and repair['cost'] > 0:
                                        st.write(f"€{repair['cost']}")
                                    if repair['status'] == "completed":
                                        st.success("✅ Completed")
                                    else:
                                        st.warning("🕒 Scheduled")
                                with rcol4:
                                    if st.button("🗑️", key=f"delete_repair_{repair['id']}"):
                                        conn = get_connection()
                                        cursor = conn.cursor()
                                        cursor.execute("DELETE FROM repairs WHERE id = ?", (repair['id'],))
                                        conn.commit()
                                        conn.close()
                                        st.toast("Repair record deleted 🗑️")
                                        st.rerun()

                                if pd.notna(repair['notes']) and repair['notes']:
                                    st.caption(f"📝 {repair['notes']}")

                                if repair['status'] == "scheduled":
                                    if st.button("✅ Mark as completed", key=f"complete_btn_{repair['id']}"):
                                        st.session_state[complete_key] = True
                                        st.rerun()
                            else:
                                st.markdown("**Complete this repair**")
                                with st.form(f"complete_form_{repair['id']}"):
                                    cc1, cc2 = st.columns(2)
                                    with cc1:
                                        final_date = st.date_input(
                                            "Completion date",
                                            value=pd.to_datetime(repair['repair_date'])
                                        )
                                        final_description = st.text_input(
                                            "Description", value=repair['description'] or ""
                                        )
                                        final_cost = st.number_input(
                                            "Cost", min_value=0.0, step=1.0,
                                            value=float(repair['cost']) if pd.notna(repair['cost']) else 0.0
                                        )
                                    with cc2:
                                        final_name = st.text_input(
                                            "Repairer name", value=repair['repairer_name'] or ""
                                        )
                                        final_contact = st.text_input(
                                            "Repairer contact", value=repair['repairer_contact'] or ""
                                        )
                                    final_notes = st.text_area(
                                        "Notes", value=repair['notes'] or ""
                                    )
                                    fc1, fc2 = st.columns(2)
                                    with fc1:
                                        confirm_complete = st.form_submit_button("✅ Save as Completed")
                                    with fc2:
                                        cancel_complete = st.form_submit_button("Cancel")

                                    if confirm_complete:
                                        conn = get_connection()
                                        cursor = conn.cursor()
                                        cursor.execute("""
                                            UPDATE repairs
                                            SET repair_date=?, description=?, cost=?, repairer_name=?,
                                                repairer_contact=?, notes=?, status='completed'
                                            WHERE id=?
                                        """, (str(final_date), final_description, final_cost,
                                              final_name, final_contact, final_notes, repair['id']))
                                        conn.commit()
                                        conn.close()
                                        st.session_state[complete_key] = False
                                        st.toast("Repair marked as completed! ✅")
                                        st.rerun()

                                    if cancel_complete:
                                        st.session_state[complete_key] = False
                                        st.rerun()

                with st.expander("➕ Add a repair record manually"):
                    with st.form(f"repair_form_{row['id']}"):
                        r_col1, r_col2 = st.columns(2)
                        with r_col1:
                            repair_date = st.date_input("Repair date", key=f"rdate_{row['id']}")
                            description = st.text_input("Description", key=f"rdesc_{row['id']}")
                            cost = st.number_input("Cost", min_value=0.0, step=1.0, key=f"rcost_{row['id']}")
                        with r_col2:
                            repairer_name = st.text_input("Repairer name", key=f"rname_{row['id']}")
                            repairer_contact = st.text_input("Repairer contact", key=f"rcontact_{row['id']}")
                            status = st.selectbox("Status", ["completed", "scheduled"], key=f"rstatus_{row['id']}")
                        notes = st.text_area("Notes (optional)", key=f"rnotes_{row['id']}")
                        repair_submitted = st.form_submit_button("Save repair")

                        if repair_submitted:
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO repairs (item_id, repair_date, description, cost, repairer_name, repairer_contact, status, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (row['id'], str(repair_date), description, cost, repairer_name, repairer_contact, status, notes))
                            conn.commit()
                            conn.close()
                            st.toast("Repair record added! 🔧")
                            st.rerun()
                # ---------------- End of repairs ----------------

                # ---------------- Documents ----------------
                st.markdown("---")
                st.markdown("**📄 Documents (Receipts, Manuals, Photos)**")

                conn = get_connection()
                docs_df = pd.read_sql_query(
                    "SELECT * FROM documents WHERE item_id = ? ORDER BY uploaded_date DESC",
                    conn, params=(row['id'],)
                )
                conn.close()

                if docs_df.empty:
                    st.caption("No documents uploaded yet.")
                else:
                    for _, doc in docs_df.iterrows():
                        with st.container(border=True):
                            dcol1, dcol2, dcol3 = st.columns([2, 2, 0.5])
                            with dcol1:
                                st.write(f"📎 **{doc['doc_type']}**")
                                st.caption(doc['file_name'])
                            with dcol2:
                                if os.path.exists(doc['file_path']):
                                    with open(doc['file_path'], "rb") as f:
                                        st.download_button(
                                            "⬇️ Download", f, file_name=doc['file_name'], key=f"download_{doc['id']}"
                                        )
                            with dcol3:
                                if st.button("🗑️", key=f"delete_doc_{doc['id']}"):
                                    if os.path.exists(doc['file_path']):
                                        os.remove(doc['file_path'])
                                    conn = get_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM documents WHERE id = ?", (doc['id'],))
                                    conn.commit()
                                    conn.close()
                                    st.toast("Document deleted 🗑️")
                                    st.rerun()

                with st.expander("➕ Upload a document manually"):
                    doc_type = st.selectbox(
                        "Document type",
                        ["Receipt", "Manual", "Photo", "Warranty Card", "Other"],
                        key=f"doctype_{row['id']}"
                    )
                    uploaded_file = st.file_uploader(
                        "Choose a file", type=["pdf", "jpg", "jpeg", "png"], key=f"uploader_{row['id']}"
                    )
                    doc_notes = st.text_area("Notes (optional)", key=f"docnotes_{row['id']}")

                    if st.button("Save document", key=f"savedoc_{row['id']}"):
                        if uploaded_file is not None:
                            file_path = save_uploaded_file(uploaded_file, row['id'])
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO documents (item_id, doc_type, file_path, file_name, uploaded_date, notes)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (row['id'], doc_type, file_path, uploaded_file.name,
                                  str(pd.Timestamp.today().date()), doc_notes))
                            conn.commit()
                            conn.close()
                            st.toast(f"'{uploaded_file.name}' uploaded successfully! 📄")
                            st.rerun()
                        else:
                            st.warning("Please choose a file first.")
                # ---------------- End of documents ----------------

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✏️ Edit item", key=f"edit_btn_{row['id']}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                with btn_col2:
                    if st.button("🗑️ Remove item", key=f"remove_{row['id']}"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE items SET status = 'removed', removed_date = ? WHERE id = ?",
                            (str(pd.Timestamp.today().date()), row['id'])
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()

            else:
                had_warranty = pd.notna(row['warranty_expiry'])
                new_has_warranty = st.checkbox(
                    "This item has a warranty", value=had_warranty, key=f"warranty_check_{row['id']}"
                )
                with st.form(f"edit_form_{row['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Item name", value=row['name'])
                        new_category = st.text_input("Category", value=row['category'])
                        new_purchase_date = st.date_input("Purchase date", value=pd.to_datetime(row['purchase_date']))
                        new_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(row['quantity']))
                    with col2:
                        new_price = st.number_input("Price", min_value=0.0, step=1.0, value=float(row['price']))
                        new_store = st.text_input("Store", value=row['store'])
                        if new_has_warranty:
                            new_warranty = st.date_input(
                                "Warranty expiry",
                                value=pd.to_datetime(row['warranty_expiry']) if had_warranty else pd.Timestamp.today()
                            )
                        else:
                            new_warranty = None

                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        save_clicked = st.form_submit_button("💾 Save changes")
                    with cancel_col:
                        cancel_clicked = st.form_submit_button("Cancel")

                    if save_clicked:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE items
                            SET name=?, category=?, purchase_date=?, price=?, store=?, warranty_expiry=?, quantity=?
                            WHERE id=?
                        """, (new_name, new_category, str(new_purchase_date), new_price, new_store,
                              str(new_warranty) if new_warranty else None, new_quantity, row['id']))
                        conn.commit()
                        conn.close()
                        st.session_state[edit_key] = False
                        st.rerun()

                    if cancel_clicked:
                        st.session_state[edit_key] = False
                        st.rerun()

    st.divider()
    nav_col1, nav_col2, nav_col3 = st.columns([1, 6, 1])
    with nav_col1:
        if st.button("⬅️ Previous", disabled=(st.session_state.current_page <= 1), use_container_width=True):
            st.session_state.current_page -= 1
            st.rerun()
    with nav_col2:
        st.markdown(
            f"<div style='text-align:center; padding-top: 6px;'>Page {st.session_state.current_page} of {total_pages} "
            f"({total_items_count} items)</div>",
            unsafe_allow_html=True
        )
    with nav_col3:
        if st.button("Next ➡️", disabled=(st.session_state.current_page >= total_pages), use_container_width=True):
            st.session_state.current_page += 1
            st.rerun()