import re
import urllib.request

BASE = "https://azmus-crm.vercel.app"
html = urllib.request.urlopen(BASE + "/", timeout=20).read().decode("utf-8", "replace")
scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
print("index scripts:", scripts)
patterns = ["onrender.com", "trycloudflare.com", "127.0.0.1:8000", "localhost:8000"]
for s in scripts:
    js = urllib.request.urlopen(BASE + s, timeout=30).read().decode("utf-8", "errors")
    found = [p for p in patterns if p in js]
    if found:
        print(s, "->", found)
