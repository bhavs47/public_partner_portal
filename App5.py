# app.py
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
                dfc = dfc[dfc[numeric_col].between(min_age, max_age, inclusive='both')]
                dfc.drop(columns=[numeric_col], inplace=True)

    # Name search
    if filters.get('name_search'):
        if filters.get('name_col'):
            dfc = dfc[dfc[filters['name_col']].astype(str).str.contains(filters['name_search'], case=False, na=False)]

    # Expertise search (if column exists)
    if filters.get('expertise_search') and filters.get('expertise_col'):
        dfc = dfc[dfc[filters['expertise_col']].astype(str).str.contains(filters['expertise_search'], case=False, na=False)]

    return dfc

# --------------------------------
# Load & Merge PECD + EDI datasets
# --------------------------------
# Replace these URLs with your repository file paths (raw URLs)
PECD_URL = "https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/PECD.xlsx"  # your PECD file
EDI_URL = "https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/EDI.xlsx"   # your EDI file (update path/name)

# Try to load both files. If your single file contains both sheets, you can adjust this block.
df_pecd = load_excel_from_url(PECD_URL)
df_edi = load_excel_from_url(EDI_URL)

if df_pecd is None:
    st.error("Failed to load PECD Pool Data.")
    st.stop()
if df_edi is None:
    st.error("Failed to load EDI Data.")
    st.stop()

# Normalize columns and build lowercase->original maps
df_pecd, pecd_map = normalize_cols(df_pecd)
df_edi, edi_map = normalize_cols(df_edi)

# Find ID columns in each dataset
# Try many common ID variations
id_names = ["id", "participant id", "unique id", "identifier"]
pecd_id_col = None
edi_id_col = None
for name in id_names:
    if pecd_id_col is None and name in pecd_map:
        pecd_id_col = pecd_map[name]
    if edi_id_col is None and name in edi_map:
        edi_id_col = edi_map[name]

# Fallback: look for first column (if ID really is column A)
if pecd_id_col is None and len(df_pecd.columns) > 0:
    pecd_id_col = df_pecd.columns[0]
if edi_id_col is None and len(df_edi.columns) > 0:
    edi_id_col = df_edi.columns[0]

if pecd_id_col is None or edi_id_col is None:
    st.error("Could not find ID column in one or both datasets. Ensure both have an ID column.")
    st.stop()

# Merge on ID (use left join so we preserve PECD rows)
try:
    df_merged = df_pecd.merge(df_edi, left_on=pecd_id_col, right_on=edi_id_col, how="left", suffixes=("", "_EDI"))
except Exception as e:
    st.error(f"Error merging datasets: {e}")
    st.stop()

# Reorder columns: PECD columns first, then EDI-only columns
pecd_cols = list(df_pecd.columns)
merged_cols = list(df_merged.columns)
edi_only_cols = [c for c in merged_cols if c not in pecd_cols]

df = df_merged[pecd_cols + edi_only_cols].copy()
df.index = df.index + 1  # make index start at 1 for display

# Build a col_map for the merged df (lowercase->original)
df, col_map = normalize_cols(df)

# --------------------------------
# Auto-detect relevant columns in merged df
# --------------------------------
# disease columns: any column containing "Disease Experience" (case-insensitive)
disease_cols = [c for c in df.columns if "disease experience" in c.lower()]

# best-guess mappings for demographic columns (adjust keys if your exact wording differs)
name_col = get_col(col_map, ['name', 'full name', 'participant name'])
email_col = get_col(col_map, ['email', 'email id', 'email address'])
age_col = get_col(col_map, ['age', 'what is your age'])
year_of_birth_col = get_col(col_map, ['year of birth', 'yob'])
gender_col = get_col(col_map, ['what is your sex?', 'what is your sex', 'sex', 'gender'])
ethnicity_col = get_col(col_map, ['what is your ethnic group?', 'ethnic group', 'ethnicity'])
carer_col = get_col(col_map, ['do you have any caring responsibility?', 'do you have any caring responsibilities?', 'do you have any caring responsibility'])
expertise_col = get_col(col_map, ['expertise', 'expertise/keywords', 'expertise keywords', 'expertise areas'])
# If your EDI uses slightly different strings, update the lists above.

# Ensure required columns exist (at least name & email)
if not name_col or not email_col:
    st.error("Your merged dataset must include columns for Name and Email. Detected columns: " + ", ".join(df.columns))
    st.stop()

# ------------------------------------------
# 1. Build filter option lists
# ------------------------------------------
all_diseases = set()
for col in disease_cols:
    all_diseases.update(df[col].dropna().astype(str).unique())

disease_options = ["Any"] + sorted([d for d in all_diseases if str(d).strip() != ""])
gender_options = ["Any"] if not gender_col else ["Any"] + sorted(df[gender_col].dropna().astype(str).unique())
carer_options = ["Any"] if not carer_col else ["Any"] + sorted(df[carer_col].dropna().astype(str).unique())
ethnicity_options = ["Any"] if not ethnicity_col else ["Any"] + sorted(df[ethnicity_col].dropna().astype(str).unique())

# ------------------------------------------
# 2. Filter defaults (MASTER DEFINITION)
# ------------------------------------------
DEFAULT_FILTERS = {
    "filter_selected_disease": "Any",
    "filter_selected_gender": "Any",
    "filter_min_age": 0,
    "filter_max_age": 120,
    "filter_selected_carer": "Any",
    "filter_selected_ethnicity": "Any",
    "filter_name_search": "",
    "filter_expertise_search": "",
}

# Initialize missing keys only
for k, v in DEFAULT_FILTERS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Reset function for Clear button (called via on_click)
def reset_filters():
    for k, v in DEFAULT_FILTERS.items():
        st.session_state[k] = v

# ------------------------------------------
# PAGE HEADER (show user)
# ------------------------------------------
claims = token_result.get("id_token_claims", {})
user_name = claims.get("name", "Unknown")
user_email = claims.get("preferred_username", "Unknown")

with st.container():
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown("## PECD Public Partner Search Tool")
        st.markdown("Filter profiles by criteria to find relevant public partners for engagement.")
    with col2:
        st.markdown(
            f"""
            <div style='background:#e9f0ff;padding:10px;border-radius:8px;text-align:right'>
                <small style='color:#2f6fdb'>Signed in as: <b>{user_name}</b></small><br>
                <small style='color:#2f6fdb'>Email: <b>{user_email}</b></small>
            </div>
            """,
            unsafe_allow_html=True
        )

st.write("---")

# ------------------------------------------
# 3. UI Widgets (consistent keys)
# ------------------------------------------
st.markdown("### Search Filters for Public Partners")
f1, f2, f3, f4, f5 = st.columns([2,2,2,2,2])

with f1:
    selected_disease = st.selectbox(
        "Health Condition", disease_options, key="filter_selected_disease"
    )
with f2:
    selected_gender = st.selectbox(
        "Gender", gender_options, key="filter_selected_gender"
    )
with f3:
    min_age_val = st.number_input(
        "Min Age", min_value=0, max_value=120, key="filter_min_age"
    )
    max_age_val = st.number_input(
        "Max Age", min_value=0, max_value=120, key="filter_max_age"
    )
with f4:
    selected_carer = st.selectbox(
        "Carer", carer_options, key="filter_selected_carer"
    )
with f5:
    selected_ethnicity = st.selectbox(
        "Ethnicity", ethnicity_options, key="filter_selected_ethnicity"
    )

# One-row: name input + clear + search buttons aligned with input
g1, btn1, btn2 = st.columns([3,1,1])
with g1:
    # Use a caption to reduce vertical height (helps alignment)
    st.caption("Partner Name Search")
    name_search = st.text_input("", placeholder="e.g. Alice", key="filter_name_search")
with btn1:
    st.button("🧹 Clear All Filters", on_click=reset_filters, use_container_width=True)
with btn2:
    do_search = st.button("🔍 Search Partners", use_container_width=True)

# Expertse search on its own row
expertise_search = st.text_input("Expertise/Keywords Search", placeholder="e.g. clinical trials", key="filter_expertise_search")

# ------------------------------------------
# Build filters dict (feeding into filter_dataframe)
# ------------------------------------------
filters = {
    'disease_area': st.session_state.get("filter_selected_disease", "Any"),
    'disease_cols': disease_cols,

    'gender': st.session_state.get("filter_selected_gender", "Any"),
    'gender_col': gender_col,

    'carer': st.session_state.get("filter_selected_carer", "Any"),
    'carer_col': carer_col,

    'ethnicity': st.session_state.get("filter_selected_ethnicity", "Any"),
    'ethnicity_col': ethnicity_col,

    'min_age': st.session_state.get("filter_min_age", 0),
    'max_age': st.session_state.get("filter_max_age", 120),
    'age_col': age_col,

    'name_search': st.session_state.get("filter_name_search", "").strip(),
    'name_col': name_col,

    'expertise_search': st.session_state.get("filter_expertise_search", "").strip(),
    'expertise_col': expertise_col
}

# ------------------------------------------
# Apply filtering
# ------------------------------------------
results = filter_dataframe(df, filters)
display_df = results.copy()

# ------------------------------------------
# Display results + export buttons
# ------------------------------------------
st.write("---")
res1, res2 = st.columns([1,3])
with res1:
    st.markdown(f"**Search Results ({len(display_df)})**")
with res2:
    if len(display_df) > 0:
        csv = display_df.to_csv(index=False).encode('utf-8')
        json_bytes = json.dumps(display_df.to_dict(orient='records'), indent=2).encode('utf-8')

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Export CSV", data=csv, file_name="filtered_participants.csv", mime="text/csv", use_container_width=True)
        with col2:
            st.download_button("Export JSON", data=json_bytes, file_name="filtered_participants.json", mime="application/json", use_container_width=True)
    else:
        st.info("No results match your filters.")

# Show the filtered table
st.dataframe(display_df, use_container_width=True, hide_index=True)

with st.expander("Show Full Data (first 2000 rows)"):
    st.dataframe(df.head(2000), hide_index=True)

st.markdown("---")
st.markdown(
    "Tips: The page merges PECD Pool Data (left) and EDI Data (appended columns) by ID. "
    "Use the filters above to narrow results. You may replace the dataset URLs at the top of the file."
)
