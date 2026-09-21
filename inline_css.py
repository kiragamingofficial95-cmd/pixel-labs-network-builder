import os
import re

base_dir = r"C:\Users\DEVXRDP\Documents\Default Project\pixel-labs-network-builder"
templates_dir = os.path.join(base_dir, "templates")
css_path = os.path.join(base_dir, "static", "css", "style.css")
js_path = os.path.join(base_dir, "static", "js", "app.js")

# Read CSS and JS
with open(css_path, "r", encoding="utf-8") as f:
    css_content = f.read()

with open(js_path, "r", encoding="utf-8") as f:
    js_content = f.read()

# Read each HTML template and replace link/script tags with inline content
for filename in os.listdir(templates_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()
        
        # Replace CSS link with inline style
        html = re.sub(
            r'<link rel="stylesheet" href="/static/css/style.css">',
            f'<style>{css_content}</style>',
            html
        )
        html = re.sub(
            r'<link rel="stylesheet" href="static/css/style.css">',
            f'<style>{css_content}</style>',
            html
        )
        
        # Replace JS script tag with inline script (before </body>)
        html = re.sub(
            r'<script src="/static/js/app.js"></script>',
            f'<script>{js_content}</script>',
            html
        )
        html = re.sub(
            r'<script src="static/js/app.js"></script>',
            f'<script>{js_content}</script>',
            html
        )
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"Updated {filename}")

print("\nDone! All CSS and JS inlined.")
