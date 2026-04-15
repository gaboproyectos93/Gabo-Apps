import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def render_app():
    st.title("🛠️ Pautas de Mantenimiento MAXUS")
    st.info("Selecciona el modelo y el kilometraje para obtener la pauta técnica oficial.")

    # ==========================================
    # 1. CONEXIÓN A GOOGLE SHEETS (DB_PAUTAS_MAXUS)
    # ==========================================
    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                return gspread.authorize(creds)
            return None
        except:
            return None

    @st.cache_data(ttl=3600) # Caché de 1 hora para optimizar recursos
    def cargar_modelos_maxus():
        try:
            client = conectar_google_sheets()
            if client:
                # Conecta específicamente a tu nueva base de datos
                sheet = client.open("DB_PAUTAS_MAXUS").sheet1
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
                
                # Busca automáticamente la columna que contenga la palabra "Modelo"
                col_modelo = [col for col in df.columns if 'modelo' in col.lower()]
                
                if col_modelo:
                    modelos = sorted(df[col_modelo[0]].dropna().unique())
                    return [str(m).strip() for m in modelos if str(m).strip() != ""]
                else:
                    # Si no hay columna llamada "Modelo", usa la primera columna por defecto
                    modelos = sorted(df.iloc[:, 0].dropna().unique())
                    return [str(m).strip() for m in modelos if str(m).strip() != ""]
        except Exception as e:
            st.warning("⚠️ Trabajando en modo local (sin conexión a DB_PAUTAS_MAXUS).")
            
        # Fallback de emergencia si falla la conexión a internet
        return ["T60", "T90", "V80", "Deliver 9", "E-Deliver 3"] 

    modelos_disponibles = cargar_modelos_maxus()

    # ==========================================
    # 2. INTERFAZ DE USUARIO (FORMULARIO)
    # ==========================================
    with st.expander("📝 Datos del Servicio", expanded=True):
        col1, col2 = st.columns(2)
        
        # Variables con nombre único para evitar cruces con las otras apps
        tec_nom = col1.text_input("Nombre del Técnico", placeholder="Ej: Juan Pérez", key="tec_maxus")
        cli_nom = col2.text_input("Nombre del Cliente", placeholder="Ej: Transportes X", key="cli_maxus")
        patente = st.text_input("Patente del Vehículo", key="pat_maxus").upper()

    st.markdown("### 🚙 Configuración del Vehículo")
    c1, c2 = st.columns(2)
    
    # La marca es fija, el modelo viene de tu Google Sheet
    modelo_sel = c1.selectbox("Modelo MAXUS", modelos_disponibles)
    
    # Kilometrajes estándar (puedes ajustar esta lista si lo necesitas)
    kms_estandar = ["10.000", "20.000", "30.000", "40.000", "50.000", "60.000", "80.000", "100.000"]
    km_sel = c2.selectbox("Kilometraje de la Mantención", kms_estandar)

    # ==========================================
    # 3. LÓGICA DE BÚSQUEDA DEL ARCHIVO PDF
    # ==========================================
    st.divider()
    
    # Limpiamos el formato para armar el nombre del archivo
    # Ejemplo esperado: pautas/Maxus_T60_20000.pdf
    km_formato = km_sel.replace(".", "")
    modelo_formato = modelo_sel.replace(" ", "_")
    nombre_archivo_pdf = f"Maxus_{modelo_formato}_{km_formato}.pdf"
    
    # Asegúrate de crear una carpeta llamada 'pautas' en tu GitHub y meter los PDFs ahí
    ruta_pdf = os.path.join("pautas", nombre_archivo_pdf)

    if st.button("🔍 Buscar Pauta Técnica", type="primary", use_container_width=True):
        if not tec_nom or not patente:
            st.error("⛔ Por favor, ingresa el nombre del técnico y la patente antes de buscar.")
        else:
            if os.path.exists(ruta_pdf):
                with open(ruta_pdf, "rb") as f:
                    pdf_bytes = f.read()
                
                st.success(f"✅ Pauta encontrada para Maxus {modelo_sel} ({km_sel} KM)")
                
                # Cuadro de resumen profesional para el técnico
                with st.container(border=True):
                    st.markdown(f"""
                    **Resumen de la Tarea Asignada:**
                    - **Técnico Responsable:** {tec_nom.upper()}
                    - **Vehículo:** MAXUS {modelo_sel} | Patente: **{patente}**
                    - **Cliente:** {cli_nom.upper() if cli_nom else 'No especificado'}
                    - **Servicio:** Mantención de Pauta - {km_sel} Kilómetros
                    """)

                st.download_button(
                    label="📥 Descargar Pauta en PDF (Checklist y Repuestos)",
                    data=pdf_bytes,
                    file_name=f"Pauta_Mantenimiento_{patente}_{km_formato}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error(f"⚠️ El archivo `{nombre_archivo_pdf}` no existe en la base de datos.")
                st.info("💡 Asegúrate de que el PDF esté guardado en la carpeta 'pautas' con ese nombre exacto.")

if __name__ == "__main__":
    render_app()
