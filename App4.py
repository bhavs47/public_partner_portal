# app3.py
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
    if filters['age_col']:
        d[filters['age_col'] + "_num"] = pd.to_numeric(d[filters['age_col']], errors='coerce')
        before = len(d)
        d = d[d[filters['age_col'] + "_num"].between(filters['min_age'], filters['max_age'], inclusive='both')]
        d.drop(columns=[filters['age_col'] + "_num"], inplace=True)

    # Name search
    if filters['name_search']:
        before = len(d)
        d = d[d[filters['name_col']].astype(str).str.contains(filters['name_search'], case=False, na=False)]
        debug_msgs.append(f"Name search removed {before - len(d)} rows")

    # Expertise search
    if filters['expertise_search'] and filters['expertise_col']:
        before = len(d)
        d = d[d[filters['expertise_col']].astype(str).str.contains(filters['expertise_search'], case=False, na=False)]

    return d


def sample_dataframe():
    data = [
        {"name": "Alice Smith", "email": "alice@example.com", "disease1": "Diabetes", "disease2": "", "age": 34, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Bob Jones", "email": "bob@example.com", "disease1": "Cancer", "disease2": "Heart Disease", "age": 45, "gender": "Male", "ethnicity": "Black", "expertise": "patient advocacy"},
        {"name": "Cathy Brown", "email": "cathy@example.com", "disease1": "Cancer", "disease2": "", "age": 52, "gender": "Female", "ethnicity": "White", "expertise": "clinical trials"},
        {"name": "Daniel Green", "email": "daniel@example.com", "disease1": "Diabetes", "disease2": "Arthritis", "age": 60, "gender": "Male", "ethnicity": "Asian", "expertise": "research"},
    ]
    return pd.DataFrame(data)


# --- UI Header ---
with st.container():
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown("## Public Partner Search Tool")
        st.markdown("Filter profiles by criteria to find relevant public partners for engagement.")
    with col2:
        st.markdown("<div style='background:#e9f0ff;padding:10px;border-radius:8px;text-align:right'>"
                    "<small style='color:#2f6fdb'>User ID: <b>02528882307476498717</b></small>"
                    "</div>", unsafe_allow_html=True)

st.write("---")


# --- Upload section ---
st.markdown("### Manage Data / Upload")
u_col1, u_col2 = st.columns([3,1])
with u_col1:
    uploaded_file = st.file_uploader("Upload participants file (Excel .xlsx/.xls or .csv)", type=["xlsx","xls","csv"])


# Load file or sample
df = load_dataframe(uploaded_file)
if df is None:
    st.warning("No file uploaded — using a sample dataset for demo.")
    df = sample_dataframe()

# normalize columns and detect important columns
df, col_map = normalize_cols(df)

# Guess columns (common names)
name_col = get_col(df, col_map, ['name'])
email_col = get_col(df, col_map, ['email id'])
age_col = get_col(df, col_map, ['age', 'years', 'age_years'])
gender_col = get_col(df, col_map, ['what is your sex?'])
ethnicity_col = get_col(df, col_map, ['do you have any physical or mental health conditions or illness lasting or expected to last for 12 months or more?'])
expertise_col = get_col(df, col_map, ['expertise', 'keywords', 'areas_of_expertise', 'notes'])
#disease_cols = ['1st Disease Experience','2nd Disease Experience', '3rd Disease Experience', '4th Disease Experience', '5th Disease Experience']

#Select diseases
columns = df.columns.tolist()
disease_cols = st.multiselect("Select ALL Disease / Condition columns", columns)
if len(disease_cols) == 0:
    st.error("Please select at least one Disease/Condition column.")
    st.stop()
    
# Ensure required columns exist (at least name & email)
if not name_col or not email_col:
    st.error("Your uploaded file must include columns for Name and Email (e.g. 'name' and 'email').\n"
             "Detected columns: " + ", ".join(df.columns))
    st.stop()

# --- Build disease options across all selected columns ---
all_diseases = set()
for col in disease_cols:
    all_diseases.update(df[col].dropna().astype(str).unique())

disease_options = ["Any"] + sorted(all_diseases)

gender_options = ["Any"] if not gender_col else ["Any"] + sorted(df[gender_col].dropna().astype(str).unique())
ethnicity_options = ["Any"] if not ethnicity_col else ["Any"] + sorted(df[ethnicity_col].dropna().astype(str).unique())


# --- Filters UI ---
st.markdown("### Search Filters")
f1, f2, f3 = st.columns([2,2,2])

with f1:
    selected_disease = st.selectbox("Health Condition", disease_options)
with f2:
    selected_gender = st.selectbox("Gender", gender_options)
with f3:
    min_age_val = st.number_input("Min Age", min_value=0, max_value=120, value=0)
    max_age_val = st.number_input("Max Age", min_value=0, max_value=120, value=120)

g1, g2 = st.columns([2,2])
with g1:
    name_search = st.text_input("Partner Name Search", placeholder="e.g. Alice")
with g2:
    expertise_search = st.text_input("Expertise/Keywords Search", placeholder="e.g. clinical trials")

eth_col = st.selectbox("Ethnicity", ethnicity_options)

st.write("")
search_col, export_col = st.columns([1,1])
with search_col:
    do_search = st.button("🔍 Search Partners")


# --- Build filters dict ---
filters = {
    'disease_area': selected_disease,
    'disease_cols': disease_cols,

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


# --- Filter ---
results = filter_dataframe(df, filters)


# --- Display table ---
display_cols = [name_col, email_col]
for c in disease_cols + [age_col, gender_col, ethnicity_col, expertise_col]:
    if c and c not in display_cols:
        display_cols.append(c)

display_df = results[display_cols]

st.write("---")
res1, res2 = st.columns([1,3])

with res1:
    st.markdown(f"**Search Results ({len(display_df)})**")

with res2:
    if len(display_df) > 0:
        csv = display_df.to_csv(index=False).encode('utf-8')
        json_bytes = json.dumps(display_df.to_dict(orient='records'), indent=2).encode('utf-8')

        st.download_button("Export CSV", data=csv, file_name="filtered_participants.csv", mime="text/csv")
        st.download_button("Export JSON", data=json_bytes, file_name="filtered_participants.json", mime="application/json")
    else:
        st.info("No results match your filters.")

st.dataframe(display_df.reset_index(drop=True), use_container_width=True)


with st.expander("Show raw data (first 200 rows)"):
    st.dataframe(df.head(200))

st.markdown("---")
st.markdown(
    "Tips: Upload an Excel (.xlsx) or CSV containing Name, Email, and Disease columns. "
    "You can map your own columns above."
)




