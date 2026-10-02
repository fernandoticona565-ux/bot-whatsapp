import os, requests, re
from bs4 import BeautifulSoup
import fitz, google.generativeai as genai

USER=os.getenv("CIMAC_USER"); PASS=os.getenv("CIMAC_PASS")
TOKEN=os.getenv("GREEN_TOKEN"); ID=os.getenv("ID_INSTANCE")
GEMINI=os.getenv("GEMINI_API_KEY")
CURSO_Q=os.getenv("CURSO_BUSCAR","todo").lower().strip()
SECCION_Q=os.getenv("SECCION_BUSCAR","todo").lower().strip()
MI="51921493279@c.us"

MAPA = {
    "base": "base de datos", "datos": "base de datos", "sql": "base de datos",
    "web": "entornos web", "html": "entornos web",
    "hab": "habilidades", "actitudes": "habilidades",
    "diseno": "grafico", "diseño": "grafico", "ilustrator": "grafico", "publicitario": "grafico",
    "progra": "programacion", "algoritmia": "programacion", "fundamentos": "programacion",
    "ingles": "idiomas", "idioma": "idiomas", "english": "idiomas",
    "soporte": "soporte", "organizacion": "soporte", "administracion": "soporte",
    "tic": "tecnologias", "excel": "tecnologias", "informacion": "tecnologias", "3383": "3383"
}
for k,v in MAPA.items():
    if k in CURSO_Q:
        CURSO_Q = v
        break

genai.configure(api_key=GEMINI)
model = genai.GenerativeModel("gemini-1.5-flash")

def wa(msg):
    url=f"https://api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"
    try:
        for i in range(0,len(msg),3500):
            requests.post(url, json={"chatId":MI,"message":msg[i:i+3500]}, timeout=25)
    except Exception as e: print(e)

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
# LOGIN
lp=s.get("https://campus.cimac.jedu.pe/login/index.php",timeout=30)
soup=BeautifulSoup(lp.text,'html.parser')
lt=soup.find('input',{'name':'logintoken'})
data={"username":USER,"password":PASS}
if lt: data["logintoken"]=lt['value']
s.post("https://campus.cimac.jedu.pe/login/index.php",data=data,timeout=30)

# 1. SACA TUS 8 CURSOS REALES
html_my = s.get("https://campus.cimac.jedu.pe/my/", timeout=30).text
cursos_ids = list(set(re.findall(r'course/view\.php\?id=(\d+)', html_my)))
print(f"IDs encontrados: {cursos_ids}")

cursos=[]
for cid in cursos_ids:
    try:
        url=f"https://campus.cimac.jedu.pe/course/view.php?id={cid}"
        ch=s.get(url,timeout=20).text
        title = BeautifulSoup(ch,'html.parser').title.get_text(strip=True).lower() if BeautifulSoup(ch,'html.parser').title else ""
        cursos.append({"id":cid,"url":url,"name":title,"html":ch})
    except: pass

print(f"Total cursos cargados: {len(cursos)}")
for c in cursos: print(c['id'], c['name'][:60])

# 2. FILTRA
if CURSO_Q=="todo":
    filtrados=cursos
else:
    filtrados=[c for c in cursos if CURSO_Q in c['name'] or CURSO_Q in c['id']]
    if not filtrados: # si escribiste mal, busca por mapa inverso
        filtrados=[c for c in cursos if "tecnologias" in CURSO_Q and "tecnologias" in c['name']]

if not filtrados:
    wa(f"⚠️ No encontre curso '{CURSO_Q}'. Tus cursos son:\n" + "\n".join([f"{c['id']} - {c['name'][:50]}" for c in cursos]))
    exit()

wa(f"🔍 Buscando: {CURSO_Q.upper()} / {SECCION_Q.upper()}\nCursos encontrados: {len(filtrados)} -> {[c['name'][:40] for c in filtrados]}")

# 3. BUSCA TAREAS Y RECURSOS - METODO DIRECTO
for curso in filtrados:
    html=curso['html']
    # Todos los links de tareas y recursos
    tareas_links = list(set(re.findall(r'https://campus\.cimac\.jedu\.pe/mod/assign/view\.php\?id=\d+', html)))
    recursos_links = list(set(re.findall(r'https://campus\.cimac\.jedu\.pe/mod/resource/view\.php\?id=\d+', html)))

    if "tarea" in SECCION_Q: links=tareas_links
    elif "recurso" in SECCION_Q: links=recursos_links
    else: links=tareas_links+recursos_links

    if not links:
        wa(f"⚠️ Curso: {curso['name'][:70]}\nNo hay links de '{SECCION_Q}'. Tareas encontradas: {len(tareas_links)} Recursos: {len(recursos_links)}")
        continue

    wa(f"📚 {curso['name'][:70]}\nEncontré {len(links)} archivos de {SECCION_Q}, descargando...")

    for link in links[:5]: # max 5 por corrida
        try:
            page=s.get(link,timeout=20).text
            sp=BeautifulSoup(page,'html.parser')
            titulo=sp.find('h2').get_text(strip=True) if sp.find('h2') else link

            # Busca PDFs dentro
            files=[a['href'] for a in sp.find_all('a',href=True) if 'forcedownload=1' in a['href'] or '.pdf' in a['href'].lower()]
            if not files: files=[link]

            for fu in files[:2]:
                u2=fu if fu.startswith("http") else "https://campus.cimac.jedu.pe"+fu
                try:
                    data=s.get(u2,timeout=30).content
                    texto=""
                    try:
                        doc=fitz.open(stream=data, filetype="pdf")
                        for p in doc: texto+=p.get_text()
                    except:
                        texto=sp.get_text(" ",strip=True)[:8000]

                    if len(texto)<30: continue

                    prompt=f"Curso CIMAC: {curso['name']} Tarea: {titulo} Contenido: {texto[:6000]}. Responde corto para WhatsApp: que pide y solucion lista para copiar."
                    sol=model.generate_content(prompt).text
                    wa(f"📚 {curso['name'][:60]}\n📝 {titulo}\n🔗 {u2}\n\n🤖 SOLUCION:\n{sol[:3500]}")
                except Exception as e: print(f"Error archivo {e}")
        except Exception as e: print(f"Error link {e}")

wa("✅ Fin")
