import os, requests, re
from bs4 import BeautifulSoup
import fitz, google.generativeai as genai

USER=os.getenv("CIMAC_USER"); PASS=os.getenv("CIMAC_PASS")
TOKEN=os.getenv("GREEN_TOKEN"); ID=os.getenv("ID_INSTANCE")
GEMINI=os.getenv("GEMINI_API_KEY")
CURSO_Q=os.getenv("CURSO_BUSCAR","todo").lower().strip()
SECCION_Q=os.getenv("SECCION_BUSCAR","todo").lower().strip()
MI="51921493279@c.us"

MAPA = {"base":"base de datos","web":"entornos web","hab":"habilidades","diseno":"grafico","diseño":"grafico","progra":"programacion","ingles":"idiomas","soporte":"soporte","tic":"tecnologias","tecnologia":"tecnologias","3383":"tecnologias"}
for k,v in MAPA.items():
    if k in CURSO_Q: CURSO_Q=v; break

genai.configure(api_key=GEMINI)
model = genai.GenerativeModel("gemini-2.5-flash")

def wa(msg):
    url=f"https://api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"
    for i in range(0,len(msg),3500):
        requests.post(url, json={"chatId":MI,"message":msg[i:i+3500]}, timeout=20)

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
lp=s.get("https://campus.cimac.jedu.pe/login/index.php",timeout=30)
soup=BeautifulSoup(lp.text,'html.parser')
lt=soup.find('input',{'name':'logintoken'})
data={"username":USER,"password":PASS}
if lt: data["logintoken"]=lt['value']
s.post("https://campus.cimac.jedu.pe/login/index.php",data=data,timeout=30)

# SACA CURSOS
my_html=s.get("https://campus.cimac.jedu.pe/my/",timeout=30).text
ids=list(set(re.findall(r'course/view\.php\?id=(\d+)',my_html)))
cursos=[]
for cid in ids:
    try:
        ch=s.get(f"https://campus.cimac.jedu.pe/course/view.php?id={cid}",timeout=20).text
        name=BeautifulSoup(ch,'html.parser').title.get_text(strip=True).lower()
        cursos.append({"id":cid,"name":name})
    except: pass

filtrados = cursos if CURSO_Q=="todo" else [c for c in cursos if CURSO_Q in c['name'] or CURSO_Q in c['id']]
wa(f"🔍 Buscando: {CURSO_Q.upper()} / {SECCION_Q.upper()}\nCursos: {len(filtrados)} -> {[c['name'][:40] for c in filtrados]}")

for curso in filtrados:
    # METODO QUE SI FUNCIONA EN MOODLE: /mod/assign/index.php?id=
    try:
        url_assign = f"https://campus.cimac.jedu.pe/mod/assign/index.php?id={curso['id']}"
        html_assign = s.get(url_assign,timeout=25).text
        soup_a = BeautifulSoup(html_assign,'html.parser')
        # Busca todas las tareas en la tabla
        links = []
        for a in soup_a.find_all('a', href=True):
            if 'mod/assign/view.php?id=' in a['href']:
                links.append(a['href'])
        links=list(set(links))

        if not links and "tarea" in SECCION_Q:
            wa(f"⚠️ {curso['name'][:70]}\nEntré a {url_assign} y no hay tareas listadas. Puede que estén como 'Tarea CLS2' en recursos. Prueba con 'todo' o 'recursos'")
            continue

        # Si pide recursos, tambien saca recursos
        if SECCION_Q in ["recursos","todo"]:
            url_res = f"https://campus.cimac.jedu.pe/course/view.php?id={curso['id']}"
            html_c = s.get(url_res,timeout=20).text
            for a in BeautifulSoup(html_c,'html.parser').find_all('a', href=True):
                if 'mod/resource/view.php' in a['href']:
                    links.append(a['href'])

        links=list(set(links))
        wa(f"📚 {curso['name'][:70]}\nEncontré {len(links)} tareas/recursos. Resolviendo...")

        for link in links[:5]:
            furl=link if link.startswith("http") else "https://campus.cimac.jedu.pe"+link
            page=s.get(furl,timeout=20).text
            sp=BeautifulSoup(page,'html.parser')
            titulo=sp.find('h2').get_text(strip=True) if sp.find('h2') else furl

            # Descarga PDF
            files=[a['href'] for a in sp.find_all('a',href=True) if 'forcedownload' in a['href'] or '.pdf' in a['href'].lower()]
            if not files: files=[furl]

            for fu in files[:2]:
                u2=fu if fu.startswith("http") else "https://campus.cimac.jedu.pe"+fu
                data=s.get(u2,timeout=30).content
                texto=""
                try:
                    doc=fitz.open(stream=data,filetype="pdf")
                    for p in doc: texto+=p.get_text()
                except:
                    texto=sp.get_text(" ",strip=True)[:8000]
                if len(texto)<30: continue
                prompt=f"Curso {curso['name']} Tarea {titulo} Contenido: {texto[:6000]}. Dame que pide y solucion lista para copiar, corto para WhatsApp."
                sol=model.generate_content(prompt).text
                wa(f"📚 {curso['name'][:60]}\n📝 {titulo}\n🔗 {u2}\n\n🤖 SOLUCION:\n{sol[:3500]}")
    except Exception as e:
        wa(f"Error en {curso['name']}: {e}")

wa("✅ Fin")
