import os, requests, re, io
from bs4 import BeautifulSoup
import fitz, google.generativeai as genai

USER=os.getenv("CIMAC_USER"); PASS=os.getenv("CIMAC_PASS")
TOKEN=os.getenv("GREEN_TOKEN"); ID=os.getenv("ID_INSTANCE")
GEMINI=os.getenv("GEMINI_API_KEY")
CURSO_Q=os.getenv("CURSO_BUSCAR","tic").lower()
SECCION_Q=os.getenv("SECCION_BUSCAR","tareas").lower()
MI="51921493279@c.us"

# TU MAPA EXACTO SEGUN TUS FOTOS
MAPA = {
    "base": "base de datos",
    "datos": "base de datos",
    "sql": "base de datos",
    "web": "entornos web",
    "html": "entornos web",
    "hab": "habilidades",
    "actitudes": "habilidades",
    "diseno": "diseño grafico",
    "diseño": "diseño grafico",
    "illustrator": "diseño grafico",
    "progra": "fundamentos de programación",
    "algoritmia": "fundamentos de programación",
    "ingles": "idiomas",
    "idioma": "idiomas",
    "soporte": "organización y administración",
    "admin": "organización y administración",
    "tic": "tecnologias de la informacion",
    "excel": "tecnologias de la informacion",
    "3383": "tecnologias"
}
for k,v in MAPA.items():
    if k in CURSO_Q: CURSO_Q=v; break

genai.configure(api_key=GEMINI)
model = genai.GenerativeModel("gemini-1.5-flash")

def wa(msg):
    url=f"https://api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"
    for i in range(0,len(msg),3500):
        requests.post(url, json={"chatId":MI,"message":msg[i:i+3500]}, timeout=25)

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
lp=s.get("https://campus.cimac.jedu.pe/login/index.php",timeout=30)
soup=BeautifulSoup(lp.text,'html.parser')
lt=soup.find('input',{'name':'logintoken'})
data={"username":USER,"password":PASS}
if lt: data["logintoken"]=lt['value']
s.post("https://campus.cimac.jedu.pe/login/index.php",data=data,timeout=30)

# SACAR TUS 8 CURSOS
cursos={}
for u in ["https://campus.cimac.jedu.pe/my/","https://campus.cimac.jedu.pe/my/courses.php"]:
    try:
        html=s.get(u,timeout=25).text
        for cid in set(re.findall(r'course/view\.php\?id=(\d+)',html)):
            if cid not in cursos:
                try:
                    ch=s.get(f"https://campus.cimac.jedu.pe/course/view.php?id={cid}",timeout=15).text
                    name=BeautifulSoup(ch,'html.parser').title.get_text(strip=True) if BeautifulSoup(ch,'html.parser').title else cid
                    cursos[cid]={"id":cid,"url":f"https://campus.cimac.jedu.pe/course/view.php?id={cid}","name":name,"html":ch}
                except: pass
    except: pass

# FILTRAR POR LO QUE ESCRIBISTE
filtrados=[c for c in cursos.values() if CURSO_Q in c['name'].lower()]
if SECCION_Q=="todo": filtrados=list(cursos.values())
if not filtrados: filtrados=list(cursos.values())[:1]

wa(f"🔍 Buscando: {CURSO_Q.upper()} / {SECCION_Q.upper()}\nCursos encontrados: {len(filtrados)}")

for curso in filtrados:
    soup=BeautifulSoup(curso['html'],'html.parser')
    # Detecta secciones
    target=[]
    for li in soup.find_all('li', id=re.compile(r'section-')):
        if SECCION_Q in li.get_text(" ").lower() or SECCION_Q=="todo" or SECCION_Q in ["tareas","recursos","practica","silabo"]:
            # Si pide tareas busca assign, si pide recursos busca resource
            if "tarea" in SECCION_Q:
                for a in li.find_all('a', href=True):
                    if 'assign' in a['href']: target.append(a['href'])
            else:
                for a in li.find_all('a', href=True):
                    if 'resource' in a['href'] or 'folder' in a['href'] or 'assign' in a['href']: target.append(a['href'])

    target=list(set(target))[:6]
    if not target:
        wa(f"⚠️ {curso['name'][:50]}\nNo encontre '{SECCION_Q}'. Pero tiene {len(soup.find_all('a'))} archivos.")
        continue

    for link in target:
        furl=link if link.startswith("http") else "https://campus.cimac.jedu.pe"+link
        try:
            page=s.get(furl,timeout=20).text
            sp=BeautifulSoup(page,'html.parser')
            files=[a['href'] for a in sp.find_all('a',href=True) if 'forcedownload' in a['href'] or '.pdf' in a['href'].lower()]
            if not files: files=[furl]

            for fu in files[:2]:
                u2=fu if fu.startswith("http") else "https://campus.cimac.jedu.pe"+fu
                data=s.get(u2,timeout=30).content
                texto=""
                try:
                    doc=fitz.open(stream=data, filetype="pdf")
                    for p in doc: texto+=p.get_text()
                except: texto=sp.get_text(" ")[:7000]

                if len(texto)<50: continue
                prompt=f"Eres alumno CIMAC Ciclo 2. Curso: {curso['name']} Seccion: {SECCION_Q} Titulo: {sp.find('h2').get_text() if sp.find('h2') else ''} Contenido: {texto[:6000]}. Dame resumen y solucion lista para entregar, formato WhatsApp corto."
                sol=model.generate_content(prompt).text
                wa(f"📚 {curso['name'][:60]}\n📂 {SECCION_Q.upper()}\n🔗 {u2}\n\n🤖 SOLUCION:\n{sol[:3500]}")
        except Exception as e: print(e)

wa("✅ Fin")
