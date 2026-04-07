import os

p_app = "/Users/noahdonovan/vequil-test/web/static/app.css"
if os.path.exists(p_app):
    with open(p_app, "r") as f:
        ca = f.read()

    ca = ca.replace("--bg: #f2efe8;", "--bg: #f8fafc;")
    ca = ca.replace("--surface: rgba(255, 252, 246, 0.82);", "--surface: #ffffff;")
    ca = ca.replace("--surface-strong: #fffaf1;", "--surface-strong: #f1f5f9;")
    ca = ca.replace("--ink: #1d2a2f;", "--ink: #0f172a;")
    ca = ca.replace("--muted: #627075;", "--muted: #64748b;")
    ca = ca.replace("--accent: #006d77;", "--accent: #004de6;")
    ca = ca.replace("--accent-soft: #d5ece7;", "--accent-soft: rgba(0, 77, 230, 0.1);")
    ca = ca.replace("linear-gradient(180deg, #f8f3ea 0%, #efe8db 100%)", "linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)")

    with open(p_app, "w") as f:
        f.write(ca)
