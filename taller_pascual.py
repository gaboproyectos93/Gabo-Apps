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

    # ==========================================
    # 2. FUNCIONES BACKEND Y NUBE
    # ==========================================
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
                remitente_sistema = st.secrets["email"]["user"]
                password = st.secrets["email"]["password"]
                msg = MIMEMultipart()
                msg['From'] = f"Sistema Cotizaciones Pascual Parabrisas <{remitente_sistema}>"
                msg['To'] = destinatario
                msg['Subject'] = asunto
                msg.add_header('reply-to', email_real_local) 
                msg.attach(MIMEText(mensaje_texto, 'plain'))
                adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
                adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
                msg.attach(adjunto)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(remitente_sistema, password)
                server.send_message(msg)
                server.quit()
                return True, "Correo enviado exitosamente."
            return False, "⚠️ Faltan credenciales del sistema de correos en Secrets."
        except Exception as e: return False, str(e)

    @st.cache_data(ttl=60)
    def cargar_directorio_patentes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Directorio_Patentes")
                data = ws.get_all_records()
                if data: return pd.DataFrame(data)
            except: pass
        return pd.DataFrame(columns=["Patente", "Institucion"])

    @st.cache_data(ttl=3600)
    def cargar_base_vehiculos():
        base_por_defecto = {
            "--- Seleccione Marca ---": ["---"],
            "Chevrolet": ["Sail", "Spark", "Tracker", "Colorado", "Silverado", "D-Max", "Captiva"],
            "Toyota": ["Yaris", "Hilux", "RAV4", "Corolla", "Auris", "4Runner"],
            "Hyundai": ["Accent", "Tucson", "Santa Fe", "Elantra", "Creta", "Grand i10", "H-1", "Porter"],
            "Kia": ["Morning", "Rio", "Cerato", "Sportage", "Sorento", "Frontier"],
            "Nissan": ["Versa", "Sentra", "Qashqai", "X-Trail", "NP300", "Navara"],
            "Suzuki": ["Swift", "Baleno", "Vitara", "Grand Nomade", "Jimny"],
            "Peugeot": ["208", "2008", "308", "3008", "Partner", "Boxer"],
            "Ford": ["Ranger", "F-150", "Territory", "Escape", "Explorer"],
            "Subaru": ["XV", "Forester", "Outback", "Crosstrek", "Impreza"],
            "Mercedes-Benz": ["Clase A", "Clase C", "Sprinter", "Vito"]
        }
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
        except: pass 
        return base_por_defecto

    BASE_VEHICULOS = cargar_base_vehiculos()

    def limpiar_patente(texto): return re.sub(r'[^A-Z0-9]', '', str(texto).upper())

    def formato_rut_chileno(rut):
        rut_limpio = re.sub(r'[^0-9Kk]', '', str(rut).upper())
        if len(rut_limpio) <= 1: return rut_limpio
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]
        try:
            cuerpo_fmt = f"{int(cuerpo):,}".replace(",", ".")
            return f"{cuerpo_fmt}-{dv}"
        except: return rut_limpio

    def formato_patente_chilena(patente):
        pat = re.sub(r'[^A-Z0-9]', '', str(patente).upper())
        if len(pat) == 6:
            if pat[2].isalpha(): return f"{pat[:4]}-{pat[4:]}"
            else: return f"{pat[:2]}-{pat[2:]}"
        return pat

    def obtener_y_registrar_correlativo(cliente, total):
        client = conectar_google_sheets()
        if client:
            try:
                spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: worksheet_hist = spreadsheet.worksheet("Historial")
                except:
                    worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="4")
                    worksheet_hist.append_row(["Fecha", "Correlativo", "Cliente", "Total"])
                datos = worksheet_hist.get_all_values()
                numero_actual = len(datos) 
                correlativo_str = str(1000 + numero_actual)
                worksheet_hist.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), correlativo_str, cliente.upper(), total])
                return correlativo_str
            except Exception: return "ERR"
        return "OFFLINE"

    @st.cache_data(ttl=60)
    def obtener_clientes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: ws = sheet.worksheet("Clientes")
                except:
                    ws = sheet.add_worksheet(title="Clientes", rows="100", cols="8")
                    ws.append_row(["RUT", "Nombre", "Direccion", "Ciudad", "Comuna", "Giro", "Contacto", "Fono"])
                return ws.get_all_records()
            except Exception: pass
        return []

    def guardar_cliente_nuevo(rut, nombre, direccion, ciudad, comuna, giro, contacto, fono):
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Clientes")
                records = ws.get_all_records()
                existe = any(str(r['RUT']).upper() == str(rut).upper() for r in records)
                if not existe:
                    ws.append_row([rut, nombre, direccion, ciudad, comuna, giro, contacto, fono])
                    st.cache_data.clear() 
            except Exception: pass

    def encontrar_imagen(nombre_base):
        for ext in ['.jpg', '.png', '.jpeg']:
            if os.path.exists(nombre_base + ext): return nombre_base + ext
        return None

    def format_clp(value):
        try: return f"${float(value):,.0f}".replace(",", ".")
        except: return "$0"

    # ==========================================
    # 3. LÓGICA DE SELECCIÓN Y ESTADO
    # ==========================================
    if 'cristales_sel' not in st.session_state: st.session_state.cristales_sel = []
    if 'servicio_desc' not in st.session_state: st.session_state.servicio_desc = "INSTALACIÓN DE CRISTAL"
    if 'items_productos' not in st.session_state: st.session_state.items_productos = []
    if 'items_servicios' not in st.session_state: st.session_state.items_servicios = []

    def toggle_cristal(cristal):
        if cristal in st.session_state.cristales_sel: st.session_state.cristales_sel.remove(cristal)
        else: st.session_state.cristales_sel.append(cristal)
            
    def set_servicio(servicio): st.session_state.servicio_desc = servicio
    def btn_type(cristal): return "primary" if cristal in st.session_state.cristales_sel else "secondary"

    def reset_session():
        st.session_state.cristales_sel = []
        st.session_state.items_productos = []
        st.session_state.items_servicios = []
        if 'presupuesto_generado' in st.session_state: del st.session_state['presupuesto_generado']
        st.rerun()

    # ==========================================
    # 4. CLASE PDF (DISEÑO COMPLETO RESTAURADO)
    # ==========================================
    class PDF(FPDF):
        def __init__(self, correlativo=""):
            super().__init__()
            self.correlativo = correlativo

        def header(self):
            logo_path = encontrar_imagen("logo_pascual") 
            if logo_path: self.image(logo_path, x=10, y=15, w=50) 
            
            self.set_xy(10, 40)
            self.set_font('Arial', 'B', 9); self.cell(120, 4, EMPRESA_NOMBRE, 0, 1, 'L')
            self.set_font('Arial', '', 8)
            self.cell(120, 4, EMPRESA_GIRO, 0, 1, 'L') 
            self.cell(120, 4, f"C.M.: {DIRECCION}", 0, 1, 'L')
            self.set_font('Arial', 'B', 9); self.cell(120, 4, f"R.U.T.: {RUT_EMPRESA}", 0, 1, 'L')

            self.set_xy(140, 15)
            self.set_text_color(255, 108, 21) 
            self.set_draw_color(255, 108, 21)
            self.set_line_width(0.4)
            
            self.set_font('Arial', 'B', 16)
            self.cell(60, 10, "COTIZACIÓN", 'LTR', 1, 'C') 
            
            self.set_x(140)
            self.set_font('Arial', 'B', 14)
            titulo = f"N° {self.correlativo}" if self.correlativo else "N° BORRADOR"
            self.cell(60, 10, titulo, 'LBR', 1, 'C')
            
            self.set_text_color(0, 0, 0)
            self.set_draw_color(0, 0, 0)
            self.set_line_width(0.2)
            self.ln(15) 

        def footer(self):
            self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(150, 150, 150)
            self.cell(0, 5, "Documento generado por Sistema Pascual Parabrisas", 0, 1, 'L')

    def generar_pdf_pascual(datos_cliente, datos_vehiculo, productos, servicios, descuento_pct, correlativo_final):
        pdf = PDF(correlativo=correlativo_final)
        pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20) 
        
        pdf.set_y(63)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(190, 5, f"VENDEDOR: {str(datos_cliente.get('vendedor', '')).upper()}", 0, 1, 'R')

        def fila_dinamica_cliente(lbl1, val1, lbl2, val2, is_last=False):
            start_y = pdf.get_y(); pdf.set_font('Arial', 'B', 9); pdf.set_xy(10, start_y); pdf.cell(25, 6, lbl1, 0, 0, 'L')
            pdf.set_font('Arial', '', 9); pdf.set_xy(35, start_y); pdf.multi_cell(85, 6, f": {val1}", 0, 'L'); y_left = pdf.get_y()
            pdf.set_font('Arial', 'B', 9); pdf.set_xy(120, start_y); pdf.cell(28, 6, lbl2, 0, 0, 'L')
            pdf.set_font('Arial', '', 9); pdf.set_xy(148, start_y); pdf.multi_cell(52, 6, f": {val2}", 0, 'L'); y_right = pdf.get_y()
            max_y = max(y_left, y_right, start_y + 6); pdf.line(10, start_y, 10, max_y); pdf.line(200, start_y, 200, max_y) 
            if is_last: pdf.line(10, max_y, 200, max_y) 
            pdf.set_xy(10, max_y)

        def fila_dinamica_vehiculo(lbl1, val1, lbl2, val2, is_last=False):
            start_y = pdf.get_y(); pdf.set_font('Arial', 'B', 9); pdf.set_xy(10, start_y); pdf.cell(25, 6, lbl1, 0, 0, 'L')
            pdf.set_font('Arial', '', 9); pdf.set_xy(35, start_y); pdf.multi_cell(70, 6, f": {val1}", 0, 'L'); y_left = pdf.get_y(); y_right = start_y
            if lbl2:
                pdf.set_font('Arial', 'B', 9); pdf.set_xy(105, start_y); pdf.cell(25, 6, lbl2, 0, 0, 'L')
                pdf.set_font('Arial', '', 9); pdf.set_xy(130, start_y); pdf.multi_cell(70, 6, f": {val2}", 0, 'L'); y_right = pdf.get_y()
            max_y = max(y_left, y_right, start_y + 6); pdf.line(10, start_y, 10, max_y); pdf.line(200, start_y, 200, max_y)
            if is_last: pdf.line(10, max_y, 200, max_y)
            pdf.set_xy(10, max_y)

        pdf.set_y(70); pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(230, 230, 230); pdf.cell(190, 6, "  DATOS DEL CLIENTE", 1, 1, 'L', 1)
        fila_dinamica_cliente(" Señor(es)", str(datos_cliente.get('nombre', '')).upper(), " Fecha Emisión", datetime.now().strftime('%d/%m/%Y'))
        fila_dinamica_cliente(" RUT", str(datos_cliente.get('rut', '')).upper(), " Teléfono", str(datos_cliente.get('fono', '')))
        fila_dinamica_cliente(" Dirección", str(datos_cliente.get('direccion', '')).upper(), " Forma de Pago", str(datos_cliente.get('pago', '')).upper())
        fila_dinamica_cliente(" Ciudad", str(datos_cliente.get('ciudad', '')).upper(), " Comuna", str(datos_cliente.get('comuna', '')).upper())
        fila_dinamica_cliente(" Giro", str(datos_cliente.get('giro', '')).upper(), " Contacto", str(datos_cliente.get('contacto', '')).upper(), is_last=True)
        pdf.ln(4)
        
        pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(230, 230, 230); pdf.cell(190, 6, "  DATOS DEL VEHÍCULO", 1, 1, 'L', 1)
        fila_dinamica_vehiculo(" Marca", str(datos_vehiculo.get('marca', '')).upper(), " Modelo", str(datos_vehiculo.get('modelo', '')).upper())
        tiene_siniestro = bool(datos_vehiculo.get('siniestro', ''))
        fila_dinamica_vehiculo(" Año", str(datos_vehiculo.get('anio', '')), " Patente", str(datos_vehiculo.get('patente', '')).upper(), is_last=not tiene_siniestro)
        if tiene_siniestro: fila_dinamica_vehiculo(" N° Siniestro", str(datos_vehiculo.get('siniestro', '')).upper(), "", "", is_last=True)
        pdf.ln(6)

        pdf.set_font('Arial', 'B', 9); pdf.set_fill_color(230, 230, 230)
        pdf.cell(130, 7, "Descripción", 1, 0, 'C', 1); pdf.cell(15, 7, "Cant.", 1, 0, 'C', 1); pdf.cell(45, 7, "Total", 1, 1, 'C', 1)
        
        total_descuento_aplicado = 0; total_bruto_sin_desc = 0

        def imprimir_fila_item(desc, cant, total):
            x = pdf.get_x(); y = pdf.get_y(); pdf.multi_cell(130, 6, desc, 1, 'L'); h = pdf.get_y() - y; pdf.set_xy(x + 130, y)
            monto_desc_item = total * (descuento_pct / 100.0); total_final_item = total - monto_desc_item
            pdf.cell(15, h, str(cant), 1, 0, 'C'); pdf.cell(45, h, format_clp(total_final_item), 1, 1, 'R'); pdf.set_xy(x, y + h)
            return monto_desc_item

        if productos:
            pdf.set_font('Arial', 'B', 8); pdf.set_fill_color(245, 245, 245); pdf.cell(190, 5, "  PRODUCTOS / REPUESTOS", 1, 1, 'L', 1); pdf.set_font('Arial', '', 9)
            for item in productos:
                monto_desc = imprimir_fila_item(item['Descripción'].upper(), item['Cantidad'], item['Total'])
                total_descuento_aplicado += monto_desc; total_bruto_sin_desc += item['Total']
                
        if servicios:
            pdf.set_font('Arial', 'B', 8); pdf.set_fill_color(245, 245, 245); pdf.cell(190, 5, "  MANO DE OBRA / SERVICIOS", 1, 1, 'L', 1); pdf.set_font('Arial', '', 9)
            for item in servicios:
                monto_desc = imprimir_fila_item(item['Descripción'].upper(), item['Cantidad'], item['Total'])
                total_descuento_aplicado += monto_desc; total_bruto_sin_desc += item['Total']

        total_final_a_pagar = total_bruto_sin_desc - total_descuento_aplicado
        neto = total_final_a_pagar / 1.19; iva = total_final_a_pagar - neto
        
        pdf.ln(5)
        pdf.set_x(140); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "SUB TOTAL", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(total_bruto_sin_desc), 1, 1, 'R')
        pdf.set_x(140); pdf.set_font('Arial', 'B', 9); texto_desc = f"DESC. ({descuento_pct}%)" if descuento_pct > 0 else "DESCUENTO"; pdf.cell(30, 6, texto_desc, 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(total_descuento_aplicado), 1, 1, 'R')
        pdf.set_x(140); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "NETO", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(neto), 1, 1, 'R')
        pdf.set_x(140); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "I.V.A. (19%)", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(iva), 1, 1, 'R')
        pdf.set_x(140); pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(230, 230, 230); pdf.cell(30, 8, "TOTAL", 1, 0, 'L', 1); pdf.cell(30, 8, format_clp(total_final_a_pagar), 1, 1, 'R', 1)

        return pdf.output(dest='S').encode('latin-1')

    # ==========================================
    # 5. UI PRINCIPAL MODO WHATSAPP
    # ==========================================
    col_centro = st.columns([1, 2, 1])

    with col_centro[1]:
        c_logo, c_btn = st.columns([3, 1], vertical_alignment="center")
        with c_logo:
            logo_app = encontrar_imagen("logo_pascual") 
            if logo_app: st.image(logo_app, width=200)
            else: st.title("🪟 Pascual Parabrisas")
        with c_btn:
            if st.button("🗑️ Limpiar Todo", type="primary", use_container_width=True): reset_session()
        st.markdown("---")

        # --- SECCIÓN 1: VEHÍCULO RÁPIDO ---
        st.markdown("#### 🚗 1. Datos del Vehículo")
        c_v1, c_v2, c_v3, c_v4 = st.columns(4)
        
        lista_marcas = list(BASE_VEHICULOS.keys())
        if "--- AGREGAR OTRA MARCA ---" not in lista_marcas: lista_marcas.append("--- AGREGAR OTRA MARCA ---")
        marca_sel = c_v1.selectbox("Marca", lista_marcas, key="v_marca")
        
        if marca_sel == "--- AGREGAR OTRA MARCA ---":
            marca_final = c_v1.text_input("Escriba la Marca:", placeholder="Ej: Motorhome", key="v_marca_man").upper()
            modelos_lista = ["--- AGREGAR OTRO MODELO ---"]
        else:
            marca_final = marca_sel
            modelos_lista = BASE_VEHICULOS.get(marca_sel, ["---"]).copy()
            if "--- AGREGAR OTRO MODELO ---" not in modelos_lista: modelos_lista.append("--- AGREGAR OTRO MODELO ---")
                
        modelo_sel = c_v2.selectbox("Modelo", modelos_lista, key="v_modelo")
        if modelo_sel == "--- AGREGAR OTRO MODELO ---": modelo_final = c_v2.text_input("Escriba el Modelo:", key="v_modelo_man").upper()
        else: modelo_final = modelo_sel
            
        lista_anios = ["---"] + list(range(2027, 1979, -1)) + ["OTRO (MÁS ANTIGUO)"]
        anio_sel = c_v3.selectbox("Año (Opcional)", lista_anios, key="v_anio")
        if anio_sel == "OTRO (MÁS ANTIGUO)": anio_final = c_v3.text_input("Escriba el Año:", key="v_anio_man")
        else: anio_final = anio_sel
            
        pat_texto = c_v4.text_input("Patente (Opcional)", placeholder="Ej: ABCD12").upper()
        patente_final = pat_texto
        if pat_texto and len(pat_texto) >= 2:
            df_p = cargar_directorio_patentes()
            if not df_p.empty:
                lista_p = sorted(list(set([str(x).strip().upper() for x in df_p['Patente'].dropna().tolist() if str(x).strip()])))
                matches = [p for p in lista_p if pat_texto in p and p != pat_texto]
                if matches:
                    sel_sug = c_v4.selectbox("💡 Sugerencias:", ["(Mantener lo que escribí)"] + matches, key="sug_pat")
                    if sel_sug != "(Mantener lo que escribí)": patente_final = sel_sug
        st.markdown("---")

        # --- SECCIÓN 2: PRODUCTOS Y SERVICIOS ---
        st.markdown("#### 🪟 2. Trabajos y Repuestos")
        tab1, tab2 = st.tabs(["📦 Selector de Cristales", "🔧 Servicios Extras"])
        
        with tab1:
            st.markdown("<div style='text-align: center; color: gray; font-size: 14px; font-weight: bold; margin-bottom: 5px;'>CRISTALES PRINCIPALES</div>", unsafe_allow_html=True)
            c_f1, c_f2 = st.columns(2)
            c_f1.button("🟩 PARABRISAS", type=btn_type("PARABRISAS"), use_container_width=True, on_click=toggle_cristal, args=("PARABRISAS",))
            c_f2.button("🟦 LUNETA TRASERA", type=btn_type("LUNETA TRASERA"), use_container_width=True, on_click=toggle_cristal, args=("LUNETA TRASERA",))

            st.markdown("<div style='text-align: center; color: gray; font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;'>LATERALES (PUERTAS Y COSTADOS)</div>", unsafe_allow_html=True)
            c_d1, c_d2, c_d3, c_d4 = st.columns(4)
            c_d1.button("Aleta Del. Izq", type=btn_type("ALETA DEL. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("ALETA DEL. IZQ.",))
            c_d2.button("Ventana Del. Izq", type=btn_type("VENTANA DEL. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA DEL. IZQ.",))
            c_d3.button("Ventana Del. Der", type=btn_type("VENTANA DEL. DER."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA DEL. DER.",))
            c_d4.button("Aleta Del. Der", type=btn_type("ALETA DEL. DER."), use_container_width=True, on_click=toggle_cristal, args=("ALETA DEL. DER.",))

            c_t1, c_t2, c_t3, c_t4 = st.columns(4)
            c_t1.button("Aleta Tras. Izq", type=btn_type("ALETA TRAS. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("ALETA TRAS. IZQ.",))
            c_t2.button("Ventana Tras. Izq", type=btn_type("VENTANA TRAS. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA TRAS. IZQ.",))
            c_t3.button("Ventana Tras. Der", type=btn_type("VENTANA TRAS. DER."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA TRAS. DER.",))
            c_t4.button("Aleta Tras. Der", type=btn_type("ALETA TRAS. DER."), use_container_width=True, on_click=toggle_cristal, args=("ALETA TRAS. DER.",))
            
            c_e1, c_e2 = st.columns(2)
            c_e1.button("Ventana Lateral Izq (Furgón/SUV)", type=btn_type("VENTANA LATERAL IZQUIERDA"), use_container_width=True, on_click=toggle_cristal, args=("VENTANA LATERAL IZQUIERDA",))
            c_e2.button("Ventana Lateral Der (Furgón/SUV)", type=btn_type("VENTANA LATERAL DERECHA"), use_container_width=True, on_click=toggle_cristal, args=("VENTANA LATERAL DERECHA",))

            st.markdown("<div style='text-align: center; color: gray; font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;'>OTROS CRISTALES</div>", unsafe_allow_html=True)
            c_o1, c_o2, c_o3 = st.columns([1, 2, 1])
            c_o2.button("⬜ SUNROOF / TECHO", type=btn_type("SUNROOF / TECHO PANORÁMICO"), use_container_width=True, on_click=toggle_cristal, args=("SUNROOF / TECHO PANORÁMICO",))
            
            st.markdown("---")

            camara_sel = "No"; sensor_sel = "No"
            if any("PARABRISAS" in c for c in st.session_state.cristales_sel):
                c_v4, c_v5 = st.columns(2)
                camara_sel = c_v4.radio("¿Tiene Cámara?", ["No", "Sí"], horizontal=True)
                sensor_sel = c_v5.radio("¿Sensor de Lluvia?", ["No", "Sí"], horizontal=True)

            cristales_a_procesar = st.session_state.cristales_sel if st.session_state.cristales_sel else ["OTRO CRISTAL / REPUESTO"]
            
            productos_temp = []
            for i, cristal in enumerate(cristales_a_procesar):
                desc_sugerida = cristal
                key_id = cristal.replace(" ", "_").replace("/", "_").replace(".", "")
                
                if marca_final and marca_final not in ["--- Seleccione Marca ---", "--- AGREGAR OTRA MARCA ---", "---"]: 
                    desc_sugerida += f" {marca_final}"
                if modelo_final and modelo_final not in ["---", "--- AGREGAR OTRO MODELO ---"]: 
                    desc_sugerida += f" {modelo_final}"
                if anio_final and anio_final not in ["---", "OTRO (MÁS ANTIGUO)"]: 
                    desc_sugerida += f" {anio_final}"
                    
                if "PARABRISAS" in cristal:
                    if camara_sel == "Sí": 
                        desc_sugerida += " C/CÁMARA"
                        key_id += "_cam"
                    if sensor_sel == "Sí": 
                        desc_sugerida += " C/SENSOR"
                        key_id += "_sen"
                
                col_p1, col_p2, col_p3 = st.columns([3, 1, 1.5])
                d_p = col_p1.text_input(f"Descripción", value=desc_sugerida, key=f"d_p_{key_id}")
                q_p = col_p2.number_input("Cant.", min_value=1, value=1, key=f"q_p_{key_id}")
                p_p = col_p3.number_input("Valor Unit. c/IVA ($)", min_value=0, step=5000, key=f"p_p_{key_id}")
                
                productos_temp.append({"desc": d_p, "cant": q_p, "precio": p_p})
            
            if st.button("➕ Agregar Producto al Resumen", use_container_width=True):
                for p in productos_temp:
                    if p['desc'] and p['precio'] > 0:
                        st.session_state.items_productos.append({
                            "Descripción": p['desc'], 
                            "Cantidad": p['cant'], 
                            "Unitario": p['precio'], 
                            "Total": p['precio'] * p['cant']
                        })
                st.session_state.cristales_sel = []; st.rerun()

            if st.session_state.items_productos:
                st.markdown("###### Agregados:")
                for idx, item in enumerate(st.session_state.items_productos):
                    col_a, col_b = st.columns([5, 1], vertical_alignment="center")
                    cant_txt = f"{item['Cantidad']}x " if item['Cantidad'] > 1 else ""
                    col_a.text(f"• {cant_txt}{item['Descripción']} | {format_clp(item['Total'])}")
                    if col_b.button("🗑️", key=f"del_prod_{idx}"): st.session_state.items_productos.pop(idx); st.rerun()

        with tab2:
            c_sf1, c_sf2, c_sf3, c_sf4 = st.columns(4)
            c_sf1.button("Instalación", use_container_width=True, on_click=set_servicio, args=("INSTALACIÓN DE CRISTAL",))
            c_sf2.button("Reparación Piquete", use_container_width=True, on_click=set_servicio, args=("REPARACIÓN DE PIQUETE",))
            c_sf3.button("Polarizado", use_container_width=True, on_click=set_servicio, args=("SERVICIO DE POLARIZADO",))
            c_sf4.button("Grabado Patentes", use_container_width=True, on_click=set_servicio, args=("GRABADO DE PATENTES",))
            
            col_s1, col_s2, col_s3 = st.columns([3, 1, 1.5])
            d_s = col_s1.text_input("Descripción", value=st.session_state.servicio_desc)
            q_s = col_s2.number_input("Cant.", min_value=1, value=1, key="q_serv_gen")
            p_s = col_s3.number_input("Valor Unit. c/IVA ($)", min_value=0, step=5000, key="p_serv_gen")
            
            if st.button("➕ Agregar Servicio al Resumen", use_container_width=True):
                if d_s and p_s > 0:
                    st.session_state.items_servicios.append({
                        "Descripción": d_s, 
                        "Cantidad": q_s, 
                        "Unitario": p_s, 
                        "Total": p_s * q_s
                    })
                    st.session_state.servicio_desc = ""; st.rerun()
                    
            if st.session_state.items_servicios:
                st.markdown("###### Agregados:")
                for idx, item in enumerate(st.session_state.items_servicios):
                    col_a, col_b = st.columns([5, 1], vertical_alignment="center")
                    cant_txt = f"{item['Cantidad']}x " if item['Cantidad'] > 1 else ""
                    col_a.text(f"• {cant_txt}{item['Descripción']} | {format_clp(item['Total'])}")
                    if col_b.button("🗑️", key=f"del_serv_{idx}"): st.session_state.items_servicios.pop(idx); st.rerun()

        # --- SECCIÓN 3: TOTAL Y WHATSAPP ---
        total_bruto = sum(x['Total'] for x in st.session_state.items_productos) + sum(x['Total'] for x in st.session_state.items_servicios)

        if total_bruto > 0:
            st.markdown("---")
            st.markdown("#### 📱 3. Resumen y Envío")
            c_tot1, c_tot2 = st.columns([1, 1])
            descuento_pct = c_tot1.number_input("Descuento Global (%)", min_value=0, max_value=100, value=0, step=1)
            total_final_vista = total_bruto * (1 - (descuento_pct / 100.0))
            c_tot2.subheader(f"📊 TOTAL CON IVA: {format_clp(total_final_vista)}")

            vehiculo_str = f"{marca_final if marca_final != '--- Seleccione Marca ---' else ''} {modelo_final if modelo_final != '---' else ''}".strip()
            if not vehiculo_str: vehiculo_str = "su vehículo"
            
            msg_wsp = f"Te adjuntamos el presupuesto para {vehiculo_str}:\n\n"
            for p in st.session_state.items_productos: 
                cant_txt = f"{p['Cantidad']}x " if p['Cantidad'] > 1 else ""
                msg_wsp += f"🔹 {cant_txt}{p['Descripción']}: {format_clp(p['Total'])}\n"
            for s in st.session_state.items_servicios: 
                cant_txt = f"{s['Cantidad']}x " if s['Cantidad'] > 1 else ""
                msg_wsp += f"🔸 {cant_txt}{s['Descripción']}: {format_clp(s['Total'])}\n"
                
            if descuento_pct > 0: msg_wsp += f"Descuento aplicado: {descuento_pct}%\n"
            msg_wsp += f"\nTotal con IVA: *{format_clp(total_final_vista)}*\n\n- Pascual Parabrisas"

            st.success("👇 Usa el ícono de copiar en la esquina superior derecha del cuadro gris y pégalo en WhatsApp:")
            st.code(msg_wsp, language="text")

            # --- SECCIÓN 4: PDF FORMAL (EXPANDER COMPLETAMENTE RESTAURADO) ---
            st.markdown("---")
            with st.expander("🏢 Habilitar Cotización Formal (PDF para Empresas / Seguros)", expanded=False):
                st.info("Solo llena estos datos si el cliente necesita el documento PDF con membrete y RUT.")
                
                clientes_db = obtener_clientes()
                clientes_dict = {}
                for c in clientes_db:
                    rut_str = str(c.get('RUT', '')).upper()
                    if rut_str and rut_str not in clientes_dict: 
                        clientes_dict[rut_str] = {'Nombre': c.get('Nombre', ''), 'RUT': c.get('RUT', ''), 'Direccion': c.get('Direccion', ''), 'Ciudad': c.get('Ciudad', ''), 'Comuna': c.get('Comuna', ''), 'Giro': c.get('Giro', ''), 'Contacto': c.get('Contacto', ''), 'Fono': c.get('Fono', '')}
                
                opciones_cli = ["--- Nuevo Cliente ---"] + [f"{datos['RUT']} | {datos['Nombre']}" for rut, datos in clientes_dict.items()]
                sel_cli = st.selectbox("Cargar cliente guardado:", opciones_cli)
                
                def_nombre = ""; def_rut = ""; def_dir = ""; def_ciu = "Temuco"; def_com = "Temuco"; def_giro = ""; def_contacto = ""; def_fono = ""
                if sel_cli != "--- Nuevo Cliente ---":
                    rut_buscado = sel_cli.split(" | ")[0]
                    cli_data = clientes_dict.get(rut_buscado)
                    if cli_data:
                        def_nombre = str(cli_data.get('Nombre', '')); def_rut = str(cli_data.get('RUT', '')); def_dir = str(cli_data.get('Direccion', '')); def_ciu = str(cli_data.get('Ciudad', '')); def_com = str(cli_data.get('Comuna', '')); def_giro = str(cli_data.get('Giro', '')); def_contacto = str(cli_data.get('Contacto', '')); def_fono = str(cli_data.get('Fono', ''))

                c_e1, c_e2 = st.columns([3, 1])
                cliente_final = c_e1.text_input("Señor(es) / Razón Social", value=def_nombre)
                rut_empresa = c_e2.text_input("RUT", value=def_rut)
                direccion = st.text_input("Dirección", value=def_dir)
                c_c1, c_c2 = st.columns(2)
                ciudad = c_c1.text_input("Ciudad", value=def_ciu)
                comuna = c_c2.text_input("Comuna", value=def_com)
                giro = st.text_input("Giro Comercial", value=def_giro)
                c_f1, c_f2 = st.columns(2)
                contacto_nombre = c_f1.text_input("Nombre Contacto", value=def_contacto)
                contacto_fono = c_f2.text_input("Teléfono", value=def_fono)
                
                c_p1, c_p2 = st.columns(2)
                condicion_pago = c_p1.selectbox("Forma de Pago", ["Transferencia Electrónica", "Efectivo / Contado", "Tarjeta (Débito/Crédito)", "Orden de Compra (O/C)", "Crédito Directo a 30 días"])
                vendedor_nombre = c_p2.text_input("Vendedor", value="ANA MARIA RIQUELME")
                siniestro_val = st.text_input("N° de Siniestro (Si aplica)")

                if 'presupuesto_generado' not in st.session_state:
                    if st.button("💾 GENERAR PDF FORMAL", type="primary", use_container_width=True):
                        if not cliente_final: st.error("⛔ Ingresa al menos el nombre o Razón Social del cliente.")
                        else:
                            guardar_cliente_nuevo(formato_rut_chileno(rut_empresa), cliente_final.upper(), direccion.upper(), ciudad.upper(), comuna.upper(), giro.upper(), contacto_nombre.upper(), contacto_fono)
                            
                            correlativo = obtener_y_registrar_correlativo(cliente_final, format_clp(total_final_vista))
                            st.session_state['correlativo_temp'] = correlativo 
                            
                            datos_cliente = {"nombre": cliente_final.upper(), "rut": formato_rut_chileno(rut_empresa), "direccion": direccion.upper(), "ciudad": ciudad.upper(), "comuna": comuna.upper(), "giro": giro.upper(), "contacto": contacto_nombre.upper(), "fono": contacto_fono, "pago": condicion_pago, "vendedor": vendedor_nombre.upper()}
                            datos_vehiculo = {"marca": marca_final if marca_final not in ["--- Seleccione Marca ---", "--- AGREGAR OTRA MARCA ---", "---"] else "", "modelo": modelo_final if modelo_final not in ["---", "--- AGREGAR OTRO MODELO ---"] else "", "anio": anio_final if anio_final not in ["---", "OTRO (MÁS ANTIGUO)"] else "", "patente": formato_patente_chilena(patente_final), "siniestro": siniestro_val.upper()}
                            
                            pdf_bytes = generar_pdf_pascual(datos_cliente, datos_vehiculo, st.session_state.items_productos, st.session_state.items_servicios, descuento_pct, correlativo)
                            nombre_pdf = f"Cotizacion_{correlativo}_{patente_final if patente_final else cliente_final}.pdf"
                            
                            asunto_resp = f"📁 RESPALDO PASCUAL: {nombre_pdf}"
                            mensaje_resp = f"Copia de seguridad automática.\n\nVehículo: {datos_vehiculo['marca']} {datos_vehiculo['modelo']}\nCliente: {datos_cliente['nombre']}\nTotal: {format_clp(total_final_vista)}\n\nEl archivo PDF va adjunto."
                            
                            exito_resp, msj_resp = enviar_correo(", ".join(DESTINATARIOS_BODEGA), asunto_resp, mensaje_resp, pdf_bytes, nombre_pdf, EMAIL_REMITENTE_SISTEMA)
                            
                            st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': nombre_pdf, 'respaldo_ok': exito_resp, 'respaldo_msj': msj_resp}
                            st.rerun()
                else:
                    data = st.session_state['presupuesto_generado']
                    st.success(f"✅ PDF '{data['nombre']}' generado.")
                    if not data.get('respaldo_ok'): 
                        st.warning(f"⚠️ Error al respaldar en la nube: {data.get('respaldo_msj')}")
                    
                    c_d1, c_d2 = st.columns(2)
                    with c_d1: st.download_button("📥 DESCARGAR PDF", data['pdf'], data['nombre'], "application/pdf", type="primary", use_container_width=True)
                    with c_d2: 
                        if st.button("🔄 Crear PDF Nuevo", use_container_width=True): 
                            del st.session_state['presupuesto_generado']; st.rerun()

if __name__ == "__main__":
    render_app()
