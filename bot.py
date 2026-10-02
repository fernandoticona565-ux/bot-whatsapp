import os, requests, re, io
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import fitz  # PyMuPDF
import google.generativeai as genai

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
ID_INSTANCE = os.getenv("ID_INSTANCE")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
MI_NUMERO = "51921493279@c.us"
PERU_TZ = pytz.timezone('America/Lima')

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

def enviar(msg):
    url = f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    try:
        for i in range(0, len(msg), 3800):
            requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3800]}, timeout=30)
    except Exception as e: print(f"Error WA {e}")

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})

# LOGIN
lp = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=30)
soup = BeautifulSoup(lp.text, 'html.parser')
lt = soup.find('input', {'name': 'logintoken'})
data = {"username": USER, "password": PASS}
if lt: data["logintoken"] = lt['value']
s.post("https://campus.cimac.jedu.pe/login/index.php", data=data, timeout=30)

ahora = datetime.now(PERU_TZ)
cursos_links = []
tareas_por_resolver = []

# 1. BUSCA TODOS LOS CURSOS (sin limite)
for url_list in ["https://campus.cimac.jedu.pe/my/", "https://campus.cimac.jedu.pe/my/courses.php"]:
    try:
        html = s.get(url_list, timeout=25).text
        found = re.findall(r'https://campus\.cimac\.jedu\.pe/course/view\.php\?id=\d+', html)
        cursos_links.extend(found)
    except: pass
cursos_links = list(set(cursos_links))
print(f"TOTAL CURSOS: {len(cursos_links)}")

# 2. ENTRA A CADA CURSO Y SACA TODAS LAS TAREAS
for curso_url in cursos_links:
    try:
        c_html = s.get(curso_url, timeout=25).text
        curso_nombre = re.search(r'<title>(.*?)</title>', c_html)
        curso_nombre = curso_nombre.group(1)[:40] if curso_nombre else curso_url
        tareas_urls = list(set(re.findall(r'https://campus\.cimac\.jedu\.pe/mod/assign/view\.php\?id=\d+', c_html)))
        
        for t_url in tareas_urls:
            t_html = s.get(t_url, timeout=20).text
            t_soup = BeautifulSoup(t_html, 'html.parser')
            titulo = (t_soup.find('h2').get_text(strip=True) if t_soup.find('h2') else "Tarea")
            texto = t_soup.get_text(" ", strip=True).lower()
            
            # Si te falta entregar
            if "no entregado" in texto or "sin entrega" in texto:
                # Busca PDFs / links de la tarea
                pdf_link = None
                for a in t_soup.find_all('a', href=True):
                    if ".pdf" in a['href'] or "forcedownload=1" in a['href']:
                        pdf_link = a['href']
                        break
                tareas_por_resolver.append({
                    "curso": curso_nombre,
                    "titulo": titulo,
                    "url": t_url,
                    "pdf": pdf_link,
                    "html": t_html
                })
    except Exception as e: print(e)

print(f"Tareas pendientes en TODOS los cursos: {len(tareas_por_resolver)}")

# 3. GEMINI RESUELVE CADA UNA
es_ventana = True  # luego cambialo a ahora.hour == 8

if es_ventana and tareas_por_resolver:
    for tarea in tareas_por_resolver[:5]: # resuelve 5 por vez para no saturar
        prompt = ""
        contenido = ""
        
        # Lee PDF si hay
        if tarea["pdf"]:
            try:
                pdf_url = tarea["pdf"]
                if not pdf_url.startswith("http"):
                    pdf_url = "https://campus.cimac.jedu.pe" + pdf_url
                pdf_data = s.get(pdf_url, timeout=30).content
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                for page in doc:
                    contenido += page.get_text()
            except Exception as e:
                print(f"Error PDF {e}")
        
        # Si no hay PDF, usa el texto de la pagina
        if not contenido:
            soup_t = BeautifulSoup(tarea["html"], 'html.parser')
            contenido = soup_t.get_text(" ", strip=True)[:8000]

        prompt = f"""Eres asistente de CIMAC. Resuelve esta tarea:
        Curso: {tarea['curso']}
        Tarea: {tarea['titulo']}
        Instrucciones: {contenido[:6000]}
        
        Dame:
        1. Resumen de que pide
        2. Resolucion lista para copiar
        Hazlo corto y directo para WhatsApp."""

        try:
            resp = model.generate_content(prompt)
            solucion = resp.text[:3000]
            msg = f"📚 {tarea['curso']}\n🔴 {tarea['titulo']}\n{tarea['url']}\n\n🤖 GEMINI RESUELVE:\n{solucion}\n\n---"
            enviar(msg)
        except Exception as e:
            enviar(f"📚 {tarea['curso']}\n{tarea['titulo']}\n{tarea['url']}\n\nNo pude resolver auto: {e}\nTexto: {contenido[:1000]}")
else:
    if not tareas_por_resolver:
        enviar(f"✅ {ahora.strftime('%H:%M')} - Revisé {len(cursos_links)} cursos, no tienes tareas pendientes en NINGUNO. Todo al día.")

print("Fin")
