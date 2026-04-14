import streamlit as st
import pandas as pd
import io
import os
import base64
import streamlit.components.v1 as components
from fpdf import FPDF
from datetime import datetime
import time
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageOps
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# NOTA: Se eliminó st.set_page_config porque se controla desde main.py

def render_app():
    # ==========================================
    # 1. CONFIGURACIÓN Y CONSTANTES
    # ==========================================
    NOMBRE_HOJA_GOOGLE = "DB_Cotizador_Pascual"
    DESTINATARIOS_BODEGA = ["c.h.servicioautomotriz@gmail.com", "sistema.cotizador.gp@gmail.com"]
    EMAIL_REMITENTE_SISTEMA = "c.h.servicioautomotriz@gmail.com" 
    EMPRESA_NOMBRE = "LILY ISABEL UNDA CONTRERAS"
    EMPRESA_GIRO = "VENTA, FABRICACIÓN Y REPARACIÓN DE PARABRISAS Y SUS ACCESORIOS"
    RUT_EMPRESA = "8.810.453-6" 
    DIRECCION = "Caupolicán 0320 - Temuco" 
    COLOR_HEX = "#ff6c15"

    # --- FUNCIONES BACKEND ---
    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = st.secrets["gcp_service_account"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                return gspread.authorize(creds)
            return None
        except: return None

    def enviar_correo(destinatario, asunto, mensaje_texto, pdf_bytes, nombre_archivo, email_real_local):
        try:
            if "email" in st.secrets:
                rem = st.secrets["email"]["user"]
                pwd = st.secrets["email"]["password"]
                msg = MIMEMultipart()
                msg['From'] = f"Pascual Parabrisas <{rem}>"
                msg['To'] = destinatario
                msg['Subject'] = asunto
                msg.add_header('reply-to', email_real_local) 
                msg.attach(MIMEText(mensaje_texto, 'plain'))
                adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
                adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
                msg.attach(adjunto)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(rem, pwd)
                server.send_message(msg)
                server.quit()
                return True, "Correo enviado."
            return False, "Faltan credenciales."
        except Exception as e: return False, str(e)

    @st.cache_data(ttl=60)
    def obtener_clientes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Clientes")
                return ws.get_all_records()
            except: pass
        return []

    def obtener_y_registrar_correlativo(cliente, total):
        client = conectar_google_sheets()
        if client:
            try:
                spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = spreadsheet.worksheet("Historial")
                datos = ws.get_all_values()
                corr = str(1000 + len(datos))
                ws.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), corr, cliente.upper(), total])
                return corr
            except: return "ERR"
        return "OFFLINE"

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")
    
    def limpiar_patente(texto): return re.sub(r'[^A-Z0-9]', '', str(texto).upper())

    # --- CLASE PDF ---
    class PDF(FPDF):
        def __init__(self, correlativo=""):
            super().__init__()
            self.correlativo = correlativo
        def header(self):
            logo = None
            for ext in ['.jpg', '.png', '.jpeg']:
                if os.path.exists("logo" + ext): logo = "logo" + ext
            if logo: self.image(logo, x=10, y=15, w=50) 
            self.set_xy(10, 40)
            self.set_font('Arial', 'B', 9); self.cell(120, 4, EMPRESA_NOMBRE, 0, 1, 'L')
            self.set_font('Arial', '', 8); self.cell(120, 4, EMPRESA_GIRO, 0, 1, 'L')
            self.set_xy(140, 15); self.set_text_color(255, 108, 21)
            self.set_font('Arial', 'B', 16); self.cell(60, 10, "COTIZACIÓN", 'LTR', 1, 'C')
            self.set_x(140); self.set_font('Arial', 'B', 14)
            titulo = f"N° {self.correlativo}" if self.correlativo else "N° BORRADOR"
            self.cell(60, 10, titulo, 'LBR', 1, 'C')
            self.set_text_color(0, 0, 0); self.ln(15)

    def generar_pdf_pascual(datos_cliente, datos_vehiculo, productos, servicios, descuento_pct, correlativo):
        pdf = PDF(correlativo=correlativo)
        pdf.add_page()
        # (Aquí va toda la lógica de dibujo de tablas del PDF que ya teníamos...)
        # Nota: Por brevedad en este mensaje omito el detalle interno del dibujo de celdas 
        # pero asegúrate de inyectar el 'correlativo' en el constructor arriba.
        return pdf.output(dest='S').encode('latin-1')

    # --- ESTILOS ---
    st.markdown(f"<style>.stButton > button[kind='primary'] {{ background-color: {COLOR_HEX} !important; color: white !important; }}</style>", unsafe_allow_html=True)

    # --- LÓGICA DE UI ---
    st.title("🪟 Pascual Parabrisas")
    
    # Inicialización de estados
    if 'cristales_pascual' not in st.session_state: st.session_state.cristales_pascual = []
    if 'items_prod' not in st.session_state: st.session_state.items_prod = []
    if 'items_serv' not in st.session_state: st.session_state.items_serv = []

    # 1. Datos Vehículo
    c1, c2, c3 = st.columns(3)
    marca = c1.text_input("Marca").upper()
    modelo = c2.text_input("Modelo").upper()
    patente = c3.text_input("Patente").upper()

    # 2. Selector Universal
    st.subheader("Seleccione Cristales")
    col_f1, col_f2 = st.columns(2)
    if col_f1.button("🟩 PARABRISAS", use_container_width=True): st.session_state.cristales_pascual.append("PARABRISAS")
    if col_f2.button("🟦 LUNETA TRASERA", use_container_width=True): st.session_state.cristales_pascual.append("LUNETA TRASERA")
    
    # (Resto de botones de la rejilla universal...)
    
    # 3. Resumen y WhatsApp
    st.divider()
    if st.session_state.items_prod or st.session_state.items_serv:
        # Lógica de cálculo de total
        total = sum(i['Total'] for i in st.session_state.items_prod + st.session_state.items_serv)
        st.subheader(f"Total: {format_clp(total)}")
        
        # WhatsApp Block
        msg = f"Te adjuntamos el presupuesto para {marca} {modelo}:\n\nTotal: {format_clp(total)}\n\n- Pascual Parabrisas"
        st.code(msg)
        
    # 4. Expander para Cotización Formal
    with st.expander("🏢 Generar PDF Formal (Empresas)"):
        # Lógica de formulario de cliente y botón Generar PDF
        pass

# Ejecución (Esto solo se activa si corres este archivo solo, 
# pero el Portero lo llamará directamente)
if __name__ == "__main__":
    render_app()
