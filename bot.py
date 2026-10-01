import os, requests, json, io
from bs4 import BeautifulSoup
import PyPDF2, docx, openpyxl

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ID_INSTANCE = "710722753429"
MI_NUMERO = "51921493279@c.us"
SEEN_FILE = "vistos.json"

def enviar(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    for i in range(0, len(msg), 3500):
        requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3500]}, timeout=30)

def resolver_gemini(texto):
    if not GEMINI_KEY or len(texto.strip())<20: return ""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        prompt = f"Resume y resuelve esta tarea de CIMAC en borrador listo para entregar. Si es Excel explica fórmulas:\n\n{texto[:10000]}"
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        return "\n\n--- SOLUCIÓN GEMINI ---\n" + r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return ""

s = requests.Session()
soup = BeautifulSoup(s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20).text, 'html.parser')
lt = soup.find('input', {'name': 'logintoken'})
s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": lt['value'] if lt else ""}, timeout=20)

vistos = json.loads(open(SEEN_FILE).read()) if os.path.exists(SEEN_FILE) else []

page = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
soup = BeautifulSoup(page.text, 'html.parser')

# Busca todos los links de actividades de Moodle
nuevos = 0
for a in soup.find_all('a', href=True):
    href = a['href']
    texto_link = a.get_text(strip=True)
    if len(texto_link) < 3: continue

    # Detectar cualquier actividad: tarea, recurso, foro, cuestionario, etc
    if any(x in href for x in ['/mod/resource/', '/mod/assign/', '/mod/forum/', '/mod/quiz/', '/mod/url/']) or href.lower().endswith(('.pdf','.docx','.doc','.xlsx','.xls')):
        if href not in vistos and href.startswith('http'):
            tipo = "📄 ARCHIVO" if any(x in href for x in ['resource','.pdf','.docx','.xlsx']) else "📝 TAREA" if 'assign' in href else "💬 FORO/ANUNCIO" if 'forum' in href else "📌 ACTIVIDAD NUEVA"
            mensaje = f"{tipo} DETECTADO EN CIMAC\n\nMateria/Actividad: {texto_link}\nLink: {href}"

            # Si es archivo, intenta descargar y resolver
            try:
                if any(x in href.lower() for x in ['.pdf','.docx','.xlsx']) or 'resource' in href:
                    fr = s.get(href, timeout=25)
                    txt=""
                    if len(fr.content) > 2000:
                        if 'pdf' in fr.headers.get('content-type','').lower() or '.pdf' in href.lower():
                            pdf=PyPDF2.PdfReader(io.BytesIO(fr.content))
                            txt="\n".join([(p.extract_text() or "") for p in pdf.pages[:5]])
                        elif '.docx' in href.lower():
                            d=docx.Document(io.BytesIO(fr.content))
                            txt="\n".join([p.text for p in d.paragraphs[:70]])
                        mensaje += resolver_gemini(txt)
            except: pass

            enviar(mensaje)
            vistos.append(href)
            nuevos += 1
            if nuevos >= 3: break # max 3 por corrida para no spam

open(SEEN_FILE,'w').write(json.dumps(vistos))
print(f"Nuevos detectados: {nuevos}")
