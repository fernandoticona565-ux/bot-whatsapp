import os, requests, json, io, base64
from bs4 import BeautifulSoup
import PyPDF2, docx
from datetime import datetime
import pytz

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ID_INSTANCE = "710722753429"
MI_NUMERO = "51921493279@c.us"
SEEN_FILE = "vistos.json"
PERU_TZ = pytz.timezone('America/Lima')

def enviar(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    for i in range(0, len(msg), 3500):
        try: requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3500]}, timeout=30)
        except: pass

def resolver_gemini(texto=None, imagen_bytes=None):
    if not GEMINI_KEY: return ""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        parts = []
        if texto and len(texto.strip())>20:
            parts.append({"text": f"Resume y resuelve esta tarea de CIMAC en borrador listo para entregar. Si es Excel explica fórmulas y pasos. Si es foto de pizarra transcribe todo:\n\n{texto[:12000]}"})
        if imagen_bytes:
            b64 = base64.b64encode(imagen_bytes).decode()
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
            parts.append({"text": "Transcribe y resuelve TODO lo que ves en esta imagen/foto de tarea de CIMAC. Dame el borrador listo para entregar."})
        if not parts: return ""
        r = requests.post(url, json={"contents": [{"parts": parts}]}, timeout=90)
        return "\n\n--- SOLUCIÓN GEMINI (incluye OCR) ---\n" + r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"\n[Gemini error: {e}]"

# Login CIMAC
s = requests.Session()
soup = BeautifulSoup(s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20).text, 'html.parser')
lt = soup.find('input', {'name': 'logintoken'})
s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": lt['value'] if lt else ""}, timeout=20)

vistos = json.loads(open(SEEN_FILE).read()) if os.path.exists(SEEN_FILE) else []
vistos_hrefs = [v['href'] if isinstance(v, dict) else v for v in vistos]

page = s.get("https://campus.cimac.jedu.pe/my/", timeout=25)
soup = BeautifulSoup(page.text, 'html.parser')

ahora_peru = datetime.now(PERU_TZ)
es_hora_resumen = ahora_peru.hour == 8 and ahora_peru.minute < 30 # 8:00-8:29 am Lima

pendientes = []
nuevos = 0

for a in soup.find_all('a', href=True):
    href = a['href']
    texto = a.get_text(strip=True)
    if len(texto) < 4 or not href.startswith('http'): continue
    if not any(x in href for x in ['/mod/', '.pdf','.docx','.doc','.xlsx','.xls','.jpg','.jpeg','.png']): continue
    if href in vistos_hrefs:
        # guardar para resumen
        if 'assign' in href: pendientes.append(f"📝 {texto} - {href}")
        continue

    tipo = "📄 ARCHIVO" if any(x in href.lower() for x in ['.pdf','.docx','.xlsx','.jpg','.png']) else "📝 TAREA" if 'assign' in href else "📌 ACTIVIDAD"
    msg = f"{tipo} NUEVO EN CIMAC\n\n{texto}\n{href}"

    # Descargar y resolver
    try:
        fr = s.get(href, timeout=30)
        if len(fr.content) > 1000:
            if '.pdf' in href.lower() or 'pdf' in fr.headers.get('content-type',''):
                pdf=PyPDF2.PdfReader(io.BytesIO(fr.content))
                txt="\n".join([(p.extract_text() or "") for p in pdf.pages[:6]])
                if len(txt.strip()) < 50: # Es escaneado -> OCR con Gemini Vision
                    msg += resolver_gemini(imagen_bytes=fr.content[:2000000]) # pdf no va como imagen, pero intentamos texto
                else:
                    msg += resolver_gemini(texto=txt)
            elif any(x in href.lower() for x in ['.jpg','.jpeg','.png']):
                msg += resolver_gemini(imagen_bytes=fr.content)
            elif '.docx' in href.lower():
                d=docx.Document(io.BytesIO(fr.content))
                txt="\n".join([p.text for p in d.paragraphs[:80]])
                msg += resolver_gemini(texto=txt)
    except Exception as e: pass

    enviar(msg)
    vistos.append({"href": href, "titulo": texto, "fecha": ahora_peru.isoformat()})
    vistos_hrefs.append(href)
    nuevos += 1
    pendientes.append(f"{tipo} {texto}")
    if nuevos >= 3: break

# 2. RESUMEN DIARIO 8AM
if es_hora_resumen:
    if pendientes:
        resumen = f"☀️ RESUMEN 8AM CIMAC - {ahora_peru.strftime('%d/%m')}\n\nTienes {len(pendientes)} pendientes activos:\n\n" + "\n".join(pendientes[:15])
        resumen += "\n\nEstoy vigilando todo el día cada 30 min."
    else:
        resumen = f"☀️ RESUMEN 8AM CIMAC - {ahora_peru.strftime('%d/%m')}\n\nNo tienes tareas pendientes nuevas. Todo al día ✅"
    enviar(resumen)
    print("Resumen enviado")

open(SEEN_FILE,'w').write(json.dumps(vistos))
print(f"Listo. Nuevos: {nuevos}, Hora Lima: {ahora_peru}")
