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

    st.title("🛠️ Pautas de Mantenimiento")
    st.info("Selecciona el modelo y su motorización para obtener la pauta técnica oficial.")

    # ID de la Google Sheet (Asegúrate de que este ID sea el correcto si creaste un archivo nuevo)
    # Si solo cambiaste el nombre del archivo existente, el ID se mantiene igual.
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
                # El sistema busca por ID, así que el nombre del archivo puede cambiar sin afectar
                sheet = client.open_by_key(SPREADSHEET_ID).sheet1
                data = sheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    df.columns = [str(c).strip().upper() for c in df.columns]
                    return df
        except Exception as e:
            st.warning(f"⚠️ Trabajando con datos locales de emergencia. ({e})")
            
        # Mock data actualizado con la nueva columna
        mock_data = {
            'MODELO': ['T60 D20', 'T90', 'DELIVER 9'],
            'MOTORIZACIÓN': ['DIESEL EURO 6', 'DIESEL EURO 6', 'DIESEL EURO 6'],
            'TRANSMISION': ['AT', 'AT', 'MT'],
            'TRACCION': ['4X4', '4X4', 'TRASERA']
        }
        return pd.DataFrame(mock_data)

    df_maxus = cargar_datos_maxus()

    # ==========================================
    # 2. CONFIGURACIÓN DEL VEHÍCULO
    # ==========================================
    st.markdown("### 🚙 Configuración del Vehículo")
    
    # ACTUALIZACIÓN: Ahora buscamos 'MOTORIZACIÓN' en lugar de 'NORMA EMISIONES'
    cols_necesarias = ['MODELO', 'MOTORIZACIÓN', 'TRANSMISION', 'TRACCION']
    faltan = [c for c in cols_necesarias if c not in df_maxus.columns]
    
    if faltan:
        st.error(f"❌ Faltan estas columnas en tu Google Sheet DB_PAUTAS: {', '.join(faltan)}")
        st.info("Revisa que el nombre en el Excel diga exactamente MOTORIZACIÓN (con tilde y en mayúsculas).")
        return

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    # Filtro Modelo
    modelos = sorted(df_maxus['MODELO'].dropna().unique())
    modelo_sel = c1.selectbox("Modelo MAXUS", [str(m) for m in modelos])
    df_mod = df_maxus[df_maxus['MODELO'] == modelo_sel]

    # Filtro Motorización (Nuevo nombre)
    motores = sorted(df_mod['MOTORIZACIÓN'].dropna().unique())
    motor_sel = c2.selectbox("Motorización", [str(m) for m in motores])
    df_mot = df_mod[df_mod['MOTORIZACIÓN'] == motor_sel]

    # Filtro Transmisión
    transmisiones = sorted(df_mot['TRANSMISION'].dropna().unique())
    trans_sel = c3.selectbox("Transmisión", [str(t) for t in transmisiones])
    df_trans = df_mot[df_mot['TRANSMISION'] == trans_sel]

    # Filtro Tracción
    tracciones = sorted(df_trans['TRACCION'].dropna().unique())
    tracc_sel = c4.selectbox("Tracción", [str(tr) for tr in tracciones])


    # ==========================================
    # 3. LÓGICA DE BÚSQUEDA DEL PDF
    # ==========================================
    st.divider()
    
    def clean_str(texto):
        return str(texto).strip().replace(" ", "_").replace("/", "_")
    
    # El nombre del archivo ahora incluirá la motorización (ej: DIESEL_EURO_6 o GASOLINA)
    nombre_archivo_pdf = f"Maxus_{clean_str(modelo_sel)}_{clean_str(motor_sel)}_{clean_str(trans_sel)}_{clean_str(tracc_sel)}.pdf"
    
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
                - **Motorización:** {motor_sel}
                - **Especificación:** {trans_sel} | {tracc_sel}
                """)

            st.download_button(
                label="📥 Descargar Pauta en PDF",
                data=pdf_bytes,
                file_name=nombre_archivo_pdf,
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.error(f"⚠️ Documento no encontrado.")
            st.code(f"El sistema buscó este archivo:\n{nombre_archivo_pdf}", language="text")
            st.info("Asegúrate de que el PDF en la carpeta 'Pautas' tenga exactamente ese nombre.")

if __name__ == "__main__":
    render_app()
