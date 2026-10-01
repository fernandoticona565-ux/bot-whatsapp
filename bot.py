import os, requests
from bs4 import BeautifulSoup

USER = os.getenv("CIMAC_USER")
PASS = os.getenv("CIMAC_PASS")
TOKEN = os.getenv("GREEN_TOKEN")
ID_INSTANCE = "710722753429"
MI_NUMERO = "51921493279@c.us"

def enviar(msg):
    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{TOKEN}"
    requests.post(url, json={"chatId": MI_NUMERO, "message": msg}, timeout=20)

try:
    s = requests.Session()
    r = s.get("https://campus.cimac.jedu.pe/login/index.php", timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    t = soup.find('input', {'name': 'logintoken'})
    lt = t['value'] if t else ""
    s.post("https://campus.cimac.jedu.pe/login/index.php", data={"username": USER, "password": PASS, "logintoken": lt}, timeout=20)
    r = s.get("https://campus.cimac.jedu.pe/my/", timeout=20)
    enviar("✅ Bot CIMAC arreglado con Gemini - Probando de nuevo")
    print("OK")
except Exception as e:
    print(f"Error: {e}")
