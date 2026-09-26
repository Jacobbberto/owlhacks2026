import tkinter as tk
from tkinter import ttk

def on_click():
    label.config(text="Searching...")

# create main window
root = tk.Tk()
root.title("Healthcare Helper")
root.geometry("1280x720")

# add a label
label = tk.Label(root, text="How can we help you today?", font=("Times New Roman", 16))
label.pack(pady=20)

#add Insurance provider menu
options = ["Independace Blue Cross (IBX)", "Highmark Blue Cross Blue Sheild", "Aetna", "Oscar Health"]
combo = ttk.Combobox(root, values = options, state="readonly")
combo.set("Choose your provider")
combo.pack(pady=10)

# add a button
button = tk.Button(root, text="Start search", command=on_click)
button.pack()

# Start the event loop
root.mainloop()