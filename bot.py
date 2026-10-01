import os, requests
from bs4 import BeautifulSoup

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
ID_INSTANCE = "710722753429"
MI_NUMERO = "51921493279@c.us"

def enviar_whatsapp(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    requests.post(url, json={"chatId": MI_NUMERO, "message": msg}, timeout=20)

try:
    s = requests.Session()
    r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    t = soup.find('input', {'name': 'logintoken'})
    logintoken = t['value'] if t else ""
    s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": logintoken}, timeout=20)
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    texto = BeautifulSoup(r.text, 'html.parser').get_text().lower()

    if any(p in texto for p in ["tarea para entregar", "fecha límite", "pendiente", "por entregar", "vence", "quiz", "cuestionario"]):
        enviar_whatsapp(f"📚 ALERTA CIMAC: Hola Fernando! Detecté una tarea/examen pendiente en tu plataforma. Entra ya a entregarla: https://campus.cimac.jedu.pe/my/")
        print("Tarea encontrada y notificada")
    else:
        print("Todo revisado, sin pendientes")

except Exception as e:
    print(f"Error: {e}")
