from flask import Flask, request, render_template
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ---- Helper: Query database ----
def query_db(query, args=(), one=False):
    conn = sqlite3.connect("participants.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (rows[0] if rows else None) if one else rows


# ---- Search Route ----
@app.route('/', methods=['GET', 'POST'])
def search():
    results = []

    if request.method == 'POST':
        disease = request.form.get("disease")
        gender = request.form.get("gender")
        min_age = request.form.get("min_age")
        max_age = request.form.get("max_age")
        name_query = request.form.get("name")
        keyword = request.form.get("keyword")

        # --- Build the query dynamically ---
        sql = """
            SELECT Name, "Email Id", "Disease Experience", "Year of Birth",
                   "Which of the following best describes your gender?" as Gender
            FROM participants
            WHERE 1=1
        """
        params = []

        # Filter by Disease Experience
        if disease and disease != "Any":
            sql += " AND `Disease Experience` LIKE ?"
            params.append(f"%{disease}%")

        # Filter by Gender
        if gender and gender != "Any":
            sql += " AND `Which of the following best describes your gender?` = ?"
            params.append(gender)

        # Age Filter
        current_year = datetime.now().year
        if min_age:
            sql += " AND ({} - `Year of Birth`) >= ?".format(current_year)
            params.append(int(min_age))

        if max_age:
            sql += " AND ({} - `Year of Birth`) <= ?".format(current_year)
            params.append(int(max_age))

        # Search by Name
        if name_query:
            sql += " AND Name LIKE ?"
            params.append(f"%{name_query}%")

        # Keyword Search (matches any textual field)
        if keyword:
            sql += " AND (`Disease Experience` LIKE ? OR Name LIKE ?)"
            params.append(f"%{keyword}%")
            params.append(f"%{keyword}%")

        # Execute query
        results = query_db(sql, params)

    return render_template("search.html", results=results)
