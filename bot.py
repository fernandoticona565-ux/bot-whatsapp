import os, requests, re
from bs4 import BeautifulSoup
import fitz
from google import genai

USER=os.getenv("CIMAC_USER"); PASS=os.getenv("CIMAC_PASS")
TOKEN=os.getenv("GREEN_TOKEN"); ID=os.getenv("ID_INSTANCE")
GEMINI=os.getenv("GEMINI_API_KEY")
CURSO_Q=os.getenv("CURSO_BUSCAR","todo").lower().strip()
SECCION_Q=os.getenv("SECCION_BUSCAR","todo").lower().strip()
MI="51921493279@c.us"

MAPA = {"base":"base de datos","web":"entornos web","hab":"habilidades","diseno":"grafico","diseño":"grafico","progra":"programacion","ingles":"idiomas","soporte":"soporte","tic":"tecnologias","tecnologia":"tecnologias","3383":"tecnologias"}
for k,v in MAPA.items():
    if k in CURSO_Q: CURSO_Q=v; break

client = genai.Client(api_key=GEMINI)

def generar(prompt):
    for modelo in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]:
        try:
            resp = client.models.generate_content(model=modelo, contents=prompt)
            return resp.text
        except Exception as e:
            print(f"Fallo {modelo}: {e}")
            continue
    return "PDF descargado, revisalo manual."

def wa(msg):
    url=f"https://api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"
    for i in range(0,len(msg),3500):
        try:
            requests.post(url, json={"chatId":MI,"message":msg[i:i+3500]}, timeout=20)
        except: pass

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
lp=s.get("https://campus.cimac.jedu.pe/login/index.php",timeout=30)
soup=BeautifulSoup(lp.text,'html.parser')
lt=soup.find('input',{'name':'logintoken'})
data={"username":USER,"password":PASS}
if lt: data["logintoken"]=lt['value']
s.post("https://campus.cimac.jedu.pe/login/index.php",data=data,timeout=30)

my_html=s.get("https://campus.cimac.jedu.pe/my/",timeout=30).text
ids=list(set(re.findall(r'course/view\.php\?id=(\d+)',my_html)))
cursos=[]
for cid in ids:
    try:
        ch=s.get(f"https://campus.cimac.jedu.pe/course/view.php?id={cid}",timeout=20).text
        name=BeautifulSoup(ch,'html.parser').title.get_text(strip=True).lower()
        cursos.append({"id":cid,"name":name})
    except: pass

filtrados = cursos if CURSO_Q=="todo" else [c for c in cursos if CURSO_Q in c['name']]
wa(f"Buscando: {CURSO_Q.upper()} / {SECCION_Q.upper()} Cursos: {len(filtrados)}")

for curso in filtrados:
    try:
        url_assign = f"https://campus.cimac.jedu.pe/mod/assign/index.php?id={curso['id']}"
        html_assign = s.get(url_assign,timeout=25).text
        soup_a = BeautifulSoup(html_assign,'html.parser')
        links = list(set([a['href'] for a in soup_a.find_all('a', href=True) if 'mod/assign/view.php?id=' in a['href']]))
        if SECCION_Q in ["recursos","todo","recursos de clases"]:
            html_c = s.get(f"https://campus.cimac.jedu.pe/course/view.php?id={curso['id']}",timeout=20).text
            for a in BeautifulSoup(html_c,'html.parser').find_all('a', href=True):
                if 'mod/resource/view.php' in a['href']: links.append(a['href'])
        links=list(set(links))
        wa(f"Curso: {curso['name'][:70]} Encontre {len(links)} archivos. Resolviendo...")
        for link in links[:5]:
            furl=link if link.startswith("http") else "https://campus.cimac.jedu.pe"+link
            page=s.get(furl,timeout=20).text
            sp=BeautifulSoup(page,'html.parser')
            titulo=sp.find('h2').get_text(strip=True) if sp.find('h2') else "Tarea"
            files=[a['href'] for a in sp.find_all('a',href=True) if 'forcedownload' in a['href'] or '.pdf' in a['href'].lower()]
            if not files: files=[furl]
            for fu in files[:2]:
                u2=fu if fu.startswith("http") else "https://campus.cimac.jedu.pe"+fu
                data=s.get(u2,timeout=30).content
                texto=""
                try:
                    doc=fitz.open(stream=data,filetype="pdf")
                    for p in doc: texto+=p.get_text()
                except: texto=sp.get_text(" ",strip=True)[:8000]
                if len(texto)<30: continue
                prompt=f"Curso {curso['name']} Tarea {titulo} Contenido: {texto[:6000]}. Dame resumen y solucion lista para copiar, corto WhatsApp."
                sol=generar(prompt)
                wa(f"{curso['name'][:60]} | {titulo} | {u2} SOLUCION: {sol[:3500]}")
    except Exception as e: wa(f"Error en {curso['name']}: {e}")

wa("Fin")
