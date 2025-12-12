import re

def inject_tracking_to_text(text, user_email):
    """
    Scansiona il testo generato da Gemini.
    Trova tutti i link che puntano a 'app.hubspot.com/documents'.
    Aggiunge ?email=user_email alla fine del link per attivare il tracciamento.
    """
    # Se non c'è una mail valida o testo vuoto, restituisce l'originale
    if not text or not user_email or "@" not in user_email:
        return text

    # Funzione interna per modificare ogni singolo match
    def add_email_param(match):
        url = match.group(0)
        # Rimuove eventuali parentesi finali catturate per errore (sicurezza per markdown)
        clean_url = url.rstrip(')')
        
        # Determina il separatore (? se non ci sono parametri, & se ci sono già)
        separator = "&" if "?" in clean_url else "?"
        
        # Restituisce il link modificato
        return f"{clean_url}{separator}email={user_email.strip()}"

    # REGEX: Cerca URL HubSpot Documents. 
    # Si ferma se incontra spazi, parentesi chiuse o fine riga.
    hubspot_pattern = r"https:\/\/app\.hubspot\.com\/documents\/d\/[a-zA-Z0-9_\-\?=&]+"
    
    try:
        modified_text = re.sub(hubspot_pattern, add_email_param, text)
        return modified_text
    except Exception:
        # In caso di errore imprevisto, restituisce il testo originale
        return text
