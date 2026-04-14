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

# LIBRERÍAS PARA EL ENVÍO DE CORREOS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def render_app():
    # ==========================================
    # 1. CONFIGURACIÓN Y CONSTANTES INTERNAS
    # ==========================================
    NOMBRE_HOJA_GOOGLE = "DB_Cotizador"
    EMPRESA_NOMBRE = "C.H. SERVICIO AUTOMOTRIZ"
    RUT_EMPRESA = "13.961.700-2" 
    DIRECCION = "Francisco Pizarro 495, Padre las Casas"
    TELEFONO = "+56 9 8922 0616"
    EMAIL_LOCAL = "c.h.servicioautomotriz@gmail.com"
    COLOR_PRIMARIO = "#0A2540" 

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

    def enviar_correo(destinatario, asunto, mensaje_texto, pdf_bytes, nombre_archivo, email_remitente):
        try:
            if "email" in st.secrets:
                user = st.secrets["email"]["user"]
                pwd = st.secrets["email"]["password"]
                msg = MIMEMultipart()
                msg['From'] = f"Sistema C.H. Automotriz <{user}>"
                msg['To'] = destinatario
                msg['Subject'] = asunto
                msg.add_header('reply-to', email_remitente) 
                msg.attach(MIMEText(mensaje_texto, 'plain'))
                adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
                adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
                msg.attach(adjunto)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(user, pwd)
                server.send_message(msg)
                server.quit()
                return True, "Enviado"
            return False, "Sin credenciales"
        except Exception as e: return False, str(e)

    @st.cache_data(ttl=60)
    def cargar_directorio_patentes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Directorio_Patentes")
                return pd.DataFrame(ws.get_all_records())
            except: pass
        return pd.DataFrame(columns=["Patente", "Institucion"])

    def obtener_y_registrar_correlativo(patente, cliente, total):
        client = conectar_google_sheets()
        if client:
            try:
                spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: ws = spreadsheet.worksheet("Historial")
                except: ws = spreadsheet.add_worksheet("Historial", 1000, 6)
                datos = ws.get_all_values()
                corr = str(len(datos))
                ws.append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), corr, patente, cliente, total])
                return corr
            except: return "ERR"
        return "OFFLINE"

    def cargar_precios():
        try:
            client = conectar_google_sheets()
            return pd.DataFrame(client.open(NOMBRE_HOJA_GOOGLE).sheet1.get_all_records())
        except: return pd.DataFrame()

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")
    def limpiar_patente(t): return re.sub(r'[^A-Z0-9]', '', str(t).upper())

    def encontrar_imagen(nombre):
        for ext in ['.png', '.jpg', '.jpeg']:
            if os.path.exists(nombre + ext): return nombre + ext
        return None

    # --- CLASE PDF ---
    class PDF(FPDF):
        def __init__(self, correlativo="", official=False): 
            super().__init__()
            self.correlativo = correlativo
            self.is_official = official
        def header(self):
            logo = encontrar_imagen("logo_christian")
            if logo: self.image(logo, x=10, y=10, w=70) 
            self.set_xy(130, 10)
            self.set_text_color(220, 0, 0)
            self.set_font('Arial', 'B', 16)
            titulo = "COTIZACIÓN" if self.is_official else "PRESUPUESTO"
            self.cell(70, 10, titulo, 'LTR', 1, 'C') 
            self.set_x(130)
            self.cell(70, 10, f"N° {self.correlativo}", 'LBR', 1, 'C')
            self.set_text_color(0, 0, 0); self.ln(15)
        def footer(self):
            self.set_y(-20); self.set_font('Arial', 'I', 8)
            self.line(10, self.get_y(), 200, self.get_y())
            self.cell(0, 4, f"Christian Herrera | RUT: {RUT_EMPRESA} | {DIRECCION}", 0, 1, 'C')

    def generar_pdf(pat, mar, mod, cli, rut, items, neto, official, est, us_f, obs, corr, fotos):
        pdf = PDF(correlativo=corr, official=official)
        pdf.add_page()
        # Lógica de dibujo de tablas
        pdf.set_y(45); pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(10, 37, 64); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 6, "  DATOS DEL CLIENTE", 1, 1, 'L', 1); pdf.set_text_color(0, 0, 0)
        # (Fila dinámica cliente...)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(10, 37, 64); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 6, "  DATOS DEL VEHÍCULO", 1, 1, 'L', 1); pdf.set_text_color(0, 0, 0)
        # (Fila dinámica vehículo...)
        pdf.ln(5)
        # Tabla de Items
        pdf.set_font('Arial', 'B', 9); pdf.cell(115, 7, "Descripción", 1); pdf.cell(15, 7, "Cant.", 1); pdf.cell(30, 7, "Unitario", 1); pdf.cell(30, 7, "Total", 1, 1)
        pdf.set_font('Arial', '', 9)
        for i in items:
            pdf.cell(115, 6, i['Descripción'][:60], 1); pdf.cell(15, 6, str(i['Cantidad']), 1); pdf.cell(30, 6, format_clp(i['Unitario_Costo']), 1); pdf.cell(30, 6, format_clp(i['Total_Costo']), 1, 1)
        # Totales
        pdf.ln(5); pdf.set_x(140); pdf.cell(30, 6, "TOTAL", 1); pdf.cell(30, 6, format_clp(neto * 1.19), 1, 1, 'R')
        return pdf.output(dest='S').encode('latin-1')

    # ==========================================
    # 2. INTERFAZ DE USUARIO (UI)
    # ==========================================
    col_l, col_r = st.columns([3, 1])
    with col_l: st.title("🚘 C.H. Servicio Automotriz")
    with col_r:
        logo_ui = encontrar_imagen("logo_christian")
        if logo_ui: st.image(logo_ui, width=150)
    
    st.divider()
    
    if 'paso_c' not in st.session_state: st.session_state.paso_c = 1
    if 'items_c' not in st.session_state: st.session_state.items_c = []

    # --- PASO 1: PATENTE ---
    if st.session_state.paso_c == 1:
        st.subheader("Buscador de Vehículo")
        pat_in = st.text_input("Ingrese Patente", placeholder="Ej: HXRP10").upper()
        pat_final = pat_in
        
        if len(pat_in) >= 2:
            df_p = cargar_directorio_patentes()
            matches = [p for p in df_p['Patente'].tolist() if pat_in in str(p).upper()]
            if matches:
                sel = st.selectbox("💡 Sugerencias:", ["Mantener escritura"] + matches)
                if sel != "Mantener escritura": pat_final = sel
        
        inst = st.selectbox("Institución", ["Particular", "SSAS", "SAMU", "Hospital Temuco", "Hospital Villarrica", "Gendarmería"])
        
        if st.button("🚀 Comenzar Cotización", type="primary", use_container_width=True):
            st.session_state.pat_c = pat_final
            st.session_state.inst_c = inst
            st.session_state.paso_c = 2
            st.rerun()

    # --- PASO 2: COTIZADOR ---
    elif st.session_state.paso_c == 2:
        c1, c2 = st.columns([1, 5])
        with c1: 
            if st.button("⬅️"): st.session_state.paso_c = 1; st.rerun()
        with c2: st.info(f"Vehículo: {st.session_state.pat_c} | Cliente: {st.session_state.inst_c}")

        t1, t2, t3 = st.tabs(["🔧 Trabajos", "🛒 Repuestos", "➕ Manual"])
        
        df_p = cargar_precios()
        with t1:
            if not df_p.empty:
                for idx, row in df_p.iterrows():
                    col_a, col_b, col_c = st.columns([4, 1, 1])
                    col_a.write(row['Trabajo'])
                    q = col_b.number_input("Cant", 0, 10, key=f"q_{idx}")
                    p = float(row.get('Costo_SSAS', 0)) # Simplificado para el ejemplo
                    if q > 0:
                        # Evitar duplicados simples
                        if not any(x['Descripción'] == row['Trabajo'] for x in st.session_state.items_c):
                            st.session_state.items_c.append({"Descripción": row['Trabajo'], "Cantidad": q, "Unitario_Costo": p, "Total_Costo": p*q})

        with t2:
            st.subheader("Calculadora Repuestos")
            d_r = st.text_input("Repuesto")
            c_r = st.number_input("Costo $", 0, step=1000)
            m_r = st.slider("Margen %", 0, 100, 30)
            if st.button("Añadir Repuesto"):
                pf = c_r * (1 + m_r/100)
                st.session_state.items_c.append({"Descripción": d_r, "Cantidad": 1, "Unitario_Costo": pf, "Total_Costo": pf})

        # Mostrar Resumen con BASUREROS
        st.divider()
        st.subheader("Resumen de Cotización")
        for i, item in enumerate(st.session_state.items_c):
            ca, cb = st.columns([5, 1])
            ca.write(f"• {item['Cantidad']}x {item['Descripción']} - {format_clp(item['Total_Costo'])}")
            if cb.button("🗑️", key=f"del_{i}"):
                st.session_state.items_c.pop(i)
                st.rerun()
        
        total_n = sum(x['Total_Costo'] for x in st.session_state.items_c)
        st.metric("TOTAL CON IVA", format_clp(total_n * 1.19))

        if st.button("💾 GENERAR Y RESPALDAR", type="primary", use_container_width=True):
            corr = obtener_y_registrar_correlativo(st.session_state.pat_c, st.session_state.inst_c, format_clp(total_n*1.19))
            pdf_b = generar_pdf(st.session_state.pat_c, "", "", "Kaufmann", "", st.session_state.items_c, total_n, True, "", "", "", corr, None)
            
            # Respaldo Email
            enviar_correo("sistema.cotizador.gp@gmail.com", f"Respaldo {corr} - {st.session_state.pat_c}", "Copia automática", pdf_b, f"{corr}.pdf", EMAIL_LOCAL)
            
            st.session_state.pdf_ready = pdf_b
            st.session_state.pdf_name = f"Cotizacion_{corr}.pdf"
            st.success(f"Documento N° {corr} generado con éxito.")

        if 'pdf_ready' in st.session_state:
            st.download_button("📥 Descargar PDF", st.session_state.pdf_ready, st.session_state.pdf_name, "application/pdf", use_container_width=True)

if __name__ == "__main__":
    render_app()
