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

    st.title("🛠️ Pautas de Mantenimiento MAXUS")
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

    @st.cache_data(ttl=600) # 10 minutos de caché
    def cargar_datos_maxus():
        try:
            client = conectar_google_sheets()
            if client:
                sheet = client.open_by_key(SPREADSHEET_ID).sheet1
                data = sheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    # Estandarizamos los nombres de las columnas a mayúsculas sin espacios extra
                    df.columns = [str(c).strip().upper() for c in df.columns]
                    return df
        except Exception as e:
            st.warning(f"⚠️ Trabajando con datos locales de emergencia. ({e})")
            
        # Fallback de emergencia por si se cae internet
        mock_data = {
            'MODELO': ['T60 D20', 'T90', 'DELIVER 9'],
            'NORMA EMISIONES': ['EURO 6', 'EURO 6', 'EURO 6'],
            'TRANSMISION': ['AT', 'AT', 'MT'],
            'TRACCION': ['4X4', '4X4', 'TRASERA']
        }
        return pd.DataFrame(mock_data)

    df_maxus = cargar_datos_maxus()

    # ==========================================
    # 2. CONFIGURACIÓN DEL VEHÍCULO (FILTROS EN CASCADA)
    # ==========================================
    st.markdown("### 🚙 Configuración del Vehículo")
    
    # Verificamos que las columnas necesarias existan en el Excel
    cols_necesarias = ['MODELO', 'MOTORIZACION', 'TRANSMISION', 'TRACCION']
    faltan = [c for c in cols_necesarias if c not in df_maxus.columns]
    
    if faltan:
        st.error(f"❌ Faltan estas columnas exactas en tu Google Sheet: {', '.join(faltan)}")
        return

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    # Nivel 1: Seleccionar Modelo
    modelos = sorted(df_maxus['MODELO'].dropna().unique())
    modelo_sel = c1.selectbox("Modelo MAXUS", [str(m) for m in modelos])

    # Filtramos el DF según el modelo elegido
    df_mod = df_maxus[df_maxus['MODELO'] == modelo_sel]

    # Nivel 2: Norma Emisiones
    normas = sorted(df_mod['NORMA EMISIONES'].dropna().unique())
    norma_sel = c2.selectbox("Norma Emisiones", [str(n) for n in normas])

    # Filtramos el DF según modelo y norma
    df_norm = df_mod[df_mod['NORMA EMISIONES'] == norma_sel]

    # Nivel 3: Transmisión
    transmisiones = sorted(df_norm['TRANSMISION'].dropna().unique())
    trans_sel = c3.selectbox("Transmisión", [str(t) for t in transmisiones])

    # Filtramos el DF según modelo, norma y transmisión
    df_trans = df_norm[df_norm['TRANSMISION'] == trans_sel]

    # Nivel 4: Tracción
    tracciones = sorted(df_trans['TRACCION'].dropna().unique())
    tracc_sel = c4.selectbox("Tracción", [str(tr) for tr in tracciones])


    # ==========================================
    # 3. LÓGICA DE BÚSQUEDA DEL ARCHIVO PDF
    # ==========================================
    st.divider()
    
    # Formateo seguro para nombres de archivo (reemplaza espacios por guion bajo)
    def clean_str(texto):
        return str(texto).strip().replace(" ", "_").replace("/", "_")
    
    # Estructura del nombre de archivo SIN kilometraje
    nombre_archivo_pdf = f"Maxus_{clean_str(modelo_sel)}_{clean_str(norma_sel)}_{clean_str(trans_sel)}_{clean_str(tracc_sel)}.pdf"
    
    ruta_pdf = os.path.join("Pautas", nombre_archivo_pdf)

    if st.button("🔍 Buscar Pauta Técnica", type="primary", use_container_width=True):
        if os.path.exists(ruta_pdf):
            with open(ruta_pdf, "rb") as f:
                pdf_bytes = f.read()
            
            st.success(f"✅ Documento encontrado exitosamente.")
            
            with st.container(border=True):
                st.markdown(f"""
                **📋 Pauta de Mantenimiento Integral:**
                - **Vehículo:** MAXUS {modelo_sel}
                - **Especificación:** {norma_sel} | {trans_sel} | {tracc_sel}
                - **Formato:** Documento completo (Todos los kilometrajes)
                """)

            st.download_button(
                label="📥 Descargar Pauta en PDF",
                data=pdf_bytes,
                file_name=nombre_archivo_pdf,
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.error(f"⚠️ Documento no encontrado en la base de datos.")
            st.code(f"El sistema buscó exactamente este archivo:\n{nombre_archivo_pdf}", language="text")
            st.info("Asegúrate de que el archivo exista en la carpeta 'Pautas' en GitHub y tenga este nombre exacto.")

if __name__ == "__main__":
    render_app()
