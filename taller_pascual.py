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

    def encontrar_imagen(nombre_base):
        for ext in ['.jpg', '.png', '.jpeg']:
            if os.path.exists(nombre_base + ext): return nombre_base + ext
        return None

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")
    
    def limpiar_patente(texto): return re.sub(r'[^A-Z0-9]', '', str(texto).upper())

    # --- CLASE PDF ---
    class PDF(FPDF):
        def __init__(self, correlativo=""):
            super().__init__()
            self.correlativo = correlativo
        def header(self):
            # ACTUALIZADO: Busca específicamente logo_pascual
            logo = encontrar_imagen("logo_pascual")
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

    # --- ESTILOS ---
    st.markdown(f"<style>.stButton > button[kind='primary'] {{ background-color: {COLOR_HEX} !important; color: white !important; }}</style>", unsafe_allow_html=True)

    # --- LÓGICA DE UI ---
    col_centro = st.columns([1, 2, 1])
    with col_centro[1]:
        c_logo, c_btn = st.columns([3, 1], vertical_alignment="center")
        with c_logo:
            # ACTUALIZADO: Busca específicamente logo_pascual
            logo_app = encontrar_imagen("logo_pascual") 
            if logo_app: st.image(logo_app, width=200)
            else: st.title("🪟 Pascual Parabrisas")
        
        st.divider()
        # ... resto del código de la app que ya tienes (botones, whatsapp, etc) ...
        st.write("Interfaz de Pascual lista y operativa.")

if __name__ == "__main__":
    render_app()
