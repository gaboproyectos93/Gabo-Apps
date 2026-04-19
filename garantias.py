import streamlit as st
from PIL import Image, ImageOps
from datetime import datetime
import os
import io
import zipfile
import smtplib
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DRIVE ---
ID_CARPETA_DRIVE = "1rymOQYirK8xljHHzn0bcn5HUOwYE-Tg7"

def render_app():
    st.title("Plataforma de garantías Kaufmann")
    st.info("Sube las fotografías y videos de respaldo directamente desde tu galería. Todo en un solo paso.")

    # ==========================================
    # 1. IDENTIFICACIÓN
    # ==========================================
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        ot = col1.text_input("Número de OT", placeholder="Ej: 85432", key="garantia_ot").upper()
        cliente = col2.text_input("Nombre del Cliente", placeholder="Ej: Transportes X", key="garantia_cli").upper()
        tecnico = col3.text_input("Técnico", placeholder="Ej: Pedro", key="garantia_tec")

    # ==========================================
    # 2. CHECKLIST Y VISTA PREVIA (CON GIRO)
    # ==========================================
    st.markdown("### 📋 Evidencia Fotográfica (Obligatoria)")
    
    requisitos = {
        "placa_vin": "1_Placa_VIN",
        "tablero": "2_Tablero_Odometro",
        "libro": "3_Libro_Mantencion",
        "diagnostico": "4_Equipo_Diagnostico",
        "vehiculo": "5_Fotografia_Vehiculo",
        "repuesto": "6_Repuesto_Involucrado"
    }

    fotos_procesadas = {}

    for key, label in requisitos.items():
        st.markdown(f"**{label.replace('_', ' ')}**")
        archivo = st.file_uploader(f"Sube la foto para {label}", type=['jpg', 'jpeg', 'png'], key=f"up_{key}", label_visibility="collapsed")
        
        if archivo:
            if f"img_name_{key}" not in st.session_state or st.session_state[f"img_name_{key}"] != archivo.name:
                img = Image.open(archivo)
                st.session_state[f"img_obj_{key}"] = ImageOps.exif_transpose(img) 
                st.session_state[f"img_name_{key}"] = archivo.name

            col_img, col_btn_izq, col_btn_der = st.columns([2, 1, 1])
            with col_img:
                st.image(st.session_state[f"img_obj_{key}"], use_container_width=True)
            with col_btn_izq:
                if st.button("↩️ Izq.", key=f"rotL_{key}", use_container_width=True):
                    st.session_state[f"img_obj_{key}"] = st.session_state[f"img_obj_{key}"].rotate(90, expand=True)
                    st.rerun()
            with col_btn_der:
                if st.button("↪️ Der.", key=f"rotR_{key}", use_container_width=True):
                    st.session_state[f"img_obj_{key}"] = st.session_state[f"img_obj_{key}"].rotate(-90, expand=True)
                    st.rerun()
            
            fotos_procesadas[key] = st.session_state[f"img_obj_{key}"]
        st.divider()

    # ==========================================
    # 3. VIDEO DE RESPALDO DIRECTO
    # ==========================================
    st.markdown("### 🎥 Evidencia en Video (Opcional)")
    st.caption("Graba o selecciona el video desde tu galería. El sistema lo procesará automáticamente.")
    video_archivo = st.file_uploader("Sube el video de respaldo (Máx 200MB)", type=['mp4', 'mov', 'avi'], key="up_video")
    st.divider()

    # ==========================================
    # 4. LÓGICA DE NUBE Y CORREO
    # ==========================================
    def subir_a_google_drive(archivo_vid, nombre_archivo):
        try:
            # Usa la llave maestra que ya tienes en Secrets
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ['https://www.googleapis.com/auth/drive'])
            service = build('drive', 'v3', credentials=creds)
            
            file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
            media = MediaIoBaseUpload(io.BytesIO(archivo_vid.read()), mimetype=archivo_vid.type, resumable=True)
            
            # Sube el archivo
            file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            return file.get('webViewLink')
        except Exception as e:
            return f"ERROR_NUBE: {e}"

    def enviar_correo(zip_bytes, link_vid=""):
        try:
            sender = st.secrets["email"]["user"]
            password = st.secrets["email"]["password"]
            receiver = "gabriel.poblete@kaufmann.cl" 
            
            msg = EmailMessage()
            msg['Subject'] = f"RESPALDO GARANTIA OT {ot} - {cliente}"
            msg['From'] = f"Plataforma de Garantías Kaufmann <{sender}>"
            msg['To'] = receiver
            
            texto_video = f"\n🎥 VIDEO ADJUNTO:\nEl técnico ha subido un video. Míralo aquí: {link_vid}\n" if link_vid else ""

            cuerpo_mensaje = f"""Hola Gabriel,

Se adjunta el respaldo de garantía para:
- OT: {ot}
- Cliente: {cliente}

Documentación generada desde la plataforma por el técnico: {tecnico}.
{texto_video}
El archivo ZIP contiene las fotografías originales solicitadas para su gestión.

Saludos."""
            msg.set_content(cuerpo_mensaje)
            msg.add_attachment(zip_bytes, maintype='application', subtype='zip', filename=f"Garantia_OT_{ot}.zip")
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)
            return True, ""
        except Exception as e:
            return False, str(e)

    progreso = len(fotos_procesadas) / len(requisitos)
    st.progress(progreso, text=f"Fotografías: {len(fotos_procesadas)} de {len(requisitos)}")

    if st.button("🚀 ENVIAR RESPALDO", type="primary", use_container_width=True):
        if not ot or not tecnico or not cliente:
            st.error("⛔ Ingresa OT, Cliente y Técnico antes de enviar.")
        elif len(fotos_procesadas) < len(requisitos):
            st.warning("⚠️ Faltan fotos obligatorias.")
        else:
            with st.spinner("📦 Procesando evidencia pesada y enviando... Esto tomará unos segundos."):
                try:
                    # 1. Subir video si existe
                    link_v = ""
                    if video_archivo:
                        link_v = subir_a_google_drive(video_archivo, f"Video_OT_{ot}_{cliente}.mp4")
                        if "ERROR_NUBE" in link_v:
                            st.error(f"Error al subir el video: {link_v}")
                            return

                    # 2. Armar el ZIP con las fotos
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for k, lbl in requisitos.items():
                            img = fotos_procesadas[k]
                            img.thumbnail((1600, 1600)) 
                            img_byte_arr = io.BytesIO()
                            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=90)
                            zip_file.writestr(f"{lbl}.jpg", img_byte_arr.getvalue())
                    zip_bytes = zip_buffer.getvalue()

                    # 3. Enviar correo final
                    exito, error_msg = enviar_correo(zip_bytes, link_v)
                    if exito:
                        st.success(f"✅ ¡Respaldo OT {ot} enviado exitosamente!")
                    else:
                        st.error(f"❌ Error al enviar el correo: {error_msg}")
                except Exception as e:
                    st.error(f"Error procesando archivos: {e}")

if __name__ == "__main__":
    render_app()
