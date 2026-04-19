import streamlit as st
from PIL import Image, ImageOps
from datetime import datetime
import os
import io
import zipfile
import smtplib
from email.message import EmailMessage

def render_app():
    # CAMBIO DE TÍTULO SOLICITADO
    st.title("Plataforma de garantías Kaufmann")
    st.info("Sube las fotografías, gíralas si es necesario, y envía el respaldo directo al analista.")

    # ==========================================
    # 1. IDENTIFICACIÓN DE LA ORDEN
    # ==========================================
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        ot = col1.text_input("Número de OT", placeholder="Ej: 85432", key="garantia_ot").upper()
        cliente = col2.text_input("Nombre del Cliente", placeholder="Ej: Transportes X", key="garantia_cli").upper()
        tecnico = col3.text_input("Técnico", placeholder="Ej: Pedro", key="garantia_tec")

    # ==========================================
    # 2. CHECKLIST Y VISTA PREVIA (CON GIRO IZQ/DER)
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
        
        archivo = st.file_uploader(f"Sube la foto para {label}", type=['jpg', 'jpeg', 'png'], key=f"up_{key}", label_visibility="collapsed")
        
        if archivo:
            if f"img_name_{key}" not in st.session_state or st.session_state[f"img_name_{key}"] != archivo.name:
                img = Image.open(archivo)
                img = ImageOps.exif_transpose(img) 
                st.session_state[f"img_obj_{key}"] = img
                st.session_state[f"img_name_{key}"] = archivo.name

            # TRES COLUMNAS: Foto y los dos botones de giro
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
    # 3. LÓGICA DE CORREO PERSONALIZADO
    # ==========================================
    def enviar_correo(zip_bytes):
        try:
            sender = st.secrets["email"]["user"]
            password = st.secrets["email"]["password"]
            receiver = "gabriel.poblete@kaufmann.cl" 
            
            msg = EmailMessage()
            # ASUNTO DINÁMICO CON CLIENTE
            msg['Subject'] = f"RESPALDO GARANTIA OT {ot} - {cliente}"
            
            # NOMBRE DEL REMITENTE PERSONALIZADO
            msg['From'] = f"Plataforma de Garantías Kaufmann <{sender}>"
            msg['To'] = receiver
            
            cuerpo_mensaje = f"""Hola,

Se adjunta el respaldo fotográfico de garantía para:
- OT: {ot}
- Cliente: {cliente}

Documentación generada desde la plataforma por el técnico: {tecnico}.
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
            with st.spinner("📦 Enviando respaldo a Kaufmann..."):
                try:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for k, lbl in requisitos.items():
                            img = fotos_procesadas[k]
                            # AUMENTAMOS RESOLUCIÓN PARA MEJOR DETALLE EN VIN/ODÓMETRO
                            img.thumbnail((1600, 1600)) 
                            img_byte_arr = io.BytesIO()
                            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=90)
                            zip_file.writestr(f"{lbl}.jpg", img_byte_arr.getvalue())
                    zip_bytes = zip_buffer.getvalue()

                    exito, error_msg = enviar_correo(zip_bytes)
                    if exito:
                        st.success(f"✅ ¡Respaldo OT {ot} enviado exitosamente!")
                    else:
                        st.error(f"❌ Error al enviar: {error_msg}")
                except Exception as e:
                    st.error(f"Error procesando archivos: {e}")

if __name__ == "__main__":
    render_app()
