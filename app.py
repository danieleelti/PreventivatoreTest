import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TEST", page_icon="🦁💰", layout="wide")

# --- GENERAZIONE SPACER CALIBRATO ---
spacer_text = "_" * 100 

# --- CSS PERSONALIZZATO (SOLO PER ANTEPRIMA STREAMLIT) ---
st.markdown("""
<style>
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; border: 1px solid #f0f2f6; border-radius: 10px; padding: 15px; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Tahoma', sans-serif !important;
        font-size: 15px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
    }
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Tahoma', sans-serif !important;
        font-size: 17px !important;
        font-weight: 800 !important;
        color: #000000 !important;
        margin-top: 20px !important; 
        margin-bottom: 5px !important;
        text-transform: uppercase !important;
    }
    div[data-testid="stChatMessage"] table {
        width: 600px !important; 
        min-width: 600px !important;
        max-width: 600px !important;
        border-collapse: collapse !important;
        border: 0px solid transparent !important;
        font-size: 14px !important;
        margin-top: 10px !important;
        font-family: 'Tahoma', sans-serif !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #f1f3f4 !important;
        color: #000 !important;
        font-weight: bold;
        text-align: left;
        padding: 12px !important;
        border-bottom: 0px solid transparent !important;
        font-family: 'Tahoma', sans-serif !important;
    }
    div[data-testid="stChatMessage"] td {
        padding: 10px !important;
        border-bottom: 1px solid #f0f0f0 !important;
        font-family: 'Tahoma', sans-serif !important;
    }
    .stButton button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
        height: 50px;
        font-size: 16px !important;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO LOCATION ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- IMPORTAZIONE MODULO HUBSPOT ---
try:
    import hubspot
except ImportError:
    hubspot = None

# --- FUNZIONI DI UTILITÀ ---
def enable_locations_callback():
    st.session_state.enable_locations_state = True
    st.session_state.retry_trigger = True

def reset_preventivo():
    st.session_state.messages = []
    st.session_state.total_tokens_used = 0
    keys_to_clear = ["wdg_cliente", "wdg_email_track", "wdg_pax", "wdg_data", "wdg_citta", "wdg_obiettivo"]
    for key in keys_to_clear:
        if key in st.session_state:
            st.session_state[key] = ""
    if "wdg_durata" in st.session_state:
        st.session_state["wdg_durata"] = "1-2h"

# --- GESTIONE DATABASE ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        return None
    except Exception as e:
        st.error(f"Errore: {e}")
        return None

@st.cache_data(ttl=600, show_spinner=False)
def carica_google_sheet(sheet_name):
    client = get_gspread_client()
    if not client: return None
    try:
        sheet = client.open(sheet_name).get_worksheet(0)
        return sheet.get_all_records()
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return None

def database_to_string(database_list):
    if not database_list: return "Nessun dato."
    try:
        if not isinstance(database_list[0], dict): return "" 
        sanitized_list = []
        for riga in database_list:
            clean_riga = {}
            for k, v in riga.items():
                val_str = str(v) if v is not None else ""
                if val_str.strip().lower().startswith("http") and " " in val_str:
                    val_str = val_str.replace(" ", "%20")
                clean_riga[k] = val_str
            sanitized_list.append(clean_riga)
        header = " | ".join(sanitized_list[0].keys())
        rows = []
        for riga in sanitized_list:
            rows.append(" | ".join(list(riga.values())))
        return header + "\n" + "\n".join(rows)
    except Exception: return ""

def salva_preventivo_su_db(cliente, utente, pax, data_evento, citta, contenuto):
    client = get_gspread_client()
    if not client: return False
    try:
        sheet = client.open("PreventiviInviatiAi").get_worksheet(0)
        tz_ita = pytz.timezone('Europe/Rome')
        now = datetime.now(tz_ita)
        row = [cliente, utente, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), pax, data_evento, citta, contenuto]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False

master_database = carica_google_sheet('MasterTbGoogleAi') 
if master_database is None: st.stop()
csv_data_string = database_to_string(master_database)

# --- LOGIN ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Area Riservata")
        pwd = st.text_input("Password", type="password")
        if st.button("Accedi"):
            users_db = st.secrets.get("passwords", {})
            if pwd in users_db:
                st.session_state.authenticated = True
                st.session_state.username = users_db[pwd]
                st.rerun()
            else: st.error("Password errata")
    st.stop()

# --- STATE ---
if "enable_locations_state" not in st.session_state: st.session_state.enable_locations_state = False
if "retry_trigger" not in st.session_state: st.session_state.retry_trigger = False
if "messages" not in st.session_state: st.session_state.messages = []

# --- AFORISMA ---
if not st.session_state.messages:
    quote = "Per aspera ad fattura."
    try:
        api_key_quote = st.secrets.get("GOOGLE_API_KEY")
        if api_key_quote:
            genai.configure(api_key=api_key_quote)
            model_quote = genai.GenerativeModel("gemini-1.5-flash", generation_config={"temperature": 1.2})
            resp = model_quote.generate_content("Genera un aforisma breve, ironico e cinico sul lavoro. Stile Murphy/Dilbert. Solo l'aforisma.")
            quote = resp.text.strip()
    except: pass
    st.session_state.messages.append({"role": "model", "content": f"Ciao **{st.session_state.username}**! 👋\n\n_{quote}_\n\nUsa la barra laterale per iniziare."})

# --- SIDEBAR ---
with st.sidebar:
    st.title("TEST")
    st.caption(f"Utente: **{st.session_state.username}**")
    st.markdown("---")
    if len(st.session_state.messages) > 1 and st.button("🔄 NUOVO PREVENTIVO", type="secondary"):
        reset_preventivo()
        st.rerun()
    st.markdown("---")
    cliente_input = st.text_input("Nome Cliente *", key="wdg_cliente")
    email_tracking_input = st.text_input("📧 Email Tracking", key="wdg_email_track")
    c1, c2 = st.columns(2)
    pax_input = c1.text_input("N. Pax", key="wdg_pax")
    data_evento_input = c2.text_input("Data", key="wdg_data")
    citta_input = st.text_input("Città / Location", key="wdg_citta")
    durata_input = st.selectbox("Durata", ["<1h", "1-2h", "2-4h", ">4h"], index=1, key="wdg_durata")
    obiettivo_input = st.text_area("Note / Obiettivo", key="wdg_obiettivo")
    st.markdown("###")
    generate_btn = st.button("🚀 GENERA PREVENTIVO", type="primary")
    st.markdown("---")
    with st.expander("⚙️ Avanzate"):
        use_location_db = st.checkbox("🏰 Abilita Location", key="enable_locations_state")
        api_key = st.secrets.get("GOOGLE_API_KEY")

# --- LOGICA LOCATION ---
location_guardrail_prompt = "NON SCRIVERE NULLA SU LOCATION. PASSA DIRETTAMENTE ALLA TABELLA."
if use_location_db:
    with st.spinner("Caricamento Location..."):
        location_database = carica_google_sheet('LocationGoogleAi')
        if location_database and locations_module:
            location_guardrail_prompt = f"SUGGERIMENTO LOCATION:\n{locations_module.get_location_instructions(database_to_string(location_database))}"

# --- SYSTEM PROMPT (AGGIORNATO: TRIPLA VERNICIATURA DI SFONDO) ---
context_brief = f"DATI BRIEF: Cliente: {cliente_input}, Pax: {pax_input}, Data: {data_evento_input}, Città: {citta_input}, Durata: {durata_input}, Obiettivo: {obiettivo_input}."

BASE_INSTRUCTIONS = f"""
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT. Rispondi in Italiano.
{context_brief}

### 🛡️ PROTOCOLLO
1.  **USO DEL DATABASE:** Usa SOLO i dati caricati.
2.  **DIVIETO:** VIETATO SCRIVERE "SU RICHIESTA".

### 🔢 CALCOLO (TEMP 0.0)
* **PAX:** {pax_input} | **P_BASE:** DB | **METODO:** DB
* **MOLTIPLICATORI:** <5:3.2|5-10:1.6|11-20:1.05|21-30:0.95|31-60:0.90|61-90:0.90|91-150:0.85|151-250:0.70|251-350:0.63|351-500:0.55|>500:0.50
* **DURATA:** ≤1h:1.05|1-2h:1.07|2-4h:1.10|>4h:1.15 | **LINGUA:** ITA:1.05|ENG:1.10 | **LOCATION:** MI:1.00|RM:0.95|VE:1.30|Centro:1.05|Nord/Sud:1.15
* **FORMULA:** Std: `P_BASE*M_PAX*M_DURATA*...*PAX` | Flat: Scaglioni fissi.
* **ARROTONDAMENTO:** 00-39->Difetto | 40-99->Eccesso. Min 1800.

---

### 🚦 OUTPUT (OBBLIGATORIO: HTML PURO)

**FASE 1: INTRODUZIONE** (3-4 righe saluti).

**FASE 2: LA REGOLA DEL 12 (4+4+2+2)**
12 format divisi in 4 categorie.

⚠️ **LAYOUT: TRIPLA VERNICIATURA (TD + TABLE + TD)**
Usa ESATTAMENTE questo HTML. Nota come il colore `#f8f9fa` è ripetuto 3 volte per forzare lo sfondo.
`<br><table width="600" border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td width="5" bgcolor="#ff4b4b"><font color="#ff4b4b">|</font></td>
    <td width="10" bgcolor="#f8f9fa"></td>
    <td width="585" bgcolor="#f8f9fa" align="left">
      <table width="100%" border="0" cellspacing="0" cellpadding="15" bgcolor="#f8f9fa">
        <tr>
          <td align="left" bgcolor="#f8f9fa">
            <strong>TITOLO CATEGORIA</strong><br>
            <font color="#666666"><i>CLAIM</i></font>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td colspan="3" bgcolor="#ffffff"><font color="#ffffff" size="1">{spacer_text}</font></td>
  </tr>
</table>`

**FORMAT ITEMS:**
`<br><strong>EMOJI NOME FORMAT</strong><br>Descrizione...<br>`

Categorie: **I BEST SELLER**, **LE NOVITÀ**, **VIBE & RELAX**, **SOCIAL**.

{location_guardrail_prompt}

**FASE 3: TABELLA RIEPILOGATIVA**
Una riga `<tr>` per ogni format.

**TITOLO (TRIPLA VERNICIATURA):**
`<br><table width="600" border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td width="5" bgcolor="#ff4b4b"><font color="#ff4b4b">|</font></td>
    <td width="10" bgcolor="#f8f9fa"></td>
    <td width="585" bgcolor="#f8f9fa" align="left">
      <table width="100%" border="0" cellspacing="0" cellpadding="15" bgcolor="#f8f9fa">
        <tr>
          <td align="left" bgcolor="#f8f9fa">
            <strong>TABELLA RIEPILOGATIVA</strong><br>
            <font color="#666666"><i>Brief: {cliente_input} | {pax_input} | {data_evento_input} | {citta_input}</i></font>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td colspan="3" bgcolor="#ffffff"><font color="#ffffff" size="1">{spacer_text}</font></td>
  </tr>
</table>`

**CONTENUTO (COPIA ESATTO - CELLPADDING 8 - NO BORDER):**
`<table width="600" border="0" cellspacing="0" cellpadding="8">
  <tr bgcolor="#f1f3f4">
    <th width="240" align="left">Nome Format</th>
    <th width="120" align="left">Costo Totale (+IVA)</th>
    <th width="240" align="left">Scheda Tecnica</th>
  </tr>
  <tr>
    <td align="left"><strong>🍳 Cooking</strong></td>
    <td align="left">€ 2.400,00</td>
    <td align="left"><a href="LINK_HUBS_LY">Cooking.pdf</a></td>
  </tr>
  <tr>
    <td colspan="3" bgcolor="#ffffff"><font color="#ffffff" size="1">{spacer_text}</font></td>
  </tr>
</table>`

**FASE 4: INFO UTILI**
`<br><br><strong>Informazioni Utili</strong><br><br>... (tua lista)`
"""

FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- APP LOGIC ---
if generate_btn:
    if not cliente_input: st.error("Inserisci Cliente"); st.stop()
    prompt = f"Ciao, sono {cliente_input}. Preventivo per {pax_input} pax, {data_evento_input}, {citta_input}. Durata: {durata_input}. Obiettivo: {obiettivo_input}."
    st.session_state.messages.append({"role": "user", "content": prompt})

chat_input = st.chat_input("Modifica...")
if chat_input: 
    prompt = chat_input
    st.session_state.messages.append({"role": "user", "content": prompt})

# --- RENDER CHAT ---
for m in st.session_state.messages:
    role = "assistant" if m["role"] == "model" else m["role"]
    with st.chat_message(role): st.markdown(m["content"], unsafe_allow_html=True)

# --- GENERATE RESPONSE ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Elaborazione..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3-pro-preview", generation_config={"temperature": 0.0}, system_instruction=FULL_SYSTEM_PROMPT)
                history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
                response = model.generate_content(history)
                resp_text = response.text
                if hubspot and email_tracking_input:
                    resp_text = hubspot.inject_tracking_to_text(resp_text, email_tracking_input)
                st.markdown(resp_text, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "model", "content": resp_text})
            except Exception as e: st.error(f"Errore: {e}")

# --- SAVE BUTTON ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "model":
    if st.button("💾 SALVA"):
        if salva_preventivo_su_db(cliente_input, st.session_state.username, pax_input, data_evento_input, citta_input, st.session_state.messages[-1]["content"]):
            st.success("Salvato!")
