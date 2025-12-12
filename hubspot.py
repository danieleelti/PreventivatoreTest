import re

def inject_tracking_to_text(text, user_email):
    """
    Scansiona il testo generato da Gemini.
    Trova tutti i link che puntano a 'app.hubspot.com/documents'.
    Aggiunge ?email=user_email alla fine del link per attivare il tracciamento.
    """
    # Se non c'è una mail valida, restituisce il testo originale senza toccarlo
    if not user_email or "@" not in user_email:
        return text

    # Funzione interna che viene chiamata per ogni link trovato
    def add_email_param(match):
        url = match.group(0)
        # Controlla se il link ha già parametri (?) o no
        separator = "&" if "?" in url else "?"
        # Restituisce il link modificato
        return f"{url}{separator}email={user_email.strip()}"

    # REGEX: Cerca URL che iniziano con il dominio dei documenti HubSpot
    # Cattura l'intero URL finché non trova uno spazio o una parentesi chiusa tipica del markdown
    hubspot_pattern = r"https:\/\/app\.hubspot\.com\/documents\/d\/[a-zA-Z0-9_\-\?=&]+"
    
    # Esegue la sostituzione nel testo
    try:
        modified_text = re.sub(hubspot_pattern, add_email_param, text)
        return modified_text
    except Exception:
        # In caso di errore imprevisto, restituisce il testo originale per non rompere l'app
        return text
