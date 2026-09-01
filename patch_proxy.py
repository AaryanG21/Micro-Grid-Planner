"""
Removes cross-origin API calls in development.

The browser was issuing successful CORS preflights to the Flask backend but
never following through with the actual POST. Routing API calls through
Create React App's dev proxy makes them same-origin, which sidesteps CORS
entirely and is the standard CRA setup anyway.

  package.json : adds "proxy": "http://127.0.0.1:5000"
  src/App.jsx  : API_URL default becomes '' (relative), so requests go to
                 http://localhost:3000/api/... and CRA forwards them to Flask.

Production is unaffected: REACT_APP_API_URL still overrides when set.
"""
import io
import json
import shutil

# ---------------------------------------------------------- package.json
shutil.copy2("package.json", "package.json.bak-proxy")
with open("package.json", encoding="utf-8") as fh:
    pkg = json.load(fh)
pkg["proxy"] = "http://127.0.0.1:5000"
with io.open("package.json", "w", encoding="utf-8") as fh:
    fh.write(json.dumps(pkg, indent=2) + "\n")
print("package.json: proxy ->", pkg["proxy"])

# ---------------------------------------------------------- src/App.jsx
path = "src/App.jsx"
shutil.copy2(path, path + ".bak-proxy")
src = io.open(path, encoding="utf-8").read()

old = "process.env.REACT_APP_API_URL || 'http://127.0.0.1:5000'"
new = "process.env.REACT_APP_API_URL || ''"
count = src.count(old)
src = src.replace(old, new)
io.open(path, "w", encoding="utf-8").write(src)
print(f"App.jsx: rewrote {count} API_URL default(s) to same-origin")
