import requests

GAME_PC_URL = "http://192.168.0.95:8765/status"

def get_game_state():
    try:
        response = requests.get(GAME_PC_URL, timeout=2)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None
