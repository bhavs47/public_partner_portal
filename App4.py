# App4.py
"""
PECD Public Partner Search Tool - Combined PECD + EDI Data
Run: streamlit run App4_clean.py
"""

import uuid
import json
from io import BytesIO
from datetime import date

import pandas as pd
import requests
import streamlit as st
from msal import ConfidentialClientApplication

# -----------------------------
# App Configuration
# -----------------------------
st.set_page_config(page_title="PECD Public Partner Search Tool", layout="wide")

# -----------------------------
# Load secrets
# -----------------------------
TENANT_ID = st.secrets["TENANT_ID"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
ALLOWED_EMAILS = st.secrets["ALLOWED_EMAILS"]  # list of allowed emails
SCOPE = ["User.Read"]

# -----------------------------
# Initialize MSAL App
# -----------------------------
msal_app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}"
)

query_params = st.experimental_get_query_params()

# -----------------------------
# Landing Page / Login
# -----------------------------
def show_login_page():
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI,
        state=str(uuid.uuid4()),
        prompt="select_account"
    )

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/University%20of%20Leeds.jpg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            filter: brightness(0.7);
        }}
        .login-container {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 90vh;
            text-align: center;
            color: white;
            animation: fadeIn 1.5s ease-in-out;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .login-button {{
            font-size: 20px;
            padding: 15px 35px;
            background: linear-gradient(90deg, #28a745, #218838);
            color: white;
            border-radius: 10px;
            text-decoration: none;
            font-weight: bold;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .login-button:hover {{
            transform: translateY(-3px);
            box-shadow: 0px 5px 15px rgba(0,0,0,0.3);
        }}
        .hero-title {{ font-size: 3rem; font-weight: 700; margin-bottom: 15px; }}
        .hero-subtitle {{ font-size: 1.5rem; margin-bottom: 30px; }}
        </style>

        <div class="login-container">
            <div class="hero-title">PECD Public Partner Search Tool</div>
            <div class="hero-subtitle">🔐 Patient Engagement in Clinical Development 🧑‍⚕️💬</div>
            <a href="{auth_url}" class="login-button">Sign In</a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.stop()

# -----------------------------
# Sign Out Function
# -----------------------------
def sign_out():
    for key in ["token_result", "user_email", "user_name"]:
        if key in st.session_state:
            st.session_state.pop(key)
    st.experimental_rerun()

# -----------------------------
# Handle Authentication
# -----------------------------
if "token_result" not in st.session_state:
    if "code" not in query_params:
        show_login_page()
    else:
        # redeem authorization code
        code = query_params["code"][0]
        token_result = msal_app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPE,
            redirect_uri=REDIRECT_URI
        )
        st.session_state["token_result"] = token_result

token_result = st.session_state.get("token_result", {})
if "access_token" not in token_result or token_result.get("error") in ["invalid_grant", "bad_token"]:
    st.session_state.pop("token_result", None)
    show_login_page()

# -----------------------------
# Validate User
# -----------------------------
claims = token_result.get("id_token_claims", {})
email = claims.get("preferred_username", "")
name = claims.get("name") or email or "User"
st.session_state["user_email"] = email
st.session_state["user_name"] = name

if email not in ALLOWED_EMAILS:
    st.error("❌ You do not have permission to access this tool.")
    st.stop()

# -----------------------------
# Top-right Sign Out Button
# -----------------------------
st.markdown(
    f"""
    <div style='position: fixed; top: 10px; right: 10px; z-index: 1000;'>
        <a href="#" onclick="window.location.reload();" 
           style='font-size:16px; padding:5px 10px; background:#FF4B4B; color:white; border-radius:5px; text-decoration:none;'>
           Sign Out
        </a>
    </div>
    """,
    unsafe_allow_html=True
)
if st.button("Sign Out"):
    sign_out()

# -----------------------------
# Helper Functions
# -----------------------------
@st.cache_data
def load_excel(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return pd.read_excel(BytesIO(r.content), engine="openpyxl")
    except Exception as e:
        st.error(f"Failed to load {url}: {e}")
        return None

def normalize_cols(df):
    df = df.rename(columns=lambda c: str(c).strip())
    col_map = {c.lower().strip(): c for c in df.columns}
    return df, col_map

def get_col(col_map, names):
    for n in names:
        key = n.lower().strip()
        if key in col_map:
            return col_map[key]
    return None

def filter_dataframe(df, filters):
    dfc = df.copy()
    # Disease
    if filters.get("disease") != "Any":
        keyword = filters["disease"].lower()
        mask = pd.Series(False, index=dfc.index)
        for col in filters["disease_cols"]:
            if col in dfc.columns:
                mask |= dfc[col].astype(str).str.lower().str.contains(keyword, na=False)
        dfc = dfc[mask]
    # Gender
    if filters.get("gender") != "Any" and filters.get("gender_col") in dfc.columns:
        dfc = dfc[dfc[filters["gender_col"]].astype(str).str.lower() == filters["gender"].lower()]
    # Ethnicity
    if filters.get("ethnicity") != "Any" and filters.get("ethnicity_col") in dfc.columns:
        dfc = dfc[dfc[filters["ethnicity_col"]].astype(str).str.lower() == filters["ethnicity"].lower()]
    # Carer
    if filters.get("carer") != "Any" and filters.get("carer_col") in dfc.columns:
        mask = dfc[filters["carer_col"]].astype(str).apply(
            lambda cell: filters["carer"].lower() in [x.strip().lower() for x in str(cell).split(";")]
        )
        dfc = dfc[mask]
    # Sexuality
    if filters.get("sexuality") != "Any" and filters.get("sexuality_col") in dfc.columns:
        dfc = dfc[dfc[filters["sexuality_col"]].astype(str).str.lower() == filters["sexuality"].lower()]
    # Age
    if filters.get("age_col") in dfc.columns:
        numeric_col = filters["age_col"] + "_num_temp"
        dfc[numeric_col] = pd.to_numeric(dfc[filters["age_col"]], errors="coerce")
        dfc = dfc[(dfc[numeric_col] >= filters.get("min_age", 0)) & (dfc[numeric_col] <= filters.get("max_age", 120))]
        dfc.drop(columns=[numeric_col], inplace=True)
    # Name search
    if filters.get("name_search") and filters.get("name_col") in dfc.columns:
        dfc = dfc[dfc[filters["name_col"]].astype(str).str.contains(filters["name_search"], case=False, na=False)]
    return dfc

# -----------------------------
# Load Data
# -----------------------------
PECD_URL = "https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/PECD%20Pool%20Data.xlsx"
EDI_URL = "https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/EDI%20Data.xlsx"

df_pecd = load_excel(PECD_URL)
df_edi = load_excel(EDI_URL)

if df_pecd is None or df_edi is None:
    st.stop()

df_pecd, pecd_map = normalize_cols(df_pecd)
df_edi, edi_map = normalize_cols(df_edi)

# Detect ID columns
id_names = ["id", "participant id", "unique id", "identifier"]
pecd_id_col = next((pecd_map[n] for n in id_names if n in pecd_map), df_pecd.columns[0])
edi_id_col = next((edi_map[n] for n in id_names if n in edi_map), df_edi.columns[0])

# Merge datasets
df_merged = df_pecd.merge(df_edi, left_on=pecd_id_col, right_on=edi_id_col, how="left", suffixes=("", "_EDI"))

df = df_merged.copy()
df.index += 1
df, col_map = normalize_cols(df)

# Auto-detect relevant columns
disease_cols = [c for c in df.columns if "disease experience" in c.lower()]
name_col = get_col(col_map, ['name', 'full name', 'participant name'])
email_col = get_col(col_map, ['email', 'email id', 'email address'])
age_col = get_col(col_map, ['age'])
gender_col = get_col(col_map, ['gender', 'sex'])
ethnicity_col = get_col(col_map, ['ethnic group', 'ethnicity'])
carer_col = get_col(col_map, ['carer', 'caring responsibilities'])
sexuality_col = get_col(col_map, ['sexual orientation'])

if not name_col or not email_col:
    st.error("Merged dataset must include Name and Email columns.")
    st.stop()

# -----------------------------
# Build Filter Options
# -----------------------------
disease_options = ["Any"] + sorted({str(d).strip() for col in disease_cols for d in df[col].dropna().unique()})
gender_options = ["Any"] + sorted(df[gender_col].dropna().unique()) if gender_col else ["Any"]
ethnicity_options = ["Any"] + sorted(df[ethnicity_col].dropna().unique()) if ethnicity_col else ["Any"]
sexuality_options = ["Any"] + sorted(df[sexuality_col].dropna().unique()) if sexuality_col else ["Any"]

# Carer options
carer_options_set = set()
if carer_col:
    for cell in df[carer_col].dropna().astype(str):
        carer_options_set.update([p.strip() for p in cell.split(";") if p.strip()])
    if df[carer_col].isna().any() or df[carer_col].astype(str).str.lower().isin(["none"]).any():
        carer_options_set.add("None")
carer_options = ["Any"] + sorted(carer_options_set)

# -----------------------------
# UI: Filters
# -----------------------------
st.markdown(f"## Welcome, {name}!")
st.markdown("### Search Filters for Public Partners")

col1, col2, col3, col4, col5, col6 = st.columns([2,2,2,2,2,2])
with col1: selected_disease = st.selectbox("Health Condition", disease_options)
with col2: selected_gender = st.selectbox("Gender", gender_options)
with col3:
    min_age = st.number_input("Min Age", min_value=0, max_value=120, value=0)
    max_age = st.number_input("Max Age", min_value=0, max_value=120, value=120)
with col4: selected_carer = st.selectbox("Carer", carer_options)
with col5: selected_ethnicity = st.selectbox("Ethnicity", ethnicity_options)
with col6: selected_sexuality = st.selectbox("Sexuality", sexuality_options)

name_search = st.text_input("Partner Name Search", placeholder="e.g. Alice")
if st.button("Clear All Filters"):
    st.experimental_rerun()

filters = {
    "disease": selected_disease,
    "disease_cols": disease_cols,
    "gender": selected_gender,
    "gender_col": gender_col,
    "ethnicity": selected_ethnicity,
    "ethnicity_col": ethnicity_col,
    "carer": selected_carer,
    "carer_col": carer_col,
    "sexuality": selected_sexuality,
    "sexuality_col": sexuality_col,
    "min_age": min_age,
    "max_age": max_age,
    "age_col": age_col,
    "name_search": name_search,
    "name_col": name_col
}

# -----------------------------
# Filter and Display Results
# -----------------------------
results = filter_dataframe(df, filters)
st.markdown(f"**Search Results ({len(results)})**")

if len(results) > 0:
    csv = results.to_csv(index=False).encode('utf-8')
    json_bytes = json.dumps(results.fillna("").to_dict(orient="records"), indent=2).encode("utf-8")
    col_csv, col_json = st.columns(2)
    with col_csv: st.download_button("Export CSV", data=csv, file_name="filtered_partners.csv")
    with col_json: st.download_button("Export JSON", data=json_bytes, file_name="filtered_partners.json")

st.dataframe(results, use_container_width=True, hide_index=True)

with st.expander("Show Full Data (first 2000 rows)"):
    st.dataframe(df.head(2000), hide_index=True)

st.markdown("---")
st.markdown("Tips: Use the filters above to narrow results. The page merges PECD Pool Data and EDI Data by ID.")
