import streamlit as st
from PIL import Image, ImageOps
from datetime import datetime
import io
import zipfile
import smtplib
from email.message import EmailMessage

# ==========================================
# CONFIGURACIÓN DE CORREOS DESTINO
# ==========================================
CORREO_ANALISTA = "gabriel.poblete@kaufmann.cl"
CORREO_ASESORA = "gabriel.poblete@kaufmann.cl" 

def render_app():
    st.title("Plataforma de garantías Kaufmann")
    st.info("Sube la evidencia técnica. Puedes delegar el libro de mantención a la asesora y omitir pasos que no apliquen.")

    # ==========================================
    # 1. IDENTIFICACIÓN
    # ==========================================
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        
        # NUEVOS PLACEHOLDERS (SUGERENCIAS)
        ot = col1.text_input("Número de OT", placeholder="Ej. 205456789", key="gar_ot").upper()
        cliente = col2.text_input("Nombre del Cliente", placeholder="Ej. Transportes M. Valenzuela", key="gar_cli").upper()
        
        # NUEVO: MENÚ DESPLEGABLE DE TÉCNICOS
        lista_tecnicos = [
            "--- Seleccione ---",
            "Claudio Flores",
            "Ignacio Chicahual",
            "Sebastian Ayenao",
            "Rafael Bastías",
            "Eduardo Peñailillo",
            "Gastón Alarcón",
        ] # <-- EDITA ESTA LISTA CON LOS NOMBRES REALES DE TU EQUIPO
        
        tecnico = col3.selectbox("Técnico", lista_tecnicos, key="gar_tec")

    # ==========================================
    # 2. CHECKLIST DINÁMICO
    # ==========================================
    st.markdown("### 📋 Evidencia Fotográfica")
    
    requisitos = {
        "placa_vin": {"label": "Placa_VIN", "opcional": False},
        "tablero": {"label": "Tablero_Odometro", "opcional": False},
        "vehiculo": {"label": "Fotografia_Vehiculo", "opcional": False},
        "diagnostico": {"label": "Equipo_Diagnostico", "opcional": True},
        "repuesto": {"label": "Repuesto_Involucrado", "opcional": True}
    }

    fotos_procesadas = {}
    acciones_completadas = 0 
    delegar_dina = False

    for key, config in requisitos.items():
        label = config["label"]
        st.markdown(f"**{label.replace('_', ' ')}**")
        
        no_aplica = False
        if config["opcional"]:
            no_aplica = st.checkbox(f"No aplica para esta falla", key=f"na_{key}")
            
        if no_aplica:
            st.success("✔️ Omitido correctamente.")
            acciones_completadas += 1
        else:
            archivo = st.file_uploader(f"Sube la foto", type=['jpg', 'jpeg', 'png'], key=f"up_{key}", label_visibility="collapsed")
            
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
                acciones_completadas += 1
                
        st.divider()

    st.markdown("**Libro Mantencion**")
    opcion_libro = st.radio("¿Quién adjuntará el libro?", ["Técnico (Subir foto ahora)", "Solicitar a Asesora (Dina Vega)"], horizontal=True)
    
    if opcion_libro == "Técnico (Subir foto ahora)":
        archivo_libro = st.file_uploader("Sube la foto del libro", type=['jpg', 'jpeg', 'png'], key="up_libro", label_visibility="collapsed")
        if archivo_libro:
            if "img_name_libro" not in st.session_state or st.session_state["img_name_libro"] != archivo_libro.name:
                img_l = Image.open(archivo_libro)
                st.session_state["img_obj_libro"] = ImageOps.exif_transpose(img_l) 
                st.session_state["img_name_libro"] = archivo_libro.name
            
            c_img, c_l, c_r = st.columns([2, 1, 1])
            c_img.image(st.session_state["img_obj_libro"], use_container_width=True)
            if c_l.button("↩️ Izq.", key="rotL_libro", use_container_width=True):
                st.session_state["img_obj_libro"] = st.session_state["img_obj_libro"].rotate(90, expand=True)
                st.rerun()
            if c_r.button("↪️ Der.", key="rotR_libro", use_container_width=True):
                st.session_state["img_obj_libro"] = st.session_state["img_obj_libro"].rotate(-90, expand=True)
                st.rerun()
            
            fotos_procesadas["libro"] = st.session_state["img_obj_libro"]
            acciones_completadas += 1
    else:
        st.info(f"✉️ Al enviar, notificaremos automáticamente a Dina ({CORREO_ASESORA}).")
        delegar_dina = True
        acciones_completadas += 1

    st.divider()

    # ==========================================
    # 3. VIDEO DE RESPALDO (Opcional)
    # ==========================================
    st.markdown("### 🎥 Evidencia en Video (Opcional)")
    st.caption("Graba videos cortos (Máx. 18 MB) para ruidos o fallas.")
    video_archivo = st.file_uploader("Sube el video de respaldo", type=['mp4', 'mov'], key="up_video")
    
    video_valido = True
    if video_archivo:
        peso_mb = video_archivo.size / (1024 * 1024)
        if peso_mb > 18:
            st.error(f"⚠️ Video demasiado pesado ({peso_mb:.1f} MB). Máximo permitido: 18 MB.")
            video_valido = False
        else:
            st.success(f"✅ Video aceptado ({peso_mb:.1f} MB).")
    st.divider()

    # ==========================================
    # 4. LÓGICA DE ENVÍO
    # ==========================================
    def enviar_correos(zip_bytes, archivo_vid=None, delegar=False):
        try:
            sender = st.secrets["email"]["user"]
            password = st.secrets["email"]["password"]
            
            msg_analista = EmailMessage()
            msg_analista['Subject'] = f"RESPALDO GARANTIA OT {ot} - {cliente}"
            msg_analista['From'] = f"Plataforma de Garantías Kaufmann <{sender}>"
            msg_analista['To'] = CORREO_ANALISTA
            
            txt_vid = "\n🎥 Se adjunta además un VIDEO DE RESPALDO.\n" if archivo_vid else ""
            txt_libro = "⚠️ NOTA: El libro de mantención fue delegado a la asesora (Dina Vega). Te lo enviará por separado.\n" if delegar else "El archivo ZIP contiene todas las fotografías solicitadas."

            cuerpo_analista = f"""Hola Gabriel,

Se adjunta el respaldo de garantía para:
- OT: {ot}
- Cliente: {cliente}

Documentación subida por: {tecnico}.
{txt_vid}
{txt_libro}

Saludos."""
            msg_analista.set_content(cuerpo_analista)
            msg_analista.add_attachment(zip_bytes, maintype='application', subtype='zip', filename=f"Garantia_OT_{ot}.zip")
            
            if archivo_vid:
                video_data = archivo_vid.read()
                formato = archivo_vid.name.split('.')[-1].lower()
                msg_analista.add_attachment(video_data, maintype='video', subtype=formato, filename=f"Video_{ot}.{formato}")

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg_analista)
                
                if delegar:
                    msg_asesora = EmailMessage()
                    msg_asesora['Subject'] = f"SOLICITUD LIBRO MANTENCIÓN - OT {ot}"
                    msg_asesora['From'] = f"Plataforma de Garantías Kaufmann <{sender}>"
                    msg_asesora['To'] = CORREO_ASESORA
                    msg_asesora.add_header('reply-to', CORREO_ANALISTA) 
                    
                    cuerpo_asesora = f"""Hola Dina,

El técnico {tecnico} ha finalizado la recolección de evidencia para la siguiente garantía:
- OT: {ot}
- Cliente: {cliente}

Por favor, cuando dispongas del Libro de Mantención timbrado, envíalo directamente a Gabriel Poblete. 
(Puedes responder directamente a este correo adjuntando la fotografía).

Gracias!"""
                    msg_asesora.set_content(cuerpo_asesora)
                    smtp.send_message(msg_asesora)

            return True, ""
        except Exception as e:
            return False, str(e)

    TOTAL_ACCIONES = 6 
    progreso = acciones_completadas / TOTAL_ACCIONES
    st.progress(progreso, text=f"Progreso del expediente: {acciones_completadas} de {TOTAL_ACCIONES} completados")

    if st.button("🚀 ENVIAR RESPALDO", type="primary", use_container_width=True):
        if not ot or tecnico == "--- Seleccione ---" or not cliente:
            st.error("⛔ Ingresa OT, Cliente y selecciona al Técnico antes de enviar.")
        elif acciones_completadas < TOTAL_ACCIONES:
            st.warning("⚠️ Faltan pasos por completar (Sube la foto o marca 'No aplica').")
        elif not video_valido:
            st.error("⛔ No se puede enviar. El video supera los 18 MB permitidos.")
        else:
            with st.spinner("📦 Empaquetando y gestionando notificaciones..."):
                try:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for k, img in fotos_procesadas.items():
                            nombre_archivo = "3_Libro_Mantencion" if k == "libro" else requisitos[k]["label"]
                            img.thumbnail((1600, 1600)) 
                            img_byte_arr = io.BytesIO()
                            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=90)
                            zip_file.writestr(f"{nombre_archivo}.jpg", img_byte_arr.getvalue())
                    zip_bytes = zip_buffer.getvalue()

                    exito, error_msg = enviar_correos(zip_bytes, video_archivo, delegar_dina)
                    if exito:
                        st.success(f"✅ ¡Respaldo enviado exitosamente!")
                        if delegar_dina:
                            st.info(f"📧 Se envió la notificación a Dina Vega ({CORREO_ASESORA}).")
                    else:
                        st.error(f"❌ Error al enviar el correo: {error_msg}")
                except Exception as e:
                    st.error(f"Error procesando archivos: {e}")

if __name__ == "__main__":
    render_app()
