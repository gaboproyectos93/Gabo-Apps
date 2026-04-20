import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import fitz  # PyMuPDF
from PIL import Image
import io

def render_app():
    # ==========================================
    # INYECCIÓN DE DISEÑO CORPORATIVO Y TÁCTIL
    # ==========================================
    st.markdown("""
    <style>
        .stApp { background-color: #000000 !important; }
        h1 {
            font-family: 'Minion Pro', 'Times New Roman', Times, serif !important;
            font-weight: 400 !important;
            color: #FFFFFF !important;
            letter-spacing: 1px;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #333333 !important;
            border-radius: 8px !important;
        }
        
        /* BOTONES GLOBALES CELESTES */
        .stButton > button[kind="primary"], [data-testid="stDownloadButton"] > button {
            background-color: #00A2ED !important;
            border-color: #00A2ED !important;
            color: #FFFFFF !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
            padding: 0.75rem 1rem !important;
        }
        .stButton > button[kind="primary"]:hover, [data-testid="stDownloadButton"] > button:hover {
            background-color: #0088C9 !important;
        }
        
        [data-testid="stImage"] {
            overflow-x: auto !important;
            display: block;
        }

        /* =========================================
           BOTONES TÁCTILES INTELIGENTES (PILLS)
           ========================================= */
        div[role="radiogroup"] {
            gap: 12px; /* Separación entre botones */
        }
        
        /* 1. Ocultar el círculo nativo feo */
        div[role="radiogroup"] input[type="radio"] + div {
            display: none !important;
        }

        /* 2. Estilo Base (APAGADO) */
        div[role="radiogroup"] label {
            background-color: #111111 !important;
            border: 2px solid #333333 !important;
            border-radius: 6px !important;
            padding: 12px 24px !important;
            transition: all 0.2s ease;
            cursor: pointer !important;
        }
        div[role="radiogroup"] label p {
            color: #888888 !important; /* Texto gris apagado */
            margin: 0 !important;
        }

        /* 3. Estilo Seleccionado (ENCENDIDO - CELESTE KAUFMANN) */
        div[role="radiogroup"] label:has(input[type="radio"]:checked) {
            background-color: #00A2ED !important;
            border-color: #00A2ED !important;
            box-shadow: 0 0 15px rgba(0, 162, 237, 0.4) !important; /* Resplandor */
        }
        
        /* 4. Texto del botón Encendido */
        div[role="radiogroup"] label:has(input[type="radio"]:checked) p {
            color: #FFFFFF !important; /* Texto blanco puro */
            font-weight: bold !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("🛠️ Pautas de Mantenimiento")
    st.info("Toca las opciones para configurar el vehículo. El teclado ya no será una molestia.")

    SPREADSHEET_ID = "1jqMJ7i_tS-lpOvlAMAtzwj-Wcpk68arrWBaJOtBVUzA"

    # ==========================================
    # 1. CONEXIÓN Y CARGA DE DATOS
    # ==========================================
    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                creds_info = dict(st.secrets["gcp_service_account"])
                if "private_key" in creds_info:
                    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
                return gspread.authorize(creds)
            return None
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            return None

    @st.cache_data(ttl=600)
    def cargar_datos_pautas():
        try:
            client = conectar_google_sheets()
            if client:
                sheet = client.open_by_key(SPREADSHEET_ID).sheet1
                data_list = sheet.get_all_values()
                if data_list:
                    header_idx = 0
                    for i, row in enumerate(data_list):
                        row_upper = [str(c).strip().upper() for c in row]
                        if 'MARCA' in row_upper and 'MODELO' in row_upper:
                            header_idx = i
                            break
                    headers = [str(c).strip().upper() for c in data_list[header_idx]]
                    rows = data_list[header_idx+1:]
                    return pd.DataFrame(rows, columns=headers)
        except:
            pass
        return pd.DataFrame(columns=['MARCA', 'MODELO', 'MOTORIZACIÓN', 'TRANSMISION', 'TRACCION', 'NOMBRE ARCHIVO'])

    df = cargar_datos_pautas()

    # ==========================================
    # 2. CONFIGURACIÓN TÁCTIL EN CASCADA
    # ==========================================
    with st.container(border=True):
        st.markdown("### 🚙 Configuración del Vehículo")
        if df.empty:
            st.warning("Cargando base de datos...")
            return

        st.markdown("**1. Selecciona la Marca**")
        marca_sel = st.radio("Marca", sorted(df['MARCA'].unique()), horizontal=True, label_visibility="collapsed")
        df_f = df[df['MARCA'] == marca_sel]
        st.divider()

        st.markdown("**2. Selecciona el Modelo**")
        modelo_sel = st.radio("Modelo", sorted(df_f['MODELO'].unique()), horizontal=True, label_visibility="collapsed")
        df_f = df_f[df_f['MODELO'] == modelo_sel]
        st.divider()

        st.markdown("**3. Motorización**")
        motor_sel = st.radio("Motorización", sorted(df_f['MOTORIZACIÓN'].unique()), horizontal=True, label_visibility="collapsed")
        df_f = df_f[df_f['MOTORIZACIÓN'] == motor_sel]
        st.divider()

        st.markdown("**4. Transmisión y Tracción**")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("*Transmisión:*")
            trans_sel = st.radio("Transmisión", sorted(df_f['TRANSMISION'].unique()), horizontal=True, label_visibility="collapsed")
        df_f = df_f[df_f['TRANSMISION'] == trans_sel]
        
        with col_t2:
            st.markdown("*Tracción:*")
            tracc_sel = st.radio("Tracción", sorted(df_f['TRACCION'].unique()), horizontal=True, label_visibility="collapsed")
        df_f = df_f[df_f['TRACCION'] == tracc_sel]

    st.markdown("### 🔍 Ajuste de Visualización")
    zoom_nivel = st.slider("Nivel de Zoom (Aumenta para ver detalles pequeños)", 1.0, 4.0, 2.0, step=0.5)
    
    st.divider()

    # ==========================================
    # 3. LÓGICA DE BÚSQUEDA Y RENDERIZADO
    # ==========================================
    def clean(txt):
        return str(txt).strip().replace(" - ", "_").replace(" ", "_").replace("-", "_").replace("/", "_")

    if st.button("🔍 Buscar y Visualizar Pauta", type="primary", use_container_width=True):
        if not df_f.empty:
            nombre_db = str(df_f.iloc[0].get('NOMBRE ARCHIVO', '')).strip()
            nombre_final = nombre_db if nombre_db and nombre_db != "nan" else f"Pauta_{clean(marca_sel)}_{clean(modelo_sel)}_{clean(motor_sel)}_{clean(trans_sel)}_{clean(tracc_sel)}.pdf"
            
            ruta_pdf = os.path.join("Pautas", nombre_final)
            
            if os.path.exists(ruta_pdf):
                with open(ruta_pdf, "rb") as f:
                    pdf_bytes = f.read()
                
                st.success(f"✅ Mostrando: {nombre_final}")

                with st.spinner("Optimizando imagen para el nivel de zoom seleccionado..."):
                    try:
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            mat = fitz.Matrix(zoom_nivel, zoom_nivel)
                            pix = page.get_pixmap(matrix=mat)
                            
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            
                            st.image(img, use_container_width=(zoom_nivel <= 1.5), caption=f"Página {page_num + 1}")
                            st.divider()
                                
                    except Exception as e:
                        st.error(f"Error en el visor: {e}")

                st.download_button(
                    label="📥 Descargar copia PDF",
                    data=pdf_bytes,
                    file_name=nombre_final,
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error(f"⚠️ Archivo no encontrado: `{nombre_final}`")
        else:
            st.error("No hay coincidencias en la base de datos.")

if __name__ == "__main__":
    render_app()
