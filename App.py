# app.py
"""
Public Partner Search Tool - Streamlit app
Save as app.py and run: streamlit run app.py
"""
from io import BytesIO
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Public Partner Search Tool", layout="wide")

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
            # let pandas detect excel engine
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
    # disease area
    if filters['disease_area'] and filters['disease_area'] != "Any":
        d = d[d[filters['disease_col']].astype(str).str.lower() == filters['disease_area'].lower()]
    # gender
    if filters['gender'] and filters['gender'] != "Any":
        d = d[d[filters['gender_col']].astype(str).str.lower() == filters['gender'].lower()]
    # ethnicity
    if filters['ethnicity'] and filters['ethnicity'] != "Any":
        d = d[d[filters['ethnicity_col']].astype(str).str.lower() == filters['ethnicity'].lower()]
    # age range
    if filters['age_col'] is not None:
        # convert to numeric, dropna when necessary
        d[filters['age_col'] + "_num"] = pd.to_numeric(d[filters['age_col']], errors='coerce')
        if filters['min_age'] is not None:
            d = d[d[filters['age_col'] + "_num"] >= filters['min_age']]
        if filters['max_age'] is not None:
            d = d[d[filters['age_col'] + "_num"] <= filters['max_age']]
    # name search
    if filters['name_search']:
        mask = d[filters['name_col']].astype(str).str.contains(filters['name_search'], case=False, na=False)
        d = d[mask]
    # expertise search (search across expertise column if exists)
    if filters['expertise_search'] and filters['expertise_col'] is not None:
        mask = d[filters['expertise_col']].astype(str).str.contains(filters['expertise_search'], case=False, na=False)
        d = d[mask]
    # Drop helper numeric age
    if filters['age_col'] is not None and filters['age_col'] + "_num" in d.columns:
        d = d.drop(columns=[filters['age_col'] + "_num"])
    return d

def sample_dataframe():
    # Small sample dataset to demo if user doesn't upload
    data = [
        {"name": "Alice Smith", "email": "alice@example.com", "disease_area": "Diabetes", "age": 34, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Bob Jones", "email": "bob@example.com", "disease_area": "Cancer", "age": 45, "gender": "Male", "ethnicity": "Black", "expertise": "patient advocacy"},
        {"name": "Cathy Brown", "email": "cathy@example.com", "disease_area": "Cancer", "age": 52, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Daniel Green", "email": "daniel@example.com", "disease_area": "Diabetes", "age": 60, "gender": "Male", "ethnicity": "Asian", "expertise": "research"},
    ]
    return pd.DataFrame(data)

# --- UI header / top bar similar to screenshot ---
with st.container():
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown("## Public Partner Search Tool")
        st.markdown("Filter profiles by criteria to find relevant public partners for engagement.")
    with col2:
        st.markdown("")
        # user id placeholder
        with st.container():
            st.write("")
        st.markdown("<div style='background:#e9f0ff;padding:10px;border-radius:8px;text-align:right'>"
                    "<small style='color:#2f6fdb'>User ID: <b>02528882307476498717</b></small>"
                    "</div>", unsafe_allow_html=True)

st.write("---")

# --- Upload area and Manage Data button (Import JSON) ---
st.markdown("### Manage Data / Upload")
u_col1, u_col2 = st.columns([3,1])
with u_col1:
    uploaded_file = st.file_uploader("Upload participants file (Excel .xlsx/.xls or .csv)", type=["xlsx","xls","csv"])
with u_col2:
    # The button here is a placeholder for "Manage Data / Import JSON"
    if st.button("+ Manage Data / Import JSON"):
        st.info("Import JSON action triggered. (Hook this to your import endpoint or JSON parser.)")

# Load dataframe
df = load_dataframe(uploaded_file)
if df is None:
    st.warning("No file uploaded — using a small sample dataset to demo the interface. (Upload your Excel/CSV to use your data.)")
    df = sample_dataframe()

# normalize columns and detect important columns
df, col_map = normalize_cols(df)

# Guess columns (common names)
name_col = get_col(df, col_map, ['name', 'full_name', 'participant_name'])
email_col = get_col(df, col_map, ['email', 'email_address', 'e-mail', 'email id'])
disease_col = get_col(df, col_map, ['disease_area', 'disease', 'condition', 'health_condition','Disease Experience'])
age_col = get_col(df, col_map, ['age', 'years', 'age_years'])
gender_col = get_col(df, col_map, ['gender', 'sex'])
ethnicity_col = get_col(df, col_map, ['ethnicity', 'race', 'ethnic_group'])
expertise_col = get_col(df, col_map, ['expertise', 'keywords', 'areas_of_expertise', 'notes'])

# Ensure required columns exist (at least name & email)
if not name_col or not email_col:
    st.error("Your uploaded file must include columns for Name and Email (e.g. 'name' and 'email').\n"
             "Detected columns: " + ", ".join(df.columns))
    st.stop()

# Prepare filter options (use unique values; add "Any")
disease_options = sorted(df[disease_col].dropna().astype(str).unique())
disease_options = ["Any"] + disease_options
gender_options = sorted(df[gender_col].dropna().astype(str).unique()) if gender_col else []
gender_options = ["Any"] + gender_options if gender_options else ["Any", "Female", "Male", "Other"]
ethnicity_options = sorted(df[ethnicity_col].dropna().astype(str).unique()) if ethnicity_col else []
ethnicity_options = ["Any"] + ethnicity_options

# --- Filter UI (match layout in screenshot) ---
st.markdown("### Search Filters")
f1, f2, f3 = st.columns([2,2,2])
with f1:
    selected_disease = st.selectbox("Health Condition", disease_options)
with f2:
    selected_gender = st.selectbox("Gender", gender_options)
with f3:
    # age inputs in a single row
    min_age, max_age = st.columns([1,1])
    with min_age:
        min_age_val = st.number_input("Min Age", min_value=0, max_value=120, value=25, step=1)
    with max_age:
        max_age_val = st.number_input("Max Age", min_value=0, max_value=120, value=60, step=1)

g1, g2 = st.columns([2,2])
with g1:
    name_search = st.text_input("Partner Name Search", placeholder="e.g. Alice")
with g2:
    expertise_search = st.text_input("Expertise/Keywords Search", placeholder="e.g. clinical trials")

eth_col = st.selectbox("Ethnicity", ethnicity_options)

st.write("")  # spacing
search_col, export_col = st.columns([1,1])
with search_col:
    do_search = st.button("🔍 Search Partners")
with export_col:
    # placeholder for spacing
    st.write("")

# Build filters dict
filters = {
    'disease_area': selected_disease,
    'disease_col': disease_col,
    'gender': selected_gender,
    'gender_col': gender_col,
    'ethnicity': eth_col,
    'ethnicity_col': ethnicity_col,
    'min_age': min_age_val,
    'max_age': max_age_val,
    'age_col': age_col,
    'name_search': name_search.strip() if name_search else "",
    'name_col': name_col,
    'expertise_search': expertise_search.strip() if expertise_search else "",
    'expertise_col': expertise_col
}

# If user hasn't clicked search, still show results (live filtering) unless they prefer explicit click
# We'll run filter whenever the button is clicked OR by default live view
results = filter_dataframe(df, filters)

# Sort and select columns to show
display_cols = [name_col, email_col]
# optionally add more visible columns
for c in [age_col, gender_col, disease_col, ethnicity_col, expertise_col]:
    if c and c not in display_cols:
        display_cols.append(c)
display_df = results[display_cols].rename(columns=lambda x: x)

st.write("---")
# Show results count and table
res1, res2 = st.columns([1,3])
with res1:
    st.markdown(f"**Search Results ({len(display_df)})**")
with res2:
    # Export buttons
    if len(display_df) > 0:
        csv = display_df.to_csv(index=False).encode('utf-8')
        json_bytes = json.dumps(display_df.to_dict(orient='records'), indent=2).encode('utf-8')
        st.download_button("Export CSV", data=csv, file_name="filtered_participants.csv", mime="text/csv")
        st.download_button("Export JSON", data=json_bytes, file_name="filtered_participants.json", mime="application/json")
    else:
        st.info("No results match your filters.")

# Display the dataframe
st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

# Optional: show raw uploaded dataframe in an expander for debugging
with st.expander("Show raw data (first 200 rows)"):
    st.dataframe(df.head(200))

# Footer / notes
st.markdown("---")
st.markdown(
    "Tips: Upload an Excel (.xlsx) or CSV containing at least **name** and **email** columns. "
    "Column names are matched case-insensitively (e.g. 'Name' or 'full_name')."
)
