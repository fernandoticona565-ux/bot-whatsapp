import os, requests, json, io
from bs4 import BeautifulSoup
import PyPDF2
import docx
import openpyxl

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ID_INSTANCE = "710722753429"
MI_NUMERO = "51921493279@c.us"
SEEN_FILE = "vistos.json"

def enviar_whatsapp(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    # Cortamos en partes de 4000 caracteres porque WhatsApp tiene límite
    for i in range(0, len(msg), 3500):
        requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3500]}, timeout=30)

def resolver_con_gemini(texto_archivo):
    if not GEMINI_KEY:
        return "Falta GEMINI_API_KEY en Secrets."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        prompt = f"""Eres un asistente académico para CIMAC. Te paso el contenido de una tarea en PDF/Word/Excel.
Haz esto:
1. Resume de qué trata la tarea
2. Si tiene preguntas o ejercicios para resolver, resuélvelos paso a paso, con fórmulas si es Excel
3. Dame un borrador listo para que el alumno copie, revise y entregue. No entregues directamente, solo el borrador.

Contenido de la tarea:
{texto_archivo[:10000]}"""

        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        data = r.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error Gemini: {e}\nTexto extraído: {texto_archivo[:2000]}"

# Login CIMAC
s = requests.Session()
r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
soup = BeautifulSoup(r.text, 'html.parser')
t = soup.find('input', {'name': 'logintoken'})
logintoken = t['value'] if t else ""
s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": logintoken}, timeout=20)

vistos = []
if os.path.exists(SEEN_FILE):
    try: vistos = json.loads(open(SEEN_FILE).read())
    except: vistos = []

r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
soup = BeautifulSoup(r.text, 'html.parser')

nuevos = 0
for link in soup.find_all('a', href=True):
    href = link['href']
    if any(x in href.lower() for x in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']) or 'mod_resource' in href:
        if href not in vistos and href.startswith('http'):
            try:
                print(f"Nuevo: {href}")
                file_r = s.get(href, timeout=30)
                if len(file_r.content) < 1000: continue
                texto = ""
                if 'pdf' in file_r.headers.get('content-type','').lower() or href.lower().endswith('.pdf'):
                    pdf = PyPDF2.PdfReader(io.BytesIO(file_r.content))
                    texto = "\n".join([p.extract_text() or "" for p in pdf.pages[:8]])
                elif 'officedocument.wordprocessing' in file_r.headers.get('content-type','') or href.lower().endswith('.docx'):
                    doc = docx.Document(io.BytesIO(file_r.content))
                    texto = "\n".join([p.text for p in doc.paragraphs[:80]])
                elif 'spreadsheet' in file_r.headers.get('content-type','') or href.lower().endswith(('.xlsx','.xls')):
                    wb = openpyxl.load_workbook(io.BytesIO(file_r.content), data_only=True)
                    ws = wb.active
                    texto = "\n".join([f"{c.value}" for row in list(ws.iter_rows(min_row=1, max_row=30)) for c in row if c.value])

                if len(texto.strip()) > 20:
                    solucion = resolver_con_gemini(texto)
                    enviar_whatsapp(f"📚 CIMAC - NUEVO ARCHIVO DETECTADO\n\nMateria: {link.text.strip()[:100]}\nLink: {href}\n\n--- GEMINI LO RESOLVIÓ (revisa y entrega) ---\n{solucion}")
                    vistos.append(href)
                    nuevos += 1
            except Exception as e:
                print(f"Error {href}: {e}")

open(SEEN_FILE, 'w').write(json.dumps(vistos))
if nuevos==0:
    print("Sin archivos nuevos")
