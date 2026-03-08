import codecs

with open('b64.txt', 'r', encoding='utf-8') as f:
    b64_str = f.read().strip()

target = '<img src="./kinov_2026_logo.jpg?v=20260304_v3" alt="KINOV Logo" class="kinov-alert-logo">'
replace = f'<img src="data:image/jpeg;base64,{b64_str}" alt="KINOV premium 3D Logo" class="kinov-alert-logo">'

with codecs.open('index.html', 'r', 'utf-8') as f:
    content = f.read()

content = content.replace(target, replace)

with codecs.open('index.html', 'w', 'utf-8') as f:
    f.write(content)

print("Injected Base64 image successfully.")
