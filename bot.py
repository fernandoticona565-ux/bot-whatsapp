import os, re, requests
from bs4 import BeautifulSoup

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
ID_INSTANCE = "7107227534"
MI_NUMERO = "51921493279@c.us"

def enviar_whatsapp(msg):
    url = f"https://7107.api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    requests.post(url, json={"chatId": MI_NUMERO, "message": msg}, timeout=20)

try:
    s = requests.Session()
    r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    token_input = soup.find('input', {'name': 'logintoken'})
    logintoken = token_input['value'] if token_input else ""
    s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": logintoken}, timeout=20)
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    texto = BeautifulSoup(r.text, 'html.parser').get_text().lower()
    if any(p in texto for p in ["tarea para entregar", "fecha límite", "pendiente", "por entregar", "vence"]):
        enviar_whatsapp("📚 Hola Fernando! Revisé TODA tu plataforma CIMAC y detecté tareas pendientes. Entra ahora: https://campus.cimac.jedu.pe/my/")
        print("Tareas detectadas")
    else:
        print("Revisé todos los cursos, sin pendientes urgentes")
        enviar_whatsapp("✅ PRUEBA: Tu bot CIMAC ya está vivo 24/7, Fernando. Si ves esto, ya funciona.")
except Exception as e:
    print(f"Error: {e}")
