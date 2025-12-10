# app5.py
"""
PECD Public Partner Search Tool - Combined PECD + EDI Data
Run: streamlit run app.py
"""

from io import BytesIO
from msal import ConfidentialClientApplication
import json
import pandas as pd
import requests
import streamlit as st
import uuid

# -----------------------------
# App Configuration
# -----------------------------
st.set_page_config(page_title="PECD Public Partner Search Tool", layout="wide")

# 1️⃣ Load secrets safely (replace with Streamlit secrets)
TENANT_ID = st.secrets["TENANT_ID"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
ALLOWED_EMAILS = st.secrets["ALLOWED_EMAILS"]  # list of allowed emails
SCOPE = ["User.Read"]

# -----------------------------
# 2️⃣ Initialize MSAL ConfidentialClientApplication
# -----------------------------
msal_app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}"
)

# -----------------------------
# Prevent re-redeeming the code (store token_result in session_state)
# -----------------------------
query_params = st.experimental_get_query_params()

if "token_result" not in st.session_state:
    if "code" not in query_params:
        st.title("🔐 Public Partner Portal Login")
        auth_url = msal_app.get_authorization_request_url(
            scopes=SCOPE,
            redirect_uri=REDIRECT_URI,
            state=str(uuid.uuid4()),
            prompt="select_account"
        )
        st.markdown(
            f'<a href="{auth_url}" style="font-size:20px; padding:10px 20px; '
            f'background:#2F80ED; color:white; border-radius:8px; text-decoration:none;">'
            f'Sign in with Microsoft</a>',
            unsafe_allow_html=True
        )
        st.stop()

    # Code exists: redeem once
    code = query_params["code"][0]
    token_result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )
    st.session_state["token_result"] = token_result
else:
    token_result = st.session_state["token_result"]

# -----------------------------
# Check token + email
# -----------------------------
if "access_token" not in token_result:
    st.error("❌ Authentication failed.")
    st.json(token_result)
    st.stop()

email = token_result["id_token_claims"].get("preferred_username")
st.session_state["user_email"] = email

if email not in ALLOWED_EMAILS:
    st.error("❌ You do not have permission to access this tool.")
    st.stop()

# --------------------------------
# Helper functions
# --------------------------------
@st.cache_data
def load_excel_from_url(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return pd.read_excel(BytesIO(r.content), engine="openpyxl")
    except Exception as e:
        st.error(f"Failed to load {url}: {e}")
        return None

def normalize_cols(df):
    """Return df and a col_map mapping lowercase->original name"""
    df = df.rename(columns=lambda c: str(c).strip())
    col_map = {c.lower().strip(): c for c in df.columns}
    return df, col_map

def get_col(col_map, names):
    """Return first matching column name (original case) from col_map by testing names list (lowercased)."""
    for n in names:
        key = n.lower().strip()
        if key in col_map:
            return col_map[key]
    return None

def safe_to_int(x):
    try:
        return int(x)
    except:
        return None

def filter_dataframe(d, filters):
    """Apply filters to dataframe d and return filtered df."""
    dfc = d.copy()

    # --- MULTI-DISEASE FILTER ---
    if filters['disease_area'] and filters['disease_area'] != "Any":
        keyword = str(filters['disease_area']).lower().strip()
        if filters['disease_cols']:
            mask = pd.Series(False, index=dfc.index)
            for col in filters['disease_cols']:
                mask = mask | dfc[col].astype(str).str.lower().str.strip().str.contains(keyword, na=False)
            dfc = dfc[mask]

    # --- Gender ---
    if filters.get('gender') and filters['gender'] != "Any" and filters.get('gender_col'):
        dfc = dfc[dfc[filters['gender_col']].astype(str).str.lower().str.strip() == filters['gender'].lower().strip()]

    # --- Ethnicity ---
    if filters.get('ethnicity') and filters['ethnicity'] != "Any" and filters.get('ethnicity_col'):
        dfc = dfc[dfc[filters['ethnicity_col']].astype(str).str.lower().str.strip() == filters['ethnicity'].lower().strip()]

    # --- Carer ---
    if filters.get('carer') and filters['carer'] != "Any" and filters.get('carer_col'):
        dfc = dfc[dfc[filters['carer_col']].astype(str).str.lower().str.strip() == filters['carer'].lower().strip()]

    # Age filter
    min_age = filters.get('min_age')
    max_age = filters.get('max_age')

    if min_age is not None and max_age is not None:
        if (min_age == 0 and max_age == 0):
            # treat as not filtering by age
            pass
        else:
            if max_age < min_age:
                st.error("⚠️ Max Age cannot be less than Min Age.")
                return dfc
            if filters.get('age_col'):
                # convert to numeric temporarily
                numeric_col = filters['age_col'] + "_num_temp"
                dfc[numeric_col] = pd.to_numeric(dfc[filters['age_col']], errors='coerce')
                dfc = dfc[dfc[numeric_col].b_]()]()
