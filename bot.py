import os, requests, json, re
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
ID_INSTANCE = os.getenv("ID_INSTANCE")
MI_NUMERO = "51921493279@c.us"
PERU_TZ = pytz.timezone('America/Lima')

def enviar(msg):
    if not TOKEN or not ID_INSTANCE:
        print("Falta GREEN_TOKEN o ID_INSTANCE")
        return
    base = ID_INSTANCE.replace("api.greenapi.com","").replace("https://","").replace("/","")
    # Si tu ID_INSTANCE ya es solo el numero tipo 7105xxxxxxx, esto funciona igual
    if "." in ID_INSTANCE:
        url = f"https://{ID_INSTANCE}/waInstance{ID_INSTANCE.split('.')[0]}/sendMessage/{TOKEN}"
        # fallback simple
        url = f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    else:
        url = f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    # url correcta para GreenAPI
    url = f"https://7105.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}" if len(ID_INSTANCE) > 10 else f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    # Intento universal
    try:
        url = f"https://{ID_INSTANCE[:4]}.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    except: pass
    try:
        url = f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
        for i in range(0, len(msg), 3800):
            requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3800]}, timeout=30)
        print("WhatsApp enviado")
    except Exception as e:
        print(f"Error WA: {e}")

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"})

print("Login CIMAC...")
lp = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=30)
soup = BeautifulSoup(lp.text, 'html.parser')
lt = soup.find('input', {'name': 'logintoken'})
data = {"username": USER, "password": PASS}
if lt and lt.get('value'):
    data["logintoken"] = lt['value']
r = s.post("https://campus.cimac.jedu.pe/login/index.php", data=data, timeout=30)
print(f"Login status: {r.status_code}")

ahora_peru = datetime.now(PERU_TZ)
retrasadas = []
proximas = []
cursos_links = []

# 1. Buscar todos los cursos en /my/ y /my/courses.php
for url_list in ["https://campus.cimac.jedu.pe/my/", "https://campus.cimac.jedu.pe/my/courses.php"]:
    try:
        html = s.get(url_list, timeout=25).text
        found = re.findall(r'https://campus\.cimac\.jedu\.pe/course/view\.php\?id=\d+', html)
        # tambien busca id entre comillas json
        found += ["https://campus.cimac.jedu.pe/course/view.php?id="+m for m in re.findall(r'course/view\.php\?id=(\d+)', html)]
        cursos_links.extend(found)
        print(f" {url_list} -> {len(found)} links")
    except Exception as e:
        print(f"Error {url_list}: {e}")

cursos_links = list(set(cursos_links))
print(f"Cursos encontrados TOTAL: {len(cursos_links)}")
for c in cursos_links:
    print(f" - {c}")

# Si quieres forzar tus cursos a mano, descomenta y pon tus IDs:
# cursos_links = [
# "https://campus.cimac.jedu.pe/course/view.php?id=3383",
# "https://campus.cimac.jedu.pe/course/view.php?id=3380",
# "https://campus.cimac.jedu.pe/course/view.php?id=3381",
# ]

if not cursos_links:
    enviar(f"⚠️ CIMAC BOT: No encontré cursos. Revisa CIMAC_USER/PASS. Hora {ahora_peru}")

# 2. ENTRAR A CADA CURSO - ESTO ARREGLA TU ERROR DE RETRASADAS 0
for curso_url in cursos_links: # <-- YA SIN [:4], AHORA LEE TODOS
    try:
        c_html = s.get(curso_url, timeout=25).text
        tareas_urls = re.findall(r'https://campus\.cimac\.jedu\.pe/mod/assign/view\.php\?id=\d+', c_html)
        tareas_urls = list(set(tareas_urls))
        print(f"Curso {curso_url.split('id=')[-1][:5]}: {len(tareas_urls)} tareas")

        for t_url in tareas_urls:
            try:
                t_html = s.get(t_url, timeout=20).text
                t_soup = BeautifulSoup(t_html, 'html.parser')
                titulo_tag = t_soup.find('h2') or t_soup.find('h1')
                titulo = titulo_tag.get_text(strip=True)[:90] if titulo_tag else t_url.split('id=')[-1]
                texto = t_soup.get_text(" ", strip=True).lower()

                if "no entregado" in texto or "sin entrega" in texto or "no se ha enviado" in texto or "no entregada" in texto:
                    # Si vencio es retrasada
                    if "vencido" in texto or "retras" in texto or "fecha límite" in texto or "fecha limite" in texto:
                        retrasadas.append(f"🔴 {titulo}\n{t_url}")
                    else:
                        proximas.append(f"🟡 {titulo}\n{t_url}")
            except Exception as e:
                print(f" Error tarea {t_url}: {e}")
                continue
    except Exception as e:
        print(f"Error curso {curso_url}: {e}")
        continue

# 3. ENVIAR REPORTE - MODO PRUEBA ACTIVADO PARA QUE TE LLEGUE AHORA
es_ventana = True # <-- CUANDO YA FUNCIONE CAMBIA A: ahora_peru.hour == 8

if es_ventana:
    if retrasadas or proximas:
        msg = f"📚 CIMAC BOT - {ahora_peru.strftime('%d/%m %H:%M')} Lima\n"
        msg += f"Cursos revisados: {len(cursos_links)}\n\n"
        if retrasadas:
            msg += f"🔴 RETRASADAS ({len(retrasadas)}):\n" + "\n\n".join(retrasadas[:15]) + "\n\n"
        if proximas:
            msg += f"🟡 POR HACER ({len(proximas)}):\n" + "\n\n".join(proximas[:15]) + "\n\n"
        msg += "Entra a cada link para entregar."
        enviar(msg)
    else:
        enviar(f"✅ CIMAC revisado {ahora_peru.strftime('%H:%M')} - Entré a {len(cursos_links)} cursos, no vi tareas con 'No entregado'. Si tienes CLS2 pendiente, dime como dice exactamente el estado.")

print(f"Listo. Cursos:{len(cursos_links)} Retrasadas:{len(retrasadas)} Proximas:{len(proximas)} Hora:{ahora_peru}")
