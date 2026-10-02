import os, requests, json, io, base64, re
from bs4 import BeautifulSoup
import PyPDF2, docx
from datetime import datetime, timedelta
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
            parts.append({"text": f"Resume y resuelve esta tarea de CIMAC en borrador listo para entregar:\n\n{texto[:12000]}"})
        if imagen_bytes:
            b64 = base64.b64encode(imagen_bytes).decode()
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
            parts.append({"text": "Transcribe y resuelve TODO lo que ves en esta imagen de tarea."})
        if not parts: return ""
        r = requests.post(url, json={"contents": [{"parts": parts}]}, timeout=90)
        return "\n\n--- SOLUCIÓN GEMINI ---\n" + r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"\n[Gemini error: {e}]"

def revisar_si_me_escribiste(pendientes_actuales):
    try:
        base = ID_INSTANCE[:4]
        url_get = f"https://{base}.api.greenapi.com/waInstance{ID_INSTANCE}/receiveNotification/{TOKEN}"
        resp = requests.get(url_get, timeout=20)
        if not resp.text.strip(): return
        r = resp.json()
        if not r or 'body' not in r: return
        body = r['body']
        if body.get('typeWebhook') == 'incomingMessageReceived':
            txt = body.get('messageData', {}).get('textMessageData', {}).get('textMessage','').lower()
            if any(k in txt for k in ['que me falta', 'que falta', 'pendientes', 'tareas', 'resumen']):
                if not pendientes_actuales:
                    enviar(f"✅ A las {datetime.now(PERU_TZ).strftime('%H:%M')} no tienes pendientes. Todo al día.")
                else:
                    enviar(f"📋 Tienes {len(pendientes_actuales)} pendientes:\n" + "\n".join(pendientes_actuales[:20]))
        receiptId = r.get('receiptId')
        if receiptId:
            requests.delete(f"https://{base}.api.greenapi.com/waInstance{ID_INSTANCE}/deleteNotification/{TOKEN}/{receiptId}", timeout=20)
    except Exception as e:
        print(f"Error WA: {e}")

# Login
s = requests.Session()
soup = BeautifulSoup(s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20).text, 'html.parser')
lt = soup.find('input', {'name': 'logintoken'})
s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": lt['value'] if lt else ""}, timeout=20)

vistos = json.loads(open(SEEN_FILE).read()) if os.path.exists(SEEN_FILE) else []
vistos_hrefs = [v['href'] if isinstance(v, dict) else v for v in vistos]
ahora_peru = datetime.now(PERU_TZ)

# --- NUEVO: REVISAR TODOS LOS CURSOS Y ESTADO DE CADA TAREA ---
retrasadas = []
proximas = []
recien_subidas = []
todos_pendientes_texto = []

# 1. Busca todos los links de tareas en /my/ y también en mis cursos
my_page = s.get("https://campus.cimac.jedu.pe/my/", timeout=25).text
soup_my = BeautifulSoup(my_page, 'html.parser')

links_tareas = []
for a in soup_my.find_all('a', href=True):
    href = a['href']
    if '/mod/assign/view.php' in href:
        links_tareas.append((a.get_text(strip=True), href))

# Eliminar duplicados
links_tareas = list({h: (t,h) for t,h in links_tareas}.values())

for texto_tarea, href_tarea in links_tareas:
    try:
        page_tarea = s.get(href_tarea, timeout=20).text
        soup_t = BeautifulSoup(page_tarea, 'html.parser')
        texto_full = soup_t.get_text(" ", strip=True).lower()

        # Estado y tiempo (como en tu captura)
        estado_match = re.search(r"estado de la entrega(.*?)estado de la calificación", texto_full)
        tiempo_match = re.search(r"tiempo restante(.*?)última modificación", texto_full)
        estado = estado_match.group(1) if estado_match else texto_full
        tiempo = tiempo_match.group(1) if tiempo_match else ""

        es_no_entregado = "no entregado" in estado or "no entregado" in texto_full

        if es_no_entregado:
            if "retrasada" in tiempo or "retrasada" in texto_full:
                retrasadas.append(f"🔴 {texto_tarea} - {tiempo.strip() or 'Retrasada'} - {href_tarea}")
            elif any(x in tiempo for x in ["hora", "horas", "día", "dias", "vence hoy"]):
                proximas.append(f"🟡 {texto_tarea} - {tiempo.strip()[:80]} - {href_tarea}")
            todos_pendientes_texto.append(f"{texto_tarea} - {href_tarea}")

        # Detectar si es nueva (nunca vista)
        if href_tarea not in vistos_hrefs and es_no_entregado:
            recien_subidas.append(f"🟢 {texto_tarea} - {href_tarea}")
            # Opcional: descargar y resolver con Gemini como ya hacías
            try:
                # intenta buscar archivo adjunto dentro de la tarea
                for a2 in soup_t.find_all('a', href=True):
                    h2 = a2['href']
                    if any(x in h2.lower() for x in ['.pdf','.docx','.jpg','.png']):
                        fr = s.get(h2, timeout=25)
                        if len(fr.content) > 1000:
                            msg = f"🟢 TAREA NUEVA EN CIMAC\n\n{texto_tarea}\n{href_tarea}\nArchivo: {h2}"
                            if '.pdf' in h2.lower():
                                pdf=PyPDF2.PdfReader(io.BytesIO(fr.content))
                                txt="\n".join([(p.extract_text() or "") for p in pdf.pages[:6]])
                                msg += resolver_gemini(texto=txt)
                            enviar(msg)
                        break
            except: pass

            vistos.append({"href": href_tarea, "titulo": texto_tarea, "fecha": ahora_peru.isoformat()})
            vistos_hrefs.append(href_tarea)

    except Exception as e:
        print(f"Error revisando {href_tarea}: {e}")
        continue

# --- ENVÍO DE RESÚMENES POR HORARIO (con ventana 8-9AM) ---
# Cambiamos la lógica: tu cron de GitHub corre cada 30min, así que aceptamos 8, 15, 20
es_ventana_manana = ahora_peru.hour == 8 # 8AM-8:59 (tu pedido)
es_ventana_tarde = ahora_peru.hour == 15 # 3PM-3:59
es_ventana_noche = ahora_peru.hour == 20 # 8PM-8:59

if es_ventana_manana or es_ventana_tarde or es_ventana_noche:
    hora_label = "8AM" if es_ventana_manana else "3PM" if es_ventana_tarde else "8PM"
    resumen = f"📚 CIMAC RESUMEN {hora_label} - {ahora_peru.strftime('%d/%m %H:%M')}\n\n"

    if retrasadas:
        resumen += f"🔴 RETRASADAS ({len(retrasadas)}):\n" + "\n".join(retrasadas[:10]) + "\n\n"
    else:
        resumen += "✅ Sin retrasadas\n\n"

    if proximas:
        resumen += f"🟡 PRÓXIMAS A VENCER ({len(proximas)}):\n" + "\n".join(proximas[:10]) + "\n\n"

    if recien_subidas:
        resumen += f"🟢 RECIÉN SUBIDAS ({len(recien_subidas)}):\n" + "\n".join(recien_subidas[:10]) + "\n\n"

    if not retrasadas and not proximas and not recien_subidas:
        resumen += "No tienes pendientes activos. Todo al día ✅"

    resumen += "\nEscríbeme 'que me falta?' cuando quieras."
    enviar(resumen)

revisar_si_me_escribiste(todos_pendientes_texto + retrasadas + proximas)

open(SEEN_FILE,'w').write(json.dumps(vistos))
print(f"Listo. Retrasadas:{len(retrasadas)} Proximas:{len(proximas)} Nuevas:{len(recien_subidas)} Hora:{ahora_peru}")
