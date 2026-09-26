import tkinter as tk
from tkinter import ttk

# ----- Color Palette (warm and calming: soft green to calm the patients)
BG_MAIN = "#F4F1E8"
BG_ACCENT = "#E4E9DD"
GREEN_DARK = "#6B8F71"
GREEN_LIGHT = "#A8C3A0"
TEXT_DARK = "#4A4238"
TERRACOTTA = "#C97B5C"

#status colors for results list
STATUS_COLORS = {
    "Accepting New Patients": "#4C7A52",
    "Waitlist": "#B8863B",
    "Not Accepting New Patients": "#A3514D"
}

sample_providers = [
    {"name": "Dr. Amanda Reyes", "insurance": "Aetna", "type": "Psychiatrist", "specialty": "Anxiety", "availability": "Accepting New Patients"},
    {"name": "Dr. Marcus Liu", "insurance": "Independence Blue Cross (IBX)", "type": "Therapist", "specialty": "Depression", "availability": "Waitlist"},
    {"name": "Dr. Priya Nair", "insurance": "Highmark Blue Cross Blue Shield", "type": "Psychologist", "specialty": "PTSD", "availability": "Accepting New Patients"},
    {"name": "Dr. James Whitfield", "insurance": "Oscar Health", "type": "Counselor", "specialty": "Substance Use", "availability": "Not Accepting New Patients"},
    {"name": "Dr. Sofia Alvarez", "insurance": "Aetna", "type": "Social Worker", "specialty": "General Mental Health", "availability": "Accepting New Patients"},
    {"name": "Dr. Ben Carter", "insurance": "Independence Blue Cross (IBX)", "type": "Psychiatrist", "specialty": "ADHD", "availability": "Waitlist"},
]


def on_click():
    label.config(text="Searching...")

    # clear old results
    results_listbox.delete(0, tk.END)

    #grab current dropdown selections
    provider_choice = provider_combo.get()
    service_choice = service_combo.get()
    specialty_choice = specialty_combo.get()
    availability_choice = availability_combo.get()

    matches = []
    for provider in sample_providers:
        if provider_choice not in ("Choose your provider", provider["insurance"]):
            continue
        if service_choice not in ("Choose your service type", provider["type"]):
            continue
        if specialty_choice not in ("Choose a Specialty", provider["specialty"]):
            continue
        if availability_choice not in ("Choose Availability", "Any", provider["availability"]):
            continue
        matches.append(provider)

    if matches:
        label.config(text=f"Found {len(matches)} provider(s):")
        for provider in matches:
            row_text = (
                f"{provider['name']} - {provider['type']} - {provider['insurance']} - "
                f"{provider['specialty']} - {provider['availability']}"
            )
            results_listbox.insert(tk.END, row_text)

            #color the row by availability status
            row_index = results_listbox.size() - 1
            row_color = STATUS_COLORS.get(provider["availability"], TEXT_DARK)
            results_listbox.itemconfig(row_index, fg=row_color)
    else:
        label.config(text="No providers matches your search.")

def clear_filters():
    #reset every dropdown back to it's placeholder text
    age_combo.set("Choose your age range")
    provider_combo.set("Choose your provider")
    service_combo.set("Choose your service type")
    verification_combo.set("Choose Verification status")
    availability_combo.set("Choose Availability")
    specialty_combo.set("Choose a Specialty")

    # clear the results list and reset the heading
    results_listbox.delete(0, tk.END)
    label.config(text="How can we help you today?")


# create main window
root = tk.Tk()
root.title("Healthcare Helper")
root.geometry("1280x720")
root.configure(bg=BG_MAIN)

# ttk styling (ttk widgets ingnore plain tk color options, so we use a style)
style = ttk.Style(root)
style.theme_use("clam")

style.configure(
    "TCombobox",
    fieldbackground=BG_ACCENT,
    background=GREEN_LIGHT,
    foreground= TEXT_DARK,
    arrowcolor=TEXT_DARK,
    padding=4,
)
style.map(
    "TCombobox",
    fieldbackground=[("readonly", BG_ACCENT)],
    background=[("active", GREEN_LIGHT)],
)


# add a label
label = tk.Label(
    root, 
    text="How can we help you today?", 
    font=("Georgia", 18, "bold"),
    bg=BG_MAIN,
    fg=GREEN_DARK,
)
label.pack(pady=(30, 20))

# frames to hold the dropdowns side by side
dropdown_frame = tk.Frame(root, bg=BG_MAIN)
dropdown_frame.pack(pady=10)

#add age group
age_options = ["Todler", "Adolescent", "Young adult", "Adult"]
age_combo = ttk.Combobox(dropdown_frame, values= age_options, state="readonly", width=18)
age_combo.set("Choose your age range")
age_combo.grid(row = 0, column = 0, padx = 6)

#add Insurance provider menu
provider_options = ["Independace Blue Cross (IBX)", "Highmark Blue Cross Blue Sheild", "Aetna", "Oscar Health"]
provider_combo = ttk.Combobox(dropdown_frame, values = provider_options, state="readonly", width=25)
provider_combo.set("Choose your provider")
provider_combo.grid(row= 0, column= 1, padx= 6)

#add Provider Type
service_options = ["Therapist", "Psychologist", "Psychiatrist", "Counselor", "Social Worker"]
service_combo = ttk.Combobox(dropdown_frame, values= service_options, state= "readonly", width=20)
service_combo.set("Choose your service type")
service_combo.grid(row=0, column=2, padx= 6)

#add Verification status
verification_options = ["All", "Verified", "Potential Issue", "Unable to Verify", "Insurance Mismatch", "Not Accepting New Patients"]
verification_combo = ttk.Combobox(dropdown_frame, values= verification_options, state= "readonly", width= 22)
verification_combo.set("Choose Verification status")
verification_combo.grid(row=0, column=3, padx= 6)

#add Availability
availability_options = ["Any", "Accepting New Patients", "Not Accepting New Patients", "Waitlist"]
availability_combo = ttk.Combobox(dropdown_frame, values= availability_options ,state= "readonly", width= 22)
availability_combo.set("Choose Availability")
availability_combo.grid(row=0, column=4, padx= 6)

#add Specialty
specialty_options = ["Anxiety", "Depression", "ADHD", "PTSD", "Substance Use", "Couples/Familty", "General Mental Health", "Other"]
specialty_combo = ttk.Combobox(dropdown_frame, values= specialty_options, state= "readonly", width=20)
specialty_combo.set("Choose a Specialty")
specialty_combo.grid(row=0, column=5, padx= 6)

# frame to hold the search and clear buttons side by side
button_frame = tk.Frame(root, bg=BG_MAIN)
button_frame.pack(pady=25)

# added Search button
button = tk.Button(
    root, 
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
button.pack(pady=25)

#added clear filters button
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

# results section
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
results_listbox.pack(side= "left", fill="both", expand= True, padx=(0,0))

results_scrollbar = tk.Scrollbar(results_frame, orient="vertical", command=results_listbox.yview)
results_scrollbar.pack(side="left", fill="y")
results_listbox.config(yscrollcommand=results_scrollbar.set)

# Start the event loop
root.mainloop()