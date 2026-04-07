import re

def to_light_mode():
    p_index = "/Users/noahdonovan/vequil-test/web/static/index.html"
    with open(p_index, "r") as f:
        c = f.read()

    # Index.html fixes
    c = c.replace("background: var(--black);", "background: #ffffff;")
    c = c.replace("rgba(8, 8, 8, 0.96)", "rgba(255, 255, 255, 0.98)") # nav
    c = c.replace("border-bottom: 1px solid rgba(255, 255, 255, 0.08)", "border-bottom: 1px solid rgba(0, 0, 0, 0.06)")
    
    # Nav links
    c = c.replace("color: rgba(255, 255, 255, 0.55);", "color: rgba(15, 23, 42, 0.65);")
    c = c.replace("color: var(--white);\n\n        }", "color: #0f172a;\n\n        }") 

    # Hero
    c = c.replace("linear-gradient(rgba(255, 255, 255, 0.03) 1px", "linear-gradient(rgba(0, 0, 0, 0.04) 1px")
    c = c.replace("rgba(255, 255, 255, 0.03) 1px", "rgba(0, 0, 0, 0.04) 1px")
    c = c.replace("color: var(--white);\n\n            margin-bottom: 32px;", "color: #0f172a;\n\n            margin-bottom: 32px;")
    c = c.replace("color: rgba(255, 255, 255, 0.45);", "color: rgba(15, 23, 42, 0.6);")
    c = c.replace("color: rgba(255, 255, 255, 0.5);", "color: rgba(15, 23, 42, 0.6);")
    
    # Hero right terminal ui
    c = c.replace("background: rgba(255, 255, 255, 0.04);", "background: #ffffff; box-shadow: 0 32px 64px rgba(0, 0, 0, 0.06);")
    c = c.replace("border: 1px solid rgba(255, 255, 255, 0.1);", "border: 1px solid rgba(0, 0, 0, 0.06);")
    c = c.replace("border-bottom: 1px solid rgba(255, 255, 255, 0.06);", "border-bottom: 1px solid rgba(0, 0, 0, 0.04);")
    c = c.replace("color: rgba(255, 255, 255, 0.25);", "color: rgba(15, 23, 42, 0.4);")
    c = c.replace("color: rgba(255, 255, 255, 0.3);", "color: rgba(15, 23, 42, 0.5);")
    c = c.replace("color: rgba(255, 255, 255, 0.2);", "color: rgba(15, 23, 42, 0.4);")
    c = c.replace("background: rgba(255, 255, 255, 0.06);", "background: rgba(0, 0, 0, 0.02);")
    
    # Summary title colors in the loop that were white
    c = c.replace("color: var(--white);\n\n            margin-bottom: 4px;", "color: #0f172a;\n\n            margin-bottom: 4px;")
    c = c.replace("color: var(--white);\n\n            margin-top: 10px;", "color: #0f172a;\n\n            margin-top: 10px;")

    with open(p_index, "w") as f:
        f.write(c)

    p_dash = "/Users/noahdonovan/vequil-test/web/static/dashboard.html"
    with open(p_dash, "r") as f:
        cd = f.read()

    # Dashboard inline overrides
    cd = re.sub(r'<style>.*?Dark mode overrides.*?</style>', '', cd, flags=re.DOTALL)
    cd = cd.replace('color: #fff;', 'color: #0f172a;')
    cd = cd.replace('rgba(255, 255, 255, 0.02)', 'rgba(0, 0, 0, 0.02)')

    with open(p_dash, "w") as f:
        f.write(cd)

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
        ca = ca.replace("background-color: #0d1117;", "background-color: #f8fafc;")

        with open(p_app, "w") as f:
            f.write(ca)

to_light_mode()
