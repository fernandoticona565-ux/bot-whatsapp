import os, requests, re
from bs4 import BeautifulSoup

ID_INSTANCE = "710722753429"
TOKEN = os.getenv("GREEN_TOKEN")
USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
MI_NUMERO = "51921493279@c.us"

def enviar_whatsapp(mensaje):
    url = f"https://7107.api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    data = {"chatId": MI_NUMERO, "message": mensaje}
    requests.post(url, json=data, timeout=20)

try:
    s = requests.Session()
    r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    token_input = soup.find('input', {'name': 'logintoken'})
    logintoken = token_input['value'] if token_input else ""
    
    s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": logintoken}, timeout=20)
    
    # Revisa TODOS los cursos
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    texto_completo = soup.get_text().lower()
    
    # Busca palabras clave de tareas en todo el dashboard
    if any(p in texto_completo for p in ["tarea para entregar", "fecha límite", "pendiente", "por entregar", "vence"]):
        # Saca un resumen de que cursos tienen actividad
        cursos = re.findall(r'Curso:\s*(.+)|TIC\s*II|Desarrollo Personal|Matemática|Comunicación', r.text, re.IGNORECASE)
        mensaje = f"📚 Hola Fernando! Revisé TODA tu plataforma CIMAC y detecté tareas pendientes.\n\nEntra ahora a revisar: https://campus.cimac.jedu.pe/my/\n\nSi es tarea, mándame foto aquí a tu WhatsApp 921493279 y te la resuelvo al toque."
        enviar_whatsapp(mensaje)
        print("Tareas detectadas en varios cursos, mensaje enviado")
    else:
        print("Revisé todos los cursos, sin pendientes urgentes")
        
except Exception as e:
    print(f"Error: {e}")
