import streamlit as st
from fpdf import FPDF
from PIL import Image, ImageOps
from datetime import datetime
import os
import io
import zipfile
import smtplib
from email.message import EmailMessage

def render_app():
    st.title("📸 Expediente de Garantías")
    st.info("Sube las fotografías, gíralas si es necesario, y envía el expediente directo al analista.")

    # ==========================================
    # 1. IDENTIFICACIÓN DE LA ORDEN
    # ==========================================
    with st.container(border=True):
        col1, col2 = st.columns(2)
        ot = col1.text_input("Número de OT", placeholder="Ej: 85432", key="garantia_ot").upper()
        tecnico = col2.text_input("Nombre del Técnico", placeholder="Ej: Pedro", key="garantia_tec")

    # ==========================================
    # 2. CHECKLIST Y VISTA PREVIA CON ROTACIÓN
    # ==========================================
    st.markdown("### 📋 Evidencia Fotográfica")
    
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
        
        # Subida de archivo
        archivo = st.file_uploader(f"Sube la foto para {label}", type=['jpg', 'jpeg', 'png'], key=f"up_{key}", label_visibility="collapsed")
        
        if archivo:
            # Si es un archivo nuevo, lo cargamos en la sesión
            if f"img_name_{key}" not in st.session_state or st.session_state[f"img_name_{key}"] != archivo.name:
                img = Image.open(archivo)
                img = ImageOps.exif_transpose(img) # Corrige la rotación nativa del celular
                st.session_state[f"img_obj_{key}"] = img
                st.session_state[f"img_name_{key}"] = archivo.name

            # Mostrar vista previa y botón de rotación
            col_img, col_btn = st.columns([2, 1])
            with col_img:
                st.image(st.session_state[f"img_obj_{key}"], use_container_width=True)
            with col_btn:
                if st.button("🔄 Girar 90°", key=f"rot_{key}"):
                    # Girar la imagen y recargar la pantalla
                    st.session_state[f"img_obj_{key}"] = st.session_state[f"img_obj_{key}"].rotate(-90, expand=True)
                    st.rerun()
            
            # Guardamos la imagen final lista para el ZIP/PDF
            fotos_procesadas[key] = st.session_state[f"img_obj_{key}"]
            
        st.divider()

    # ==========================================
    # 3. LÓGICA DE PDF, ZIP Y CORREO
    # ==========================================
    def compilar_pdf():
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.cell(0, 20, "EXPEDIENTE DE GARANTIA", 0, 1, "C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"OT: {ot}  |  Tecnico: {tecnico}  |  Fecha: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
        
        for k, lbl in requisitos.items():
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, lbl.replace('_', ' '), 0, 1, "C")
            
            img = fotos_procesadas[k]
            img.thumbnail((1000, 1000))
            temp_path = f"temp_{k}.jpg"
            img.convert('RGB').save(temp_path, format="JPEG", quality=85)
            
            ancho_max, alto_max = 180, 240
            ancho_img, alto_img = img.size
            ratio = min(ancho_max/ancho_img, alto_max/alto_img)
            nuevo_ancho = ancho_img * ratio
            x_pos = (210 - nuevo_ancho) / 2
            
            pdf.image(temp_path, x=x_pos, w=nuevo_ancho)
            os.remove(temp_path)
            
        return pdf.output(dest='S').encode('latin-1')

    def enviar_correo(zip_bytes):
        try:
            # Rescatar credenciales de los Secrets
            sender = st.secrets["email"]["correo_envio"]
            password = st.secrets["email"]["password_aplicacion"]
            receiver = st.secrets["email"]["correo_analista"]
            
            msg = EmailMessage()
            msg['Subject'] = f"NUEVA GARANTÍA - OT: {ot} (Técnico: {tecnico})"
            msg['From'] = sender
            msg['To'] = receiver
            msg.set_content(f"Hola,\n\nSe adjunta el expediente de garantía para la OT {ot}, generado desde la plataforma por el técnico {tecnico}.\n\nEl archivo ZIP contiene el PDF unificado y las fotografías originales.\n\nSaludos.")
            
            msg.add_attachment(zip_bytes, maintype='application', subtype='zip', filename=f"Garantia_OT_{ot}.zip")
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)
            return True, ""
        except Exception as e:
            return False, str(e)

    progreso = len(fotos_procesadas) / len(requisitos)
    st.progress(progreso, text=f"Fotografías: {len(fotos_procesadas)} de {len(requisitos)}")

    if st.button("🚀 ENVIAR EXPEDIENTE", type="primary", use_container_width=True):
        if not ot or not tecnico:
            st.error("⛔ Ingresa la OT y el Nombre del Técnico.")
        elif len(fotos_procesadas) < len(requisitos):
            st.warning("⚠️ Faltan fotografías. Sube las 6 fotos obligatorias.")
        else:
            if "email" not in st.secrets:
                st.error("⚠️ Falta configurar las credenciales de correo en los Secrets de Streamlit.")
                return

            with st.spinner("📦 Comprimiendo fotos y enviando correo..."):
                try:
                    # 1. Generar el PDF
                    pdf_bytes = compilar_pdf()
                    
                    # 2. Crear el archivo ZIP en memoria
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        # Guardar el PDF en el ZIP
                        zip_file.writestr(f"Expediente_OT_{ot}.pdf", pdf_bytes)
                        
                        # Guardar cada foto original en el ZIP
                        for k, lbl in requisitos.items():
                            img = fotos_procesadas[k]
                            img_byte_arr = io.BytesIO()
                            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=90)
                            zip_file.writestr(f"{lbl}.jpg", img_byte_arr.getvalue())
                    
                    zip_bytes = zip_buffer.getvalue()

                    # 3. Enviar el correo
                    exito, error_msg = enviar_correo(zip_bytes)
                    
                    if exito:
                        st.success("✅ ¡Expediente enviado exitosamente al analista de garantías!")
                        # Opcional: Dejar el botón para que el técnico lo descargue por si acaso
                        st.download_button("📥 Descargar Copia Local (ZIP)", data=zip_bytes, file_name=f"Copia_OT_{ot}.zip", mime="application/zip", use_container_width=True)
                    else:
                        st.error(f"❌ Error al enviar el correo: {error_msg}")
                        
                except Exception as e:
                    st.error(f"Error procesando los archivos: {e}")

if __name__ == "__main__":
    render_app()
