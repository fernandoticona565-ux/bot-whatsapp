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

def enviar(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    for i in range(0, len(msg), 3500):
        requests.post(url, json={"chatId": MI_NUMERO, "message": msg[i:i+3500]}, timeout=30)

def resolver_gemini(texto):
    if not GEMINI_KEY:
        return "Texto extraído (falta GEMINI_API_KEY para resolver)"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        prompt = f"Resume y resuelve esta tarea de CIMAC en un borrador listo para entregar. Si es Excel explica fórmulas:\n\n{texto[:10000]}"
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error IA: {e}"

try:
    s = requests.Session()
    r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    lt = soup.find('input', {'name': 'logintoken'})
    lt = lt['value'] if lt else ""
    s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": lt}, timeout=20)
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')

    count=0
    for a in soup.find_all('a', href=True):
        href=a['href']
        if any(x in href.lower() for x in ['.pdf','.docx','.xlsx']) and href.startswith('http'):
            try:
                fr=s.get(href, timeout=20)
                if len(fr.content)<2000: continue
                texto=""
                if '.pdf' in href.lower():
                    pdf=PyPDF2.PdfReader(io.BytesIO(fr.content))
                    texto="\n".join([(p.extract_text() or "") for p in pdf.pages[:5]])
                elif '.docx' in href.lower():
                    d=docx.Document(io.BytesIO(fr.content))
                    texto="\n".join([p.text for p in d.paragraphs[:60]])
                elif '.xlsx' in href.lower():
                    wb=openpyxl.load_workbook(io.BytesIO(fr.content), data_only=True)
                    ws=wb.active
                    texto="\n".join([str(c.value) for row in list(ws.iter_rows(max_row=20)) for c in row if c.value])

                if len(texto.strip())>30:
                    sol=resolver_gemini(texto)
                    enviar(f"📚 CIMAC NUEVO: {a.text.strip()[:80]}\n{href}\n\n--- SOLUCIÓN GEMINI ---\n{sol}")
                    count+=1
                    if count>=2: break
            except: pass

    if count==0:
        print("Sin archivos nuevos hoy")
        # enviar("✅ CIMAC: Revisado con Gemini, sin archivos nuevos")

except Exception as e:
    print(f"Error: {e}")
