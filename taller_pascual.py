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

def render_app():
    # ==========================================
    # 1. CONFIGURACIÓN Y CONSTANTES
    # ==========================================
    NOMBRE_HOJA_GOOGLE = "DB_Cotizador_Pascual"
    EMPRESA_NOMBRE = "LILY ISABEL UNDA CONTRERAS"
    EMPRESA_GIRO = "VENTA, FABRICACIÓN Y REPARACIÓN DE PARABRISAS Y SUS ACCESORIOS"
    RUT_EMPRESA = "8.810.453-6" 
    DIRECCION = "Caupolicán 0320 - Temuco" 
    COLOR_HEX = "#ff6c15"

    # Inyección de CSS para el Naranjo Pascual
    st.markdown(f"""
    <style>
        .stButton > button[kind="primary"] {{ 
            background-color: {COLOR_HEX} !important; 
            border-color: {COLOR_HEX} !important; 
            color: white !important; 
            font-weight: bold; 
        }}
        .stButton > button[kind="primary"]:hover {{ 
            background-color: #E65A0D !important; 
            border-color: #E65A0D !important; 
        }}
    </style>
    """, unsafe_allow_html=True)

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
        return {"--- Seleccione Marca ---": ["---"]}

    BASE_VEHICULOS = cargar_base_vehiculos()

    # --- FUNCIONES DE ESTADO Y UI ---
    if 'cristales_sel' not in st.session_state: st.session_state.cristales_sel = []
    if 'items_productos' not in st.session_state: st.session_state.items_productos = []
    if 'items_servicios' not in st.session_state: st.session_state.items_servicios = []
    if 'servicio_desc' not in st.session_state: st.session_state.servicio_desc = ""

    def toggle_cristal(cristal):
        if cristal in st.session_state.cristales_sel: 
            st.session_state.cristales_sel.remove(cristal)
        else: 
            st.session_state.cristales_sel.append(cristal)

    def set_servicio(servicio):
        st.session_state.servicio_desc = servicio

    def btn_type(cristal):
        return "primary" if cristal in st.session_state.cristales_sel else "secondary"

    def reset_session():
        keys_to_keep = ['logueado', 'perfil']
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]
                
        st.session_state.cristales_sel = []
        st.session_state.items_productos = []
        st.session_state.items_servicios = []
        st.session_state.servicio_desc = ""
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

    def encontrar_imagen(nombre_base):
        for ext in ['.png', '.jpg', '.jpeg']:
            if os.path.exists(nombre_base + ext): return nombre_base + ext
        return None

    def format_clp(v): return f"${float(v):,.0f}".replace(",", ".")
    
    def limpiar_patente(texto): return re.sub(r'[^A-Z0-9]', '', str(texto).upper())

    def formato_rut_chileno(rut):
        rut_limpio = re.sub(r'[^0-9Kk]', '', str(rut).upper())
        if len(rut_limpio) <= 1: return rut_limpio
        cuerpo = rut_limpio[:-1]; dv = rut_limpio[-1]
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
                try: ws = spreadsheet.worksheet("Historial")
                except: ws = spreadsheet.add_worksheet("Historial", 1000, 4)
                datos = ws.get_all_values()
                corr = str(1000 + len(datos))
                ws.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), corr, cliente.upper(), total])
                return corr
            except: return "ERR"
        return "OFFLINE"

    @st.cache_data(ttl=60)
    def obtener_clientes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: 
                    ws = sheet.worksheet("Clientes")
                    encabezados = ws.row_values(1)
                    if len(encabezados) < 8 or encabezados[6] != "Contacto":
                        ws.update_acell('G1', 'Contacto')
                        ws.update_acell('H1', 'Fono')
                except:
                    ws = sheet.add_worksheet(title="Clientes", rows="100", cols="8")
                    ws.append_row(["RUT", "Nombre", "Direccion", "Ciudad", "Comuna", "Giro", "Contacto", "Fono"])
                
                registros = ws.get_all_records()
                for r in registros:
                    contacto = str(r.get('Contacto', '')).strip()
                    fono = str(r.get('Fono', '')).strip()
                    if contacto and not fono and re.match(r'^[\d\+ \-]+$', contacto):
                        r['Fono'] = contacto
                        r['Contacto'] = ""
                return registros
            except Exception: pass
        return []

    def guardar_cliente_nuevo(rut, nombre, direccion, ciudad, comuna, giro, contacto, fono):
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Clientes")
                # Revisar si el cliente y ese contacto específico ya existen para no duplicar
                records = ws.get_all_records()
                existe = any(
                    str(r['RUT']).upper() == str(rut).upper() and 
                    str(r.get('Contacto', '')).upper() == str(contacto).upper() 
                    for r in records
                )
                if not existe:
                    ws.append_row([rut, nombre, direccion, ciudad, comuna, giro, contacto, fono])
                    st.cache_data.clear() 
            except Exception: pass

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
            self.cell(120, 4, f"C.M.: {DIRECCION}", 0, 1, 'L')
            self.set_font('Arial', 'B', 9); self.cell(120, 4, f"R.U.T.: {RUT_EMPRESA}", 0, 1, 'L')
            self.set_xy(140, 15); self.set_text_color(255, 108, 21)
            self.set_font('Arial', 'B', 15); self.cell(60, 10, "PRESUPUESTO", 'LTR', 1, 'C')
            self.set_x(140); self.set_font('Arial', 'B', 14)
            titulo = f"N° {self.correlativo}" if self.correlativo else "N° BORRADOR"
            self.cell(60, 10, titulo, 'LBR', 1, 'C')
            self.set_text_color(0, 0, 0); self.ln(15)
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

        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(90, 7, "Descripción", 1, 0, 'C', 1)
        pdf.cell(15, 7, "Cant.", 1, 0, 'C', 1)
        pdf.cell(25, 7, "Unitario", 1, 0, 'C', 1)
        pdf.cell(25, 7, "Desc. %", 1, 0, 'C', 1)
        pdf.cell(35, 7, "Total", 1, 1, 'C', 1)
        
        total_descuento_aplicado = 0
        total_bruto_sin_desc = 0

        def imprimir_fila_item(desc, cant, unitario, total_sin_desc):
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.multi_cell(90, 6, desc, 1, 'L')
            h = pdf.get_y() - y
            pdf.set_xy(x + 90, y)
            
            monto_desc_item = total_sin_desc * (descuento_pct / 100.0)
            total_final_item = total_sin_desc - monto_desc_item

            pdf.cell(15, h, str(cant), 1, 0, 'C')
            pdf.cell(25, h, format_clp(unitario), 1, 0, 'R')
            texto_desc_fila = f"{descuento_pct}%" if descuento_pct > 0 else "-"
            pdf.cell(25, h, texto_desc_fila, 1, 0, 'C')
            pdf.cell(35, h, format_clp(total_final_item), 1, 1, 'R')
            
            pdf.set_xy(x, y + h)
            return monto_desc_item, total_sin_desc

        if productos:
            pdf.set_font('Arial', 'B', 8)
            pdf.set_fill_color(245, 245, 245)
            pdf.cell(190, 5, "  PRODUCTOS / REPUESTOS", 1, 1, 'L', 1)
            pdf.set_font('Arial', '', 9)
            for item in productos:
                m_desc, t_sin_desc = imprimir_fila_item(item['Descripción'].upper(), item['Cantidad'], item['Unitario'], item['Total'])
                total_descuento_aplicado += m_desc
                total_bruto_sin_desc += t_sin_desc
                
        if servicios:
            pdf.set_font('Arial', 'B', 8)
            pdf.set_fill_color(245, 245, 245)
            pdf.cell(190, 5, "  MANO DE OBRA / SERVICIOS", 1, 1, 'L', 1)
            pdf.set_font('Arial', '', 9)
            for item in servicios:
                m_desc, t_sin_desc = imprimir_fila_item(item['Descripción'].upper(), item['Cantidad'], item['Unitario'], item['Total'])
                total_descuento_aplicado += m_desc
                total_bruto_sin_desc += t_sin_desc

        total_final_a_pagar = total_bruto_sin_desc - total_descuento_aplicado
        neto = total_final_a_pagar / 1.19
        iva = total_final_a_pagar - neto
        
        pdf.ln(5)
        pdf.set_x(130); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "SUB TOTAL", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(40, 6, format_clp(total_bruto_sin_desc), 1, 1, 'R')
        if descuento_pct > 0:
            pdf.set_x(130); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, f"DESC. ({descuento_pct}%)", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(40, 6, f"- {format_clp(total_descuento_aplicado)}", 1, 1, 'R')
        pdf.set_x(130); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "NETO", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(40, 6, format_clp(neto), 1, 1, 'R')
        pdf.set_x(130); pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "I.V.A. (19%)", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(40, 6, format_clp(iva), 1, 1, 'R')
        pdf.set_x(130); pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(230, 230, 230); pdf.cell(30, 8, "TOTAL A PAGAR", 1, 0, 'L', 1); pdf.cell(40, 8, format_clp(total_final_a_pagar), 1, 1, 'R', 1)

        return pdf.output(dest='S').encode('latin-1')

    # ==========================================
    # 5. INTERFAZ DE USUARIO (UI)
    # ==========================================
    col_centro = st.columns([1, 4, 1])

    with col_centro[1]:
        c_logo, c_btn = st.columns([3, 1], vertical_alignment="center")
        with c_logo:
            logo_app = encontrar_imagen("logo_pascual") 
            if logo_app: st.image(logo_app, width=200)
            else: st.title("🪟 Pascual Parabrisas")
        with c_btn:
            if st.button("🗑️ Limpiar", type="primary", use_container_width=True): reset_session()
        st.divider()

        st.markdown("#### 🚗 1. Datos del Vehículo")
        cv_1, cv_2 = st.columns(2)
        lista_marcas = list(BASE_VEHICULOS.keys())
        if "--- AGREGAR OTRA MARCA ---" not in lista_marcas: lista_marcas.append("--- AGREGAR OTRA MARCA ---")
        marca_sel = cv_1.selectbox("Marca", lista_marcas, key="v_marca")
        
        if marca_sel == "--- AGREGAR OTRA MARCA ---":
            marca_final = cv_1.text_input("Marca Man:", key="v_marca_man").upper()
            modelos_lista = ["--- AGREGAR OTRO MODELO ---"]
        else:
            marca_final = marca_sel
            modelos_lista = BASE_VEHICULOS.get(marca_sel, ["---"]).copy()
            if "--- AGREGAR OTRO MODELO ---" not in modelos_lista: modelos_lista.append("--- AGREGAR OTRO MODELO ---")
                
        modelo_sel = cv_2.selectbox("Modelo", modelos_lista, key="v_modelo")
        modelo_final = cv_2.text_input("Modelo Man:", key="v_mod_man").upper() if modelo_sel == "--- AGREGAR OTRO MODELO ---" else modelo_sel
            
        cv_3, cv_4 = st.columns(2)
        lista_anios = ["---"] + list(range(2027, 1979, -1)) + ["OTRO (MÁS ANTIGUO)"]
        anio_sel = cv_3.selectbox("Año", lista_anios, key="v_anio")
        anio_final = cv_3.text_input("Escriba el Año:", key="v_anio_man") if anio_sel == "OTRO (MÁS ANTIGUO)" else anio_sel
        patente_final = cv_4.text_input("Patente", key="v_pat").upper()

        st.divider()

        st.markdown("#### 🪟 2. Trabajos y Repuestos")
        tab1, tab2 = st.tabs(["📦 Cristales", "🔧 Servicios Extras"])
        
        with tab1:
            st.markdown("<div style='text-align: center; color: gray; font-weight: bold;'>PRINCIPALES</div>", unsafe_allow_html=True)
            cf1, cf2 = st.columns(2)
            cf1.button("🟩 PARABRISAS", type=btn_type("PARABRISAS"), use_container_width=True, on_click=toggle_cristal, args=("PARABRISAS",))
            cf2.button("🟦 LUNETA TRAS.", type=btn_type("LUNETA TRASERA"), use_container_width=True, on_click=toggle_cristal, args=("LUNETA TRASERA",))

            st.markdown("<div style='text-align: center; color: gray; font-weight: bold; margin-top: 10px;'>LATERALES</div>", unsafe_allow_html=True)
            cd_1, cd_2 = st.columns(2)
            cd_1.button("Aleta D. Izq", type=btn_type("ALETA DEL. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("ALETA DEL. IZQ.",))
            cd_2.button("Ventana D. Izq", type=btn_type("VENTANA DEL. IZQ."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA DEL. IZQ.",))
            
            cd_3, cd_4 = st.columns(2)
            cd_3.button("Ventana D. Der", type=btn_type("VENTANA DEL. DER."), use_container_width=True, on_click=toggle_cristal, args=("VENTANA DEL. DER.",))
            cd_4.button("Aleta D. Der", type=btn_type("ALETA DEL. DER."), use_container_width=True, on_click=toggle_cristal, args=("ALETA DEL. DER.",))

            ce_1, ce_2 = st.columns(2)
            ce_1.button("Ventana Lat. Izq", type=btn_type("VENTANA LATERAL IZQUIERDA"), use_container_width=True, on_click=toggle_cristal, args=("VENTANA LATERAL IZQUIERDA",))
            ce_2.button("Ventana Lat. Der", type=btn_type("VENTANA LATERAL DERECHA"), use_container_width=True, on_click=toggle_cristal, args=("VENTANA LATERAL DERECHA",))
            
            camara_sel = "No"
            sensor_sel = "No"
            if any("PARABRISAS" in c for c in st.session_state.cristales_sel):
                st.markdown("<div style='text-align: center; color: gray; font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;'>OPCIONES PARABRISAS</div>", unsafe_allow_html=True)
                c_cam, c_sen = st.columns(2)
                camara_sel = c_cam.radio("¿Cámara?", ["No", "Sí"], horizontal=True)
                sensor_sel = c_sen.radio("¿Sensor?", ["No", "Sí"], horizontal=True)

            cristales_a_procesar = st.session_state.cristales_sel if st.session_state.cristales_sel else ["CRISTAL / REPUESTO"]
            
            productos_temp = []
            for i, cristal in enumerate(cristales_a_procesar):
                st.markdown(f"**Ajuste de Ítem: {cristal}**")
                desc_sug = f"{cristal} {marca_final} {modelo_final}".strip()
                if "PARABRISAS" in cristal:
                    if camara_sel == "Sí": desc_sug += " C/CÁMARA"
                    if sensor_sel == "Sí": desc_sug += " C/SENSOR"
                    
                d_p = st.text_input(f"Descripción (Edita si quieres)", value=desc_sug, key=f"d_p_{cristal}_{i}")
                
                cp_1, cp_2 = st.columns(2)
                q_p = cp_1.number_input("Cant.", min_value=1, max_value=10, value=1, step=1, key=f"q_p_{cristal}_{i}")
                p_p = cp_2.number_input("Precio c/IVA $", min_value=0, step=1000, key=f"p_p_{cristal}_{i}")
                
                productos_temp.append({"desc": d_p, "cant": q_p, "precio": p_p})
                
            if st.button("➕ Agregar al Resumen", type="primary", use_container_width=True):
                for p in productos_temp:
                    if p['desc'] and p['precio'] >= 0:
                        st.session_state.items_productos.append({
                            "Descripción": p['desc'], 
                            "Cantidad": p['cant'], 
                            "Unitario": p['precio'], 
                            "Total": p['precio'] * p['cant']
                        })
                st.session_state.cristales_sel = []
                st.rerun()

        with tab2:
            cs_1, cs_2 = st.columns(2)
            cs_1.button("Instalación", use_container_width=True, on_click=set_servicio, args=("INSTALACIÓN DE CRISTAL",))
            cs_2.button("Piquete", use_container_width=True, on_click=set_servicio, args=("REPARACIÓN DE PIQUETE",))
            
            cs_3, cs_4 = st.columns(2)
            cs_3.button("Polarizado", use_container_width=True, on_click=set_servicio, args=("SERVICIO DE POLARIZADO",))
            cs_4.button("Grabado", use_container_width=True, on_click=set_servicio, args=("GRABADO DE PATENTES",))
            
            d_s = st.text_input("Descripción del Servicio", value=st.session_state.servicio_desc)
            
            ci_1, ci_2 = st.columns(2)
            q_s = ci_1.number_input("Cant.", min_value=1, max_value=10, value=1, step=1, key="q_serv")
            p_s = ci_2.number_input("Precio c/IVA $", min_value=0, step=1000, key="p_serv")
            
            if st.button("➕ Agregar Servicio", type="primary", use_container_width=True):
                if d_s and p_s >= 0:
                    st.session_state.items_servicios.append({"Descripción": d_s, "Cantidad": q_s, "Unitario": p_s, "Total": p_s * q_s})
                    st.session_state.servicio_desc = ""
                    st.rerun()

        total_bruto = sum(x['Total'] for x in st.session_state.items_productos + st.session_state.items_servicios)
        t_final = total_bruto
        desc_pct = 0
        
        if total_bruto > 0:
            st.divider()
            st.markdown("#### 📱 3. Resumen y Mensaje")
            
            desc_pct = st.number_input("Descuento Global %", min_value=0, max_value=100, value=0, step=5)
            t_final = total_bruto * (1 - desc_pct/100)
            st.subheader(f"TOTAL: {format_clp(t_final)}")

            veh = f"{marca_final} {modelo_final}".strip() or "su vehículo"
            msg = f"Te adjuntamos el presupuesto para {veh}:\n\n"
            for i in st.session_state.items_productos + st.session_state.items_servicios:
                msg += f"🔹 {i['Cantidad']}x {i['Descripción']}: {format_clp(i['Total'])}\n"
            if desc_pct > 0: msg += f"Descuento aplicado: {desc_pct}%\n"
            msg += f"\nTotal con IVA: *{format_clp(t_final)}*\n\n- Pascual Parabrisas"
            
            st.info("Copia el texto para WhatsApp 👇")
            st.code(msg, language="text")

            st.markdown("**Ítems Agregados (Toca la basura para borrar):**")
            for idx, item in enumerate(st.session_state.items_productos + st.session_state.items_servicios):
                ca, cb = st.columns([5, 1])
                ca.write(f"• {item['Cantidad']}x {item['Descripción']}")
                if cb.button("🗑️", key=f"del_{idx}"):
                    if idx < len(st.session_state.items_productos): st.session_state.items_productos.pop(idx)
                    else: st.session_state.items_servicios.pop(idx - len(st.session_state.items_productos))
                    st.rerun()

        # ==========================================
        # COTIZACIÓN FORMAL (PDF) CON MULTIPLES CONTACTOS
        # ==========================================
        st.divider()
        with st.expander("🏢 Generar PDF Formal"):
            st.info("Ingresa los datos para armar el PDF.")
            
            clientes_db = obtener_clientes()
            clientes_dict = {}
            
            # --- NUEVA LÓGICA DE DICCIONARIO (AGRUPA CONTACTOS) ---
            for c in clientes_db:
                rut_str = str(c.get('RUT', '')).upper()
                if rut_str:
                    if rut_str not in clientes_dict: 
                        dir_val = str(c.get('Direccion', c.get('Dirección', '')))
                        clientes_dict[rut_str] = {
                            'Nombre': c.get('Nombre', ''), 'RUT': c.get('RUT', ''), 
                            'Direccion': dir_val, 'Ciudad': c.get('Ciudad', ''), 
                            'Comuna': c.get('Comuna', ''), 'Giro': c.get('Giro', ''), 
                            'Contactos': [] # Lista para almacenar a Álvaro, Gabriel, etc.
                        }
                    
                    contacto_val = str(c.get('Contacto', ''))
                    fono_val = str(c.get('Fono', ''))
                    
                    # Evitamos agregar contactos vacíos o duplicados a la lista de esa empresa
                    contacto_existe = any(x['Contacto'] == contacto_val and x['Fono'] == fono_val for x in clientes_dict[rut_str]['Contactos'])
                    if not contacto_existe:
                        clientes_dict[rut_str]['Contactos'].append({'Contacto': contacto_val, 'Fono': fono_val})
            
            opciones_cli = ["--- Nuevo Cliente ---"] + [f"{datos['RUT']} | {datos['Nombre']}" for rut, datos in clientes_dict.items()]
            
            sel_cli = st.selectbox("Cargar cliente guardado:", opciones_cli, key="selector_cliente")
            
            # 1. Al cambiar de Empresa, actualizamos datos fijos e inicializamos con el 1er contacto
            if 'cliente_previo' not in st.session_state: st.session_state.cliente_previo = "--- Nuevo Cliente ---"
                
            if st.session_state.selector_cliente != st.session_state.cliente_previo:
                st.session_state.cliente_previo = st.session_state.selector_cliente
                sel = st.session_state.selector_cliente
                
                if sel != "--- Nuevo Cliente ---":
                    rut_buscado = sel.split(" | ")[0]
                    cli_data = clientes_dict.get(rut_buscado)
                    if cli_data:
                        st.session_state.c_nombre = str(cli_data.get('Nombre', ''))
                        st.session_state.c_rut = str(cli_data.get('RUT', ''))
                        st.session_state.c_dir = str(cli_data.get('Direccion', ''))
                        st.session_state.c_ciu = str(cli_data.get('Ciudad', ''))
                        st.session_state.c_com = str(cli_data.get('Comuna', ''))
                        st.session_state.c_giro = str(cli_data.get('Giro', ''))
                        
                        # Si tiene contactos, cargamos el primero por defecto
                        if cli_data['Contactos']:
                            st.session_state.c_con = str(cli_data['Contactos'][0]['Contacto'])
                            st.session_state.c_fon = str(cli_data['Contactos'][0]['Fono'])
                            st.session_state.contacto_previo = f"{cli_data['Contactos'][0]['Contacto']} - {cli_data['Contactos'][0]['Fono']}"
                else:
                    st.session_state.c_nombre = ""; st.session_state.c_rut = ""; st.session_state.c_dir = ""
                    st.session_state.c_ciu = "Temuco"; st.session_state.c_com = "Temuco"; st.session_state.c_giro = ""
                    st.session_state.c_con = ""; st.session_state.c_fon = ""

            # 2. Si la empresa seleccionada tiene múltiples contactos, mostramos el menú secundario
            if sel_cli != "--- Nuevo Cliente ---":
                rut_buscado = sel_cli.split(" | ")[0]
                contactos_empresa = clientes_dict.get(rut_buscado, {}).get('Contactos', [])
                
                if len(contactos_empresa) > 1:
                    st.markdown("👇 **Esta empresa tiene múltiples contactos. Elige uno:**")
                    opciones_contacto = [f"{c['Contacto']} - {c['Fono']}" for c in contactos_empresa]
                    
                    if 'contacto_previo' not in st.session_state:
                         st.session_state.contacto_previo = opciones_contacto[0]
                         
                    sel_contacto = st.selectbox("Seleccionar Contacto:", opciones_contacto, key="selector_contacto")
                    
                    # Si cambian el contacto en el menú secundario, actualizamos el texto y fono
                    if sel_contacto != st.session_state.contacto_previo:
                        st.session_state.contacto_previo = sel_contacto
                        idx_contacto = opciones_contacto.index(sel_contacto)
                        st.session_state.c_con = str(contactos_empresa[idx_contacto]['Contacto'])
                        st.session_state.c_fon = str(contactos_empresa[idx_contacto]['Fono'])

            st.divider()

            # --- INICIALIZACIÓN DE VARIABLES PARA LA UI ---
            if 'c_nombre' not in st.session_state: st.session_state.c_nombre = ""
            if 'c_rut' not in st.session_state: st.session_state.c_rut = ""
            if 'c_dir' not in st.session_state: st.session_state.c_dir = ""
            if 'c_ciu' not in st.session_state: st.session_state.c_ciu = "Temuco"
            if 'c_com' not in st.session_state: st.session_state.c_com = "Temuco"
            if 'c_giro' not in st.session_state: st.session_state.c_giro = ""
            if 'c_con' not in st.session_state: st.session_state.c_con = ""
            if 'c_fon' not in st.session_state: st.session_state.c_fon = ""

            # --- RENDERIZADO DEL FORMULARIO ---
            cliente_final = st.text_input("Señor(es) / Razón Social", key="c_nombre")
            rut_empresa = st.text_input("RUT", key="c_rut")
            direccion = st.text_input("Dirección", key="c_dir")
            
            c_c1, c_c2 = st.columns(2)
            ciudad = c_c1.text_input("Ciudad", key="c_ciu")
            comuna = c_c2.text_input("Comuna", key="c_com")
            
            giro = st.text_input("Giro Comercial", key="c_giro")
            
            c_f1, c_f2 = st.columns(2)
            contacto_nombre = c_f1.text_input("Nombre Contacto", key="c_con")
            contacto_fono = c_f2.text_input("Teléfono", key="c_fon")
            
            condicion_pago = st.selectbox("Forma de Pago", ["Transferencia Electrónica", "Efectivo / Contado", "Tarjeta (Débito/Crédito)", "Orden de Compra (O/C)", "Crédito Directo a 30 días"], key="c_pago")
            vendedor_nombre = st.text_input("Vendedor", value="ANA MARIA RIQUELME", key="c_vend")
            siniestro_val = st.text_input("N° de Siniestro (Si aplica)", key="c_sin")

            if st.button("💾 GENERAR PDF", type="primary", use_container_width=True):
                if not cliente_final: 
                    st.error("⛔ Ingresa al menos el nombre o Razón Social del cliente.")
                else:
                    guardar_cliente_nuevo(formato_rut_chileno(rut_empresa), cliente_final.upper(), direccion.upper(), ciudad.upper(), comuna.upper(), giro.upper(), contacto_nombre.upper(), contacto_fono)
                    
                    corr = obtener_y_registrar_correlativo(cliente_final, format_clp(t_final))
                    
                    datos_cliente = {
                        "nombre": cliente_final.upper(), "rut": formato_rut_chileno(rut_empresa), 
                        "direccion": direccion.upper(), "ciudad": ciudad.upper(), 
                        "comuna": comuna.upper(), "giro": giro.upper(), 
                        "contacto": contacto_nombre.upper(), "fono": contacto_fono, 
                        "pago": condicion_pago, "vendedor": vendedor_nombre.upper()
                    }
                    datos_vehiculo = {
                        "marca": marca_final if marca_final not in ["--- Seleccione Marca ---", "--- AGREGAR OTRA MARCA ---", "---"] else "", 
                        "modelo": modelo_final if modelo_final not in ["---", "--- AGREGAR OTRO MODELO ---"] else "", 
                        "anio": anio_final if anio_final not in ["---", "OTRO (MÁS ANTIGUO)"] else "", 
                        "patente": formato_patente_chilena(patente_final), 
                        "siniestro": siniestro_val.upper()
                    }
                    
                    pdf_bytes = generar_pdf_pascual(datos_cliente, datos_vehiculo, st.session_state.items_productos, st.session_state.items_servicios, desc_pct, corr)
                    
                    cliente_limpio = cliente_final.strip().upper().replace("/", "-")
                    pat_format = formato_patente_chilena(patente_final).strip()
                    
                    if pat_format:
                        nombre_pdf = f"Presupuesto {corr} - {cliente_limpio} - {pat_format}.pdf"
                    else:
                        nombre_pdf = f"Presupuesto {corr} - {cliente_limpio}.pdf"
                    
                    st.session_state.pdf_ready = {"pdf": pdf_bytes, "nombre": nombre_pdf, "corr": corr}
                    st.rerun()

            if 'pdf_ready' in st.session_state:
                d = st.session_state.pdf_ready
                st.success(f"✅ Presupuesto N° {d['corr']} generado.")
                
                st.download_button("📥 DESCARGAR PDF", d['pdf'], d['nombre'], "application/pdf", type="primary", use_container_width=True)
                if st.button("🔄 Crear Nuevo Presupuesto", use_container_width=True): 
                    del st.session_state['pdf_ready']; reset_session()

if __name__ == "__main__":
    render_app()
