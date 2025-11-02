# gui.py
import json
import tkinter as tk

CONFIG_FILE = "config.json"

def toggle_option(option):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    config[option] = not config[option]
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    label_vars[option].set(f"{option.capitalize()}: {'ON' if config[option] else 'OFF'}")

root = tk.Tk()
root.title("Panel TikTok Printer")

label_vars = {}

for opt in ["gifts", "likes", "comments", "tts"]:
    label_vars[opt] = tk.StringVar()
    label_vars[opt].set(f"{opt.capitalize()}: ON")
    tk.Button(root, textvariable=label_vars[opt], command=lambda o=opt: toggle_option(o), width=20).pack(pady=5)

root.mainloop()
