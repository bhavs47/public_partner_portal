# app4.py
"""
Public Partner Search Tool - Streamlit app
Save as app.py and run: streamlit run app.py
"""
from io import BytesIO
#from msal import PublicClientApplication
from msal import ConfidentialClientApplication
import json
import pandas as pd
import requests
import streamlit as st
import msal
import uuid

# App Configuration
# -----------------------------
st.set_page_config(page_title="PECD Public Partner Search Tool", layout="wide")

# 1️⃣ Load secrets safely
# -----------------------------
TENANT_ID = st.secrets["TENANT_ID"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
ALLOWED_EMAILS = st.secrets["ALLOWED_EMAILS"]  # This should be a list of emails
SCOPE = ["User.Read"]

# -----------------------------
# 2️⃣ Initialize MSAL PublicClientApplication
# -----------------------------
app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    #authority=AUTHORITY
    authority=f"https://login.microsoftonline.com/{TENANT_ID}"
)

# -----------------------------
# Prevent re-redeeming the code
# -----------------------------
query_params = st.experimental_get_query_params()

if "token_result" not in st.session_state:

    # No code yet → show login button
    if "code" not in query_params:
        st.title("🔐 Public Partner Portal Login")

        auth_url = app.get_authorization_request_url(
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

    # Code exists → redeem it ONE TIME
    code = query_params["code"][0]
    token_result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

    # Store token so Streamlit won’t redeem again
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

# --- Helper functions ---
@st.cache_data
def load_dataframe(uploaded_file):
    if uploaded_file is None:
        return None
    fname = uploaded_file.name.lower()
    try:
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return None
    return df

def normalize_cols(df):
    # Lowercase column names and strip spaces so user can have different column names
    df = df.rename(columns=lambda c: str(c).strip())
    col_map = {}
    for c in df.columns:
        lc = c.lower().strip()
        col_map[lc] = c
    return df, col_map

def get_col(df, col_map, names):
    # names: list of possible names e.g. ['name','full_name']
    for n in names:
        if n in col_map:
            return col_map[n]
    return None

def safe_to_int(x):
    try:
        return int(x)
    except:
        return None


def filter_dataframe(df, filters):

    d = df.copy()

    # --- MULTI-DISEASE FILTER ---
    if filters['disease_area'] and filters['disease_area'] != "Any":
        keyword = filters['disease_area'].lower()
        disease_match = False

        for col in filters['disease_cols']:
            mask = d[col].astype(str).str.lower().str.strip().str.contains(keyword, na=False)
            disease_match = disease_match | mask

        d = d[disease_match]

    # --- Gender ---
    if filters['gender'] != "Any" and filters['gender_col']:
        before = len(d)
        d = d[d[filters['gender_col']].astype(str).str.lower().str.strip() == filters['gender'].lower().strip()]

    # --- Ethnicity ---
    if filters['ethnicity'] != "Any" and filters['ethnicity_col']:
        before = len(d)
        d = d[d[filters['ethnicity_col']].astype(str).str.lower().str.strip() == filters['ethnicity'].lower().strip()]

    # Age filter
    min_age = filters['min_age']
    max_age = filters['max_age']

    # CASE 1: Age not entered → skip filtering
    # (Assuming empty age inputs become 0 — adjust if needed)
    if (min_age == 0 and max_age == 0) or (min_age is None and max_age is None):
        # No age filter — return other filters' results
        pass  # do nothing and continue with other filters

    else:
        # CASE 2: Invalid range → show message (no crash)
        if max_age < min_age:
            st.error("⚠️ Max Age cannot be less than Min Age.")
            return d  # return unfiltered (except for other filters already applied)

        # CASE 3: Valid range → apply age filter
        if filters['age_col']:
            d[filters['age_col'] + "_num"] = pd.to_numeric(
                d[filters['age_col']], errors='coerce'
            )

            d = d[
                d[filters['age_col'] + "_num"].between(
                    min_age, max_age, inclusive='both'
                )
            ]

            d.drop(columns=[filters['age_col'] + "_num"], inplace=True)

    # Name search
    if filters['name_search']:
        before = len(d)
        d = d[d[filters['name_col']].astype(str).str.contains(filters['name_search'], case=False, na=False)]
        #debug_msgs.append(f"Name search removed {before - len(d)} rows")

    return d


def sample_dataframe():
    data = [
        {"name": "Alice Smith", "email": "alice@example.com", "disease1": "Diabetes", "disease2": "", "age": 34, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Bob Jones", "email": "bob@example.com", "disease1": "Cancer", "disease2": "Heart Disease", "age": 45, "gender": "Male", "ethnicity": "Black", "expertise": "patient advocacy"},
        {"name": "Cathy Brown", "email": "cathy@example.com", "disease1": "Cancer", "disease2": "", "age": 52, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Daniel Green", "email": "daniel@example.com", "disease1": "Diabetes", "disease2": "Arthritis", "age": 60, "gender": "Male", "ethnicity": "Asian", "expertise": "research"},
    ]
    return pd.DataFrame(data)



# After successful authentication
claims = token_result.get("id_token_claims", {})

user_email = claims.get("preferred_username", "Unknown")
user_name = claims.get("name", "Unknown")

# Displaying the app header with user info
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

# Raw GitHub URL (make sure it ends with .xlsx)
dataset_url = "https://raw.githubusercontent.com/bhavs47/public_partner_portal/main/Database.xlsx"

try:
    # Download the file content
    response = requests.get(dataset_url)
    response.raise_for_status()  # ensure download succeeded

    # Read Excel from bytes
    df = pd.read_excel(BytesIO(response.content), engine="openpyxl")
    #st.success("Dataset already loaded successfully!")

except requests.exceptions.RequestException as e:
    st.error(f"Failed to download file: {e}")
except ValueError as e:
    st.error(f"Failed to read Excel file: {e}")


# Adjust the index to start from 1 instead of 0
df.index = df.index + 1
    
def load_dataframe_from_github(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content), engine="openpyxl")
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to download file: {e}")
        return None
    except ValueError as e:
        st.error(f"Failed to read Excel file: {e}")
        return None

# Load the dataset
df = load_dataframe_from_github(dataset_url)
if df is None:
    st.stop()  # stop the app if loading failed

# normalize columns and detect important columns
df, col_map = normalize_cols(df)

# --- Automatically detect disease columns ---
disease_cols = [
    "1st Disease Experience",
    "2nd Disease Experience",
    "3rd Disease Experience",
    "4th Disease Experience",
    "5th Disease Experience"
]

disease_cols = [col for col in df.columns if "Disease Experience" in col]

# Guess columns (common names)
name_col = get_col(df, col_map, ['name'])
email_col = get_col(df, col_map, ['email id'])
age_col = get_col(df, col_map, ['age'])
disability_col = get_col(df, col_map, ['do you consider yourself to be a disabled person?'])
physical_col = get_col(df, col_map, ['do you have any physical or mental health conditions or illness lasting or expected to last for 12 months or more?'])
ethnicity_col = get_col(df, col_map, ['what is your ethnic group? choose one option that best describes your ethnic group or background?'])
religion_col = get_col(df, col_map, ['what is your religion?'])
gender_col = get_col(df, col_map, ['what is your sex?'])
transgender_col = get_col(df, col_map, ['do you identify as trans?'])
sexualorientation_col = get_col(df, col_map, ['which of the following best describes your sexual orientation?'])
carer_col = get_col(df, col_map, ['do you have any caring responsibility?'])
    
# Ensure required columns exist (at least name & email)
if not name_col or not email_col:
    st.error("Your uploaded file must include columns for Name and Email (e.g. 'name' and 'email').\n"
             "Detected columns: " + ", ".join(df.columns))
    st.stop()


# ------------------------------------------
# 1. Build filter option lists
# ------------------------------------------
all_diseases = set()
for col in disease_cols:
    all_diseases.update(df[col].dropna().astype(str).unique())

disease_options = ["Any"] + sorted(all_diseases)

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

# ------------------------------------------
# Reset function for Clear button
# ------------------------------------------
def reset_filters():
    for k, v in DEFAULT_FILTERS.items():
        st.session_state[k] = v

# ------------------------------------------
# 3. UI Widgets (now using consistent keys)
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

g1, btn1, btn2 = st.columns([2,1,1])
with g1:
    name_search = st.text_input(
        "Partner Name Search", placeholder="e.g. Alice", key="filter_name_search"
    )

# ------------------------------------------
# 4. Buttons
# ------------------------------------------

with btn1:
    st.markdown("<div style='margin-top:26px'></div>", unsafe_allow_html=True)
    clear_clicked = st.button("🧹 Clear All Filters", on_click=reset_filters, use_container_width=True)

with btn2:
    st.markdown("<div style='margin-top:26px'></div>", unsafe_allow_html=True)
    do_search = st.button("🔍 Search Partners", use_container_width=True)



# --- Build filters dict ---
filters = {
    'disease_area': selected_disease,
    'disease_cols': disease_cols,

    'gender': selected_gender,
    'gender_col': gender_col,

    'carer': selected_carer,
    'carer_col': carer_col,

    'ethnicity': selected_ethnicity,
    'ethnicity_col': ethnicity_col,
    
    #'ethnicity': eth_col,
    #'ethnicity_col': ethnicity_col,

    'min_age': min_age_val,
    'max_age': max_age_val,
    'age_col': age_col,

    'name_search': name_search.strip() if name_search else "",
    'name_col': name_col,
}




# --- Filter ---
results = filter_dataframe(df, filters)


# --- Display table ---
display_df = results  

st.write("---")
res1, res2 = st.columns([1,3])

with res1:
    st.markdown(f"**Search Results ({len(display_df)})**")

with res2:
    if len(display_df) > 0:
        csv = display_df.to_csv(index=False).encode('utf-8')
        json_bytes = json.dumps(display_df.to_dict(orient='records'), indent=2).encode('utf-8')

        # --- Two buttons side by side ---
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "Export CSV",
                data=csv,
                file_name="filtered_participants.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col2:
            st.download_button(
                "Export JSON",
                data=json_bytes,
                file_name="filtered_participants.json",
                mime="application/json",
                use_container_width=True
            )

    else:
        st.info("No results match your filters.")

# with res2:
#     if len(display_df) > 0:
#         csv = display_df.to_csv(index=False).encode('utf-8')
#         json_bytes = json.dumps(display_df.to_dict(orient='records'), indent=2).encode('utf-8')

#         st.download_button("Export CSV", data=csv, file_name="filtered_participants.csv", mime="text/csv")
#         st.download_button("Export JSON", data=json_bytes, file_name="filtered_participants.json", mime="application/json")
#     else:
#         st.info("No results match your filters.")
        
#st.dataframe(display_df.reset_index(drop=True), use_container_width=True)
st.dataframe(display_df, use_container_width=True, hide_index=True)


with st.expander("Show Full Data"):
    st.dataframe(df.head(2000), hide_index=True)

st.markdown("---")
st.markdown(
    "Tips: Upload an Excel (.xlsx) or CSV containing Name, Email, and Disease columns. "
    "You can map your own columns above."
)

































































































































