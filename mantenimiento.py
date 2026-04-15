import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def render_app():
    st.title("🛠️ Pautas de Mantenimiento MAXUS")
    st.info("Selecciona el modelo y el kilometraje para obtener la pauta técnica oficial.")

    # ID ÚNICO DEL DOCUMENTO (Sacado de tu link)
    SPREADSHEET_ID = "1jqMJ7i_tS-lpOvlAMAtzwj-Wcpk68arrWBaJOtBVUzA"

    # ==========================================
    # 1. CONEXIÓN A GOOGLE SHEETS
    # ==========================================
    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                # Convertimos el AttrDict de Streamlit a un dict real de Python
                creds_info = dict(st.secrets["gcp_service_account"])
                # Reparamos los saltos de línea de la llave privada por si acaso
                if "private_key" in creds_info:
                    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
                return gspread.authorize(creds)
            return None
        except Exception as e:
            st.error(f"Error técnico de conexión: {e}")
            return None

    @st.cache_data(ttl=600) # 10 minutos de caché
    def cargar_modelos_maxus():
        try:
            client = conectar_google_sheets()
            if client:
                # CONEXIÓN POR ID (Más seguro que por nombre)
                sheet = client.open_by_key(SPREADSHEET_ID).sheet1
                data = sheet.get_all_records()
                if not data:
                    return ["T60", "V80", "Deliver 9"] # Fallback si el sheet está vacío
                
                df = pd.DataFrame(data)
                # Buscamos cualquier columna que se llame 'modelo'
                col_modelo = [col for col in df.columns if 'modelo' in col.lower()]
                
                if col_modelo:
                    modelos = sorted(df[col_modelo[0]].dropna().unique())
                    return [str(m).strip() for m in modelos if str(m).strip() != ""]
                else:
                    # Si no hay columna 'Modelo', tomamos la primera columna
                    modelos = sorted(df.iloc[:, 0].dropna().unique())
                    return [str(m).strip() for m in modelos if str(m).strip() != ""]
        except Exception as e:
            st.warning(f"⚠️ Nota: {e}")
            
        return ["T60", "T90", "V80", "Deliver 9", "G10"] 

    modelos_disponibles = cargar_modelos_maxus()

    # ==========================================
    # 2. INTERFAZ DE USUARIO
    # ==========================================
    with st.expander("📝 Datos del Servicio", expanded=True):
        col1, col2 = st.columns(2)
        tec_nom = col1.text_input("Nombre del Técnico", key="tec_maxus")
        cli_nom = col2.text_input("Nombre del Cliente", key="cli_maxus")
        patente = st.text_input("Patente del Vehículo", key="pat_maxus").upper()

    st.markdown("### 🚙 Configuración del Vehículo")
    c1, c2 = st.columns(2)
    modelo_sel = c1.selectbox("Modelo MAXUS", modelos_disponibles)
    kms_estandar = ["10.000", "20.000", "30.000", "40.000", "50.000", "60.000", "80.000", "100.000"]
    km_sel = c2.selectbox("Kilometraje de la Mantención", kms_estandar)

    # ==========================================
    # 3. LÓGICA DE PDF
    # ==========================================
    st.divider()
    km_formato = km_sel.replace(".", "")
    modelo_formato = modelo_sel.replace(" ", "_")
    nombre_archivo_pdf = f"Maxus_{modelo_formato}_{km_formato}.pdf"
    ruta_pdf = os.path.join("pautas", nombre_archivo_pdf)

    if st.button("🔍 Buscar Pauta Técnica", type="primary", use_container_width=True):
        if not tec_nom or not patente:
            st.error("⛔ Ingresa técnico y patente.")
        else:
            if os.path.exists(ruta_pdf):
                with open(ruta_pdf, "rb") as f:
                    pdf_bytes = f.read()
                
                st.success(f"✅ Pauta cargada: Maxus {modelo_sel}")
                
                with st.container(border=True):
                    st.markdown(f"""
                    **Orden de Trabajo:**
                    - **Técnico:** {tec_nom.upper()}
                    - **Vehículo:** MAXUS {modelo_sel} | **{patente}**
                    - **Kilometraje:** {km_sel} KM
                    """)

                st.download_button(
                    label="📥 Descargar Pauta en PDF",
                    data=pdf_bytes,
                    file_name=f"Pauta_{patente}_{km_formato}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error(f"⚠️ El archivo '{nombre_archivo_pdf}' no está en la carpeta /pautas.")

if __name__ == "__main__":
    render_app()
