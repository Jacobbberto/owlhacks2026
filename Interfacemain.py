import tkinter as tk
from tkinter import ttk

sample_providers = [
    {"name": "Dr. Amanda Reyes", "insurance": "Aetna", "type": "Psychiatrist", "specialty": "Anxiety"},
    {"name": "Dr. Marcus Liu", "insurance": "Independence Blue Cross (IBX)", "type": "Therapist", "specialty": "Depression"},
    {"name": "Dr. Priya Nair", "insurance": "Highmark Blue Cross Blue Shield", "type": "Psychologist", "specialty": "PTSD"},
    {"name": "Dr. James Whitfield", "insurance": "Oscar Health", "type": "Counselor", "specialty": "Substance Use"},
    {"name": "Dr. Sofia Alvarez", "insurance": "Aetna", "type": "Social Worker", "specialty": "General Mental Health"},
    {"name": "Dr. Ben Carter", "insurance": "Independence Blue Cross (IBX)", "type": "Psychiatrist", "specialty": "ADHD"},
]

def on_click():
    label.config(text="Searching...")

    # clear old results
    results_listbox.delete(0, tk.END)

    #grab current dropdown selections
    provider_choice = provider_combo.get()
    service_choice = service_combo.get()
    specialty_choice = specialty_combo.get()

    matches = []
    for provider in sample_providers:
        if provider_choice not in ("Choose your provider", provider["insurance"]):
            continue
        if service_choice not in ("Choose your service type", provider["type"]):
            continue
        if specialty_choice not in ("Choose a Specialty", provider["specialty"]):
            continue
        matches.append(provider)

    if matches:
        label.config(text=f"Found {len(matches)} provider(s):")
        for provider in matches:
            results_listbox.insert(
                tk.END,
                f"{provider['name']} - {provider['type']} - {provider['insurance']} - {provider['specialty']}"
            )
    else:
        label.config(text="No providers matches your search.")


# create main window
root = tk.Tk()
root.title("Healthcare Helper")
root.geometry("1280x720")

# add a label
label = tk.Label(root, text="How can we help you today?", font=("Times New Roman", 16))
label.pack(pady=20)

# frames to hold the dropdowns side by side
dropdown_frame = tk.Frame(root)
dropdown_frame.pack(pady=10)

#add age group
age_options = ["Todler", "Adolescent", "Young adult", "Adult"]
age_combo = ttk.Combobox(dropdown_frame, values= age_options, state="readonly", width=18)
age_combo.set("Choose your age range")
age_combo.grid(row = 0, column = 0, padx = 5)

#add Insurance provider menu
provider_options = ["Independace Blue Cross (IBX)", "Highmark Blue Cross Blue Sheild", "Aetna", "Oscar Health"]
provider_combo = ttk.Combobox(dropdown_frame, values = provider_options, state="readonly", width=25)
provider_combo.set("Choose your provider")
provider_combo.grid(row= 0, column= 1, padx= 5)

#add Provider Type
service_options = ["Therapist", "Psychologist", "Psychiatrist", "Counselor", "Social Worker"]
service_combo = ttk.Combobox(dropdown_frame, values= service_options, state= "readonly", width=20)
service_combo.set("Choose your service type")
service_combo.grid(row=0, column=2, padx= 5)

#add Verification status
verification_options = ["All", "Verified", "Potential Issue", "Unable to Verify", "Insurance Mismatch", "Not Accepting New Patients"]
verification_combo = ttk.Combobox(dropdown_frame, values= verification_options, state= "readonly", width= 22)
verification_combo.set("Choose Verification status")
verification_combo.grid(row=0, column=3, padx= 5)

#add Availability
availability_options = ["Any", "Accepting New Patients", "Not Accepting New Patients", "Waitlist"]
availability_combo = ttk.Combobox(dropdown_frame, values= availability_options ,state= "readonly", width= 22)
availability_combo.set("Choose Availability")
availability_combo.grid(row=0, column=4, padx= 5)

#add Specialty
specialty_options = ["Anxiety", "Depression", "ADHD", "PTSD", "Substance Use", "Couples/Familty", "General Mental Health", "Other"]
specialty_combo = ttk.Combobox(dropdown_frame, values= specialty_options, state= "readonly", width=20)
specialty_combo.set("Choose a Specialty")
specialty_combo.grid(row=0, column=5, padx= 5)

# add a button
button = tk.Button(root, text="Start search", command=on_click)
button.pack(pady=20)

# results section
results_frame = tk.Frame(root)
results_frame.pack(pady=10, fill="both", expand=True)

results_listbox = tk.Listbox(results_frame, width=100, height=15, font=("Ariel", 11))
results_listbox.pack(side= "left", fill="both", expand= True, padx=(20,0))

results_scrollbar = tk.Scrollbar(results_frame, orient="vertical", command=results_listbox.yview)
results_scrollbar.pack(side="left", fill="y")
results_listbox.config(yscrollcommand=results_scrollbar.set)

# Start the event loop
root.mainloop()