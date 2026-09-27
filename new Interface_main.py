import os
import sqlite3
import tkinter as tk
from tkinter import ttk

# ----- Color Palette (kept from the original design: warm and calming)
BG_MAIN = "#F4F1E8"
BG_ACCENT = "#E4E9DD"
GREEN_DARK = "#6B8F71"
GREEN_LIGHT = "#A8C3A0"
TEXT_DARK = "#4A4238"
TERRACOTTA = "#C97B5C"

# status colors for results list, keyed by score bucket
# (thresholds match the web frontend's score bands: >=65 green, 35-64 amber, <35 red)
STATUS_COLORS = {
    "Verified - Good Signal": "#4C7A52",
    "Unverified / Mixed": "#B8863B",
    "Poor Signal / Issue Found": "#A3514D",
}

# ----- Real data source: the shared Unghosted database, not a standalone CSV.
# This file lives at the project root, so the db is at backend/unghosted.db
# relative to it.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "unghosted.db")

FALLBACK_PROVIDERS = [
    {
        "id": None, "name": "Sample Provider (no database found)", "provider_type": "Facility",
        "specialty": "General Mental Health", "phone": "N/A", "zip_code": "19140",
        "languages": "English", "population_served": "Adults", "telehealth_available": 1,
        "score": 50, "score_reason": "placeholder - run backend/load_providers.py first",
    },
]


def score_bucket(score):
    """Buckets a 0-100 score into the same 3 bands the web frontend uses."""
    if score is None:
        return "Unverified / Mixed"
    if score >= 65:
        return "Verified - Good Signal"
    if score >= 35:
        return "Unverified / Mixed"
    return "Poor Signal / Issue Found"


def load_providers(db_path):
    """
    Reads provider records straight from the shared unghosted.db (the same
    database the FastAPI backend and web frontend use), so this interface
    always reflects real, current verification data instead of a separate
    CSV someone has to keep in sync by hand.
    """
    if not os.path.exists(db_path):
        print(f"Database not found at '{db_path}' - using fallback sample data instead.")
        return FALLBACK_PROVIDERS

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, provider_type, specialty, phone, zip_code, languages, "
        "population_served, telehealth_available, score, score_reason "
        "FROM providers ORDER BY score DESC"
    ).fetchall()
    conn.close()

    providers = []
    for row in rows:
        providers.append({
            "id": row["id"],
            "name": row["name"],
            "provider_type": row["provider_type"] or "",
            "specialty": row["specialty"] or "",
            "phone": row["phone"] or "",
            "zip_code": row["zip_code"] or "",
            "languages": row["languages"] or "",
            "population_served": row["population_served"] or "",
            "telehealth_available": row["telehealth_available"],
            "score": row["score"] if row["score"] is not None else 50,
            "score_reason": row["score_reason"] or "no verification signals yet",
        })
    return providers


def unique_sorted(values):
    return sorted({v.strip() for v in values if v and v.strip()})


def split_multivalue(raw_values):
    """languages / population_served are stored as comma-separated strings;
    this pulls out the individual distinct values for a filter dropdown."""
    out = set()
    for raw in raw_values:
        if not raw:
            continue
        for part in raw.split(","):
            part = part.strip()
            if part:
                out.add(part)
    return sorted(out)


sample_providers = load_providers(DB_PATH)


def on_click():
    label.config(text="Searching...")
    results_listbox.delete(0, tk.END)

    zip_choice = zip_combo.get()
    specialty_choice = specialty_combo.get()
    population_choice = population_combo.get()
    language_choice = language_combo.get()
    telehealth_choice = telehealth_combo.get()
    verification_choice = verification_combo.get()

    matches = []
    for provider in sample_providers:
        if zip_choice not in ("Choose Zip Code", provider["zip_code"]):
            continue
        if specialty_choice not in ("Choose a Specialty", provider["specialty"]):
            continue
        if population_choice != "Choose Population Served" and population_choice not in provider["population_served"]:
            continue
        if language_choice != "Choose a Language" and language_choice not in provider["languages"]:
            continue
        if telehealth_choice == "Telehealth: Yes" and not provider["telehealth_available"]:
            continue
        if telehealth_choice == "Telehealth: No" and provider["telehealth_available"]:
            continue

        bucket = score_bucket(provider["score"])
        if verification_choice not in ("Choose Verification status", "All", bucket):
            continue

        matches.append((provider, bucket))

    if matches:
        label.config(text=f"Found {len(matches)} provider(s):")
        for provider, bucket in matches:
            row_text = (
                f"{provider['name']} - {provider['specialty']} - Zip {provider['zip_code']} - "
                f"Score {provider['score']}/100 - {provider['score_reason']}"
            )
            results_listbox.insert(tk.END, row_text)
            row_index = results_listbox.size() - 1
            row_color = STATUS_COLORS.get(bucket, TEXT_DARK)
            results_listbox.itemconfig(row_index, fg=row_color)
    else:
        label.config(text="No providers match your search.")


def clear_filters():
    zip_combo.set("Choose Zip Code")
    specialty_combo.set("Choose a Specialty")
    population_combo.set("Choose Population Served")
    language_combo.set("Choose a Language")
    telehealth_combo.set("Telehealth: Any")
    verification_combo.set("Choose Verification status")

    results_listbox.delete(0, tk.END)
    label.config(text="How can we help you today?")


# create main window
root = tk.Tk()
root.title("Unghosted - Provider Lookup")
root.geometry("1280x720")
root.configure(bg=BG_MAIN)

style = ttk.Style(root)
style.theme_use("clam")

style.configure(
    "TCombobox",
    fieldbackground=BG_ACCENT,
    background=GREEN_LIGHT,
    foreground=TEXT_DARK,
    arrowcolor=TEXT_DARK,
    padding=4,
)
style.map(
    "TCombobox",
    fieldbackground=[("readonly", BG_ACCENT)],
    background=[("active", GREEN_LIGHT)],
)

label = tk.Label(
    root,
    text="How can we help you today?",
    font=("Georgia", 18, "bold"),
    bg=BG_MAIN,
    fg=GREEN_DARK,
)
label.pack(pady=(30, 20))

dropdown_frame = tk.Frame(root, bg=BG_MAIN)
dropdown_frame.pack(pady=10)

# Zip code (replaces the insurance dropdown - CBH is Medicaid-only, so
# insurance is constant across every listed provider and isn't a useful
# filter here; zip code is what patients actually search by)
zip_options = unique_sorted(p["zip_code"] for p in sample_providers)
zip_combo = ttk.Combobox(dropdown_frame, values=zip_options, state="readonly", width=16)
zip_combo.set("Choose Zip Code")
zip_combo.grid(row=0, column=0, padx=6)

# Specialty
specialty_options = unique_sorted(p["specialty"] for p in sample_providers)
specialty_combo = ttk.Combobox(dropdown_frame, values=specialty_options, state="readonly", width=32)
specialty_combo.set("Choose a Specialty")
specialty_combo.grid(row=0, column=1, padx=6)

# Population served (replaces the old age-range dropdown with the real field)
population_options = split_multivalue(p["population_served"] for p in sample_providers)
population_combo = ttk.Combobox(dropdown_frame, values=population_options, state="readonly", width=22)
population_combo.set("Choose Population Served")
population_combo.grid(row=0, column=2, padx=6)

# Language
language_options = split_multivalue(p["languages"] for p in sample_providers)
language_combo = ttk.Combobox(dropdown_frame, values=language_options, state="readonly", width=18)
language_combo.set("Choose a Language")
language_combo.grid(row=0, column=3, padx=6)

# Telehealth
telehealth_combo = ttk.Combobox(
    dropdown_frame, values=["Telehealth: Any", "Telehealth: Yes", "Telehealth: No"],
    state="readonly", width=16,
)
telehealth_combo.set("Telehealth: Any")
telehealth_combo.grid(row=0, column=4, padx=6)

# Verification status (replaces the static "outcome" dropdown - this is
# now derived live from the score the backend actually computed from real
# phone call outcomes, not a value someone typed into a spreadsheet)
verification_combo = ttk.Combobox(
    dropdown_frame,
    values=["All", "Verified - Good Signal", "Unverified / Mixed", "Poor Signal / Issue Found"],
    state="readonly", width=24,
)
verification_combo.set("Choose Verification status")
verification_combo.grid(row=0, column=5, padx=6)

button_frame = tk.Frame(root, bg=BG_MAIN)
button_frame.pack(pady=25)

button = tk.Button(
    button_frame,
    text="Start search",
    command=on_click,
    bg=TERRACOTTA,
    fg="white",
    activebackground=GREEN_DARK,
    activeforeground="white",
    font=("Georgia", 12, "bold"),
    relief="flat",
    padx=18,
    pady=8,
    cursor="hand2",
)
button.grid(row=0, column=0, padx=8)

clear_button = tk.Button(
    button_frame,
    text="Clear filters",
    command=clear_filters,
    bg=BG_ACCENT,
    fg=TEXT_DARK,
    activebackground=GREEN_LIGHT,
    activeforeground=TEXT_DARK,
    font=("Georgia", 12, "bold"),
    relief="flat",
    padx=18,
    pady=8,
    cursor="hand2",
)
clear_button.grid(row=0, column=1, padx=8)

results_frame = tk.Frame(root, bg=BG_MAIN)
results_frame.pack(pady=10, fill="both", expand=True, padx=40)

results_listbox = tk.Listbox(
    results_frame,
    width=100,
    height=15,
    font=("Georgia", 11),
    bg=BG_ACCENT,
    fg=TEXT_DARK,
    selectbackground=GREEN_LIGHT,
    selectforeground=TEXT_DARK,
    relief="flat",
    highlightthickness=1,
    highlightbackground=GREEN_LIGHT,
    borderwidth=0,
)
results_listbox.pack(side="left", fill="both", expand=True, padx=(0, 0))

results_scrollbar = tk.Scrollbar(results_frame, orient="vertical", command=results_listbox.yview)
results_scrollbar.pack(side="left", fill="y")
results_listbox.config(yscrollcommand=results_scrollbar.set)

if __name__ == "__main__":
    root.mainloop()
