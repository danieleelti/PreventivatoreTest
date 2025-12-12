import re
import requests

def inject_tracking_to_text(text, user_email):
    """
    Versione 4.0 (AUTO-EXPAND):
    1. Trova i link corti (hubs.ly) nel testo.
    2. Li 'visita' dietro le quinte per ottenere il link lungo VERO (con l'accessId completo).
    3. Aggiunge la mail al link lungo usando il separatore corretto (&).
    """
    # Se non c'è mail o testo, ritorna originale
    if not text or not user_email or "@" not in user_email:
        return text

    def expand_and_track(match):
        short_url = match.group(0).rstrip(').')
        
        # Se è un link corto hubs.ly, lo espandiamo per trovare quello lungo
        if "hubs.ly" in short_url:
            try:
                # Chiede a internet dove porta questo link
                response = requests.get(short_url, allow_redirects=True, timeout=5)
                # Ottiene il link finale (es. ...hubspotdocuments.com/...accessId=xyz...)
                full_url = response.url
            except Exception:
                # Se fallisce la connessione, usa il link originale (meglio di niente)
                full_url = short_url
        else:
            full_url = short_url

        # Ora che abbiamo il link lungo (full_url), aggiungiamo la mail
        # Se c'è già un '?' (come nel 99% dei link lunghi), usiamo '&'
        separator = "&" if "?" in full_url else "?"
        
        return f"{full_url}{separator}email={user_email.strip()}"

    # Cerca sia link corti che lunghi
    hubspot_pattern = r"https:\/\/(?:[a-zA-Z0-9-]+\.)?(?:hubs\.ly|hubspot(?:documents)?\.com\/documents)\/[^\s\)]+"
    
    try:
        # Sostituisce nel testo
        modified_text = re.sub(hubspot_pattern, expand_and_track, text)
        return modified_text
    except Exception:
        return text
