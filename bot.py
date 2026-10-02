import os, requests, io, re
import fitz
from google import genai
import pandas as pd
import docx

USER=os.getenv("CIMAC_USER")
PASS=os.getenv("CIMAC_PASS")
TOKEN=os.getenv("GREEN_TOKEN")
ID=os.getenv("ID_INSTANCE")
GEMINI=os.getenv("GEMINI_API_KEY")
CURSO_Q=os.getenv("CURSO_BUSCAR","todo").lower().strip()
MI="51921493279@c.us"
MOODLE="https://campus.cimac.jedu.pe"

MAPA = {"base":"base de datos","web":"entornos web","hab":"habilidades","diseno":"grafico","diseño":"grafico","progra":"programacion","ingles":"idiomas","soporte":"soporte","tic":"tecnologias","3383":"tecnologias"}
for k,v in MAPA.items():
    if k in CURSO_Q: CURSO_Q=v; break

client = genai.Client(api_key=GEMINI)

def wa(msg):
    url=f"https://api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"
    for i in range(0,len(msg),3500):
        try: requests.post(url, json={"chatId":MI,"message":msg[i:i+3500]}, timeout=25)
        except: pass

def generar(prompt):
    for m in ["gemini-2.5-flash","gemini-2.5-flash-lite"]:
        try:
            r=client.models.generate_content(model=m, contents=prompt)
            return r.text
        except: continue
    return "archivo listo para revisar"

def leer_binario(content, url):
    txt=""
    try:
        if ".xlsx" in url or ".xls" in url or "spreadsheet" in url:
            xls=pd.ExcelFile(io.BytesIO(content))
            for hoja in xls.sheet_names[:4]:
                df=xls.parse(hoja, nrows=30)
                txt+=f"\n[HOJA {hoja}]\n{df.to_string()}\n"
        elif ".docx" in url:
            d=docx.Document(io.BytesIO(content))
            txt="\n".join([p.text for p in d.paragraphs][:100])
        else:
            doc=fitz.open(stream=content,filetype="pdf")
            for p in doc: txt+=p.get_text()
    except:
        try:
            doc=fitz.open(stream=content,filetype="pdf")
            for p in doc: txt+=p.get_text()
        except: txt=""
    return txt[:7000]

# 1. TOKEN OFICIAL MOODLE
print("Obteniendo token...")
r=requests.get(f"{MOODLE}/login/token.php", params={"username":USER,"password":PASS,"service":"moodle_mobile_app"}, timeout=20)
data=r.json()
if "token" not in data:
    wa(f"Error login CIMAC: {data}")
    exit()
moodle_token=data["token"]
wa(f"API conectada. Token OK. Buscando: {CURSO_Q.upper()}")

# 2. MIS CURSOS
def call_ws(func, params={}):
    params.update({"wstoken":moodle_token,"wsfunction":func,"moodlewsrestformat":"json"})
    return requests.post(f"{MOODLE}/webservice/rest/server.php", data=params, timeout=30).json()

# cursos por timeline (los 8 tuyos)
try:
    cursos = call_ws("core_course_get_enrolled_courses_by_timeline_classification", {"classification":"all"})
    cursos = cursos.get("courses",[])
except:
    cursos = call_ws("core_enrol_get_users_courses", {"userid":0})
    if isinstance(cursos, dict): cursos=cursos.get("courses",[])

# fallback si falla
if not cursos:
    import requests as req, re
    from bs4 import BeautifulSoup
    s=req.Session()
    lp=s.get(f"{MOODLE}/login/index.php",timeout=20)
    soup=BeautifulSoup(lp.text,'html.parser')
    lt=soup.find('input',{'name':'logintoken'})
    d={"username":USER,"password":PASS}
    if lt: d["logintoken"]=lt['value']
    s.post(f"{MOODLE}/login/index.php",data=d,timeout=20)
    my=s.get(f"{MOODLE}/my/",timeout=20).text
    ids=list(set(re.findall(r'course/view\.php\?id=(\d+)',my)))
    cursos=[{"id":cid,"fullname":cid} for cid in ids]

filtrados=[]
for c in cursos:
    nombre=(c.get("fullname","")+ " "+c.get("shortname","")).lower()
    if CURSO_Q=="todo" or CURSO_Q in nombre:
        filtrados.append(c)

wa(f"Encontre {len(filtrados)} cursos. Ahora sacando TODAS las tareas con API, sin importar nombre.")

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
# login para descargar archivos
lp=s.get(f"{MOODLE}/login/index.php",timeout=20)
from bs4 import BeautifulSoup
soup=BeautifulSoup(lp.text,'html.parser')
lt=soup.find('input',{'name':'logintoken'})
d={"username":USER,"password":PASS}
if lt: d["logintoken"]=lt['value']
s.post(f"{MOODLE}/login/index.php",data=d,timeout=20)

for curso in filtrados:
    cid=curso["id"]
    try:
        # ESTO TRAE TODO: recursos, tareas, foros, carpetas, sin importar el nombre
        contents = call_ws("core_course_get_contents", {"courseid":cid})
        wa(f"CURSO {curso.get('fullname','ID '+str(cid))[:60].upper()} -> {len(contents)} secciones. Leyendo todo...")

        for seccion in contents:
            for mod in seccion.get("modules",[]):
                modname=mod.get("modname","") # assign, resource, quiz, forum, folder, etc
                nombre=mod.get("name","sin nombre")
                # AHORA SI: leemos TODO modname, no solo assign
                if modname not in ["assign","resource","forum","quiz","workshop","lesson","folder","url","page"]:
                    continue

                archivos=[]
                if "contents" in mod:
                    for f in mod["contents"]:
                        if f.get("type")=="file":
                            archivos.append(f.get("fileurl")+"?token="+moodle_token)

                # si no tiene archivo, igual leemos la descripcion
                texto_base = mod.get("description","") + " " + nombre
                if modname=="assign":
                    # traer intro mas completa de la tarea
                    try:
                        assigns = call_ws("mod_assign_get_assignments", {"courseids[]":cid})
                        for co in assigns.get("courses",[]):
                            for a in co.get("assignments",[]):
                                if a["id"]==mod.get("instance"):
                                    texto_base+= " " + a.get("intro","")
                    except: pass

                for fileurl in archivos[:4]:
                    try:
                        bin_data=s.get(fileurl,timeout=30).content if "token=" not in fileurl else requests.get(fileurl,timeout=30).content
                        if len(bin_data)<1000: continue
                        texto=leer_binario(bin_data, fileurl)
                        if not texto: texto=texto_base[:6000]
                        else: texto=texto_base[:2000] + "\n" + texto

                        prompt=f"Curso {curso.get('fullname')} Actividad {nombre} Tipo {modname} Contenido: {texto[:6000]}. Da QUE PIDE y SOLUCION lista para copiar en WhatsApp corto. Si es Excel da formulas exactas."
                        sol=generar(prompt)
                        wa(f"📚 {curso.get('fullname','')[:45]}\n📝 {nombre} ({modname})\n🔗 {fileurl[:80]}\n\nSOLUCION:\n{sol[:3500]}")
                    except Exception as e: print(e)

                # si no tenia archivo pero si descripcion (foros, paginas)
                if not archivos and len(texto_base)>20:
                    prompt=f"Curso {curso.get('fullname')} Actividad {nombre} Tipo {modname} Descripcion: {texto_base[:6000]}. Da resumen y solucion WhatsApp."
                    sol=generar(prompt)
                    wa(f"📚 {curso.get('fullname','')[:45]}\n📝 {nombre} ({modname})\n\nSOLUCION:\n{sol[:3500]}")

    except Exception as e:
        wa(f"Error curso {cid}: {e}")

wa("Fin API - Se leyeron TODAS las actividades sin filtrar por nombre")
