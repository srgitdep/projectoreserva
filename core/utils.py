# core/utils.py

import requests
from .whatsapp_config import ZAPI_URL, ZAPI_TOKEN

def enviar_notificacao_whatsapp(telefone, mensagem):
    """
    Envia uma mensagem WhatsApp usando a Z-API.
    
    Args:
        telefone (str): Número no formato 258841455334
        mensagem (str): Texto da mensagem a enviar
    """
    # Remove espaços e caracteres especiais
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    
    payload = {
        "phone": telefone_limpo,
        "message": mensagem
    }
    
    headers = {
        "Client-Token": ZAPI_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(ZAPI_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)