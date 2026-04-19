import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import fitz  # <-- NUEVA LIBRERÍA: PyMuPDF para leer el PDF
from PIL import Image

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
    st.info("Selecciona los parámetros del vehículo para visualizar o descargar el documento oficial.")

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
    # 2. FILTROS EN CASCADA
    # ==========================================
    st.markdown("### 🚙 Configuración del Vehículo")
    
    if df.empty:
        st.warning("Cargando base de datos...")
        return

    c1, c2 = st.columns(2)
    c3, c4, c5 = st.columns(3)

    marcas = sorted(df['MARCA'].unique())
    marca_sel = c1.selectbox("Marca", marcas)
    df_f = df[df['MARCA'] == marca_sel]

    modelos = sorted(df_f['MODELO'].unique())
    modelo_sel = c2.selectbox("Modelo", modelos)
    df_f = df_f[df_f['MODELO'] == modelo_sel]

    motores = sorted(df_f['MOTORIZACIÓN'].unique())
    motor_sel = c3.selectbox("Motorización", motores)
    df_f = df_f[df_f['MOTORIZACIÓN'] == motor_sel]

    trans = sorted(df_f['TRANSMISION'].unique())
    trans_sel = c4.selectbox("Transmisión", trans)
    df_f = df_f[df_f['TRANSMISION'] == trans_sel]

    trac = sorted(df_f['TRACCION'].unique())
    tracc_sel = c5.selectbox("Tracción", trac)
    df_f = df_f[df_f['TRACCION'] == tracc_sel]

    # ==========================================
    # 3. LÓGICA DE BÚSQUEDA Y VISUALIZACIÓN MÓVIL
    # ==========================================
    st.divider()

    def clean(txt):
        return str(txt).strip().replace(" - ", "_").replace(" ", "_").replace("-", "_").replace("/", "_")

    if st.button("🔍 Buscar Pauta Técnica", type="primary", use_container_width=True):
        if not df_f.empty:
            nombre_db = str(df_f.iloc[0].get('NOMBRE ARCHIVO', '')).strip()
            
            if nombre_db and nombre_db != "" and nombre_db != "nan":
                nombre_final = nombre_db
            else:
                nombre_final = f"Pauta_{clean(marca_sel)}_{clean(modelo_sel)}_{clean(motor_sel)}_{clean(trans_sel)}_{clean(tracc_sel)}.pdf"
            
            ruta_pdf = os.path.join("Pautas", nombre_final)
            
            if os.path.exists(ruta_pdf):
                with open(ruta_pdf, "rb") as f:
                    pdf_bytes = f.read()
                
                st.success(f"✅ Documento encontrado.")
                
                with st.container(border=True):
                    st.markdown(f"""
                    **Detalles del Vehículo:**
                    - **Archivo:** `{nombre_final}`
                    - **Especificación:** {motor_sel} | {trans_sel} | {tracc_sel}
                    """)

                # --- NUEVO: RENDERIZADO DE PDF A IMÁGENES (PARA CELULARES) ---
                st.markdown("### 👁️ Vista Previa del Documento")
                
                with st.spinner("Generando vista previa de alta calidad..."):
                    try:
                        # Abrir el PDF desde los bytes
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        # Generar un contenedor con borde para simular una hoja de papel
                        with st.container(border=True):
                            for page_num in range(len(doc)):
                                page = doc.load_page(page_num)
                                # Aplicamos un zoom 2x para que las letras pequeñas se lean perfecto
                                zoom = 2.0 
                                mat = fitz.Matrix(zoom, zoom)
                                pix = page.get_pixmap(matrix=mat)
                                
                                # Convertir la imagen capturada a un formato que Streamlit entienda
                                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                
                                # Mostrar la imagen en pantalla
                                st.image(img, use_container_width=True, caption=f"Página {page_num + 1} de {len(doc)}")
                                st.divider()
                                
                    except Exception as e:
                        st.error(f"Error al generar la vista previa visual: {e}")
                # -------------------------------------------------------------

                st.download_button(
                    label="📥 Descargar Pauta en PDF",
                    data=pdf_bytes,
                    file_name=nombre_final,
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error(f"⚠️ No se encontró el archivo físico en GitHub.")
                st.info(f"El sistema buscó exactamente este nombre: `{nombre_final}`")
        else:
            st.error("No hay coincidencias en la base de datos.")

if __name__ == "__main__":
    render_app()
