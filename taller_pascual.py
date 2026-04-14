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

    # --- CARGA DINÁMICA DESDE CSV ---
    @st.cache_data(ttl=3600)
    def cargar_base_vehiculos():
        try:
            if os.path.exists("vehiculos.csv"):
                df = pd.read_csv("vehiculos.csv", encoding='utf-8')
                if 'Marca' in df.columns and 'Modelo' in df.columns:
                    base_csv = {"--- Seleccione Marca ---": ["---"]}
                    marcas = sorted([str(m) for m in df['Marca'].dropna().unique()])
                    for marca in marcas:
                        modelos = df[df['Marca'] == marca]['Modelo'].dropna().tolist()
                        base_csv[marca] = sorted(list(set([str(m) for m in modelos])))
                    return base_csv
        except Exception as e:
            st.error(f"Error al leer vehiculos.csv: {e}")
        # Fallback mínimo si el archivo falla
        return {"--- Seleccione Marca ---": ["---"]}

    BASE_VEHICULOS = cargar_base_vehiculos()

    # --- FUNCIONES DE ESTADO Y UI ---
    if 'cristales_sel' not in st.session_state: st.session_state.cristales_sel = []
    if 'items_productos' not in st.session_state: st.session_state.items_productos = []
    if 'items_servicios' not in st.session_state: st.session_state.items_servicios = []
    if 'servicio_desc' not in st.session_state: st.session_state.servicio_desc = ""

    def toggle_cristal(cristal):
        if cristal in st.session_state.cristales_sel: st.session_state.cristales_sel.remove(cristal)
        else: st.session_state.cristales_sel.append(cristal)

    def btn_type(cristal):
        return "primary" if cristal in st.session_state.cristales_sel else "secondary"

    def reset_session():
        st.session_state.cristales_sel = []
        st.session_state.items_productos = []
        st.session_state.items_servicios = []
        st.rerun()

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
                return True, "Enviado"
            return False, "Faltan credenciales"
        except Exception as e: return False, str(e)

    def encontrar_imagen(nombre_base):
        for ext in ['.png', '.jpg', '.jpeg']:
            if os.path.exists(nombre_base + ext): return nombre_base + ext
        return None

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")
    
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

    # --- CLASE PDF ---
    class PDF(FPDF):
        def __init__(self, correlativo=""):
            super().__init__()
            self.correlativo = correlativo
        def header(self):
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

    # ==========================================
    # 2. INTERFAZ DE USUARIO (UI)
    # ==========================================
    col_centro = st.columns([1, 3, 1])

    with col_centro[1]:
        c_logo, c_btn = st.columns([3, 1], vertical_alignment="center")
        with c_logo:
            logo_app = encontrar_imagen("logo_pascual") 
            if logo_app: st.image(logo_app, width=200)
            else: st.title("🪟 Pascual Parabrisas")
        with c_btn:
            if st.button("🗑️ Limpiar Todo", type="primary", use_container_width=True): reset_session()
        st.divider()

        # DATOS VEHÍCULO
        st.markdown("#### 🚗 1. Datos del Vehículo")
        c_v1, c_v2, c_v3, c_v4 = st.columns(4)
        
        lista_marcas = list(BASE_VEHICULOS.keys())
        if "--- AGREGAR OTRA MARCA ---" not in lista_marcas: lista_marcas.append("--- AGREGAR OTRA MARCA ---")
        marca_sel = c_v1.selectbox("Marca", lista_marcas, key="v_marca")
        
        if marca_sel == "--- AGREGAR OTRA MARCA ---":
            marca_final = c_v1.text_input("Marca Man:", key="v_marca_man").upper()
            modelos_lista = ["--- AGREGAR OTRO MODELO ---"]
        else:
            marca_final = marca_sel
            modelos_lista = BASE_VEHICULOS.get(marca_sel, ["---"]).copy()
            if "--- AGREGAR OTRO MODELO ---" not in modelos_lista: modelos_lista.append("--- AGREGAR OTRO MODELO ---")
                
        modelo_sel = c_v2.selectbox("Modelo", modelos_lista, key="v_modelo")
        modelo_final = c_v2.text_input("Modelo Man:", key="v_mod_man").upper() if modelo_sel == "--- AGREGAR OTRO MODELO ---" else modelo_sel
            
        anio_sel = c_v3.selectbox("Año", ["---"] + list(range(2027, 1980, -1)), key="v_anio")
        patente_final = c_v4.text_input("Patente", key="v_pat").upper()

        st.divider()

        # SELECTOR DE CRISTALES (REJILLA UNIVERSAL)
        st.markdown("#### 🪟 2. Trabajos y Repuestos")
        tab1, tab2 = st.tabs(["📦 Selector de Cristales", "🔧 Servicios Extras"])
        
        with tab1:
            st.markdown("<div style='text-align: center; color: gray; font-weight: bold;'>PRINCIPALES</div>", unsafe_allow_html=True)
            cf1, cf2 = st.columns(2)
            if cf1.button("🟩 PARABRISAS", type=btn_type("PARABRISAS"), use_container_width=True): toggle_cristal("PARABRISAS")
            if cf2.button("🟦 LUNETA TRASERA", type=btn_type("LUNETA TRASERA"), use_container_width=True): toggle_cristal("LUNETA TRASERA")

            st.markdown("<div style='text-align: center; color: gray; font-weight: bold; margin-top: 10px;'>LATERALES</div>", unsafe_allow_html=True)
            c_d1, c_d2, c_d3, c_d4 = st.columns(4)
            if c_d1.button("Aleta D. Izq", type=btn_type("ALETA DEL. IZQ."), use_container_width=True): toggle_cristal("ALETA DEL. IZQ.")
            if c_d2.button("Ventana D. Izq", type=btn_type("VENTANA DEL. IZQ."), use_container_width=True): toggle_cristal("VENTANA DEL. IZQ.")
            if c_d3.button("Ventana D. Der", type=btn_type("VENTANA DEL. DER."), use_container_width=True): toggle_cristal("VENTANA DEL. DER.")
            if c_d4.button("Aleta D. Der", type=btn_type("ALETA DEL. DER."), use_container_width=True): toggle_cristal("ALETA DEL. DER.")

            c_e1, c_e2 = st.columns(2)
            if c_e1.button("Ventana Lateral Izq", type=btn_type("VENTANA LATERAL IZQUIERDA"), use_container_width=True): toggle_cristal("VENTANA LATERAL IZQUIERDA")
            if c_e2.button("Ventana Lateral Der", type=btn_type("VENTANA LATERAL DERECHA"), use_container_width=True): toggle_cristal("VENTANA LATERAL DERECHA")
            
            cristales_a_procesar = st.session_state.cristales_sel if st.session_state.cristales_sel else ["CRISTAL / REPUESTO"]
            for i, cristal in enumerate(cristales_a_procesar):
                desc_sug = f"{cristal} {marca_final} {modelo_final}".strip()
                col_p1, col_p2, col_p3 = st.columns([3, 1, 1.5])
                d_p = col_p1.text_input(f"Descripción Item {i}", value=desc_sug, key=f"d_p_{cristal}_{i}")
                q_p = col_p2.number_input("Cant.", 1, 10, key=f"q_p_{cristal}_{i}")
                p_p = col_p3.number_input("Unitario c/IVA $", 0, step=5000, key=f"p_p_{cristal}_{i}")
                if st.button(f"➕ Agregar {cristal}", key=f"btn_add_{cristal}_{i}", use_container_width=True):
                    st.session_state.items_productos.append({"Descripción": d_p, "Cantidad": q_p, "Unitario": p_p, "Total": p_p * q_p})
                    st.session_state.cristales_sel = []; st.rerun()

        with tab2:
            c_sf1, c_sf2, c_sf3, c_sf4 = st.columns(4)
            if c_sf1.button("Instalación", use_container_width=True): st.session_state.servicio_desc = "INSTALACIÓN DE CRISTAL"
            if c_sf2.button("Piquete", use_container_width=True): st.session_state.servicio_desc = "REPARACIÓN DE PIQUETE"
            if c_sf3.button("Polarizado", use_container_width=True): st.session_state.servicio_desc = "SERVICIO DE POLARIZADO"
            if c_sf4.button("Grabado", use_container_width=True): st.session_state.servicio_desc = "GRABADO DE PATENTES"
            
            col_s1, col_s2, col_s3 = st.columns([3, 1, 1.5])
            d_s = col_s1.text_input("Servicio", value=st.session_state.servicio_desc)
            q_s = col_s2.number_input("Cant.", 1, 10, key="q_serv")
            p_s = col_s3.number_input("Unitario c/IVA $", 0, step=5000, key="p_serv")
            if st.button("➕ Agregar Servicio", use_container_width=True):
                st.session_state.items_servicios.append({"Descripción": d_s, "Cantidad": q_s, "Unitario": p_s, "Total": p_s * q_s})
                st.rerun()

        # TOTAL Y WHATSAPP
        total_bruto = sum(x['Total'] for x in st.session_state.items_productos + st.session_state.items_servicios)
        if total_bruto > 0:
            st.divider()
            st.markdown("#### 📱 3. Resumen y Envío Rápido")
            desc_pct = st.number_input("Descuento Global %", 0, 100, 0)
            t_final = total_bruto * (1 - desc_pct/100)
            st.subheader(f"TOTAL CON IVA: {format_clp(t_final)}")

            # MENSAJE WHATSAPP OPTIMIZADO
            veh = f"{marca_final} {modelo_final}".strip() or "su vehículo"
            msg = f"Te adjuntamos el presupuesto para {veh}:\n\n"
            for i in st.session_state.items_productos + st.session_state.items_servicios:
                msg += f"🔹 {i['Cantidad']}x {i['Descripción']}: {format_clp(i['Total'])}\n"
            if desc_pct > 0: msg += f"Descuento aplicado: {desc_pct}%\n"
            msg += f"\nTotal con IVA: *{format_clp(t_final)}*\n\n- Pascual Parabrisas"
            
            st.info("Copia el texto aquí mismo 👇")
            st.code(msg, language="text")

            # BASUREROS
            for idx, item in enumerate(st.session_state.items_productos + st.session_state.items_servicios):
                ca, cb = st.columns([5, 1])
                ca.write(f"• {item['Cantidad']}x {item['Descripción']}")
                if cb.button("🗑️", key=f"del_{idx}"):
                    if idx < len(st.session_state.items_productos): st.session_state.items_productos.pop(idx)
                    else: st.session_state.items_servicios.pop(idx - len(st.session_state.items_productos))
                    st.rerun()

        # COTIZACIÓN FORMAL (PDF)
        st.divider()
        with st.expander("🏢 Generar Cotización Formal (PDF)"):
            cli_nombre = st.text_input("Razón Social / Cliente")
            cli_rut = st.text_input("RUT Cliente")
            if st.button("💾 GENERAR PDF Y RESPALDAR", type="primary", use_container_width=True):
                if not cli_nombre: st.error("Ingresa el nombre del cliente.")
                else:
                    corr = obtener_y_registrar_correlativo(cli_nombre, format_clp(t_final))
                    
                    pdf = PDF(correlativo=corr)
                    pdf.add_page()
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(190, 10, f"Señor(es): {cli_nombre.upper()}", 0, 1)
                    pdf.cell(190, 10, f"Vehículo: {marca_final} {modelo_final} - Patente: {patente_final}", 0, 1)
                    pdf.ln(5)
                    for i in st.session_state.items_productos + st.session_state.items_servicios:
                        pdf.cell(130, 8, i['Descripción'], 1); pdf.cell(20, 8, str(i['Cantidad']), 1, 0, 'C'); pdf.cell(40, 8, format_clp(i['Total']), 1, 1, 'R')
                    pdf.ln(5)
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(150, 10, "TOTAL CON IVA", 0); pdf.cell(40, 10, format_clp(t_final), 0, 1, 'R')
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    nombre_pdf = f"Cot_Pascual_{corr}.pdf"
                    
                    exito, msj = enviar_correo(", ".join(DESTINATARIOS_BODEGA), f"Respaldo: {nombre_pdf}", f"Cliente: {cli_nombre}\nTotal: {format_clp(t_final)}", pdf_bytes, nombre_pdf, EMAIL_REMITENTE_SISTEMA)
                    st.session_state.pdf_ready = {"pdf": pdf_bytes, "nombre": nombre_pdf, "exito": exito, "msj": msj, "corr": corr}
                    st.rerun()

            if 'pdf_ready' in st.session_state:
                d = st.session_state.pdf_ready
                st.success(f"✅ Cotización N° {d['corr']} generada.")
                if d['exito']: st.info("☁️ Respaldo enviado por correo.")
                else: st.warning(f"⚠️ Error de respaldo: {d['msj']}")
                st.download_button("📥 Descargar PDF", d['pdf'], d['nombre'], use_container_width=True)

if __name__ == "__main__":
    render_app()
