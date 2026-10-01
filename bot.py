import os, requests, json, io, base64
from bs4 import BeautifulSoup
import PyPDF2, docx
from datetime import datetime
import pytz

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ID_INSTANCE = os.getenv("ID_INSTANCE")
MI_NUMERO = "51921493279@c.us"
SEEN_FILE = "vistos.json"
PERU_TZ = pytz.timezone('America/Lima')

def enviar(msg):
    url = f"https://{ID_INSTANCE[:4]}.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
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

# --- NUEVO: FUNCION PARA ESCUCHAR TU WHATSAPP ---
def revisar_si_me_escribiste(pendientes_actuales):
    try:
        url_get = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/getNotification/{TOKEN}"
        r = requests.get(url_get, timeout=20).json()
        if not r or 'body' not in r:
            return
        body = r['body']
        if body.get('typeWebhook') == 'incomingMessageReceived':
            # texto que me escribiste
            txt = body.get('messageData', {}).get('textMessageData', {}).get('textMessage','').lower()
            if any(k in txt for k in ['que me falta', 'que falta', 'pendientes', 'tareas', 'resumen', 'ayuda']):
                if not pendientes_actuales:
                    enviar(f"✅ A las {datetime.now(PERU_TZ).strftime('%H:%M')} no tienes pendientes activos. Todo al día.")
                else:
                    lista = "\n".join(pendientes_actuales[:15])
                    enviar(f"📋 Me preguntaste a las {datetime.now(PERU_TZ).strftime('%H:%M')} - Tienes {len(pendientes_actuales)} pendientes:\n\n{lista}")

        # borrar notificacion para no repetir
        receiptId = r.get('receiptId')
        if receiptId:
            requests.delete(f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/deleteNotification/{TOKEN}/{receiptId}", timeout=20)
    except Exception as e:
        print(f"Error escuchando WA: {e}")

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
es_hora_resumen = ahora_peru.hour == 15 and ahora_peru.minute < 30 # 3:00-3:29 pm Lima

pendientes = []
nuevos = 0

for a in soup.find_all('a', href=True):
    href = a['href']
    texto = a.get_text(strip=True)
    if len(texto) < 4 or not href.startswith('http'): continue
    if not any(x in href for x in ['/mod/', '.pdf','.docx','.doc','.xlsx','.xls','.jpg','.jpeg','.png']): continue
    if href in vistos_hrefs:
        if 'assign' in href: pendientes.append(f"📝 {texto} - {href}")
        continue

    tipo = "📄 ARCHIVO" if any(x in href.lower() for x in ['.pdf','.docx','.xlsx','.jpg','.png']) else "📝 TAREA" if 'assign' in href else "📌 ACTIVIDAD"
    msg = f"{tipo} NUEVO EN CIMAC\n\n{texto}\n{href}"

    try:
        fr = s.get(href, timeout=30)
        if len(fr.content) > 1000:
            if '.pdf' in href.lower() or 'pdf' in fr.headers.get('content-type',''):
                pdf=PyPDF2.PdfReader(io.BytesIO(fr.content))
                txt="\n".join([(p.extract_text() or "") for p in pdf.pages[:6]])
                msg += resolver_gemini(texto=txt, imagen_bytes=None if len(txt.strip())>50 else fr.content[:2000000])
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

# --- NUEVO 1: ALERTA VENCIMIENTO 8AM y 8PM ---
if ahora_peru.hour in [8, 20] and ahora_peru.minute < 30:
    if pendientes:
        enviar(f"⏰ RECORDATORIO {'8AM' if ahora_peru.hour==8 else '8PM'} - Tienes {len(pendientes)} pendientes que pueden vencer pronto:\n\n" + "\n".join(pendientes[:10]))

# --- NUEVO 2: SI TÚ LE ESCRIBES, TE RESPONDE ---
revisar_si_me_escribiste(pendientes)

# RESUMEN DIARIO 3PM (como lo querias)
if es_hora_resumen:
    if pendientes:
        resumen = f"☀️ RESUMEN 3PM CIMAC - {ahora_peru.strftime('%d/%m')}\n\nTienes {len(pendientes)} pendientes activos:\n\n" + "\n".join(pendientes[:15])
        resumen += "\n\nEstoy vigilando todo el día cada 30 min. Escríbeme 'que me falta?' cuando quieras."
    else:
        resumen = f"☀️ RESUMEN 3PM CIMAC - {ahora_peru.strftime('%d/%m')}\n\nNo tienes tareas pendientes nuevas. Todo al día ✅"
    enviar(resumen)
    print("Resumen enviado")

open(SEEN_FILE,'w').write(json.dumps(vistos))
print(f"Listo. Nuevos: {nuevos}, Hora Lima: {ahora_peru}")
