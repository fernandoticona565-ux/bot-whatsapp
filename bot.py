import os, requests
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
    
    payload = {"username": USER, "password": PASS, "logintoken": logintoken}
    s.post("https://campus.cimac.jedu.pe/login/index.php", data=payload, timeout=20)
    
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    texto = r.text.lower()
    
    if "tic" in texto or "tarea" in texto or "actividad" in texto:
        enviar_whatsapp("📚 Hola Fernando! Revisé tu plataforma CIMAC ahora mismo y hay actividades pendientes de TIC II. Entra rápido a campus.cimac.jedu.pe/my/ - Si es una tarea mándame foto por aquí y te la resuelvo al toque para tu número 921493279.")
    else:
        print("Revisado, sin tareas nuevas detectadas")
        
except Exception as e:
    print(f"Error: {e}")
