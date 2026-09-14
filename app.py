import streamlit as st
import streamlit.components.v1 as components
from streamlit.runtime.secrets import StreamlitSecretNotFoundError
import sqlite3
import time
import os
import hashlib
import json
import requests
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime, date
import difflib
import re
from concurrent.futures import ThreadPoolExecutor

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import healthsherpa_service
except ImportError:
    healthsherpa_service = None

# ==============================================================================
# 1. BÚSQUEDA DEL LOGO
# ==============================================================================
def generar_fechas_efectivas_futuras():
    today = date.today()
    fechas = []
    y = today.year
    m = today.month
    for _ in range(18):
        fechas.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return fechas

def buscar_logo():
    posibles_nombres = ["logo.png.png", "logo.png", "logo.png.gif", "logo.gif"]
    base_dir = os.path.dirname(os.path.abspath(__file__))
    posibles_carpetas = [".", base_dir, os.path.join(base_dir, "Nexxel Corporation"), os.path.join(base_dir, "..")]
    for carpeta in posibles_carpetas:
        for nombre in posibles_nombres:
            ruta = os.path.join(carpeta, nombre)
            if os.path.isfile(ruta):
                return ruta
    return None

logo_file = buscar_logo()

def obtener_logo_base64(ruta_logo):
    if ruta_logo and os.path.isfile(ruta_logo):
        with open(ruta_logo, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

logo_b64 = obtener_logo_base64(logo_file)

# ==============================================================================
# 2. CONFIGURACIÓN DE PÁGINA Y ESTILOS ORIGINALES
# ==============================================================================
st.set_page_config(
    page_title="Nexxell Quotes Preview",
    page_icon=logo_file if logo_file else "⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
        :root {
            --primary: #1C237A;
            --primary-dark: #121752;
            --secondary: #7E228B;
            --accent-pink: #EB3C96;
            --pink-soft: #FDF0F6;
            --bg: #F8F9FD;
            --panel: #FFFFFF;
            --text: #171B34;
            --muted: #697089;
            --border-subtle: #E2E8F0;
            --success: #10B981;
            --warning: #F59E0B;
        }
        .stApp {
            background: linear-gradient(180deg, #F8F9FD 0%, #EEF2F9 100%);
            color: var(--text);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        /* ── BOTONES GLOBALES COMPACTOS (DESKTOP ENTERPRISE SAAS) ── */
        .stButton > button,
        .stDownloadButton > button,
        button[kind="secondary"],
        button[kind="primary"] {
            border-radius: 8px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 1.15rem !important;
            font-size: 0.86rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.2px !important;
            transition: all 0.18s ease-in-out !important;
            cursor: pointer !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        }

        /* ── BOTÓN PRIMARIO (AZUL MARINO CORPORATIVO NEXXELL #1C237A) ── */
        button[kind="primary"] {
            background: #1C237A !important;
            color: #FFFFFF !important;
            border: 1px solid #1C237A !important;
            box-shadow: 0 2px 6px rgba(28, 35, 122, 0.18) !important;
        }
        button[kind="primary"]:hover {
            background: #121752 !important;
            border-color: #121752 !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(28, 35, 122, 0.28) !important;
        }

        /* ── BOTÓN SECUNDARIO / BASE (FONDO BLANCO LIMPIO CON BORDE SUTIL) ── */
        .stButton > button,
        button[kind="secondary"] {
            background: #FFFFFF !important;
            color: #334155 !important;
            border: 1.5px solid #CBD5E1 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        }
        .stButton > button:hover,
        button[kind="secondary"]:hover {
            background: #F8FAFC !important;
            border-color: #1C237A !important;
            color: #1C237A !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 6px rgba(28, 35, 122, 0.08) !important;
        }

        /* ── BOTÓN PRIMARIO Y ACCIONES PRINCIPALES (AZUL MARINO SÓLIDO #1C237A) ── */
        button[kind="primary"],
        div[data-testid="stBaseButton-primary"] button,
        .st-key-btn_upload_monday button,
        .st-key-btn_download_pdf button,
        .st-key-btn_sync_changes_crm button {
            background: #1C237A !important;
            background-color: #1C237A !important;
            background-image: none !important;
            color: #FFFFFF !important;
            border: 1px solid #1C237A !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(28, 35, 122, 0.22) !important;
            transition: all 0.18s ease-in-out !important;
        }
        button[kind="primary"]:hover,
        div[data-testid="stBaseButton-primary"] button:hover,
        .st-key-btn_upload_monday button:hover,
        .st-key-btn_download_pdf button:hover,
        .st-key-btn_sync_changes_crm button:hover {
            background: #121752 !important;
            background-color: #121752 !important;
            border-color: #121752 !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(28, 35, 122, 0.3) !important;
        }

        /* ── BOTÓN SECUNDARIO OUTLINED (UPDATE DETAILS, REFRESH) ── */
        .st-key-btn_update_candidate button,
        .st-key-btn_refresh_crm button {
            background: #FFFFFF !important;
            color: #1C237A !important;
            border: 1.5px solid #1C237A !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        }
        .st-key-btn_update_candidate button:hover,
        .st-key-btn_download_pdf button:hover,
        .st-key-btn_refresh_crm button:hover {
            background: #F0F4FF !important;
            border-color: #121752 !important;
            color: #121752 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 8px rgba(28, 35, 122, 0.12) !important;
        }

        /* ── BOTÓN DESTRUCTIVO / REMOVE COLUMN (COLOR PSYCHOLOGY) ── */
        .st-key-btn_remove_plan button {
            background: #F8F9FD !important;
            color: #64748B !important;
            border: 1.5px solid #E2E8F0 !important;
            box-shadow: none !important;
        }
        .st-key-btn_remove_plan button:hover {
            background: #FFF1F2 !important;
            border-color: #FECDD3 !important;
            color: #E11D48 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 8px rgba(225, 29, 72, 0.12) !important;
        }

        /* ── BOTÓN ADD PLAN COLUMN (PRIMARIO MARINO) ── */
        .st-key-btn_add_plan button {
            background: #1C237A !important;
            color: #FFFFFF !important;
            border: 1px solid #1C237A !important;
        }
        .st-key-btn_add_plan button:hover {
            background: #2A104E !important;
            border-color: #2A104E !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 3px 10px rgba(28, 35, 122, 0.22) !important;
        }

        /* ── INPUTS REFINADOS CON BORDES MODERNOS ── */
        div[data-baseweb="input"] {
            border-radius: 8px !important; border: 1.5px solid var(--border-subtle) !important;
            background-color: #FFFFFF !important; padding: 2px 8px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important; transition: all 0.2s ease !important;
        }
        div[data-baseweb="input"]:focus-within {
            border-color: var(--secondary) !important; box-shadow: 0 0 0 3px rgba(235, 60, 150, 0.15) !important;
        }
        section[data-testid="stSidebar"], div[data-testid="stSidebar"] {
            background-color: #0F1535 !important; border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        /* ── BOTONES EN LA BARRA LATERAL (CONSERVAN DEGRADADO CORPORATIVO ORIGINAL) ── */
        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stDownloadButton > button,
        div[data-testid="stSidebar"] .stButton > button,
        div[data-testid="stSidebar"] .stDownloadButton > button {
            background: linear-gradient(115deg, #1C237A 0%, #631C82 50%, #EB3C96 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 3px 10px rgba(99, 28, 130, 0.3) !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover,
        section[data-testid="stSidebar"] .stDownloadButton > button:hover,
        div[data-testid="stSidebar"] .stButton > button:hover,
        div[data-testid="stSidebar"] .stDownloadButton > button:hover {
            box-shadow: 0 5px 16px rgba(235, 60, 150, 0.45) !important;
            transform: translateY(-1px) !important;
            filter: brightness(1.08) !important;
        }
        .info-card {
            background: #FFFFFF; border: 1px solid var(--border-subtle); border-radius: 14px;
            padding: 1.2rem 1.4rem; box-shadow: 0 4px 16px rgba(28, 35, 122, 0.05); margin-bottom: 1.2rem;
        }
        .info-card h4 { color: var(--primary); margin-top: 0; margin-bottom: 0.5rem; font-weight: 700; }
        .stMetric {
            background: var(--panel); border: 1px solid var(--border-subtle); border-radius: 14px;
            padding: 0.9rem 1rem; box-shadow: 0 4px 16px rgba(28, 35, 122, 0.05);
        }
        .info-pill {
            display: inline-block; padding: 0.35rem 0.75rem; border-radius: 999px;
            background: var(--pink-soft); color: var(--accent-pink);
            border: 1px solid rgba(235, 60, 150, 0.25); font-size: 0.8rem; font-weight: 600; margin-bottom: 0.6rem;
        }
        .empty-state {
            border: 1px dashed rgba(28, 35, 122, 0.25); border-radius: 12px; padding: 1rem;
            background: rgba(255, 255, 255, 0.6); text-align: center; color: var(--muted);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 3. GESTIÓN DE SESIÓN Y AUTENTICACIÓN
# ==============================================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_user" not in st.session_state:
    st.session_state["current_user"] = ""
if "input_user" not in st.session_state:
    st.session_state["input_user"] = ""
if "input_pass" not in st.session_state:
    st.session_state["input_pass"] = ""

def make_hash(password):
    return hashlib.pbkdf2_hmac("sha256", str(password).strip().encode("utf-8"), b"nexxel-corp", 200_000).hex()

def verify_password(stored_value, password):
    if not stored_value:
        return False
    p_str = str(password).strip()
    if isinstance(stored_value, list):
        return any(verify_password(v, p_str) for v in stored_value)
    if stored_value == make_hash(p_str):
        return True
    if stored_value == hashlib.sha256(p_str.encode("utf-8")).hexdigest():
        return True
    if stored_value == p_str:
        return True
    return False

def get_secrets_data():
    try:
        return dict(st.secrets)
    except Exception:
        return {}

# Default verified password hashes (PBKDF2-HMAC-SHA256 encrypted)
DEFAULT_USERS = {
    "andreap": [
        "32ed7f88cad7abfc2c9fbc875ddd991e3bea3b9582fcfdd031f8e59951d86a3c",  # Nexxell2026!
        "1a5f98afdca9c9efcf7d75256fd4ac33a828e6f038bc5018d47ac6b28c7d0d1d",  # Nexxel2026!
    ],
    "gabriela.o": "cc6d76d665a61914fe5ff9e30e25742eaa4235580643b4cfbcc1043b7668929d",
}

SECRETS = get_secrets_data()
USERS = {**DEFAULT_USERS, **SECRETS.get("passwords", {})}
if "andreap" in USERS:
    current_stored = USERS["andreap"]
    active_list = current_stored if isinstance(current_stored, list) else [current_stored]
    for h in DEFAULT_USERS["andreap"]:
        if h not in active_list:
            active_list.append(h)
    USERS["andreap"] = active_list

MONDAY_API_KEY = SECRETS.get("monday", {}).get("api_token") or os.environ.get("MONDAY_API_TOKEN", "")
MONDAY_BOARD_ID = str(SECRETS.get("monday", {}).get("board_id") or os.environ.get("MONDAY_BOARD_ID", "18400693607"))
HEALTHSHERPA_API_KEY = str(
    SECRETS.get("healthsherpa", {}).get("api_key")
    or os.environ.get("HEALTHSHERPA_API_KEY", "hs1d97b8327d7a1acfb8ba498fe31523d2e50c900cc76b99d0cfdd041d920")
).strip()
HEALTHSHERPA_BASE_URL = str(
    SECRETS.get("healthsherpa", {}).get("base_url")
    or os.environ.get("HEALTHSHERPA_BASE_URL", "https://api.one.healthsherpa.com")
).strip()

def verify_login():
    u = st.session_state.get("input_user", "").strip().lower()
    p = st.session_state.get("input_pass", "").strip()
    user_match = None
    for registered_user in USERS.keys():
        reg_clean = str(registered_user).strip().lower()
        if reg_clean == u or reg_clean.split(".")[0] == u:
            user_match = registered_user
            break
    if user_match and verify_password(USERS[user_match], p):
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = user_match
        st.session_state["input_pass"] = ""
    else:
        st.error("❌ Invalid username or password.")
        
# PANTALLA DE LOGIN
if not st.session_state["authenticated"]:
    css_login = """
        <style>
            header { visibility: hidden; }
            .stApp { background: linear-gradient(135deg, #F4F6FB 0%, #E9EDF7 100%) !important; }
            .block-container {
                max-width: 550px !important; padding-top: 5vh !important;
                padding-bottom: 5vh !important; margin-left: auto !important; margin-right: auto !important;
            }
            .login-logo-container { display: flex; justify-content: center; align-items: center; margin-bottom: 1.4rem; width: 100%; }
            .login-logo-container img { height: 80px !important; max-width: 260px !important; object-fit: contain; }
            .login-header-text { text-align: center; margin-bottom: 2rem; width: 100%; }
            .login-header-text h2 { color: #161C63 !important; font-size: 1.85rem !important; font-weight: 800 !important; margin: 0 0 0.4rem 0 !important; letter-spacing: -0.5px; }
            .login-header-text p { color: #64748B !important; font-size: 0.95rem !important; margin: 0 auto !important; line-height: 1.4 !important; }
            div[data-testid="column"], div[data-testid="stColumn"] {
                background: linear-gradient(145deg, #161C63 0%, #2A104E 55%, #4D165E 100%) !important;
                border-radius: 26px !important; border: 1px solid rgba(255, 255, 255, 0.15) !important;
                box-shadow: 0 24px 60px rgba(22, 28, 99, 0.28) !important;
                padding: 3.2rem 3rem 2.6rem 3rem !important; width: 100% !important; box-sizing: border-box !important;
            }
            div[data-testid="column"] label p, div[data-testid="stColumn"] label p { color: #FFFFFF !important; font-weight: 600 !important; font-size: 0.95rem !important; }
            div[data-baseweb="input"] { border-radius: 12px !important; border: 1.5px solid rgba(255, 255, 255, 0.25) !important; background-color: #FFFFFF !important; padding: 4px 8px !important; }
            div[data-baseweb="input"] input { color: #161C63 !important; font-size: 0.96rem !important; }
            div[data-testid="column"] button[kind="primary"], div[data-testid="column"] .stButton > button,
            div[data-testid="stColumn"] button[kind="primary"], div[data-testid="stColumn"] .stButton > button {
                position: relative !important; overflow: hidden !important;
                background: linear-gradient(115deg, #D92686 0%, #B02287 30%, #F672B6 48%, #B02287 52%, #7E1A8A 80%, #5D1677 100%) !important;
                background-size: 250% 100% !important; background-position: 0% 0 !important;
                animation: shimmerEffect 4.5s ease-in-out infinite !important;
                color: #FFFFFF !important; border: none !important; border-radius: 14px !important;
                padding: 0.85rem 1.6rem !important; font-size: 1.05rem !important; font-weight: 700 !important;
                box-shadow: 0 6px 18px rgba(176, 34, 135, 0.28) !important; cursor: pointer !important; width: 100% !important;
            }
            @keyframes shimmerEffect { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
            .login-footer-secure { text-align: center; font-size: 0.82rem; color: #D8B4FE !important; margin-top: 2rem; display: flex; align-items: center; justify-content: center; gap: 6px; opacity: 0.9; }
        </style>
    """
    st.markdown(css_login, unsafe_allow_html=True)
    if logo_b64:
        st.markdown(f'<div class="login-logo-container"><img src="data:image/png;base64,{logo_b64}" alt="Nexxell Logo"></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="login-logo-container"><h1 style="color:#161C63; font-weight:800;">nexxell</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-header-text"><h2>Quotes Portal</h2><p>Please enter your credentials to access the system</p></div>', unsafe_allow_html=True)
    form_col, = st.columns(1)
    with form_col:
        st.text_input("Username:", key="input_user", placeholder="Enter your username")
        st.text_input("Password:", type="password", key="input_pass", placeholder="••••••••")
        st.markdown("<div style='margin-top: 1.6rem;'></div>", unsafe_allow_html=True)
        st.button("Log In", on_click=verify_login, use_container_width=True, type="primary")
        st.markdown('<div class="login-footer-secure"><span>🔒</span> <span>Nexxell Corporation</span></div>', unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# 4. BASE DE DATOS Y CONEXIONES
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cotizaciones_salud.db')
DB_HOST = os.environ.get("DB_HOST", "")
DB_NAME = os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "appdb"))
DB_USER = os.environ.get("DB_USER", os.environ.get("POSTGRES_USER", "postgres"))
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))
DB_PORT = os.environ.get("DB_PORT", "5432")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DB_HOST or DATABASE_URL)

class DBCursorWrapper:
    def __init__(self, raw_cursor, is_postgres=False):
        self.raw_cursor = raw_cursor
        self.is_postgres = is_postgres
    def execute(self, sql, params=None):
        if self.is_postgres:
            sql = sql.replace('?', '%s')
        if params is None:
            return self.raw_cursor.execute(sql)
        return self.raw_cursor.execute(sql, params)
    def fetchall(self): return self.raw_cursor.fetchall()
    def fetchone(self): return self.raw_cursor.fetchone()
    def fetchmany(self, size=None): return self.raw_cursor.fetchmany(size) if size else self.raw_cursor.fetchmany()
    @property
    def description(self): return getattr(self.raw_cursor, "description", None)
    def close(self): self.raw_cursor.close()
    def __getattr__(self, name): return getattr(self.raw_cursor, name)

class DBWrapper:
    def __init__(self, raw_conn, is_postgres=False):
        self.raw_conn = raw_conn
        self.is_postgres = is_postgres
    def cursor(self): return DBCursorWrapper(self.raw_conn.cursor(), self.is_postgres)
    def commit(self): self.raw_conn.commit()
    def rollback(self): self.raw_conn.rollback()
    def close(self): self.raw_conn.close()
    def __getattr__(self, name): return getattr(self.raw_conn, name)
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None: self.rollback()
        else: self.commit()
        self.close()

def get_db_connection():
    if USE_POSTGRES:
        import psycopg2
        if DATABASE_URL:
            raw_conn = psycopg2.connect(DATABASE_URL)
        else:
            raw_conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)
        return DBWrapper(raw_conn, is_postgres=True)
    else:
        raw_conn = sqlite3.connect(DB_PATH)
        return DBWrapper(raw_conn, is_postgres=False)

def init_and_migrate_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    id_pk = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS chicas_excel (
            id_cliente {id_pk}, nombre_gc TEXT UNIQUE, edad INTEGER, estado TEXT,
            codigo_postal TEXT, compania_seguros TEXT, agencia TEXT, hospital_preferido TEXT,
            doctor_preferido TEXT, embarazada TEXT DEFAULT 'No', plan_actual TEXT DEFAULT 'None',
            monday_item_id TEXT, enrollment_status TEXT DEFAULT 'Pending'
        )
    ''')
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS cotizaciones_historial (
            id_cotizacion {id_pk}, nombre_gc TEXT,
            fecha_cotizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP, planes_json TEXT, agencia TEXT
        )
    ''')
    columns_to_add = [
        ("agencia", "TEXT"), ("hospital_preferido", "TEXT"), ("doctor_preferido", "TEXT"),
        ("embarazada", "TEXT DEFAULT 'No'"), ("plan_actual", "TEXT DEFAULT 'None'"),
        ("monday_item_id", "TEXT"), ("enrollment_status", "TEXT DEFAULT 'Pending'"),
        ("fecha_nacimiento", "TEXT")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE chicas_excel ADD COLUMN {col_name} {col_type}")
            conn.commit()
        except Exception:
            pass
    try:
        cursor.execute("UPDATE chicas_excel SET plan_actual = 'None' WHERE plan_actual = 'Ninguno' OR plan_actual IS NULL")
        conn.commit()
    except Exception:
        pass
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chicas_agencia ON chicas_excel(agencia)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chicas_monday ON chicas_excel(monday_item_id)")
        conn.commit()
    except Exception:
        pass
    conn.close()

init_and_migrate_db()

def get_clean_agencies():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT agencia FROM chicas_excel WHERE agencia IS NOT NULL AND TRIM(agencia) != ''")
    raw_agencies = [r[0].strip() for r in cursor.fetchall()]
    conn.close()
    unique_agencies = []
    for ag in raw_agencies:
        matches = difflib.get_close_matches(ag, unique_agencies, n=1, cutoff=0.85)
        if not matches:
            unique_agencies.append(ag)
    return sorted(unique_agencies)

# ==============================================================================
# 5. SINCRONIZADOR Y API MONDAY.COM
# ==============================================================================
def calcular_edad_desde_texto(texto_edad_o_fecha):
    if not texto_edad_o_fecha:
        return 25
    txt = str(texto_edad_o_fecha).strip()
    if txt.isdigit():
        return int(txt)
    formatos_fecha = [
        "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y"
    ]
    for fmt in formatos_fecha:
        try:
            fecha_nac = datetime.strptime(txt, fmt).date()
            hoy = date.today()
            edad_calc = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
            return max(18, min(edad_calc, 99))
        except Exception:
            continue
    return 25

def calcular_edad_actuarial(texto_edad_o_fecha, fecha_efectiva=None):
    """
    Calculates exact actuarial age on the target coverage effective date (ACA standard).
    Returns (age: int, formatted_dob: str).
    """
    if not texto_edad_o_fecha:
        return 25, ""
    txt = str(texto_edad_o_fecha).strip()

    if not fecha_efectiva:
        today = date.today()
        if today.month == 12:
            fecha_efectiva = date(today.year + 1, 1, 1)
        else:
            fecha_efectiva = date(today.year, today.month + 1, 1)
    elif isinstance(fecha_efectiva, datetime):
        fecha_efectiva = fecha_efectiva.date()

    formatos_fecha = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y",
        "%b %d %Y", "%B %d %Y", "%Y/%m/%d", "%m-%d-%Y"
    ]
    fecha_nac = None
    for fmt in formatos_fecha:
        try:
            fecha_nac = datetime.strptime(txt, fmt).date()
            break
        except Exception:
            continue

    if fecha_nac:
        edad_calc = fecha_efectiva.year - fecha_nac.year - (
            (fecha_efectiva.month, fecha_efectiva.day) < (fecha_nac.month, fecha_nac.day)
        )
        return max(18, min(edad_calc, 99)), fecha_nac.strftime("%Y-%m-%d")

    if txt.isdigit():
        return max(18, min(int(txt), 99)), ""

    return 25, ""

def resolver_marketplace_por_estado(state_str, zip_code=""):
    st_clean = str(state_str).strip().upper()
    portales_estatales = {
        "CA": "Covered California", "NY": "NY State of Health", "NV": "Nevada Health Link",
        "NJ": "GetCoveredNJ", "PA": "Pennie", "WA": "Washington Healthplanfinder",
        "CO": "Connect for Health Colorado", "MD": "Maryland Health Connection",
        "MA": "Health Connector", "MN": "MNsure"
    }
    return portales_estatales.get(st_clean, "Marketplace (HealthCare.gov)")

# ==============================================================================
# 5.1 MOTOR EXCLUSIVO DE COTIZACIÓN: HEALTHSHERPA ONE API
# ==============================================================================
@st.cache_data(ttl=900, show_spinner=False)
def _fetch_unified_plans_cached(zipcode, age, fips_code=None, state_code=None, pregnant=False, carrier_pref=None, provider_npis=None, effective_date=None, _cache_ver="hs_v5"):
    """
    Motor oficial de cotizaciones HealthSherpa One API (Caché inteligente de éxito):
    - Precios 100% reales directo de aseguradoras (Kaiser, Anthem, Blue Shield, etc.)
    - Solo almacena en caché respuestas con planes activos reales; nunca almacena fallos ni listas vacías.
    """
    if healthsherpa_service and HEALTHSHERPA_API_KEY:
        target_fips = fips_code
        target_state = state_code
        if not target_fips or not target_state:
            counties = healthsherpa_service.lookup_counties(zipcode, HEALTHSHERPA_API_KEY, base_url=HEALTHSHERPA_BASE_URL)
            if counties and isinstance(counties, list) and len(counties) > 0:
                target_fips = target_fips or counties[0].get("fips_code") or counties[0].get("fips")
                target_state = target_state or counties[0].get("state")

        hs_res = healthsherpa_service.quote_plans(
            zip_code=zipcode,
            fips_code=target_fips,
            state=target_state or "CA",
            age=int(age),
            api_key=HEALTHSHERPA_API_KEY,
            pregnant=pregnant,
            effective_date=effective_date,
            provider_npis=provider_npis,
            base_url=HEALTHSHERPA_BASE_URL
        )
        if hs_res.get("success") and hs_res.get("plans"):
            all_formatted = []
            for p in hs_res["plans"]:
                g_prem = float(p.get("gross_premium", 0.0) or p.get("net_premium", 0.0) or p.get("prem_val", 0.0))
                urls = p.get("urls", {}) or {}
                sbc_doc = p.get("benefits_url") or urls.get("sbc") or urls.get("summary_of_benefits") or ""
                all_formatted.append({
                    "id": str(p.get("hios_id") or p.get("id")),
                    "name": p.get("name"),
                    "issuer": p.get("issuer"),
                    "metal": p.get("metal_level") or p.get("metal") or "Bronze",
                    "plan_type": p.get("plan_type"),
                    "prem": f"${g_prem:,.2f}",
                    "prem_val": g_prem,
                    "gross_prem_val": g_prem,
                    "net_prem": f"${g_prem:,.2f}",
                    "net_prem_val": g_prem,
                    "subsidy": 0.0,
                    "ded": str(p.get("deductible", p.get("ded", "$0"))),
                    "oop": str(p.get("moop", p.get("oop", "$9,200"))),
                    "pcp": str(p.get("pcp", "$50 copay")),
                    "spec": str(p.get("spec", "$90 copay")),
                    "rx": str(p.get("rx", "$15 copay")),
                    "emergency_room": str(p.get("emergency_room", "$350 copay")),
                    "urgent_care": str(p.get("urgent_care", "$60 copay")),
                    "ambulance": str(p.get("ambulance", "$250 copay")),
                    "labs": str(p.get("labs", "Covered in Tier")),
                    "xrays": str(p.get("xrays", "Standard Diagnostic")),
                    "office_visits": str(p.get("office_visits", "Covered")),
                    "cb_phys": str(p.get("cb_phys", "Standard In-Network")),
                    "cb_fac": str(p.get("cb_fac", "Standard In-Network")),
                    "lien": p.get("lien", "No"),
                    "benefits_url": sbc_doc,
                    "brochure_url": urls.get("brochure") or p.get("brochure_url", ""),
                    "formulary_url": urls.get("formulary") or p.get("formulary_url", ""),
                    "network_url": urls.get("provider_directory") or urls.get("network") or p.get("network_url", ""),
                    "providers": p.get("providers", {}),
                    "deeplink_enrollment": p.get("deeplink_enrollment", False),
                    "engine": "HealthSherpa One"
                })

            carrier_target = str(carrier_pref or "").strip().lower()
            matched_pool = []
            if carrier_target and carrier_target not in ["no preference", "none", "n/a", "no", "anthem"]:
                tokens = [t for t in carrier_target.replace("/", " ").replace("-", " ").split() if len(t) > 2]
                for p in all_formatted:
                    iss_str = p["issuer"].lower()
                    pln_str = p["name"].lower()
                    if any(t in iss_str or t in pln_str for t in tokens):
                        matched_pool.append(p)

            candidate_pool = matched_pool if matched_pool else all_formatted
            categorized = {"Bronze": [], "Silver": [], "Gold": [], "Platinum": [], "Other": []}
            for p in candidate_pool:
                ml = p.get("metal", "Other")
                matched_cat = "Other"
                for c_tier in categorized.keys():
                    if c_tier.lower() in ml.lower():
                        matched_cat = c_tier
                        break
                categorized[matched_cat].append(p)

            selected_default = []
            for lvl in ["Bronze", "Silver", "Gold", "Platinum"]:
                if categorized[lvl]:
                    selected_default.append(categorized[lvl][0])
            for p in candidate_pool:
                if p not in selected_default:
                    selected_default.append(p)
                if len(selected_default) >= 5:
                    break

            return True, selected_default, target_state, target_fips, all_formatted, "HealthSherpa One"

    raise RuntimeError("HealthSherpa One API did not return plans for this query.")


def fetch_unified_plans(zipcode, age, fips_code=None, state_code=None, pregnant=False, carrier_pref=None, provider_npis=None, effective_date=None, _cache_ver="hs_v5"):
    try:
        return _fetch_unified_plans_cached(
            zipcode=zipcode,
            age=age,
            fips_code=fips_code,
            state_code=state_code,
            pregnant=pregnant,
            carrier_pref=carrier_pref,
            provider_npis=provider_npis,
            effective_date=effective_date,
            _cache_ver=_cache_ver
        )
    except Exception:
        # Avoid caching temporary empty responses so next retry executes live
        return False, [], state_code or "CA", fips_code or "", [], "HealthSherpa One"


def obtener_cotizaciones_healthsherpa(zip_code, age, income=0, household_size=1, effective_date=None, pregnant=False, fips_code=None, state_code=None, carrier_pref=None):
    """
    Submits quotes to HealthSherpa One API strictly without subsidies (for surrogate mothers).
    Single source of truth for all ACA and private carrier quotes across all states.
    """
    if not healthsherpa_service or not HEALTHSHERPA_API_KEY:
        return {"plans": [], "engine": "HealthSherpa One"}
    try:
        ok, def_p, st_api, co_api, all_p, eng = fetch_unified_plans(
            zipcode=zip_code,
            age=age,
            fips_code=fips_code,
            state_code=state_code,
            pregnant=pregnant,
            carrier_pref=carrier_pref,
            effective_date=effective_date
        )
        if ok and all_p:
            return {"plans": all_p, "engine": eng}
    except Exception:
        pass
    return {"plans": [], "engine": "HealthSherpa One"}


def get_monday_headers():
    return {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json", "API-Version": "2023-10"}

def sync_monday_candidates():
    if not MONDAY_API_KEY:
        return False, "MONDAY_API_KEY is not configured in Secrets."
    conn = get_db_connection()
    cursor = conn.cursor()
    inserted = 0
    updated = 0
    cursor_page = None
    has_more = True
    try:
        while has_more:
            cursor_param = f', cursor: "{cursor_page}"' if cursor_page else ""
            query = f"""
            query {{
              boards (ids: {MONDAY_BOARD_ID}) {{
                items_page (limit: 500{cursor_param}) {{
                  cursor
                  items {{
                    id name
                    column_values {{ id text value column {{ title }} }}
                  }}
                }}
              }}
            }}
            """
            response = requests.post("https://api.monday.com/v2", headers=get_monday_headers(), json={"query": query}, timeout=20)
            if response.status_code != 200:
                conn.close()
                return False, f"API Error: {response.status_code} - {response.text}"
            data = response.json()
            if "errors" in data:
                conn.close()
                return False, f"GraphQL Error: {data['errors'][0]['message']}"
            page_data = data["data"]["boards"][0]["items_page"]
            items = page_data.get("items", [])
            cursor_page = page_data.get("cursor")
            if not cursor_page or len(items) == 0:
                has_more = False

            for item in items:
                item_id = item["id"]
                cand_name = item["name"].strip() if item["name"] else "Unknown Candidate"
                agency = "General Agency"; state = ""; zip_code = ""; carrier = ""
                hosp = ""; doc = ""; pregnant_val = "No"; raw_age = ""; enroll_status = "Pending"
                for cv in item["column_values"]:
                    cid = str(cv.get("id", "")).lower()
                    title = str(cv.get("column", {}).get("title", "")).lower().strip()
                    text = str(cv.get("text", "")).strip()
                    if not text: continue
                    if "agency" in title or "agency" in cid or "agencia" in title: agency = text
                    elif "state" in title or "estado" in title:
                        state = "CA" if text.upper() in ["CA", "CALIFORNIA", "FRESNO", "LOS ANGELES", "SAN DIEGO"] else text.upper()
                    elif "zip" in title or "postal" in title or "codigo" in title: zip_code = text
                    elif title == "insurance company" or (("carrier" in title or "insurance company" in title) and not ("card" in title or "id" in title or "link" in title or "dl" in title)):
                        if not text.lower().startswith("http") and "jotform" not in text.lower(): carrier = text
                    elif "preferred hospital" in title or "hospital" in title: hosp = text
                    elif "obgyn" in title or "pcp" in title or "doctor" in title or "provider" in title:
                        if not ("address" in title or "link" in title or text.lower().startswith("http")): doc = text
                    elif "pregnant" in title or "embaraz" in title:
                        pregnant_val = "Yes" if ("yes" in text.lower() or "si" in text.lower()) else "No"
                    elif title in ["dob", "age", "edad", "birth date", "fecha de nacimiento"]: raw_age = text
                    elif "enrollment status" in title or "status" in title: enroll_status = text
                if zip_code.startswith("9") and (not state or state == "FRESNO"): state = "CA"
                final_state = state if state else "No State in Monday"
                final_zip = zip_code if zip_code else "No Zip Code in Monday"
                final_hosp = hosp if hosp else "No Preference"
                final_doc = doc if doc else "No Preference"
                final_age, parsed_dob = calcular_edad_actuarial(raw_age)
                final_carrier = carrier if carrier else resolver_marketplace_por_estado(final_state, final_zip)
                cursor.execute("SELECT id_cliente FROM chicas_excel WHERE (monday_item_id = ? AND monday_item_id != '') OR LOWER(TRIM(nombre_gc)) = LOWER(TRIM(?))", (item_id, cand_name))
                row = cursor.fetchone()
                if row:
                    cursor.execute("""
                        UPDATE chicas_excel SET monday_item_id=?, agencia=?, edad=?, estado=?, codigo_postal=?,
                        compania_seguros=?, hospital_preferido=?, doctor_preferido=?, embarazada=?, enrollment_status=?,
                        fecha_nacimiento=?
                        WHERE id_cliente=?
                    """, (item_id, agency, final_age, final_state, final_zip, final_carrier, final_hosp, final_doc, pregnant_val, enroll_status, parsed_dob or raw_age, row[0]))
                    updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO chicas_excel (nombre_gc, edad, estado, codigo_postal, compania_seguros,
                        agencia, hospital_preferido, doctor_preferido, embarazada, monday_item_id, enrollment_status, fecha_nacimiento)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cand_name, final_age, final_state, final_zip, final_carrier, agency, final_hosp, final_doc, pregnant_val, item_id, enroll_status, parsed_dob or raw_age))
                    inserted += 1
        conn.commit()
        conn.close()
        return True, f"Sync complete! {inserted} added, {updated} updated."
    except Exception as e:
        return False, f"Connection exception: {str(e)}"

def push_status_to_monday(item_id, status_label):
    if not MONDAY_API_KEY or not item_id: return False
    query = """
    mutation ($boardId: ID!, $itemId: ID!, $columnId: String!, $value: JSON!) {
      change_column_value (board_id: $boardId, item_id: $itemId, column_id: $columnId, value: $value) { id }
    }
    """
    vars = {"boardId": MONDAY_BOARD_ID, "itemId": str(item_id), "columnId": "status", "value": json.dumps({"label": status_label})}
    try:
        res = requests.post("https://api.monday.com/v2", headers=get_monday_headers(), json={"query": query, "variables": vars}, timeout=10)
        data = res.json()
        return "data" in data and data["data"] is not None
    except Exception:
        return False

def update_candidate_details_in_monday(item_id, hospital_pref, obgyn_pref, pregnant, current_plan, hosp_in_net=True, doc_in_net=True):
    if not MONDAY_API_KEY or not item_id:
        return False, "Falta API Key o ID de candidato en Monday."
    col_vals = {}
    if hospital_pref:
        col_vals["text_mkns7kzp"] = str(hospital_pref).strip()
    if obgyn_pref:
        col_vals["text_mknsg5d2"] = str(obgyn_pref).strip()
    col_vals["text_mkwq2ab7"] = str(pregnant).strip()
    col_vals["text_mkvqxw52"] = str(pregnant).strip()
    if current_plan:
        col_vals["text_mknsgbap"] = str(current_plan).strip()
    col_vals["color_mkx8t0nm"] = {"label": "IN" if hosp_in_net else "OUT"}
    col_vals["color_mkx8ngc5"] = {"label": "IN" if doc_in_net else "OUT"}

    query = """
    mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
      change_multiple_column_values (board_id: $boardId, item_id: $itemId, column_values: $columnValues) {
        id
      }
    }
    """
    vars = {
        "boardId": MONDAY_BOARD_ID,
        "itemId": str(item_id),
        "columnValues": json.dumps(col_vals)
    }
    try:
        res = requests.post(
            "https://api.monday.com/v2",
            headers=get_monday_headers(),
            json={"query": query, "variables": vars},
            timeout=12
        )
        data = res.json()
        if "errors" in data:
            return False, data["errors"][0].get("message", "Error in GraphQL")
        return True, "Monday updated successfully"
    except Exception as e:
        return False, str(e)


def upload_pdf_to_monday(item_id, pdf_bytes, file_name):
    if not MONDAY_API_KEY or not item_id:
        return False, "Falta API Key o ID de candidato en Monday."
    url = "https://api.monday.com/v2/file"
    headers = {"Authorization": MONDAY_API_KEY}
    query = """
    mutation ($file: File!, $itemId: ID!, $columnId: String!) {
      add_file_to_column (file: $file, item_id: $itemId, column_id: $columnId) { id }
    }
    """
    for col_id in ['file_mm0r6d7e', 'files']:
        payload = {'query': query, 'variables': json.dumps({'itemId': str(item_id), 'columnId': col_id})}
        files = {'variables[file]': (file_name, pdf_bytes.getvalue(), 'application/pdf')}
        try:
            res = requests.post(url, headers=headers, data=payload, files=files, timeout=20)
            res_data = res.json()
            if "data" in res_data and res_data["data"]:
                return True, "PDF subido con éxito a Monday.com"
        except Exception:
            continue
    return False, "No se pudo subir a Monday. Verifica permisos del token."

# ==============================================================================
# 6. DIRECTORIO OFICIAL DE HOSPITALES Y RESOLUTOR INTELIGENTE
# ==============================================================================
HOSPITALES_OFICIALES = [
    "No Preference",
    "Sharp Mary Birch Hospital for Women & Newborns", "Scripps Memorial Hospital La Jolla",
    "UCSD Jacobs Medical Center", "Kaiser Permanente San Diego Medical Center",
    "Palomar Medical Center Escondido", "Sharp Grossmont Hospital",
    "Scripps Mercy Hospital San Diego", "Huntington Hospital (Pasadena)",
    "Pomona Valley Hospital Medical Center", "Cedars-Sinai Medical Center",
    "Torrance Memorial Medical Center", "Hoag Hospital - Newport Beach",
    "Hoag Hospital - Irvine", "Temecula Valley Hospital",
    "Loma Linda University Medical Center", "Saint Agnes Medical Center (Fresno)",
    "Community Regional Medical Center (Fresno)", "Other / Out of Network"
]

def resolver_hospital_preferido(hospital_input, lista_base):
    h_clean = str(hospital_input or "").strip()
    if not h_clean or h_clean.lower() in ["no preference", "none", "n/a", "no", "tbc", "sin preferencia"]:
        return "No Preference", list(lista_base)
    
    if h_clean in lista_base:
        return h_clean, list(lista_base)
    
    lower_map = {h.lower(): h for h in lista_base}
    if h_clean.lower() in lower_map:
        return lower_map[h_clean.lower()], list(lista_base)
    
    matches = difflib.get_close_matches(h_clean, lista_base, n=1, cutoff=0.55)
    if matches:
        return matches[0], list(lista_base)
    
    nueva_lista = list(lista_base)
    if "Other / Out of Network" in nueva_lista:
        idx_other = nueva_lista.index("Other / Out of Network")
        nueva_lista.insert(idx_other, h_clean)
    else:
        nueva_lista.append(h_clean)
    return h_clean, nueva_lista

# ==============================================================================
# 7. GENERADOR PDF DINÁMICO
# ==============================================================================
def generar_cotizacion_pdf(candidate_name, agency_name, hospital_pref, obgyn_pref, hosp_in_net, doc_in_net, pregnant, current_plan, plans):
    buffer = BytesIO()
    if not plans:
        return buffer
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    style_normal    = ParagraphStyle('Norm',    parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.black)
    style_bold      = ParagraphStyle('Bld',     parent=style_normal, fontName='Helvetica-Bold')
    style_purple_hdr = ParagraphStyle('PurpHdr', parent=style_normal, fontName='Helvetica-Bold', textColor=colors.white, alignment=1)
    style_purple_sub = ParagraphStyle('PurpSub', parent=style_normal, fontName='Helvetica-Bold', textColor=colors.HexColor('#2A0845'), alignment=1)

    story = []

    # LOGO CENTRADO
    if logo_file and os.path.isfile(logo_file):
        try:
            logo_img = Image(logo_file, width=130, height=40)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 8))
        except Exception:
            pass

    # SALUDO (Agencia en negrita y nombre limpio sin notas internas)
    clean_cand = re.sub(r'[\(\[\{].*?[\)\]\}]', '', str(candidate_name or "")).strip()
    clean_cand = re.sub(r'\s+', ' ', clean_cand).strip()
    if not clean_cand:
        clean_cand = str(candidate_name or "").strip()

    story.append(Paragraph(f"Hi <b>{agency_name}</b>.<br/><br/>Thanks for sending <b>{clean_cand}'s</b> enrollment form.", style_normal))
    story.append(Spacer(1, 6))

    # BULLET POINTS
    details_lines = []
    if obgyn_pref and obgyn_pref.strip().lower() not in ["none", "n/a", ""]:
        details_lines.append(f"• <b>Preferred OB-GYN:</b> {obgyn_pref} ({'In-Network' if doc_in_net else 'Out-of-Network'})")
    else:
        details_lines.append("• <b>Preferred OB-GYN:</b> TBC")
    if hospital_pref and hospital_pref.strip().lower() not in ["none", "n/a", ""]:
        details_lines.append(f"• <b>Preferred Hospital:</b> {hospital_pref} ({'In-Network' if hosp_in_net else 'Out-of-Network'})")
    else:
        details_lines.append("• <b>Preferred Hospital:</b> TBC")
    details_lines.append(f"• <b>Pregnant?</b> {pregnant or 'TBC'}")

    clean_plan = str(current_plan or "").strip()
    if not clean_plan or clean_plan.lower() in ["ninguno", "none", "n/a", "no", "sin plan", "ninguna", "null"]:
        clean_plan = "None"
    details_lines.append(f"• <b>Current Health Plan:</b> {clean_plan}")
    story.append(Paragraph("<br/>".join(details_lines), style_normal))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Please review our recommendations and quotes below:", style_normal))
    story.append(Spacer(1, 8))

    # SECCIÓN 1
    story.append(Paragraph("<b>1) Recommendations:</b>", style_normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph("• Please remind the GC not to apply for health insurance during Open Enrollment to avoid potential complications from having multiple plans.", style_normal))
    story.append(Spacer(1, 10))

    # SECCIÓN 2: TABLA
    story.append(Paragraph("<b>2) Quotes Preview</b>", style_normal))
    story.append(Spacer(1, 6))

    headers_row = [""] + [Paragraph(p["tier"], style_purple_hdr) for p in plans]
    matrix_data = [headers_row]
    matrix_data.extend([
        [Paragraph("<b>Monthly Premium **</b>", style_bold)] + [Paragraph(f"<b>${p['premium']:.2f}</b>", style_purple_sub) for p in plans],
        [Paragraph("<b>Deductible</b>", style_bold)]         + [Paragraph(p['deductible'], style_purple_sub) for p in plans],
        [Paragraph("<b>Max Out of pocket</b>", style_bold)]  + [Paragraph(p['oop_max'], style_purple_sub) for p in plans],
        [Paragraph("Primary Care Physician", style_normal)]  + [Paragraph(p.get('pcp', '$50 copay'), style_normal) for p in plans],
        [Paragraph("Specialist", style_normal)]              + [Paragraph(p.get('specialist', '$90 copay'), style_normal) for p in plans],
        [Paragraph("Emergency Services", style_normal)]      + [Paragraph(p.get('emergency_room', '$350 copay'), style_normal) for p in plans],
        [Paragraph("Urgent Care", style_normal)]             + [Paragraph(p.get('urgent_care', '$60 copay'), style_normal) for p in plans],
        [Paragraph("Ambulance", style_normal)]               + [Paragraph(p.get('ambulance', '$250 copay'), style_normal) for p in plans],
        [Paragraph("Labs", style_normal)]                    + [Paragraph(p.get('labs', '$50 copay'), style_normal) for p in plans],
        [Paragraph("X-Rays", style_normal)]                  + [Paragraph(p.get('xrays', '40% coinsurance'), style_normal) for p in plans],
        [Paragraph("Office Visits", style_normal)]           + [Paragraph("No charge", style_normal) for _ in plans],
        [Paragraph("Childbirth/ Physician Services", style_normal)] + [Paragraph(p.get('cb_phys', '30% coinsurance'), style_normal) for p in plans],
        [Paragraph("Childbirth/ Delivery Facility", style_normal)]  + [Paragraph(p.get('cb_fac', '30% coinsurance'), style_normal) for p in plans],
        [Paragraph("<b>Lien for surrogacy?</b>", ParagraphStyle('Wht', parent=style_bold, textColor=colors.white))] +
        [Paragraph(str(p.get('lien', 'Yes')), ParagraphStyle('WhtC', parent=style_normal, textColor=colors.white, alignment=1)) for p in plans],
    ])

    len_p = max(1, len(plans))
    col_w = [150] + [int(400 / len_p)] * len_p
    t_quote = Table(matrix_data, colWidths=col_w)
    t_quote.setStyle(TableStyle([
        ('BACKGROUND', (1, 0),  (-1, 0),  colors.HexColor('#2A0845')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#2A0845')),
        ('ALIGN',      (1, 0),  (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0),  (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0),  (-1, -1), 0.5, colors.HexColor('#B8A9C9')),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_quote)
    story.append(Spacer(1, 12))

    # SECCIÓN 3
    story.append(Paragraph("<b>3) Please confirm the following:</b>", style_normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "■ <b>Preferred health plan:</b><br/>"
        "■ <b>Coverage Start Date:</b><br/>"
        "■ <b>Initial Premium</b> (the initial premium is required to enroll. Please provide a US credit/debit card, checking/savings account):<br/>"
        "■ <b>Monthly Payments</b> (please confirm if you would like to use the same payment method to set up automatic monthly payments):",
        style_normal
    ))
    story.append(Spacer(1, 12))

    # IMPORTANT
    story.append(Paragraph("<b><u>IMPORTANT</u></b>", ParagraphStyle('Imp', parent=style_normal, fontName='Helvetica-Bold', fontSize=8)))
    story.append(Spacer(1, 4))
    p_disc = ParagraphStyle('Disc', parent=style_normal, fontSize=6.5, leading=8.5, textColor=colors.HexColor('#444444'))
    story.append(Paragraph("<b>In-Network Providers:</b> The information provided is based on data from different websites (Insurance Companies, Health Insurance Marketplace websites, etc.). This information may not be up-to-date. Please get in touch with your doctor and hospital to ensure they accept these plans.", p_disc))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Monthly Premium Amounts:</b> The quoted amounts are estimates. The final premium amount will be confirmed after the application is completed.", p_disc))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 8. BARRA LATERAL (SIDEBAR ORIGINAL)
# ==============================================================================
st.sidebar.markdown(
    """
    <style>
        /* ── FONDO SIDEBAR: selectores múltiples para forzar color ── */
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div,
        section[data-testid="stSidebar"] > div > div,
        div[data-testid="stSidebar"],
        div[data-testid="stSidebar"] > div {
            background-color: #0F1535 !important;
            background: #0F1535 !important;
        }

        /* ── MENÚ RADIO: ocultar botón nativo ── */
        div[data-testid="stRadio"] div[role="radiogroup"] {
            display: flex !important; flex-direction: column !important;
            width: 100% !important; gap: 0.3rem !important;
        }
        div[role="radiogroup"] label > div:first-child,
        div[data-testid="stRadio"] label > div:first-child,
        div[data-testid="stRadio"] label input[type="radio"],
        div[data-testid="stRadio"] label span,
        div[data-testid="stRadio"] label [data-testid="stRadioBtn"] {
            display: none !important; width: 0 !important; height: 0 !important;
            opacity: 0 !important; visibility: hidden !important; position: absolute !important;
        }

        /* ── ITEMS DEL MENÚ ── */
        div[data-testid="stRadio"] div[role="radiogroup"] label {
            display: flex !important; align-items: center !important;
            width: 100% !important; min-height: 42px !important; height: 42px !important;
            padding: 0 1rem !important; margin: 0 !important;
            border-radius: 10px !important;
            background: transparent !important;
            border: 1px solid transparent !important;
            cursor: pointer !important; transition: all 0.18s ease !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
            background: rgba(255, 255, 255, 0.07) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
        }
        div[data-testid="stRadio"] label p,
        div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
            color: rgba(255, 255, 255, 0.8) !important;
            font-size: 0.88rem !important; font-weight: 500 !important;
            margin: 0 !important; white-space: nowrap !important;
        }

        /* ── ITEM ACTIVO ── */
        div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
            background: rgba(235, 60, 150, 0.12) !important;
            border: 1px solid rgba(235, 60, 150, 0.25) !important;
            border-left: 3px solid #EB3C96 !important;
        }
        div[data-testid="stRadio"] label:has(input:checked) p {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        /* ── BOTÓN SYNC MONDAY (CONSERVA DEGRADADO CORPORATIVO ORIGINAL) ── */
        .st-key-btn_sync_monday_sidebar button {
            background: linear-gradient(115deg, #1C237A 0%, #631C82 50%, #EB3C96 100%) !important;
            color: #FFFFFF !important; border: none !important;
            border-radius: 8px !important; height: 38px !important; min-height: 38px !important;
            font-size: 0.87rem !important; font-weight: 600 !important;
            box-shadow: 0 3px 10px rgba(99, 28, 130, 0.3) !important;
            transition: all 0.18s ease-in-out !important;
        }
        .st-key-btn_sync_monday_sidebar button:hover {
            box-shadow: 0 5px 16px rgba(235, 60, 150, 0.45) !important;
            transform: translateY(-1px) !important;
            filter: brightness(1.08) !important;
        }

        /* ── BOTÓN LOG OUT ── */
        .st-key-btn_logout_sidebar button {
            background: transparent !important;
            color: rgba(255, 255, 255, 0.5) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 8px !important; height: 38px !important; min-height: 38px !important;
            font-size: 0.87rem !important; font-weight: 500 !important;
        }
        .st-key-btn_logout_sidebar button:hover {
            color: rgba(255, 255, 255, 0.85) !important;
            border-color: rgba(255, 255, 255, 0.25) !important;
            background: rgba(255, 255, 255, 0.05) !important;
        }

        /* ── TEXTOS GENERALES DEL SIDEBAR ── */
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div {
            color: #FFFFFF !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if logo_file and os.path.isfile(logo_file):
    st.sidebar.image(logo_file, use_container_width=True)

user_name = st.session_state.get('current_user') or 'User'
st.sidebar.markdown(
    f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;
                text-align: center; margin-top: 0.4rem; margin-bottom: 1rem; width: 100%;">
        <span style="background: rgba(235, 60, 150, 0.15); color: #F472B6;
                     border: 1px solid rgba(235, 60, 150, 0.3); font-size: 0.72rem;
                     font-weight: 700; padding: 0.18rem 0.7rem; border-radius: 20px;
                     letter-spacing: 0.5px; text-transform: uppercase;">
            Welcome
        </span>
        <div style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF; margin-top: 0.4rem;">
            {user_name}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    "<hr style='margin: 0.2rem 0 0.8rem 0; border: none; border-top: 1px solid rgba(255,255,255,0.08);'>",
    unsafe_allow_html=True
)
st.sidebar.markdown(
    "<div style='font-size: 0.68rem; font-weight: 700; color: rgba(255,255,255,0.4); "
    "letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 0.5rem;'>MENU</div>",
    unsafe_allow_html=True
)

menu_option = st.sidebar.radio(
    "Navigation Menu",
    ["🔍 Search & Quote Candidate", "📋 Pending Enrollments (CRM)", "➕ Add New Candidate", "📊 Quote History"],
    key="sidebar_navigation_menu", label_visibility="collapsed"
)

st.sidebar.markdown(
    "<hr style='margin: 1rem 0; border: none; border-top: 1px solid rgba(255,255,255,0.08);'>",
    unsafe_allow_html=True
)

if st.sidebar.button("🔄 Sync with monday.com", key="btn_sync_monday_sidebar", use_container_width=True):
    with st.spinner("Connecting to monday.com..."):
        success, msg = sync_monday_candidates()
        if success:
            st.sidebar.success(msg)
            time.sleep(1)
            st.rerun()
        else:
            st.sidebar.error(msg)

st.sidebar.markdown("<div style='margin-top: 0.4rem;'></div>", unsafe_allow_html=True)

if st.sidebar.button("Log Out", key="btn_logout_sidebar", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = ""
    st.session_state["input_user"] = ""
    st.session_state["input_pass"] = ""
    st.rerun()
# ==============================================================================
# PANTALLA DE CARGA INICIAL (SPLASH / LOADING SCREEN)
# ==============================================================================
# PANTALLA DE CARGA INICIAL (FROSTED GLASS / FULLSCREEN BLUR OVERLAY)
# ==============================================================================
def mostrar_pantalla_carga(user_name="User"):
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:72px; max-width:240px; object-fit:contain; margin-bottom:1.4rem; filter:drop-shadow(0 4px 12px rgba(235, 60, 150, 0.3));" />' if logo_b64 else '<h1 style="color:#FFFFFF; font-weight:800; margin:0 0 1.4rem 0; letter-spacing:-0.5px;">nexxell</h1>'
    display_name = str(user_name).capitalize() if user_name else "User"

    st.markdown(
        f"""
        <style>
            /* ── OVERLAY DE PANTALLA COMPLETA CON DESENFOQUE TOTAL (FROSTED GLASS) ── */
            .frosted-glass-overlay {{
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                z-index: 9999999 !important;
                background: rgba(10, 14, 39, 0.78) !important;
                backdrop-filter: blur(20px) saturate(160%) !important;
                -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 1.5rem !important;
                box-sizing: border-box !important;
            }}

            /* ── TARJETA FLOTANTE DE CRISTAL ── */
            .frosted-glass-card {{
                background: linear-gradient(145deg, rgba(22, 28, 99, 0.88) 0%, rgba(42, 16, 78, 0.92) 55%, rgba(77, 22, 94, 0.88) 100%) !important;
                border: 1px solid rgba(255, 255, 255, 0.22) !important;
                border-radius: 30px !important;
                padding: 3.4rem 3rem !important;
                max-width: 520px !important;
                width: 90% !important;
                box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.3) !important;
                text-align: center !important;
                animation: frostedFloat 3.5s ease-in-out infinite !important;
            }}

            @keyframes frostedFloat {{
                0%, 100% {{
                    transform: translateY(0px);
                    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), 0 0 35px rgba(235, 60, 150, 0.18);
                }}
                50% {{
                    transform: translateY(-5px);
                    box-shadow: 0 35px 95px rgba(0, 0, 0, 0.65), 0 0 55px rgba(235, 60, 150, 0.32);
                }}
            }}

            .frosted-title {{
                color: #FFFFFF !important;
                font-size: 1.48rem !important;
                font-weight: 800 !important;
                margin-bottom: 0.5rem !important;
                letter-spacing: -0.4px !important;
            }}

            .frosted-sub {{
                color: #E2D4F5 !important;
                font-size: 0.96rem !important;
                margin-bottom: 2.2rem !important;
                line-height: 1.5 !important;
            }}

            .frosted-progress-track {{
                width: 100% !important;
                height: 7px !important;
                background: rgba(255, 255, 255, 0.16) !important;
                border-radius: 999px !important;
                overflow: hidden !important;
                position: relative !important;
                margin-bottom: 1.8rem !important;
            }}

            .frosted-progress-bar {{
                width: 100% !important;
                height: 100% !important;
                background: linear-gradient(90deg, #1C237A 0%, #7E228B 35%, #EB3C96 50%, #7E228B 65%, #1C237A 100%) !important;
                background-size: 250% 100% !important;
                animation: frostedShimmer 1.8s linear infinite !important;
                border-radius: 999px !important;
            }}

            @keyframes frostedShimmer {{
                0% {{ background-position: 200% 0; }}
                100% {{ background-position: -200% 0; }}
            }}

            .frosted-badge {{
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 8px !important;
                background: rgba(255, 255, 255, 0.1) !important;
                border: 1px solid rgba(255, 255, 255, 0.18) !important;
                padding: 7px 18px !important;
                border-radius: 999px !important;
                font-size: 0.82rem !important;
                color: #FFFFFF !important;
                font-weight: 500 !important;
                letter-spacing: 0.2px !important;
            }}
        </style>
        <div class="frosted-glass-overlay">
            <div class="frosted-glass-card">
                {logo_html}
                <div class="frosted-title">Welcome back, {display_name}!</div>
                <div class="frosted-sub">Syncing candidate directory with monday.com...</div>
                <div class="frosted-progress-track">
                    <div class="frosted-progress-bar"></div>
                </div>
                <div class="frosted-badge">
                    <span>⚡</span> <span>Secure connection with monday.com active</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==============================================================================
# 9. MÓDULO PRINCIPAL: SEARCH & QUOTE CANDIDATE
# ==============================================================================
if menu_option == "🔍 Search & Quote Candidate":
    if "monday_synced_session" not in st.session_state:
        splash_placeholder = st.empty()
        with splash_placeholder.container():
            curr_u = st.session_state.get("current_user") or "User"
            mostrar_pantalla_carga(curr_u)
            sync_monday_candidates()
            time.sleep(0.6)
        st.session_state["monday_synced_session"] = True
        splash_placeholder.empty()
        st.rerun()

    st.title("Search Candidate")
    st.caption("Review candidate details, build a quote, and send the official proposal.")

    agencies = get_clean_agencies()
    if not agencies:
        agencies = ["General Agency"]

    col_ag, col_cand = st.columns(2)
    with col_ag:
        selected_agency = st.selectbox("1. Select Agency / Organization:", ["All Agencies"] + agencies)

    conn = get_db_connection()
    cursor = conn.cursor()
    if selected_agency == "All Agencies":
        cursor.execute("SELECT nombre_gc FROM chicas_excel ORDER BY nombre_gc ASC")
    else:
        cursor.execute("SELECT nombre_gc FROM chicas_excel WHERE TRIM(agencia) LIKE ? ORDER BY nombre_gc ASC", (f"%{selected_agency}%",))
    candidates = [r[0] for r in cursor.fetchall()]
    conn.close()

    with col_cand:
        selected_candidate = st.selectbox("2. Search Candidate (Type to filter):", [""] + candidates)

    hospital_pref = ""
    obgyn_pref = ""
    hosp_in_net = True
    doc_in_net = True
    pregnant = "No"
    current_plan = "None"
    final_plans = []
    id_c = None

    if "last_selected_cand" not in st.session_state:
        st.session_state["last_selected_cand"] = ""

    if selected_candidate != st.session_state["last_selected_cand"]:
        for k in list(st.session_state.keys()):
            if k.startswith("plan_") or k.startswith("num_plans_") or k.startswith("sel_api_") or k.startswith("carrier_filt_") or k.startswith("quoting_stage_"):
                del st.session_state[k]
        st.session_state["last_selected_cand"] = selected_candidate

    if selected_candidate:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chicas_excel WHERE nombre_gc = ?", (selected_candidate,))
        cand_data = cursor.fetchone()
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        c_dict = dict(zip(col_names, cand_data)) if cand_data else {}
        conn.close()

        id_c       = c_dict.get('id_cliente')
        age        = c_dict.get('edad', 25)
        state_db   = c_dict.get('estado') or 'CA'
        zip_db     = c_dict.get('codigo_postal') or c_dict.get('zip_code', '')
        carrier_db = c_dict.get('compania_seguros') or c_dict.get('carrier_pref', 'Anthem')
        agency_db  = c_dict.get('agencia') or 'General Agency'
        hospital_pref = c_dict.get('hospital_preferido') or c_dict.get('hospital_pref', '')
        obgyn_pref    = c_dict.get('doctor_preferido') or c_dict.get('doctor_pref', '')
        pregnant      = c_dict.get('embarazada', 'No')
        current_plan_raw = c_dict.get('plan_actual') or 'None'
        if str(current_plan_raw).strip().lower() in ['ninguno', 'ninguna', 'sin plan', 'null', 'none', '']:
            current_plan = 'None'
        else:
            current_plan = str(current_plan_raw).strip()
        item_id       = c_dict.get('monday_item_id', '')

        cand_key = selected_candidate.replace(" ", "_")

        # ── Surrogacy Demographic & Rating Parameters ──
        today = date.today()
        default_eff = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
        stored_dob = c_dict.get('fecha_nacimiento') or ''
        initial_dob = stored_dob if stored_dob else (f"{today.year - int(age) if str(age).isdigit() else today.year - 25}-01-01")

        # Ensure eff_date and dob persist across stages in session_state
        eff_date_key = f"eff_date_{cand_key}"
        if eff_date_key not in st.session_state:
            st.session_state[eff_date_key] = default_eff
        eff_date = st.session_state[eff_date_key]

        dob_key = f"dob_input_{cand_key}"
        if dob_key not in st.session_state:
            st.session_state[dob_key] = initial_dob
        dob_val = st.session_state[dob_key]

        actuarial_age, clean_dob = calcular_edad_actuarial(dob_val, eff_date)

        # Stage management (Stage 1: Location, Stage 2: Household, Stage 3: ACA Quotes)
        stage_key = f"quoting_stage_{cand_key}"
        if stage_key not in st.session_state:
            st.session_state[stage_key] = 1
        curr_stage = st.session_state[stage_key]

        # ── 2. Interactive Visual Stepper Navigation (Matching User Reference Image Exactly) ──
        s1_active = (curr_stage == 1)
        s2_active = (curr_stage == 2)
        s3_active = (curr_stage == 3)

        line1_color = "#10B981" if curr_stage >= 2 else "#E2E8F0"
        line2_color = "#10B981" if curr_stage >= 3 else "#E2E8F0"

        # Labels matching the user reference screenshot
        if s1_active:
            s1_label = "📍 **1. Location**\n\nZIP & County Resolution"
        else:
            s1_label = "✅ **1. Location**\n\nZIP & County Resolution" if curr_stage > 1 else "**1. Location**\n\nZIP & County Resolution"

        if s2_active:
            s2_label = "👥 **2. Household**\n\nIncome & Demographics"
        elif curr_stage > 2:
            s2_label = "✅ **2. Household**\n\nIncome & Demographics"
        else:
            s2_label = "**2. Household**\n\nIncome & Demographics"

        if s3_active:
            s3_label = "📄 **3. ACA Quotes**\n\nPlans & Subsidies"
        elif curr_stage == 3 or (len(st.session_state.get(f"sel_plan_ids_{cand_key}", [])) > 0):
            s3_label = "✅ **3. ACA Quotes**\n\nPlans & Subsidies"
        else:
            s3_label = "**3. ACA Quotes**\n\nPlans & Subsidies"

        st.markdown(
            """
            <style>
            /* Stepper Outer Container matching screenshot */
            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) {
                background: #FFFFFF !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 14px !important;
                padding: 10px 18px !important;
                margin-bottom: 16px !important;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03) !important;
                align-items: center !important;
            }

            /* Stepper Button Reset & Elevation */
            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button {
                background: transparent !important;
                border: 1px solid transparent !important;
                border-radius: 12px !important;
                padding: 8px 14px !important;
                text-align: left !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: flex-start !important;
                justify-content: center !important;
                box-shadow: none !important;
                width: 100% !important;
                min-height: 56px !important;
                transition: all 0.2s ease !important;
            }

            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button:hover {
                background: #F8FAFC !important;
                border-color: #E2E8F0 !important;
            }

            /* Active Step Button - Light Blue Pill matching Image */
            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button[kind="primary"] {
                background: #EFF6FF !important;
                border: 1.5px solid #BFDBFE !important;
                box-shadow: 0 1px 6px rgba(37, 99, 235, 0.08) !important;
            }

            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button p {
                margin: 0 !important;
                line-height: 1.35 !important;
                font-size: 0.88rem !important;
                color: #0F172A !important;
            }

            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button[kind="primary"] p {
                color: #1D4ED8 !important;
            }

            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button p:last-child {
                font-size: 0.72rem !important;
                font-weight: 500 !important;
                color: #64748B !important;
            }

            div[data-testid="stHorizontalBlock"]:has(.stepper-visual-marker) button[kind="primary"] p:last-child {
                color: #2563EB !important;
            }
            </style>
            <div class="stepper-visual-marker" style="display:none;"></div>
            """,
            unsafe_allow_html=True
        )

        col_s1, col_l1, col_s2, col_l2, col_s3 = st.columns([3.4, 1.2, 3.4, 1.2, 3.4])
        with col_s1:
            if st.button(s1_label, key=f"nav_tab_1_{cand_key}", use_container_width=True, type="primary" if s1_active else "secondary"):
                st.session_state[stage_key] = 1
                st.rerun()
        with col_l1:
            st.markdown(f'<div style="height:2px; background:{line1_color}; margin-top:27px;"></div>', unsafe_allow_html=True)
        with col_s2:
            if st.button(s2_label, key=f"nav_tab_2_{cand_key}", use_container_width=True, type="primary" if s2_active else "secondary"):
                st.session_state[stage_key] = 2
                st.rerun()
        with col_l2:
            st.markdown(f'<div style="height:2px; background:{line2_color}; margin-top:27px;"></div>', unsafe_allow_html=True)
        with col_s3:
            if st.button(s3_label, key=f"nav_tab_3_{cand_key}", use_container_width=True, type="primary" if s3_active else "secondary"):
                st.session_state[stage_key] = 3
                st.rerun()

        # ── STAGE 1: LOCATION RESOLUTION ──
        if curr_stage == 1:
            st.markdown("### Stage 1: Location & Rating Area Resolution")
            st.markdown(
                f"""
                <div class="info-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #E2E8F0; padding-bottom:8px; margin-bottom:12px;">
                        <h4 style="margin:0; color:#1C237A; font-size:1.1rem; font-weight:700;">Candidate: {selected_candidate}</h4>
                        <span style="background:#FDF0F6; color:#EB3C96; border:1px solid rgba(235,60,150,0.3); padding:3px 12px; border-radius:999px; font-size:0.75rem; font-weight:700;">
                            Location & Eligibility
                        </span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;">
                        <div><span style="color:#64748B; font-size:0.75rem; font-weight:600; text-transform:uppercase;">Agency (Monday):</span><br><b>{agency_db}</b></div>
                        <div><span style="color:#64748B; font-size:0.75rem; font-weight:600; text-transform:uppercase;">State / ZIP Code:</span><br><b>{state_db} ({zip_db})</b></div>
                        <div><span style="color:#64748B; font-size:0.75rem; font-weight:600; text-transform:uppercase;">Preferred Carrier:</span><br><b>{carrier_db}</b></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            fechas_disponibles = generar_fechas_efectivas_futuras()
            idx_eff_s1 = fechas_disponibles.index(eff_date) if eff_date in fechas_disponibles else 0
            c_eff_s1, c_space_s1 = st.columns([1.5, 2])
            with c_eff_s1:
                new_eff = st.selectbox(
                    "Target Coverage Effective Date:",
                    options=fechas_disponibles,
                    index=idx_eff_s1,
                    format_func=lambda d: d.strftime("%Y/%m/01"),
                    key=f"eff_sel_s1_{cand_key}",
                    help="ACA rate curves depend on the candidate's exact age on the first day of coverage."
                )
                if new_eff != eff_date:
                    st.session_state[eff_date_key] = new_eff
                    st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Continue to 2. Household & Demographics ➔", key=f"btn_next_to_s2_{cand_key}", type="primary", use_container_width=True):
                st.session_state[stage_key] = 2
                st.rerun()

        # ── STAGE 2: HOUSEHOLD & DEMOGRAPHICS ──
        elif curr_stage == 2:
            st.markdown("### Stage 2: Household & Demographics")

            hh_size_key = f"hh_size_{cand_key}"
            if hh_size_key not in st.session_state:
                st.session_state[hh_size_key] = 1

            hh_income_key = f"hh_income_{cand_key}"
            if hh_income_key not in st.session_state:
                st.session_state[hh_income_key] = 150000

            st.markdown(
                f"""
                <div class="info-card" style="margin-bottom: 1.1rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0; color:#1C237A; font-size:1.15rem; font-weight:700;">Candidate: {selected_candidate}</h4>
                        <div style="background:#F8FAFC; border:1px solid #CBD5E1; padding:4px 14px; border-radius:8px; font-size:0.82rem; color:#475569; font-weight:600;">
                            Location: <b style="color:#1C237A;">{state_db} ({zip_db})</b>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Editable Household Parameters
            c_hh1, c_hh2 = st.columns(2)
            with c_hh1:
                hh_size_options = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
                curr_hh_size = st.session_state.get(hh_size_key, 1)
                idx_hh = hh_size_options.index(curr_hh_size) if curr_hh_size in hh_size_options else 0
                new_hh_size = st.selectbox(
                    "Household Size:",
                    options=hh_size_options,
                    index=idx_hh,
                    format_func=lambda x: f"{x} Member" if x == 1 else f"{x} Members",
                    key=f"sel_hh_size_{cand_key}",
                    help="Select household size to include spouse or additional dependents."
                )
                if new_hh_size != curr_hh_size:
                    st.session_state[hh_size_key] = new_hh_size
                    st.rerun()

            with c_hh2:
                curr_income = st.session_state.get(hh_income_key, 150000)
                new_income = st.number_input(
                    "Household Income ($ / year):",
                    min_value=0,
                    max_value=2000000,
                    value=int(curr_income),
                    step=5000,
                    format="%d",
                    key=f"num_hh_income_{cand_key}",
                    help="Annual household MAGI used for ACA eligibility and subsidy calculations."
                )
                if new_income != curr_income:
                    st.session_state[hh_income_key] = new_income
                    st.rerun()

            if new_hh_size > 1:
                st.info(f"👥 Household updated: **{new_hh_size} Members** (Primary Applicant + {new_hh_size - 1} dependent{'s' if new_hh_size > 2 else ''} included in quoting scope).")

            fechas_disponibles = generar_fechas_efectivas_futuras()
            idx_eff_s2 = fechas_disponibles.index(eff_date) if eff_date in fechas_disponibles else 0
            c_eff1, c_eff2, c_eff3 = st.columns([1.5, 1.5, 1.2])
            with c_eff1:
                new_eff = st.selectbox(
                    "Target Coverage Effective Date:",
                    options=fechas_disponibles,
                    index=idx_eff_s2,
                    format_func=lambda d: d.strftime("%Y/%m/01"),
                    key=f"eff_sel_s2_{cand_key}",
                    help="ACA rate curves depend on the candidate's exact age on the first day of coverage."
                )
                if new_eff != eff_date:
                    st.session_state[eff_date_key] = new_eff
                    st.rerun()
            with c_eff2:
                new_dob = st.text_input(
                    "Date of Birth (DOB - YYYY-MM-DD or MM/DD/YYYY):",
                    value=dob_val,
                    key=f"dob_s2_{cand_key}",
                    placeholder="e.g. 1998-05-14"
                )
                if new_dob != dob_val:
                    st.session_state[dob_key] = new_dob
                    st.rerun()
            with c_eff3:
                st.markdown(
                    f"""
                    <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:10px; text-align:center; margin-top:1.55rem;">
                        <div style="font-size:0.72rem; color:#1E40AF; font-weight:700; text-transform:uppercase;">Actuarial Age</div>
                        <div style="font-size:1.25rem; color:#1E3A8A; font-weight:800;">{actuarial_age} <span style="font-size:0.8rem; font-weight:500;">yrs</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with st.expander("Medical and Provider Preferences", expanded=True):
                col_med1, col_med2 = st.columns(2)
                with col_med1:
                    hosp_sel, lista_hosp_actual = resolver_hospital_preferido(hospital_pref, HOSPITALES_OFICIALES)
                    idx_hosp = lista_hosp_actual.index(hosp_sel) if hosp_sel in lista_hosp_actual else 0
                    hospital_pref = st.selectbox("Preferred Delivery Hospital:", lista_hosp_actual, index=idx_hosp)
                    hosp_in_net = st.checkbox("Hospital is In-Network", value=True)
                with col_med2:
                    obgyn_pref = st.text_input("Preferred OB-GYN / Clinic:", value=obgyn_pref, placeholder="e.g. Dr. Ron Lichtenstein, Sharp Rees-Stealy...")
                    doc_in_net = st.checkbox("OB-GYN is In-Network", value=True)

                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    pregnant = st.selectbox("Currently Pregnant?", ["No", "Yes"], index=0 if pregnant == "No" else 1)
                with col_sub2:
                    current_plan = st.text_input("Current Plan (if any):", value=current_plan, placeholder="e.g. Kaiser Silver HMO, None...")

                if st.button("Update Candidate Details", key="btn_update_candidate"):
                    save_plan = "None" if str(current_plan).strip().lower() in ["ninguno", "ninguna", "sin plan", "none", ""] else str(current_plan).strip()
                    conn = get_db_connection()
                    conn.cursor().execute("""
                        UPDATE chicas_excel SET hospital_preferido=?, doctor_preferido=?, embarazada=?, plan_actual=?, edad=?, fecha_nacimiento=?
                        WHERE id_cliente=?
                    """, (hospital_pref, obgyn_pref, pregnant, save_plan, actuarial_age, clean_dob or dob_val, id_c))
                    conn.commit()
                    conn.close()

                    if item_id:
                        with st.spinner("Syncing updates with monday.com..."):
                            ok_m, msg_m = update_candidate_details_in_monday(
                                item_id=item_id,
                                hospital_pref=hospital_pref,
                                obgyn_pref=obgyn_pref,
                                pregnant=pregnant,
                                current_plan=save_plan,
                                hosp_in_net=hosp_in_net,
                                doc_in_net=doc_in_net
                            )
                        if ok_m:
                            st.success("Candidate details updated and synchronized with monday.com successfully.")
                        else:
                            st.warning(f"Saved locally, but monday.com sync returned: {msg_m}")
                    else:
                        st.success("Candidate information updated successfully.")

            col_b_s2, col_n_s2 = st.columns(2)
            with col_b_s2:
                if st.button("⬅ Back to 1. Location", key=f"btn_back_s1_{cand_key}", use_container_width=True):
                    st.session_state[stage_key] = 1
                    st.rerun()
            with col_n_s2:
                if st.button("Proceed to 3. ACA Quotes ➔", key=f"btn_next_to_s3_{cand_key}", type="primary", use_container_width=True):
                    st.session_state[stage_key] = 3
                    st.rerun()

        # ── STAGE 3: ACA QUOTES & PROPOSAL GALLERY (IMAGE 3 VISUAL) ──
        elif curr_stage == 3:
            # ── BOX 1: Clean Demographics Header (No APTC / No Active Rating Bar) ──
            with st.container(border=True):
                c_s1, c_s2, c_s3 = st.columns(3)
                with c_s1:
                    st.markdown(
                        f"""
                        <div style="font-size:0.75rem; color:#64748B; font-weight:600;">Rating Location</div>
                        <div style="font-weight:700; color:#0F172A; font-size:0.95rem;">{state_db} ({zip_db})</div>
                        """,
                        unsafe_allow_html=True
                    )
                with c_s2:
                    curr_hh = st.session_state.get(f"hh_size_{cand_key}", 1)
                    curr_inc = st.session_state.get(f"hh_income_{cand_key}", 150000)
                    hh_str = f"{curr_hh} Person" if curr_hh == 1 else f"{curr_hh} People"
                    st.markdown(
                        f"""
                        <div style="font-size:0.75rem; color:#64748B; font-weight:600;">Household / Income</div>
                        <div style="font-weight:700; color:#0F172A; font-size:0.95rem;">{hh_str} &bull; ${curr_inc:,.0f}/yr</div>
                        """,
                        unsafe_allow_html=True
                    )
                with c_s3:
                    st.markdown(
                        f"""
                        <div style="font-size:0.75rem; color:#64748B; font-weight:600;">Effective Coverage Date</div>
                        <div style="font-weight:700; color:#0F172A; font-size:0.95rem;">{eff_date.strftime('%Y-%m-%d')}</div>
                        """,
                        unsafe_allow_html=True
                    )

            # ── 1. Universo Completo de Planes ──
            all_available_plans = []

            # ── 1. Universo Completo de Planes (HealthSherpa One API Exclusivo) ──
            all_available_plans = []

            with st.spinner("Fetching live carrier quotes from HealthSherpa One API..."):
                api_quotes_data = obtener_cotizaciones_healthsherpa(
                    zip_code=zip_db,
                    age=int(actuarial_age),
                    income=0,
                    household_size=1,
                    effective_date=eff_date.strftime("%Y-%m-%d"),
                    pregnant=(str(pregnant).strip().lower() == "yes"),
                    state_code=state_db,
                    carrier_pref=carrier_db
                )
                all_api_plans = api_quotes_data.get("plans", [])

            if all_api_plans:
                for p in all_api_plans:
                    g_val = float(p.get("prem_val", 0.0) or p.get("gross_prem_val", 0.0))
                    n_val = float(p.get("net_prem_val", g_val))
                    all_available_plans.append({
                        "id": str(p.get("id")),
                        "name": p.get("name"),
                        "issuer": p.get("issuer"),
                        "metal": p.get("metal") or "Bronze",
                        "plan_type": p.get("plan_type") or "HMO",
                        "prem_val": n_val,
                        "gross_prem_val": g_val,
                        "ded": str(p.get("ded", "$0")),
                        "oop": str(p.get("oop", "$9,200")),
                        "pcp": str(p.get("pcp", "$50 copay")),
                        "spec": str(p.get("spec", "$90 copay")),
                        "rx": str(p.get("rx", "$15 copay")),
                        "emergency_room": str(p.get("emergency_room", "$350 copay")),
                        "urgent_care": str(p.get("urgent_care", "$60 copay")),
                        "ambulance": str(p.get("ambulance", "$250 copay")),
                        "labs": str(p.get("labs", "Covered in Tier")),
                        "xrays": str(p.get("xrays", "Standard Diagnostic")),
                        "office_visits": str(p.get("office_visits", "Covered")),
                        "cb_phys": str(p.get("cb_phys", "Standard In-Network")),
                        "cb_fac": str(p.get("cb_fac", "Standard In-Network")),
                        "lien": str(p.get("lien", "No")),
                        "benefits_url": p.get("benefits_url", ""),
                        "brochure_url": p.get("brochure_url", ""),
                        "formulary_url": p.get("formulary_url", ""),
                        "network_url": p.get("network_url", ""),
                        "providers": p.get("providers", {}),
                        "deeplink_enrollment": p.get("deeplink_enrollment", False)
                    })
            else:
                st.warning(f"⚠️ HealthSherpa One API did not return active plans for ZIP **{zip_db}** ({state_db}). Please verify candidate location details.")

            # ── 2. Estado de Selección de la Propuesta (INICIA COMPLETAMENTE DESELECCIONADO) ──
            sel_plan_ids_key = f"sel_plan_ids_{cand_key}"
            if sel_plan_ids_key not in st.session_state:
                st.session_state[sel_plan_ids_key] = []

            selected_plan_ids = st.session_state[sel_plan_ids_key]

            # ── CSS ESTRICTO: PALETA CORPORATIVA #1C237A & PÍLDORAS COMPACTAS ──
            st.markdown(
                """
                <style>
                /* Badges */
                .badge-tier-catastrophic { background:#FEE2E2; color:#DC2626; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; letter-spacing:0.4px; text-transform:uppercase; }
                .badge-tier-bronze       { background:#FEF3C7; color:#92400E; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; letter-spacing:0.4px; text-transform:uppercase; }
                .badge-tier-silver       { background:#F1F5F9; color:#475569; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; letter-spacing:0.4px; text-transform:uppercase; }
                .badge-tier-gold         { background:#FEF9C3; color:#854D0E; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; letter-spacing:0.4px; text-transform:uppercase; }
                .badge-tier-platinum     { background:#EDE9FE; color:#6D28D9; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; letter-spacing:0.4px; text-transform:uppercase; }
                .badge-network           { background:#F1F5F9; color:#475569; font-weight:700; font-size:0.68rem; padding:3px 10px; border-radius:999px; text-transform:uppercase; }

                /* BOTONES PRIMARIOS: EXACTO AZUL MARINO CORPORATIVO #1C237A */
                button[kind="primary"],
                div[data-testid="stBaseButton-primary"] button {
                    background-color: #1C237A !important;
                    background: #1C237A !important;
                    background-image: none !important;
                    color: #FFFFFF !important;
                    border: 1px solid #1C237A !important;
                    border-radius: 9px !important;
                    font-weight: 700 !important;
                    box-shadow: 0 2px 6px rgba(28, 35, 122, 0.22) !important;
                    transition: all 0.2s ease !important;
                }
                button[kind="primary"]:hover,
                div[data-testid="stBaseButton-primary"] button:hover {
                    background-color: #121752 !important;
                    background: #121752 !important;
                    border-color: #121752 !important;
                    color: #FFFFFF !important;
                }

                /* Compact Metal Tier Pill Buttons matching Image 2 */
                div[data-testid="stHorizontalBlock"]:has(.metal-pill-box) button {
                    padding: 3px 10px !important;
                    min-height: 30px !important;
                    height: 30px !important;
                    font-size: 0.78rem !important;
                    font-weight: 600 !important;
                    border-radius: 999px !important;
                    border: none !important;
                    background: #F1F5F9 !important;
                    color: #475569 !important;
                    margin: 0 !important;
                    box-shadow: none !important;
                    transition: all 0.15s ease !important;
                }
                div[data-testid="stHorizontalBlock"]:has(.metal-pill-box) button:hover {
                    background: #E2E8F0 !important;
                    color: #0F172A !important;
                }
                div[data-testid="stHorizontalBlock"]:has(.metal-pill-box) button[kind="primary"] {
                    background: #0F172A !important;
                    color: #FFFFFF !important;
                    border: none !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            # ── BOX 2: Filter Panel Box (Matching Image 2 Box 2 Exactly) ──
            tier_filter_key = f"tier_filter_{cand_key}"
            if tier_filter_key not in st.session_state:
                st.session_state[tier_filter_key] = []
            active_tiers = st.session_state[tier_filter_key]

            with st.container(border=True):
                st.markdown(
                    """
                    <div style="font-size:0.75rem; font-weight:700; color:#334155; text-transform:uppercase; margin-bottom:6px; letter-spacing:0.3px;">
                        METAL TIERS: <span style="font-weight:400; color:#64748B; text-transform:none;">(Click to multi-select, e.g. Bronze + Silver)</span>
                    </div>
                    <div class="metal-pill-box" style="display:none;"></div>
                    """,
                    unsafe_allow_html=True
                )

                # Row 1: Compact Metal Tiers (Left) and Sort Dropdown (Right)
                col_tiers, col_sort = st.columns([3.8, 1.2])
                with col_tiers:
                    t_cols = st.columns(6)
                    with t_cols[0]:
                        all_active = (len(active_tiers) == 0)
                        if st.button("All Metal Tiers", key=f"btn_tier_all_{cand_key}", type="primary" if all_active else "secondary", use_container_width=True):
                            st.session_state[tier_filter_key] = []
                            st.rerun()
                    tier_names = ["Bronze", "Silver", "Gold", "Platinum", "Catastrophic"]
                    for i_t, t_name in enumerate(tier_names):
                        with t_cols[i_t + 1]:
                            is_t_active = t_name in active_tiers
                            t_label = f"✓ {t_name}" if is_t_active else t_name
                            if st.button(t_label, key=f"btn_t_{t_name}_{cand_key}", type="primary" if is_t_active else "secondary", use_container_width=True):
                                if is_t_active:
                                    active_tiers.remove(t_name)
                                else:
                                    active_tiers.append(t_name)
                                st.session_state[tier_filter_key] = active_tiers
                                st.rerun()

                with col_sort:
                    sort_by = st.selectbox(
                        "⇅ Sort by:",
                        ["Lowest Monthly Premium", "Lowest Deductible", "Lowest OOP Max", "Plan Name"],
                        key=f"f_sort_{cand_key}"
                    )

                # Row 2: Carrier, Network, Search (Matching Image 2)
                f_c1, f_c2, f_c3 = st.columns([1.3, 1.2, 2.5])
                issuers_list = sorted(list(set(p["issuer"] for p in all_available_plans if p.get("issuer"))))
                with f_c1:
                    filt_carrier = st.selectbox("Carrier:", ["All Carriers"] + issuers_list, key=f"f_carrier_{cand_key}")
                with f_c2:
                    filt_network = st.selectbox("Network:", ["All Network Types", "HMO", "EPO", "PPO"], key=f"f_network_{cand_key}")
                with f_c3:
                    search_query = st.text_input("Search plan name or carrier...", placeholder="Search plan name or carrier...", key=f"f_search_{cand_key}")

                # ── Filtrar y Ordenar ──
                filtered_plans = list(all_available_plans)

                if active_tiers:
                    filtered_plans = [
                        p for p in filtered_plans 
                        if any(t.lower() in p.get("metal", "").lower() for t in active_tiers)
                    ]

                selected_carrier = st.session_state.get(f"f_carrier_{cand_key}", filt_carrier)
                if selected_carrier and selected_carrier != "All Carriers":
                    sc_clean = str(selected_carrier).strip().lower()
                    filtered_plans = [
                        p for p in filtered_plans 
                        if sc_clean == str(p.get("issuer", "")).strip().lower()
                    ]

                selected_network = st.session_state.get(f"f_network_{cand_key}", filt_network)
                if selected_network and selected_network != "All Network Types":
                    sn_clean = str(selected_network).strip().upper()
                    filtered_plans = [
                        p for p in filtered_plans 
                        if sn_clean == str(p.get("plan_type", "")).strip().upper()
                    ]

                if search_query and search_query.strip():
                    sq = search_query.strip().lower()
                    filtered_plans = [p for p in filtered_plans if sq in p.get("name", "").lower() or sq in p.get("issuer", "").lower()]

                if "Lowest Monthly Premium" in sort_by or "Lowest Net Premium" in sort_by:
                    filtered_plans.sort(key=lambda x: x.get("prem_val", 0))
                elif sort_by == "Lowest Deductible":
                    filtered_plans.sort(key=lambda x: float(re.sub(r'[^0-9.]', '', str(x.get("ded", 0))) or 0))
                elif sort_by == "Lowest OOP Max":
                    filtered_plans.sort(key=lambda x: float(re.sub(r'[^0-9.]', '', str(x.get("oop", 0))) or 0))
                elif sort_by == "Plan Name":
                    filtered_plans.sort(key=lambda x: x.get("name", ""))

                # Row 3: Proposal Selection Summary matching Image 2
                plan_dict = {p["id"]: p for p in all_available_plans}
                selected_plan_ids = [pid for pid in selected_plan_ids if pid in plan_dict]
                st.session_state[sel_plan_ids_key] = selected_plan_ids
                c_prop_l, c_prop_r = st.columns([3.5, 1.5])
                with c_prop_l:
                    c_sel_btn1, c_sel_btn2 = st.columns([1.4, 1.2])
                    with c_sel_btn1:
                        if st.button(f"Select All Filtered ({min(5, len(filtered_plans))})", key=f"btn_sel_all_{cand_key}"):
                            for p in filtered_plans[:5]:
                                if p["id"] not in selected_plan_ids:
                                    selected_plan_ids.append(p["id"])
                            st.session_state[sel_plan_ids_key] = selected_plan_ids
                            st.rerun()
                    with c_sel_btn2:
                        if len(selected_plan_ids) > 0:
                            if st.button(f"Clear Selection ({len(selected_plan_ids)})", key=f"btn_clear_sel_{cand_key}"):
                                st.session_state[sel_plan_ids_key] = []
                                st.rerun()

                with c_prop_r:
                    st.markdown(
                        f"""
                        <div style="font-size:0.84rem; text-align:right; padding-top:8px;">
                            <span style="color:#64748B;">Showing <b>{len(filtered_plans)}</b> of {len(all_available_plans)} quotes</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

            # ── BOX 3: Galería de Tarjetas en 3 Columnas (Con Borde Unificado Exacto) ──
            if not filtered_plans:
                st.info("No plans match the selected filters. Try changing your Metal Tier or Carrier filter.")

            for chunk_idx in range(0, len(filtered_plans), 3):
                chunk = filtered_plans[chunk_idx:chunk_idx+3]
                cols = st.columns(3)
                for col_i, plan in enumerate(chunk):
                    with cols[col_i]:
                        pid = plan["id"]
                        is_selected = pid in selected_plan_ids
                        m_lower = plan.get("metal", "Bronze").lower()
                        if "catastrophic" in m_lower:
                            tier_badge_class = "badge-tier-catastrophic"
                        elif "silver" in m_lower:
                            tier_badge_class = "badge-tier-silver"
                        elif "gold" in m_lower:
                            tier_badge_class = "badge-tier-gold"
                        elif "plat" in m_lower:
                            tier_badge_class = "badge-tier-platinum"
                        else:
                            tier_badge_class = "badge-tier-bronze"

                        # Card selection border: Blue 2px when selected
                        sel_border = "border: 2px solid #2563EB; box-shadow: 0 4px 16px rgba(37, 99, 235, 0.12);" if is_selected else "border: 1px solid #E2E8F0; box-shadow: 0 2px 6px rgba(0,0,0,0.03);"

                        # Badges & Selection Indicator INSIDE the unified card container
                        sel_indicator = '<span style="background:#EFF6FF; color:#1D4ED8; font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:12px; border:1px solid #BFDBFE;">✓ Selected</span>' if is_selected else ''

                        card_html = f"""<div style="{sel_border} border-radius:14px; padding:16px; background:#FFFFFF; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <div style="display:flex; gap:6px; align-items:center;">
        <span class="{tier_badge_class}">{plan.get("metal", "Bronze")}</span>
        <span class="badge-network">{plan.get("plan_type", "HMO")}</span>
    </div>
    <div>{sel_indicator}</div>
</div>
<div style="font-size:0.75rem; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.3px; margin-bottom:2px;">{plan.get('issuer', 'Carrier')}</div>
<div style="font-size:0.95rem; font-weight:800; color:#0F172A; line-height:1.3; min-height:44px; margin-bottom:12px;">{plan.get('name', 'Health Plan')}</div>
<div style="font-size:0.74rem; color:#64748B; font-weight:600; margin-bottom:4px;">Monthly Premium</div>
<div style="display:flex; justify-content:flex-start; align-items:baseline; margin-bottom:12px; border-bottom:1px solid #F1F5F9; padding-bottom:8px;">
<div style="color:#059669; font-size:1.85rem; font-weight:800; line-height:1; letter-spacing:-0.5px;">${plan.get('prem_val', 0):,.2f} <span style="font-size:0.82rem; font-weight:600; color:#64748B;">/month</span></div>
</div>
<div style="font-size:0.79rem;">
<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px dashed #F1F5F9;">
<span style="color:#64748B;">Individual Medical Deductible</span>
<span style="font-weight:700; color:#0F172A;">{plan.get('ded', '$0')}</span>
</div>
<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px dashed #F1F5F9;">
<span style="color:#64748B;">Out-of-Pocket Maximum</span>
<span style="font-weight:700; color:#0F172A;">{plan.get('oop', '$9,200')}</span>
</div>
<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px dashed #F1F5F9;">
<span style="color:#64748B;">Primary Doctor Visit</span>
<span style="font-weight:700; color:#0F172A;">{plan.get('pcp', '$50 copay')}</span>
</div>
<div style="display:flex; justify-content:space-between; padding:5px 0;">
<span style="color:#64748B;">Generic Rx Copay</span>
<span style="font-weight:700; color:#0F172A;">{plan.get('rx', '$15 copay')}</span>
</div>
</div>
</div>"""
                        st.markdown(card_html, unsafe_allow_html=True)

                        # Single Action Button Row (View Details on left, + Add / Added on right)
                        btn_c1, btn_c2 = st.columns([1, 1])
                        with btn_c1:
                            with st.popover("👁 View Details", use_container_width=True):
                                st.markdown(f"**{plan['name']}**")
                                st.write(f"• **Carrier:** {plan.get('issuer')}")
                                st.write(f"• **Tier & Network:** {plan.get('metal')} ({plan.get('plan_type')})")
                                st.write(f"• **Specialist Copay:** {plan.get('spec', '$90 copay')}")
                                st.write(f"• **Emergency Services:** {plan.get('emergency_room', '$350 copay')}")
                                st.write(f"• **Urgent Care:** {plan.get('urgent_care', '$60 copay')}")
                                st.write(f"• **Ambulance:** {plan.get('ambulance', '$250 copay')}")
                                st.write(f"• **Childbirth Physician:** {plan.get('cb_phys', '30% coinsurance')}")
                                st.write(f"• **Delivery Facility:** {plan.get('cb_fac', '30% coinsurance')}")
                                st.write(f"• **Surrogacy Lien:** {plan.get('lien', 'Yes')}")
                                b_url = plan.get("benefits_url")
                                if b_url:
                                    if ".pdf" in b_url.lower() or "cloudfront" in b_url.lower():
                                        st.markdown(f"[📄 Official Summary of Benefits (SBC PDF)]({b_url})")
                                    else:
                                        st.markdown(f"[🌐 Official Summary of Benefits (Carrier Portal)]({b_url})")
                        with btn_c2:
                            btn_lbl = "✓ Added" if is_selected else "+ Add"
                            btn_type = "secondary" if is_selected else "primary"
                            if st.button(btn_lbl, key=f"btn_add_plan_{cand_key}_{pid}", type=btn_type, use_container_width=True):
                                if is_selected:
                                    selected_plan_ids.remove(pid)
                                else:
                                    if len(selected_plan_ids) < 5:
                                        selected_plan_ids.append(pid)
                                    else:
                                        st.warning("Maximum of 5 plans can be included in the official quote.")
                                st.session_state[sel_plan_ids_key] = selected_plan_ids
                                st.rerun()

                        st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

            # ── Proposal Actions: Review, Lien Customization, Download PDF & Upload to Monday.com ──
            f_plans = [plan_dict[pid] for pid in selected_plan_ids if pid in plan_dict]
            if len(f_plans) > 0:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown("#### 📋 Official Proposal Review & Lien Selection")
                    st.caption("Review your selected plans and set the Surrogacy Lien status (Yes / No) for each plan before generating the official PDF proposal.")

                    pdf_plans_data = []
                    for idx_p, p in enumerate(f_plans):
                        p_id = p.get("id")
                        iss_name = str(p.get("issuer", "")).lower()
                        default_lien = "No" if (state_db == "CA" or "kaiser" in iss_name or "anthem" in iss_name or "blue shield" in iss_name or p.get("lien") == "No") else "Yes"

                        col_lp1, col_lp2, col_lp3 = st.columns([3, 1.5, 1.5])
                        with col_lp1:
                            st.markdown(f"**{p.get('name')}**")
                            st.caption(f"{p.get('issuer')} &bull; {p.get('metal')} ({p.get('plan_type')})", unsafe_allow_html=True)
                        with col_lp2:
                            st.markdown(f"**${p.get('prem_val', 0.0):,.2f}** <span style='font-size:0.8rem; color:#64748B;'>/mo</span>", unsafe_allow_html=True)
                            st.caption(f"Ded: {p.get('ded')} &bull; OOP: {p.get('oop')}", unsafe_allow_html=True)
                        with col_lp3:
                            lien_key = f"sel_lien_{cand_key}_{p_id}"
                            chosen_lien = st.selectbox(
                                "Surrogacy Lien?",
                                options=["No", "Yes"],
                                index=0 if default_lien == "No" else 1,
                                key=lien_key,
                                help="Set 'Yes' or 'No' according to Andrea's review. Covered CA / California plans typically standard is 'No'."
                            )

                        pdf_plans_data.append({
                            "id": p_id,
                            "tier": p.get("name"),
                            "issuer": p.get("issuer"),
                            "metal": p.get("metal"),
                            "premium": float(p.get("prem_val", 0.0)),
                            "deductible": str(p.get("ded", "$0")),
                            "oop_max": str(p.get("oop", "$9,200")),
                            "pcp": str(p.get("pcp", "$50 copay")),
                            "specialist": str(p.get("spec", "$90 copay")),
                            "emergency_room": str(p.get("emergency_room", "$350 copay")),
                            "urgent_care": str(p.get("urgent_care", "$60 copay")),
                            "ambulance": str(p.get("ambulance", "$250 copay")),
                            "labs": str(p.get("labs", "$50 copay")),
                            "xrays": str(p.get("xrays", "40% coinsurance")),
                            "office_visits": str(p.get("office_visits", "No charge")),
                            "cb_phys": str(p.get("cb_phys", "30% coinsurance")),
                            "cb_fac": str(p.get("cb_fac", "30% coinsurance")),
                            "lien": chosen_lien,
                            "benefits_url": p.get("benefits_url", ""),
                            "brochure_url": p.get("brochure_url", ""),
                            "formulary_url": p.get("formulary_url", ""),
                            "network_url": p.get("network_url", "")
                        })
                        if idx_p < len(f_plans) - 1:
                            st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed #E2E8F0;'>", unsafe_allow_html=True)

                    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

                    pdf_buffer = generar_cotizacion_pdf(
                        candidate_name=selected_candidate,
                        agency_name=agency_db,
                        hospital_pref=hospital_pref,
                        obgyn_pref=obgyn_pref,
                        hosp_in_net=hosp_in_net,
                        doc_in_net=doc_in_net,
                        pregnant=pregnant,
                        current_plan=current_plan,
                        plans=pdf_plans_data
                    )
                    pdf_bytes_data = pdf_buffer.getvalue()

                    clean_cand_fn = re.sub(r'[\(\[\{].*?[\)\]\}]', '', selected_candidate).strip()
                    clean_cand_fn = re.sub(r'\s+', '_', clean_cand_fn)
                    file_name = f"Nexxel_Quote_{clean_cand_fn}.pdf"

                    c_down, c_mon = st.columns(2)
                    with c_down:
                        st.download_button(
                            label="📥 Download Official Proposal PDF",
                            data=pdf_bytes_data,
                            file_name=file_name,
                            mime="application/pdf",
                            key="btn_download_pdf",
                            type="primary",
                            use_container_width=True
                        )
                    with c_mon:
                        if st.button("☁ Upload Proposal to monday.com & Mark as 'Quotes Sent'", type="primary", key="btn_upload_monday", use_container_width=True):
                            if not item_id:
                                st.error("This candidate does not have an associated monday.com Item ID.")
                            else:
                                with st.spinner("Uploading proposal to monday.com..."):
                                    ok_up, msg_up = upload_pdf_to_monday(item_id, BytesIO(pdf_bytes_data), file_name)
                                    ok_st = push_status_to_monday(item_id, "Quotes Sent")
                                if ok_up:
                                    st.success("Official proposal PDF uploaded successfully to monday.com (Files column).")
                                    conn = get_db_connection()
                                    conn.cursor().execute("UPDATE chicas_excel SET enrollment_status='Quotes Sent' WHERE nombre_gc=?", (selected_candidate,))
                                    conn.commit()
                                    conn.close()
                                else:
                                    st.error(f"Failed to upload to monday.com: {msg_up}")
                                if ok_st:
                                    st.info("Candidate status updated to 'Quotes Sent' in monday.com.")
            else:
                st.info("💡 Please click '+ Add' on the plan cards above to select up to 5 plans for the official quote proposal.")


            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⬅ Back to 2. Household & Demographics", key=f"btn_back_s2_bottom_{cand_key}", use_container_width=True):
                st.session_state[stage_key] = 2
                st.rerun()

    else:
        st.markdown('<div class="empty-state">Select a candidate to review the profile, edit preferences, and prepare the official quote.</div>', unsafe_allow_html=True)

# ==============================================================================
# 10. MÓDULO CRM (PENDING ENROLLMENTS)
# ==============================================================================
elif menu_option == "📋 Pending Enrollments (CRM)":
    st.title("Pending Enrollments (Andrea's View)")
    st.markdown("Update candidate statuses here. Changes will be instantly synced to monday.com.")
    conn = get_db_connection()
    df_crm = pd.read_sql_query('''
        SELECT monday_item_id, nombre_gc AS Candidate, agencia AS Agency,
               estado AS State, compania_seguros AS Carrier, enrollment_status AS "Enrollment Status"
        FROM chicas_excel ORDER BY id_cliente DESC
    ''', conn)
    conn.close()
    if "df_crm_original" not in st.session_state or st.button("Refresh Data", key="btn_refresh_crm"):
        st.session_state.df_crm_original = df_crm.copy()
    edited_df = st.data_editor(
        st.session_state.df_crm_original,
        column_config={
            "monday_item_id": None,
            "Enrollment Status": st.column_config.SelectboxColumn(
                "Enrollment Status", help="Select the current status to sync with monday",
                options=["Pending", "Quotes Sent", "Do not Enroll", "Pre (Done)", "Done"], required=True,
            )
        },
        disabled=["Candidate", "Agency", "State", "Carrier"],
        use_container_width=True, hide_index=True, key="crm_editor"
    )
    if st.button("🔄 Sync Changes to monday.com", key="btn_sync_changes_crm", type="primary"):
        changes = 0
        for idx, row in edited_df.iterrows():
            orig_status = st.session_state.df_crm_original.loc[idx, "Enrollment Status"]
            new_status  = row["Enrollment Status"]
            item_id     = row["monday_item_id"]
            if orig_status != new_status:
                if not item_id:
                    st.warning(f"Cannot sync {row['Candidate']} - No monday.com ID found")
                    continue
                with st.spinner(f"Updating {row['Candidate']} in monday.com..."):
                    if push_status_to_monday(item_id, new_status):
                        conn = get_db_connection()
                        conn.cursor().execute("UPDATE chicas_excel SET enrollment_status=? WHERE monday_item_id=?", (new_status, item_id))
                        conn.commit()
                        conn.close()
                        changes += 1
                    else:
                        st.error(f"Failed to update {row['Candidate']} in monday.com.")
        if changes > 0:
            st.success(f"Successfully synced {changes} updates to monday.com!")
            st.session_state.df_crm_original = edited_df.copy()
            st.balloons()
        else:
            st.info("No status changes to sync.")

# ==============================================================================
# 11. MÓDULO: ADD NEW CANDIDATE
# ==============================================================================
elif menu_option == "➕ Add New Candidate":
    st.title("Register New Candidate Manually")
    with st.form("form_add_new"):
        name      = st.text_input("Full Name:", placeholder="e.g. Jane Doe")
        agency_in = st.text_input("Agency / Organization:", "General Agency", placeholder="e.g. Los Angeles Surrogacy")
        age_in    = st.number_input("Age:", 18, 65, 25)
        state_in  = st.selectbox("State:", ["CA", "AZ", "FL", "TX", "NV", "IL", "NY"])
        zip_in    = st.text_input("Zip Code:", placeholder="e.g. 90210 or 93721")
        carrier_in= st.text_input("Preferred Carrier:", "Anthem", placeholder="e.g. Anthem, Kaiser, Blue Shield")
        hosp_in   = st.text_input("Preferred Hospital (Optional):", placeholder="e.g. Sharp Mary Birch Hospital")
        doc_in    = st.text_input("Preferred OB-GYN (Optional):", placeholder="e.g. Dr. Ron Lichtenstein")
        if st.form_submit_button("Save Candidate", use_container_width=True) and name and zip_in:
            conn = get_db_connection()
            try:
                conn.cursor().execute('''
                    INSERT INTO chicas_excel (nombre_gc, edad, estado, codigo_postal, compania_seguros, agencia, hospital_preferido, doctor_preferido)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, age_in, state_in, zip_in, carrier_in, agency_in, hosp_in, doc_in))
                conn.commit()
                st.success(f"🎉 Candidate '{name}' registered successfully under '{agency_in}'!")
            except Exception:
                st.error("Candidate already exists.")
            conn.close()

# ==============================================================================
# 12. MÓDULO: QUOTE HISTORY
# ==============================================================================
elif menu_option == "📊 Quote History":
    st.title("Historical Database")
    conn = get_db_connection()
    df_hist = pd.read_sql_query('SELECT nombre_gc AS Candidate, agencia AS Agency, edad AS Age, estado AS State, codigo_postal AS Zip, compania_seguros AS Carrier, enrollment_status AS Status FROM chicas_excel ORDER BY id_cliente DESC', conn)
    conn.close()
    st.dataframe(df_hist, use_container_width=True, hide_index=True)
