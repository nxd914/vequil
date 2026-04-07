import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (r"background: var\(--black\);\n\n            color: var\(--white\);", r"background: #ffffff;\n\n            color: var(--black);"),
    (r"background: rgba\(8, 8, 8, 0\.95\);\n\n            border-bottom: 1px solid rgba\(255, 255, 255, 0\.05\);", 
     r"background: rgba(255, 255, 255, 0.98);\n\n            border-bottom: 1px solid rgba(0, 0, 0, 0.06);"),
    (r"color: rgba\(255, 255, 255, 0\.65\);", r"color: rgba(15, 23, 42, 0.65);"),
    (r"\.nav-links a:hover \{\n\n            color: #ffffff;\n\n        \}", r".nav-links a:hover {\n\n            color: #0f172a;\n\n        }"),
    (r"background: var\(--black\);\n\n            display: flex;\n\n            flex-direction: column;\n\n            justify-content: flex-end;\n\n            padding: 0 56px 100px;\n\n            position: relative;",
     r"background: #ffffff;\n\n            display: flex;\n\n            flex-direction: column;\n\n            justify-content: flex-end;\n\n            padding: 0 56px 100px;\n\n            position: relative;"),
    (r"color: var\(--white\);", r"color: #0f172a;"), # For headers and text
    (r"color: rgba\(255, 255, 255, 0\.7\);", r"color: rgba(15, 23, 42, 0.6);"), # Text descriptions
    (r"#stats \{\n\n            background: var\(--black\);", r"#stats {\n\n            background: #ffffff;"),
    (r"\.stat-item \{\n\n            background: #111111;", r".stat-item {\n\n            background: #ffffff;"),
    (r"#product \{\n\n            background: var\(--black\);", r"#product {\n\n            background: var(--white);"),
    (r"\.p-card \{\n\n            background: #111111;", r".p-card {\n\n            background: var(--white);"),
    (r"#how \{\n\n            background: var\(--black\);", r"#how {\n\n            background: #ffffff;"),
    (r"#integrations \{\n\n            background: #0d0d0d;", r"#integrations {\n\n            background: var(--off-white);"),
    (r"\.int-card \{\n\n            background: #111111;", r".int-card {\n\n            background: var(--white);"),
    (r"#pricing \{\n\n            background: var\(--black\);", r"#pricing {\n\n            background: var(--white);"),
    (r"\.pr-card \{\n\n            background: #111111;", r".pr-card {\n\n            background: var(--white);"),
    (r"\.pr-card\.featured \{\n\n            background: #1a1a1a;", r".pr-card.featured {\n\n            background: #ffffff;"),
    (r"border: 1px solid rgba\(255, 255, 255, 0\.1\);", r"border: 1px solid rgba(0, 0, 0, 0.06);"),
    (r"background: rgba\(255, 255, 255, 0\.05\);", r"background: #ffffff;"),
    (r"box-shadow: 0 32px 64px rgba\(0, 0, 0, 0\.5\);", r"box-shadow: 0 32px 64px rgba(0, 0, 0, 0.06);"),
    (r"footer \{\n\n            background: #000000;", r"footer {\n\n            background: #ffffff;"),
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
