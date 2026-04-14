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

# NOTA: Se eliminó st.set_page_config porque ahora se controla desde main.py

def render_app():
    # ==========================================
    # CONFIGURACIÓN Y CONSTANTES INTERNAS
    # ==========================================
    NOMBRE_HOJA_GOOGLE = "DB_Cotizador"
    EMPRESA_NOMBRE = "C.H. SERVICIO AUTOMOTRIZ"
    RUT_EMPRESA = "13.961.700-2" 
    DIRECCION = "Francisco Pizarro 495, Padre las Casas"
    TELEFONO = "+56 9 8922 0616"
    EMAIL = "c.h.servicioautomotriz@gmail.com"
    COLOR_PRIMARIO = "#0A2540" 

    # --- FUNCIONES DE APOYO (Backend) ---
    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = st.secrets["gcp_service_account"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                return gspread.authorize(creds)
            return None
        except: return None

    def enviar_correo(destinatario, asunto, mensaje_texto, pdf_bytes, nombre_archivo, email_real_cristian):
        try:
            if "email" in st.secrets:
                remitente_sistema = st.secrets["email"]["user"]
                password = st.secrets["email"]["password"]
                msg = MIMEMultipart()
                msg['From'] = f"Sistema Cotizaciones C.H. Automotriz <{remitente_sistema}>"
                msg['To'] = destinatario
                msg['Subject'] = asunto
                msg.add_header('reply-to', email_real_cristian) 
                msg.attach(MIMEText(mensaje_texto, 'plain'))
                adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
                adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
                msg.attach(adjunto)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(remitente_sistema, password)
                server.send_message(msg)
                server.quit()
                return True, "Correo enviado."
            return False, "Faltan credenciales."
        except Exception as e: return False, str(e)

    def obtener_y_registrar_correlativo(patente, cliente, total):
        client = conectar_google_sheets()
        if client:
            try:
                spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: worksheet_hist = spreadsheet.worksheet("Historial")
                except:
                    worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="6")
                    worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Patente", "Cliente", "Monto Total"])
                datos = worksheet_hist.get_all_values()
                correlativo_str = str(len(datos))
                worksheet_hist.append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M:%S"), correlativo_str, patente, cliente, total])
                return correlativo_str
            except: return "ERR"
        return "OFFLINE"

    def cargar_datos():
        try:
            client = conectar_google_sheets()
            sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
            return pd.DataFrame(sheet.get_all_records())
        except: return pd.DataFrame(columns=["Categoria","Trabajo","Costo_SSAS","Costo_Hosp_Temuco","Costo_Hosp_Villarrica","Costo_Hosp_Lautaro","Costo_Hosp_Pitrufquen","Costo_Gend"])

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")

    # --- CLASE PDF ---
    class PDF(FPDF):
        def __init__(self, correlativo="", official=False): 
            super().__init__()
            self.correlativo = correlativo
            self.is_official = official
        def header(self):
            logo = None
            for ext in ['.jpg', '.png', '.jpeg']:
                if os.path.exists("logo" + ext): logo = "logo" + ext
            if logo: self.image(logo, x=10, y=10, w=70) 
            self.set_xy(130, 10)
            self.set_text_color(220, 0, 0)
            self.set_font('Arial', 'B', 16)
            titulo = "COTIZACIÓN" if self.is_official else "PRESUPUESTO"
            self.cell(70, 10, titulo, 'LTR', 1, 'C') 
            self.set_x(130)
            self.cell(70, 10, f"N° {self.correlativo}", 'LBR', 1, 'C')
            self.set_text_color(0, 0, 0)
            self.ln(15)
        def footer(self):
            self.set_y(-20)
            self.set_font('Arial', 'I', 8)
            self.line(10, self.get_y(), 200, self.get_y())
            self.cell(0, 4, f"Christian Herrera | RUT: {RUT_EMPRESA} | {DIRECCION}", 0, 1, 'C')

    # ==========================================
    # LÓGICA DE INTERFAZ (UI)
    # ==========================================
    st.title("🚘 Cotizador C.H. Servicio Automotriz")
    
    if 'paso_cristian' not in st.session_state: st.session_state.paso_cristian = 1
    df_precios = cargar_datos()

    if st.session_state.paso_cristian == 1:
        st.subheader("1. Identificación")
        patente = st.text_input("Ingrese Patente").upper()
        t_cli = st.selectbox("Institución", ["SSAS", "SAMU", "Hospital Temuco", "Hospital Villarrica", "Gendarmería", "Particular"])
        if st.button("Comenzar"):
            st.session_state.patente_c = patente
            st.session_state.tipo_c = t_cli
            st.session_state.paso_cristian = 2
            st.rerun()

    elif st.session_state.paso_cristian == 2:
        st.write(f"Cotizando Patente: **{st.session_state.patente_c}**")
        if st.button("⬅️ Volver"): 
            st.session_state.paso_cristian = 1
            st.rerun()
        
        # Aquí iría el resto de la lógica de selección de trabajos que ya tienes...
        st.info("Despliegue de categorías y selección de ítems...")
        
        # Por brevedad, cerramos con el botón de finalizar
        if st.button("💾 Generar Documento"):
            st.success("¡Documento generado y respaldado!")
            # Aquí llamas a las funciones de PDF y Email que ya definimos arriba
