import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def render_app():
    # ==========================================
    # INYECCIÓN DE DISEÑO CORPORATIVO (KAUFMANN)
    # ==========================================
    st.markdown("""
    <style>
        /* Fondo negro absoluto para toda la aplicación */
        .stApp { background-color: #000000 !important; }
        
        /* Título principal en Minion Pro Regular */
        h1 {
            font-family: 'Minion Pro', 'Times New Roman', Times, serif !important;
            font-weight: 400 !important;
            color: #FFFFFF !important;
            letter-spacing: 1px;
        }
        
        /* Ajuste de bordes para cajas */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #333333 !important;
            border-radius: 8px !important;
        }
        
        /* BOTONES KAUFMANN (CELESTE) */
        /* Estilo para los botones principales y el de descarga */
        .stButton > button[kind="primary"], [data-testid="stDownloadButton"] > button {
            background-color: #00A2ED !important;
            border-color: #00A2ED !important;
            color: #FFFFFF !important;
            border-radius: 2px !important;
            font-weight: 600 !important;
        }
        .stButton > button[kind="primary"]:hover, [data-testid="stDownloadButton"] > button:hover {
            background-color: #0088C9 !important;
            border-color: #0088C9 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("🛠️ Pautas de Mantenimiento Kaufmann")
    st.info("Selecciona el modelo y sus especificaciones para obtener la pauta técnica oficial.")

    SPREADSHEET_ID = "1jqMJ7i_tS-lpOvlAMAtzwj-Wcpk68arrWBaJOtBVUzA"

    # ==========================================
    # 1. CONEXIÓN Y CARGA DE DATOS EN CASCADA
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
            st.error(f"Error técnico de conexión: {e}")
            return None

    @st.cache_data(ttl=600)
    def cargar_datos_maxus():
        try:
            client = conectar_google_sheets()
            if client:
                sheet = client.open_by_key(SPREADSHEET_ID).sheet1
                data = sheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    df.columns = [str(c).strip().upper() for c in df.columns]
                    return df
        except Exception as e:
            st.warning(f"⚠️ Trabajando con datos locales de emergencia. ({e})")
            
        mock_data = {
            'MODELO': ['T60 D20', 'T90', 'DELIVER 9'],
            'NORMA EMISIONES': ['EURO 6', 'EURO 6', 'EURO 6'],
            'TRANSMISION': ['AT', 'AT', 'MT'],
            'TRACCION': ['4X4', '4X4', 'TRASERA']
        }
        return pd.DataFrame(mock_data)

    df_maxus = cargar_datos_maxus()

    # ==========================================
    # 2. FORMULARIO DE IDENTIFICACIÓN
    # ==========================================
    with st.expander("📝 Datos del Servicio", expanded=True):
        col1, col2 = st.columns(2)
        tec_nom = col1.text_input("Nombre del Técnico", key="tec_maxus")
        cli_nom = col2.text_input("Nombre del Cliente", key="cli_maxus")
        patente = st.text_input("Patente del Vehículo", key="pat_maxus").upper()

    # ==========================================
    # 3. CONFIGURACIÓN DEL VEHÍCULO
    # ==========================================
    st.markdown("### 🚙 Configuración del Vehículo")
    
    cols_necesarias = ['MODELO', 'NORMA EMISIONES', 'TRANSMISION', 'TRACCION']
    faltan = [c for c in cols_necesarias if c not in df_maxus.columns]
    
    if faltan:
        st.error(f"❌ Faltan estas columnas exactas en tu Google Sheet: {', '.join(faltan)}")
        return

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    modelos = sorted(df_maxus['MODELO'].dropna().unique())
    modelo_sel = c1.selectbox("Modelo Vehículo", [str(m) for m in modelos])

    df_mod = df_maxus[df_maxus['MODELO'] == modelo_sel]
    normas = sorted(df_mod['NORMA EMISIONES'].dropna().unique())
    norma_sel = c2.selectbox("Norma Emisiones", [str(n) for n in normas])

    df_norm = df_mod[df_mod['NORMA EMISIONES'] == norma_sel]
    transmisiones = sorted(df_norm['TRANSMISION'].dropna().unique())
    trans_sel = c3.selectbox("Transmisión", [str(t) for t in transmisiones])

    df_trans = df_norm[df_norm['TRANSMISION'] == trans_sel]
    tracciones = sorted(df_trans['TRACCION'].dropna().unique())
    tracc_sel = c4.selectbox("Tracción", [str(tr) for tr in tracciones])

    st.markdown("### ⚙️ Kilometraje")
    kms_estandar = ["10.000", "20.000", "30.000", "40.000", "50.000", "60.000", "80.000", "100.000"]
    km_sel = st.selectbox("Seleccione KM de Mantención", kms_estandar)

    # ==========================================
    # 4. LÓGICA DE BÚSQUEDA
    # ==========================================
    st.divider()
    
    def clean_str(texto):
        return str(texto).strip().replace(" ", "_").replace("/", "_")

    km_formato = km_sel.replace(".", "")
    nombre_archivo_pdf = f"Maxus_{clean_str(modelo_sel)}_{clean_str(norma_sel)}_{clean_str(trans_sel)}_{clean_str(tracc_sel)}_{km_formato}.pdf"
    ruta_pdf = os.path.join("Pautas", nombre_archivo_pdf)

    if st.button("🔍 Buscar Pauta Técnica", type="primary", use_container_width=True):
        if not tec_nom or not patente:
            st.error("⛔ Ingresa el nombre del técnico y la patente para continuar.")
        else:
            if os.path.exists(ruta_pdf):
                with open(ruta_pdf, "rb") as f:
                    pdf_bytes = f.read()
                
                st.success(f"✅ Pauta cargada exitosamente.")
                
                with st.container(border=True):
                    st.markdown(f"""
                    **📋 Orden de Trabajo Generada:**
                    - **Técnico Asignado:** {tec_nom.upper()}
                    - **Vehículo:** {modelo_sel} ({norma_sel} | {trans_sel} | {tracc_sel})
                    - **Patente:** **{patente}**
                    - **Mantención:** {km_sel} KM
                    """)

                st.download_button(
                    label="📥 Descargar Pauta en PDF",
                    data=pdf_bytes,
                    file_name=f"Pauta_{patente}_{km_formato}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error(f"⚠️ Archivo no encontrado en la base de datos.")
                st.code(f"El sistema buscó exactamente este archivo:\n{nombre_archivo_pdf}", language="text")

if __name__ == "__main__":
    render_app()
