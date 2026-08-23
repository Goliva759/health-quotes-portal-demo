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
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import difflib

# Cargar variables de entorno locales si existe archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- 1. BÚSQUEDA DEL LOGO ---
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

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Quotes Preview",
    page_icon=logo_file if logo_file else "📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
        :root {
            --bg: #f4f4f9;
            --panel: #ffffff;
            --primary: #2A0845;
            --primary-soft: #efe7f7;
            --secondary: #6f42c1;
            --success: #2e7d32;
            --warning: #f9a825;
            --text: #1f1f2d;
            --muted: #666b7a;
        }
        .stApp {
            background: linear-gradient(180deg, #f8f7fb 0%, #f2f4f8 100%);
            color: var(--text);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2A0845 0%, #3b1465 100%);
            color: white;
        }
        div[data-testid="stSidebar"] .stButton > button,
        div[data-testid="stSidebar"] .stDownloadButton > button {
            background: rgba(255,255,255,0.12);
            color: white;
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 10px;
        }
        div[data-testid="stSidebar"] .stButton > button:hover,
        div[data-testid="stSidebar"] .stDownloadButton > button:hover {
            background: rgba(255,255,255,0.2);
        }
        .stMetric {
            background: var(--panel);
            border: 1px solid rgba(42,8,69,0.08);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            box-shadow: 0 4px 16px rgba(42, 8, 69, 0.06);
        }
        .section-header {
            background: linear-gradient(90deg, rgba(42,8,69,0.06), rgba(111,66,193,0.08));
            border: 1px solid rgba(42,8,69,0.08);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin-bottom: 1rem;
            font-weight: 700;
            color: var(--primary);
        }
        .info-pill {
            display: inline-block;
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
            background: rgba(111,66,193,0.08);
            color: var(--secondary);
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 0.6rem;
        }
        .status-card {
            background: rgba(46,125,50,0.06);
            border: 1px solid rgba(46,125,50,0.18);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin-top: 0.5rem;
        }
        .empty-state {
            border: 1px dashed rgba(42,8,69,0.25);
            border-radius: 12px;
            padding: 1rem;
            background: rgba(255,255,255,0.5);
            text-align: center;
            color: var(--muted);
        }
        .plan-highlight {
            border: 2px solid rgba(42,8,69,0.25);
            background: rgba(42,8,69,0.02);
            border-radius: 12px;
            padding: 0.6rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 3. GESTIÓN DE SESIÓN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_user" not in st.session_state:
    st.session_state["current_user"] = ""

def make_hash(password):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"nexxel-corp", 200_000).hex()


def verify_password(stored_value, password):
    if not stored_value:
        return False

    if isinstance(stored_value, dict):
        expected_hash = stored_value.get("hash")
        salt = stored_value.get("salt")
        if expected_hash and salt:
            candidate_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                200_000,
            ).hex()
            return candidate_hash == expected_hash
        return False

    if stored_value == make_hash(password):
        return True

    if stored_value == hashlib.sha256(password.encode("utf-8")).hexdigest():
        return True

    return False


def get_secrets_data():
    secrets = {}
    try:
        secrets = dict(st.secrets)
    except (StreamlitSecretNotFoundError, FileNotFoundError, KeyError, TypeError):
        secrets = {}

    # Si st.secrets está vacío, intentar leer secrets.toml directamente del archivo
    if not secrets:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        posibles_rutas = [
            "secrets.toml",
            ".streamlit/secrets.toml",
            os.path.join(base_dir, "secrets.toml"),
            os.path.join(base_dir, ".streamlit", "secrets.toml")
        ]
        for ruta in posibles_rutas:
            if os.path.isfile(ruta):
                try:
                    import tomllib  # Nativo en Python 3.11+
                    with open(ruta, "rb") as f:
                        secrets = tomllib.load(f)
                        break
                except Exception:
                    pass

    # Soporte para variables de entorno de Cloud Run / Secret Manager
    monday_token = os.environ.get("MONDAY_API_TOKEN")
    monday_board = os.environ.get("MONDAY_BOARD_ID")
    if monday_token or monday_board:
        if "monday" not in secrets:
            secrets["monday"] = {}
        if monday_token:
            secrets["monday"]["api_token"] = monday_token
        if monday_board:
            secrets["monday"]["board_id"] = monday_board

    users_env = os.environ.get("APP_USERS_JSON")
    if users_env:
        try:
            parsed_users = json.loads(users_env)
            if "passwords" not in secrets:
                secrets["passwords"] = {}
            secrets["passwords"].update(parsed_users)
        except Exception:
            pass

    # Credenciales de prueba para el repositorio público de portafolio
    if not secrets.get("passwords"):
        secrets["passwords"] = {
            "demo": "85cfffa7f1177f4cf4e8217d1bdfbce2650b111145145550068228926797fdd5"  # password: demo123
        }

    return secrets

SECRETS = get_secrets_data()
USERS = SECRETS.get("passwords", {})

def verify_login():
    u = st.session_state.get("input_user", "").strip().lower()
    p = st.session_state.get("input_pass", "").strip()
    if u in USERS and verify_password(USERS[u], p):
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = u.capitalize()
    else:
        st.error("❌ Invalid username or password.")

# Pantalla de Login con diseño completo y visible
if not st.session_state["authenticated"]:
    st.markdown(
        """
        <style>
            [data-testid="stAppViewContainer"] { background: #fdfcf9; }
            header { visibility: hidden; }
            .login-shell {
                display: flex;
                width: 100vw;
                min-height: 100vh;
                margin-left: calc(50% - 50vw);
                margin-right: calc(50% - 50vw);
                background: #fdfcf9;
            }
            .login-left {
                flex: 1;
                background: linear-gradient(135deg, #1b0f2e 0%, #3b1c5c 100%);
                color: #ffffff;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 4rem;
            }
            .brand-wrap {
                max-width: 560px;
                width: 100%;
            }
            .brand-wrap h1 {
                font-size: 3rem;
                margin-bottom: 0.2rem;
                font-weight: 700;
            }
            .brand-wrap h3 {
                color: #d8b4fe;
                font-weight: 400;
                margin-bottom: 1.5rem;
            }
            .brand-wrap p {
                color: #e2e8f0;
                font-size: 1.1rem;
                line-height: 1.6;
            }
            .brand-wrap ul {
                list-style: none;
                padding: 0;
                margin-top: 2rem;
            }
            .brand-wrap li {
                margin-bottom: 1rem;
                font-size: 1.05rem;
                color: #c4b5fd;
            }
            .login-right {
                flex: 1;
                background: #fdfcf9;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }
            .login-card {
                width: min(420px, 100%);
            }
            .login-card h2 {
                margin-bottom: 0.4rem;
            }
            .login-card p {
                color: #5f6470;
                margin-bottom: 1.5rem;
            }
            @media (max-width: 900px) {
                .login-shell {
                    flex-direction: column;
                }
                .login-left, .login-right {
                    min-height: 45vh;
                    width: 100%;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.05, 1], gap="large")

    with left_col:
        st.markdown(
            """
            <div class="login-left">
                <div class="brand-wrap">
                    <h1>Nexxell Insurance</h1>
                    <h3>Quotes Portal</h3>
                    <p>A centralized and efficient platform for managing medical quotes and operational workflows.</p>
                    <ul>
                        <li>⚡ Fast management of candidates and carriers</li>
                        <li>🔄 Automatic synchronization with monday.com</li>
                        <li>📄 Instant generation of PDF proposals</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        st.markdown("<div class='login-right'><div class='login-card'>", unsafe_allow_html=True)
        if logo_file and os.path.isfile(logo_file):
            st.image(logo_file, width=120)
        st.title("Welcome 👋")
        st.caption("Please enter your credentials to access the panel.")
        st.text_input("Username:", key="input_user")
        st.text_input("Password:", type="password", key="input_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Log In", on_click=verify_login, use_container_width=True, type="primary")
        st.markdown("</div></div>", unsafe_allow_html=True)

    st.stop()

# --- 4. BASE DE DATOS Y MIGRACIÓN (HÍBRIDO POSTGRES / SQLITE) ---
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
            # Reemplazar ? por %s para compatibilidad con PostgreSQL
            sql = sql.replace('?', '%s')
            if params is None:
                return self.raw_cursor.execute(sql)
            return self.raw_cursor.execute(sql, params)
        else:
            if params is None:
                return self.raw_cursor.execute(sql)
            return self.raw_cursor.execute(sql, params)

    def fetchall(self):
        return self.raw_cursor.fetchall()

    def fetchone(self):
        return self.raw_cursor.fetchone()

    def fetchmany(self, size=None):
        return self.raw_cursor.fetchmany(size) if size else self.raw_cursor.fetchmany()

    @property
    def description(self):
        return getattr(self.raw_cursor, "description", None)

    def close(self):
        self.raw_cursor.close()

    def __getattr__(self, name):
        return getattr(self.raw_cursor, name)


class DBWrapper:
    def __init__(self, raw_conn, is_postgres=False):
        self.raw_conn = raw_conn
        self.is_postgres = is_postgres

    def cursor(self):
        return DBCursorWrapper(self.raw_conn.cursor(), self.is_postgres)

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

    def close(self):
        self.raw_conn.close()

    def __getattr__(self, name):
        return getattr(self.raw_conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_db_connection():
    if USE_POSTGRES:
        import psycopg2
        if DATABASE_URL:
            raw_conn = psycopg2.connect(DATABASE_URL)
        else:
            raw_conn = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
        return DBWrapper(raw_conn, is_postgres=True)
    else:
        raw_conn = sqlite3.connect(DB_PATH)
        return DBWrapper(raw_conn, is_postgres=False)


def init_and_migrate_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chicas_excel (
                id_cliente SERIAL PRIMARY KEY,
                nombre_gc TEXT UNIQUE,
                edad INTEGER,
                estado TEXT,
                codigo_postal TEXT,
                compania_seguros TEXT,
                agencia TEXT DEFAULT 'General Agency',
                hospital_preferido TEXT,
                doctor_preferido TEXT,
                monday_item_id TEXT,
                enrollment_status TEXT DEFAULT 'Pending'
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chicas_excel (
                id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_gc TEXT UNIQUE,
                edad INTEGER,
                estado TEXT,
                codigo_postal TEXT,
                compania_seguros TEXT
            )
        ''')
        cursor.execute("PRAGMA table_info(chicas_excel)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "agencia" not in columns:
            cursor.execute("ALTER TABLE chicas_excel ADD COLUMN agencia TEXT DEFAULT 'General Agency'")
        if "hospital_preferido" not in columns:
            cursor.execute("ALTER TABLE chicas_excel ADD COLUMN hospital_preferido TEXT")
        if "doctor_preferido" not in columns:
            cursor.execute("ALTER TABLE chicas_excel ADD COLUMN doctor_preferido TEXT")
        if "monday_item_id" not in columns:
            cursor.execute("ALTER TABLE chicas_excel ADD COLUMN monday_item_id TEXT")
        if "enrollment_status" not in columns:
            cursor.execute("ALTER TABLE chicas_excel ADD COLUMN enrollment_status TEXT DEFAULT 'Pending'")
            
    conn.commit()
    conn.close()

init_and_migrate_db()

# --- 4.1. LIMPIEZA DE AGENCIAS ---
def get_clean_agencies():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT DISTINCT agencia FROM chicas_excel WHERE agencia IS NOT NULL AND agencia != ''", conn)
    conn.close()
    if df.empty: return []
    
    raw_agencies = df['agencia'].str.strip().str.title().unique().tolist()
    unique_agencies = []
    for agency in sorted(raw_agencies):
        matches = difflib.get_close_matches(agency, unique_agencies, n=1, cutoff=0.85)
        if not matches:
            unique_agencies.append(agency)
    return sorted(unique_agencies)

# --- 5. SINCRONIZADOR API MONDAY.COM ---
def push_status_to_monday(item_id, new_status):
    monday_cfg = get_secrets_data().get("monday", {})
    if not monday_cfg:
        return False
    api_token = monday_cfg.get("api_token")
    board_id = monday_cfg.get("board_id")
    if not api_token or not board_id:
        return False

    url = "https://api.monday.com/v2"
    headers = {"Authorization": api_token, "Content-Type": "application/json"}
    
    query = """
    mutation ($itemId: ID!, $boardId: ID!, $columnValues: JSON!) {
      change_multiple_column_values(item_id: $itemId, board_id: $boardId, column_values: $columnValues) {
        id
      }
    }
    """
    variables = {
        "itemId": int(item_id),
        "boardId": int(board_id),
        "columnValues": f'{{"status": {{"label": "{new_status}"}}}}' 
    }
    try:
        res = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
        if res.status_code == 200 and "errors" not in res.json():
            return True
        return False
    except Exception:
        return False

def sync_monday_candidates():
    monday_cfg = get_secrets_data().get("monday", {})
    if not monday_cfg:
        return False, "Monday API credentials not found in secrets.toml"

    api_token = monday_cfg.get("api_token")
    board_id = monday_cfg.get("board_id")
    if not api_token or not board_id:
        return False, "Monday API credentials are incomplete in secrets.toml"

    url = "https://api.monday.com/v2"
    headers = {"Authorization": api_token, "Content-Type": "application/json"}
    
    conn = get_db_connection()
    cursor_db = conn.cursor()
    
    imported_count = 0
    cursor_page = None
    has_more = True
    
    try:
        while has_more:
            cursor_param = f', cursor: "{cursor_page}"' if cursor_page else ''
            query = f'''
            query {{
                boards(ids: {board_id}) {{
                    items_page(limit: 500{cursor_param}) {{
                        cursor
                        items {{
                            id
                            name
                            column_values {{
                                column {{ title }}
                                text
                            }}
                        }}
                    }}
                }}
            }}
            '''
            
            response = requests.post(url, json={'query': query}, headers=headers)
            res_data = response.json()
            
            if "errors" in res_data:
                conn.close()
                return False, f"Monday API Error: {res_data['errors'][0]['message']}"
                
            page_data = res_data["data"]["boards"][0]["items_page"]
            items = page_data["items"]
            cursor_page = page_data.get("cursor")
            
            if not items or not cursor_page:
                has_more = False
                
            for item in items:
                item_id = item["id"]
                name = item["name"]
                values = {cv["column"]["title"].lower(): cv["text"] for cv in item["column_values"] if cv["text"]}
                
                agency = values.get("agency", values.get("agencia", "Unassigned Agency"))
                raw_age = values.get("age") or values.get("edad") or ""
                age = int(raw_age) if str(raw_age).isdigit() else 25
                
                state = values.get("state", values.get("estado", "CA"))
                zip_c = values.get("zip", values.get("zip code", values.get("codigo postal", "90001")))
                carrier = values.get("carrier", values.get("aseguradora", "Anthem"))
                hosp = values.get("preferred hospital", values.get("hospital", None))
                doc = values.get("preferred ob-gyn", values.get("doctor", None))
                enr_status = values.get("enrollment status", values.get("status", "Pending"))
                
                cursor_db.execute('''
                    INSERT INTO chicas_excel (
                        monday_item_id, nombre_gc, edad, estado, codigo_postal, 
                        compania_seguros, agencia, hospital_preferido, doctor_preferido, enrollment_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(nombre_gc) DO UPDATE SET
                        monday_item_id=excluded.monday_item_id,
                        agencia=excluded.agencia,
                        hospital_preferido=excluded.hospital_preferido,
                        doctor_preferido=excluded.doctor_preferido,
                        enrollment_status=excluded.enrollment_status
                ''', (item_id, name, age, state, zip_c, carrier, agency, hosp, doc, enr_status))
                imported_count += 1
                
        conn.commit()
        conn.close()
        return True, f"Successfully synced ALL {imported_count} candidates from monday.com!"
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, str(e)

# --- 6. DIRECTORIO OFICIAL ---
MARKETPLACE_DIRECTORIES = {
    "AL": {"site": "CuidadoDeSalud.gov", "url": "https://www.cuidadodesalud.gov"},
    "CA": {"site": "Covered California", "url": "https://www.coveredca.com/shopandcompare/"},
}

def determinar_red_por_zip(zip_code, state):
    zip_str = str(zip_code).strip()
    if state.upper() == "CA" and (zip_str.startswith("922") or zip_str.startswith("923") or zip_str.startswith("924") or zip_str.startswith("925")):
        return "HMO"
    return "EPO"

# --- 7. GENERADOR PDF DINÁMICO ---
def generate_exact_quote_pdf(candidate_name, hospital_pref, obgyn_pref, hosp_in_net, doc_in_net, pregnant, current_plan, plans):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    style_normal = ParagraphStyle('Norm', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.black)
    style_bold = ParagraphStyle('Bld', parent=style_normal, fontName='Helvetica-Bold')
    style_purple_hdr = ParagraphStyle('PurpHdr', parent=style_normal, fontName='Helvetica-Bold', textColor=colors.white, alignment=1)
    style_purple_sub = ParagraphStyle('PurpSub', parent=style_normal, fontName='Helvetica-Bold', textColor=colors.HexColor('#2A0845'), alignment=1)
    
    story = []
    
    if logo_file and os.path.isfile(logo_file):
        try:
            story.append(Image(logo_file, width=130, height=40))
            story.append(Spacer(1, 8))
        except Exception:
            pass
            
    story.append(Paragraph(f"Hi Brett and Kirsten.<br/><br/>Thanks for sending <b>{candidate_name}'s</b> enrollment form.", style_normal))
    story.append(Spacer(1, 6))
    
    details_lines = []
    if obgyn_pref and obgyn_pref.strip().lower() not in ["none", "n/a", ""]:
        status_txt = "In-Network" if doc_in_net else "Out-of-Network"
        details_lines.append(f"• <b>Preferred OB-GYN:</b> {obgyn_pref} ({status_txt})")
    else:
        details_lines.append("• <b>Preferred OB-GYN:</b> TBC")
        
    if hospital_pref and hospital_pref.strip().lower() not in ["none", "n/a", ""]:
        status_txt = "In-Network" if hosp_in_net else "Out-of-Network"
        details_lines.append(f"• <b>Preferred Hospital:</b> {hospital_pref} ({status_txt})")
    else:
        details_lines.append("• <b>Preferred Hospital:</b> TBC")
    
    details_lines.append(f"• <b>Pregnant?</b> {pregnant or 'TBC'}")
    details_lines.append(f"• <b>Current Health Plan:</b> {current_plan or 'TBC'}")
    
    story.append(Paragraph("<br/>".join(details_lines), style_normal))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Please review our recommendations and quotes below:", style_normal))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>1) Recommendations:</b>", style_normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph("• Please remind the GC not to apply for health insurance during Open Enrollment to avoid potential complications from having multiple plans.", style_normal))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>2) Quotes Preview</b>", style_normal))
    story.append(Spacer(1, 6))
    
    headers_row_1 = [""] + [Paragraph(p["tier"], style_purple_hdr) for p in plans]
    matrix_data = [headers_row_1]
    
    matrix_data.extend([
        [Paragraph("<b>Monthly Premium **</b>", style_bold)] + [Paragraph(f"<b>${p['premium']:.2f}</b>", style_purple_sub) for p in plans],
        [Paragraph("<b>Deductible</b>", style_bold)] + [Paragraph(p['deductible'], style_purple_sub) for p in plans],
        [Paragraph("<b>Max Out of pocket</b>", style_bold)] + [Paragraph(p['oop_max'], style_purple_sub) for p in plans],
        [Paragraph("Primary Care Physician", style_normal)] + [Paragraph(p.get('pcp', '$50 copay'), style_normal) for p in plans],
        [Paragraph("Specialist", style_normal)] + [Paragraph(p.get('specialist', '$90 copay'), style_normal) for p in plans],
        [Paragraph("Labs", style_normal)] + [Paragraph(p.get('labs', '$50 copay'), style_normal) for p in plans],
        [Paragraph("X-Rays", style_normal)] + [Paragraph(p.get('xrays', '40% coinsurance'), style_normal) for p in plans],
        [Paragraph("Office Visits", style_normal)] + [Paragraph("No charge", style_normal) for _ in plans],
        [Paragraph("Childbirth/ Physician Services", style_normal)] + [Paragraph(p.get('cb_phys', '30% coinsurance'), style_normal) for p in plans],
        [Paragraph("Childbirth/ Delivery Facility", style_normal)] + [Paragraph(p.get('cb_fac', '30% coinsurance'), style_normal) for p in plans],
        [Paragraph("<b>Lien for surrogacy?</b>", ParagraphStyle('Wht', parent=style_bold, textColor=colors.white))] + [Paragraph("No", ParagraphStyle('WhtC', parent=style_normal, textColor=colors.white, alignment=1)) for _ in plans]
    ])
    
    col_w = [150] + [int(400 / len(plans))] * len(plans)
    t_quote = Table(matrix_data, colWidths=col_w)
    t_quote.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (-1,0), colors.HexColor('#2A0845')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#2A0845')),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#B8A9C9')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    story.append(t_quote)
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>3) Please confirm the following:</b>", style_normal))
    story.append(Spacer(1, 4))
    
    confirmations = (
        "▶ <b>Preferred health plan:</b><br/>"
        "▶ <b>Coverage Start Date:</b> The deadline to enroll is.<br/>"
        "▶ <b>Initial Premium (the initial premium is required to enroll. Please provide a US credit/debit card, checking/savings account):</b><br/>"
        "▶ <b>Monthly Payments (please confirm if you would like to use the same payment method to set up automatic monthly payments):</b>"
    )
    story.append(Paragraph(confirmations, style_normal))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("<b><u>IMPORTANT</u></b>", ParagraphStyle('Imp', parent=style_normal, fontName='Helvetica-Bold', fontSize=8)))
    story.append(Spacer(1, 4))
    
    disc_1 = "<b>In-Network Providers:</b> The information provided is based on data from different websites (Insurance Companies, Health Insurance Marketplace websites, etc.). This information may not be up-to-date. Please get in touch with your doctor and hospital to ensure they accept these plans."
    disc_2 = "<b>Monthly Premium Amounts:</b> The quoted amounts are estimates. The final premium amount will be confirmed after the application is completed."
    p_disc_style = ParagraphStyle('Disc', parent=style_normal, fontSize=6.5, leading=8.5, textColor=colors.HexColor('#444444'))
    story.append(Paragraph(disc_1, p_disc_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(disc_2, p_disc_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- 8. BARRA LATERAL ---
if logo_file and os.path.isfile(logo_file):
    st.sidebar.image(logo_file, use_container_width=True)

st.sidebar.markdown("<div class='info-pill'>Welcome</div>", unsafe_allow_html=True)
st.sidebar.write(f"**{st.session_state['current_user'] or 'User'}**")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sync with monday.com", use_container_width=True):
    with st.spinner("Connecting to monday.com..."):
        success, msg = sync_monday_candidates()
        if success:
            st.sidebar.success(msg)
            time.sleep(1)
            st.rerun()
        else:
            st.sidebar.error(msg)

if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = ""
    st.session_state["input_user"] = ""
    st.session_state["input_pass"] = ""
    st.rerun()

st.sidebar.markdown("---")
menu_option = st.sidebar.radio("Navigation Menu", [
    "🔍 Search & Quote Candidate", 
    "📋 Pending Enrollments (CRM)", 
    "➕ Add New Candidate", 
    "📊 Quote History"
])

# --- 9. MÓDULO PRINCIPAL ---
if menu_option == "🔍 Search & Quote Candidate":
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
    hosp_in_net = False
    doc_in_net = False
    pregnant = "No"
    current_plan = "None"
    final_plans = []
    id_c = None

    if "last_selected_cand" not in st.session_state:
        st.session_state["last_selected_cand"] = ""

    if selected_candidate != st.session_state["last_selected_cand"]:
        for k in list(st.session_state.keys()):
            if k.startswith("p_") or k.startswith("chk_") or k.startswith("net_") or k.startswith("hosp_") or k.startswith("doc_") or k.startswith("plans_") or k.startswith("num_plans_"):
                del st.session_state[k]
        st.session_state["last_selected_cand"] = selected_candidate

    if selected_candidate:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, edad, estado, codigo_postal, compania_seguros, hospital_preferido, doctor_preferido, agencia FROM chicas_excel WHERE nombre_gc = ?", (selected_candidate,))
        row = cursor.fetchone()
        conn.close()

        if row:
            id_c, age, state, zip_c, carrier, hosp_db, doc_db, agency_db = row
            auto_network = determinar_red_por_zip(zip_c, state)
            market_info = MARKETPLACE_DIRECTORIES.get(state.upper(), {"site": "CuidadoDeSalud.gov", "url": "https://www.cuidadodesalud.gov"})

            st.markdown("<div class='section-header'>Candidate Overview</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Age", f"{age} yrs")
            c2.metric("State / Zip", f"{state} ({zip_c})")
            c3.metric("Agency", agency_db or "General Agency")
            c4.metric("Preferred Carrier", carrier or "Anthem")

            st.markdown(f"🔗 **[Open Portal ({market_info['site']})]({market_info['url']})**", unsafe_allow_html=True)
            st.markdown("<div class='status-card'>Ready to review and build the official proposal for this candidate.</div>", unsafe_allow_html=True)

            candidate_profile, quote_builder = st.tabs(["Candidate Profile", "Quote Builder"])

            with candidate_profile:
                col_pref1, col_pref2 = st.columns(2)
                val_hosp = hosp_db if (hosp_db and hosp_db.strip().lower() not in ["none", "n/a", ""]) else "None"
                val_doc = doc_db if (doc_db and doc_db.strip().lower() not in ["none", "n/a", ""]) else "None"

                with col_pref1:
                    hospital_pref = st.text_input("Preferred Hospital:", value=val_hosp, key=f"hosp_{selected_candidate}")
                    obgyn_pref = st.text_input("Preferred OB-GYN:", value=val_doc, key=f"doc_{selected_candidate}")

                    st.markdown("#### 🏥 Provider Network Status Verification")
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        if hospital_pref and hospital_pref.strip().lower() not in ["none", "n/a", ""]:
                            hosp_in_net = st.checkbox("✅ Hospital In-Network", value=True, key=f"chk_hosp_{selected_candidate}")
                        else:
                            hosp_in_net = False
                    with col_v2:
                        if obgyn_pref and obgyn_pref.strip().lower() not in ["none", "n/a", ""]:
                            doc_in_net = st.checkbox("✅ OB-GYN In-Network", value=True, key=f"chk_doc_{selected_candidate}")
                        else:
                            doc_in_net = False

                with col_pref2:
                    pregnant = st.selectbox("Pregnant?", ["No", "Yes"], key=f"preg_{selected_candidate}")
                    current_plan = st.text_input("Current Health Plan:", "None", key=f"plan_{selected_candidate}")
                    network_options = ["HMO", "EPO", "PPO", "D EPO"]
                    default_idx = network_options.index(auto_network) if auto_network in network_options else 0
                    network_type = st.selectbox(f"Network Type ({market_info['site']} Market):", network_options, index=default_idx, key=f"net_{selected_candidate}")

            with quote_builder:
                st.markdown("### 💰 Monthly Premium")

                num_plans_key = f"num_plans_{selected_candidate}"
                if num_plans_key not in st.session_state:
                    st.session_state[num_plans_key] = 4

                if f"plans_{selected_candidate}" not in st.session_state:
                    st.session_state[f"plans_{selected_candidate}"] = [
                        {"tier": "Anthem Bronze 60 D EPO", "premium": 0.00, "deductible": "$5,800", "oop": "$9,800"},
                        {"tier": "Anthem Silver 70 D EPO", "premium": 0.00, "deductible": "$5,200", "oop": "$9,800"},
                        {"tier": "Anthem Gold 80 D EPO", "premium": 0.00, "deductible": "$0", "oop": "$9,200"},
                        {"tier": "Anthem Platinum 90 D EPO", "premium": 0.00, "deductible": "$0", "oop": "$5,000"}
                    ]

                col_btn_add, col_btn_rem = st.columns([1, 1])
                with col_btn_add:
                    if st.button("➕ Add Plan Column"):
                        st.session_state[num_plans_key] += 1
                        st.session_state[f"plans_{selected_candidate}"].append({"tier": f"{carrier} Custom Plan EPO", "premium": 0.00, "deductible": "$0", "oop": "$5,000"})
                        st.rerun()
                with col_btn_rem:
                    if st.session_state[num_plans_key] > 1 and st.button("➖ Remove Last Plan Column"):
                        st.session_state[num_plans_key] -= 1
                        st.session_state[f"plans_{selected_candidate}"].pop()
                        st.rerun()

                active_plans = st.session_state[f"plans_{selected_candidate}"][:st.session_state[num_plans_key]]
                cols = st.columns(len(active_plans))
                final_plans = []

                for idx, p in enumerate(active_plans):
                    with cols[idx]:
                        custom_tier = st.text_input(f"Plan {idx+1} Name:", value=p['tier'], key=f"tier_name_{selected_candidate}_{idx}")
                        new_prem = st.number_input(f"Premium ($):", value=float(p['premium']), format="%.2f", key=f"prem_{selected_candidate}_{idx}")
                        final_plans.append({
                            "tier": custom_tier, "premium": new_prem, "deductible": p['deductible'], "oop_max": p['oop'],
                            "pcp": "$50 copay", "specialist": "$90 copay", "labs": "$50 copay", "xrays": "40% coinsurance",
                            "cb_phys": "30% coinsurance", "cb_fac": "30% coinsurance", "surrogacy": "No"
                        })

                st.markdown("### Quotes Preview")
                df_display = pd.DataFrame(final_plans)[["tier", "premium", "deductible", "oop_max"]]
                df_display.columns = ["Plan Tier", "Monthly Premium ($)", "Deductible", "Max OOP"]
                if not df_display.empty:
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    best_plan = df_display.sort_values("Monthly Premium ($)").iloc[0]
                    st.markdown(
                        f"<div class='plan-highlight'><strong>Best value option:</strong> {best_plan['Plan Tier']} — ${best_plan['Monthly Premium ($)']:.2f}/mo</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown("<div class='empty-state'>No plan data available yet. Add a plan to begin the quote.</div>", unsafe_allow_html=True)

                st.markdown("---")
                with st.form("official_quote_form"):
                    submitted = st.form_submit_button("🚀 Generate Official Proposal PDF", use_container_width=True, type="primary")
                    if submitted and not final_plans:
                        st.warning("Please create at least one plan before generating a quote.")

                if submitted and final_plans:
                    with st.spinner("Building official matrix PDF quote..."):
                        time.sleep(1)
                        pdf_data = generate_exact_quote_pdf(selected_candidate, hospital_pref, obgyn_pref, hosp_in_net, doc_in_net, pregnant, current_plan, final_plans)

                    st.success("✅ Official PDF quote successfully generated!")
                    st.download_button(
                        label="📄 Download Official Quote PDF",
                        data=pdf_data,
                        file_name=f"Quote_{selected_candidate.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT monday_item_id FROM chicas_excel WHERE nombre_gc = ?", (selected_candidate,))
                        item_id_row = cursor.fetchone()

                        if item_id_row and item_id_row[0]:
                            item_id = item_id_row[0]
                            if push_status_to_monday(item_id, "Quotes Sent"):
                                cursor.execute("UPDATE chicas_excel SET enrollment_status = 'Quotes Sent' WHERE id_cliente = ?", (id_c,))
                                conn.commit()
                                st.info("🔄 Status automatically updated to 'Quotes Sent' in CRM and monday.com!")
                        conn.close()
                    except Exception:
                        pass

    else:
        st.markdown(
            """
            <div class='empty-state'>
                Select a candidate to review the profile, edit preferences, and prepare the official quote.
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- 10. NUEVO MÓDULO CRM ---
elif menu_option == "📋 Pending Enrollments (CRM)":
    st.title("Pending Enrollments (Andrea's View)")
    st.markdown("Update candidate statuses here. Changes will be instantly synced to monday.com.")
    
    conn = get_db_connection()
    df_crm = pd.read_sql_query('''
        SELECT monday_item_id, nombre_gc AS Candidate, agencia AS Agency, 
               estado AS State, compania_seguros AS Carrier, enrollment_status AS "Enrollment Status" 
        FROM chicas_excel 
        ORDER BY id_cliente DESC
    ''', conn)
    conn.close()

    if "df_crm_original" not in st.session_state or st.button("Refresh Data"):
        st.session_state.df_crm_original = df_crm.copy()

    edited_df = st.data_editor(
        st.session_state.df_crm_original,
        column_config={
            "monday_item_id": None,
            "Enrollment Status": st.column_config.SelectboxColumn(
                "Enrollment Status",
                help="Select the current status to sync with monday",
                options=["Pending", "Quotes Sent", "Do not Enroll", "Pre (Done)", "Done"],
                required=True,
            )
        },
        disabled=["Candidate", "Agency", "State", "Carrier"],
        use_container_width=True,
        hide_index=True,
        key="crm_editor"
    )

    if st.button("🔄 Sync Changes to monday.com", type="primary"):
        changes = 0
        for idx, row in edited_df.iterrows():
            orig_status = st.session_state.df_crm_original.loc[idx, "Enrollment Status"]
            new_status = row["Enrollment Status"]
            item_id = row["monday_item_id"]
            
            if orig_status != new_status:
                if not item_id:
                    st.warning(f"Cannot sync {row['Candidate']} - No monday.com ID found (Was this candidate added manually without sync?)")
                    continue
                    
                with st.spinner(f"Updating {row['Candidate']} in monday.com..."):
                    if push_status_to_monday(item_id, new_status):
                        conn = get_db_connection()
                        conn.cursor().execute("UPDATE chicas_excel SET enrollment_status = ? WHERE monday_item_id = ?", (new_status, item_id))
                        conn.commit()
                        conn.close()
                        changes += 1
                    else:
                        st.error(f"Failed to update {row['Candidate']} in monday.com. Ensure the status column name matches.")
        
        if changes > 0:
            st.success(f"Successfully synced {changes} updates to monday.com!")
            st.session_state.df_crm_original = edited_df.copy()
            st.balloons()
        elif changes == 0:
            st.info("No status changes to sync.")

elif menu_option == "➕ Add New Candidate":
    st.title("Register New Candidate Manually")
    with st.form("form_add_new"):
        name = st.text_input("Full Name:")
        agency_in = st.text_input("Agency / Organization:", "General Agency")
        age_in = st.number_input("Age:", 18, 65, 25)
        state_in = st.selectbox("State:", ["CA", "AZ", "FL", "TX", "NV", "IL", "NY"])
        zip_in = st.text_input("Zip Code:")
        carrier_in = st.text_input("Preferred Carrier:", "Anthem")
        hosp_in = st.text_input("Preferred Hospital (Optional):")
        doc_in = st.text_input("Preferred OB-GYN (Optional):")
        
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

elif menu_option == "📊 Quote History":
    st.title("Historical Database")
    conn = get_db_connection()
    df_hist = pd.read_sql_query('SELECT nombre_gc AS Candidate, agencia AS Agency, edad AS Age, estado AS State, codigo_postal AS Zip, compania_seguros AS Carrier, enrollment_status AS Status FROM chicas_excel', conn)
    conn.close()
    st.dataframe(df_hist, use_container_width=True, hide_index=True)