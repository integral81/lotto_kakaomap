from PIL import Image
import base64
import io

img_path = r'C:\Users\이승민\.gemini\antigravity\brain\5d02a260-c03e-451d-b3e4-662069eac8c7\kinov_premium_logo_1772601569261.png'
img = Image.open(img_path)
img.thumbnail((120, 120))
buffer = io.BytesIO()
img.convert('RGB').save(buffer, format='JPEG', quality=85)
b = base64.b64encode(buffer.getvalue()).decode('utf-8')

with open('b64.txt', 'w') as f:
    f.write(b)
