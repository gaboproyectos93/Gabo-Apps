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
    # 1. CONFIGURACIÓN Y CONEXIÓN
    # ==========================================
    NOMBRE_HOJA_GOOGLE = "DB_Cotizador"

    def conectar_google_sheets():
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        try:
            if "gcp_service_account" in st.secrets:
                # Aseguramos que el secret se lea como diccionario para evitar errores
                creds_dict = dict(st.secrets["gcp_service_account"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            elif os.path.exists('credentials.json'):
                creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            else: 
                return None
            return gspread.authorize(creds)
        except: 
            return None

    # ==========================================
    # 2. LÓGICA DE CORREO Y BORRADOR
    # ==========================================
    def enviar_correo(destinatario, asunto, mensaje_texto, pdf_bytes, nombre_archivo, email_real_cristian):
        try:
            if "email" in st.secrets:
                remitente_sistema = st.secrets["email"]["user"]
                password = st.secrets["email"]["password"]
            else: 
                return False, "⚠️ Faltan credenciales en Secrets."
                
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
            return True, "Correo enviado exitosamente."
        except Exception as e: 
            return False, str(e)

    def obtener_y_registrar_correlativo(patente, cliente, total):
        client = conectar_google_sheets()
        if client:
            try:
                spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
                try: 
                    worksheet_hist = spreadsheet.worksheet("Historial")
                except:
                    worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="6")
                    worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Patente", "Cliente", "Monto Total"])
                    
                datos = worksheet_hist.get_all_values()
                correlativo_str = str(len(datos))
                ahora = datetime.now()
                worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, patente, cliente, total])
                return correlativo_str
            except: 
                return "ERR-NUBE"
        return "OFFLINE"

    def guardar_borrador_nube():
        client = conectar_google_sheets()
        if not client: return
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            ws = sheet.worksheet("Borrador")
            keys_to_save = ['paso_actual', 'lista_particular', 'items_manuales_extra', 'lista_repuestos']
            datos = {k: v for k, v in st.session_state.items() if k.endswith('_confirmado') or k.endswith('_confirmada') or k in keys_to_save or k.startswith('q_')}
            ws.update_acell('A1', json.dumps(datos))
        except: 
            pass

    def cargar_borrador_nube():
        client = conectar_google_sheets()
        if not client: return None
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            ws = sheet.worksheet("Borrador")
            val = ws.acell('A1').value
            if val: 
                return json.loads(val)
        except: 
            pass
        return None

    def limpiar_borrador_nube():
        client = conectar_google_sheets()
        if not client: return
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            ws = sheet.worksheet("Borrador")
            ws.update_acell('A1', '')
        except: 
            pass

    # ==========================================
    # 3. BASE DE DATOS INTELIGENTE
    # ==========================================
    def limpiar_patente(texto):
        if not texto: return ""
        return re.sub(r'[^A-Z0-9]', '', texto.upper())

    @st.cache_data(ttl=3600)
    def cargar_base_vehiculos():
        base_def = {
            "--- Seleccione Marca ---": ["---"], 
            "Mercedes-Benz": ["Sprinter", "Vito", "Citan", "Clase A", "Clase C", "GLA", "GLC", "GLE"], 
            "Especiales / Conversiones": ["Carro de Arrastre", "Clínica Móvil", "Conversión a Ambulancia", "Oficina Móvil", "Remolque Especial"]
        }
        try:
            if os.path.exists("vehiculos.csv"):
                df = pd.read_csv("vehiculos.csv", encoding='utf-8')
                if 'Marca' in df.columns and 'Modelo' in df.columns:
                    base_csv = {"--- Seleccione Marca ---": ["---"], "Especiales / Conversiones": base_def["Especiales / Conversiones"]}
                    for m in sorted(df['Marca'].dropna().unique()):
                        base_csv[str(m)] = sorted(list(set([str(mod) for mod in df[df['Marca'] == m]['Modelo'].dropna()])))
                    return base_csv
        except: 
            pass 
        return base_def

    BASE_VEHICULOS = cargar_base_vehiculos()

    @st.cache_data(ttl=60)
    def cargar_directorio_correos():
        client = conectar_google_sheets()
        default_c = [
            {"Nombre": "Mickel Rojas (Asesor Vans)", "Email": "mrojas@kaufmann.cl"}, 
            {"Nombre": "Franz Schubert (Jefe de Servicio)", "Email": "fschubert@kaufmann.cl"}, 
            {"Nombre": "Gabriel Poblete (Planificador de Taller)", "Email": "gpoblete@kaufmann.cl"}
        ]
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Directorio_Correos")
                data = ws.get_all_records()
                if data: 
                    return {row["Nombre"]: row["Email"] for row in data if "Nombre" in row and "Email" in row}
            except: 
                pass
        return {c["Nombre"]: c["Email"] for c in default_c}

    @st.cache_data(ttl=60)
    def cargar_directorio_patentes():
        client = conectar_google_sheets()
        if client:
            try:
                sheet = client.open(NOMBRE_HOJA_GOOGLE)
                ws = sheet.worksheet("Directorio_Patentes")
                data = ws.get_all_records()
                if data: 
                    return pd.DataFrame(data)
            except: 
                pass
        return pd.DataFrame(columns=["Patente", "Institucion"])

    def detectar_cliente_automatico(patente_input):
        p_clean = limpiar_patente(patente_input)
        df_p = cargar_directorio_patentes()
        
        if df_p.empty:
            return None, None
            
        match = df_p[df_p['Patente'].astype(str).str.upper() == p_clean]
        
        if not match.empty:
            inst = str(match.iloc[0]['Institucion']).upper()
            if "GENDARMERÍA" in inst or "GENDARMERIA" in inst: 
                return "GENDARMERÍA DE CHILE", "Gendarmería de Chile"
            elif "SAMU" in inst: 
                return "SAMU", "SAMU"
            elif "TEMUCO" in inst: 
                return inst, "Hospital Temuco"
            elif "VILLARRICA" in inst: 
                return inst, "Hospital Villarrica"
            elif "LAUTARO" in inst: 
                return inst, "Hospital Lautaro"
            elif "PITRUFQUEN" in inst or "PITRUFQUÉN" in inst: 
                return inst, "Hospital Pitrufquén"
            else: 
                return inst, "SSAS (Servicio Salud)"
                
        return None, None

    # --- SOLUCIÓN AL BUG DE LAS SECCIONES DESAPARECIDAS ---
    @st.cache_data(ttl=60)
    def cargar_datos():
        try:
            client = conectar_google_sheets()
            sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except: 
            return pd.read_csv(io.StringIO("Categoria,Trabajo,Costo_SSAS,Costo_Hosp_Temuco,Costo_Hosp_Villarrica,Costo_Hosp_Lautaro,Costo_Hosp_Pitrufquen,Costo_Gend"))

    # ==========================================
    # 5. UTILS Y ESTILOS
    # ==========================================
    EMPRESA_NOMBRE = "C.H. SERVICIO AUTOMOTRIZ"
    RUT_EMPRESA = "13.961.700-2" 
    DIRECCION = "Francisco Pizarro 495, Padre las Casas"
    TELEFONO = "+56 9 8922 0616"
    EMAIL = "c.h.servicioautomotriz@gmail.com"
    COLOR_PRIMARIO = "#0A2540" 

    def format_clp(v): 
        try: 
            return f"${float(v):,.0f}".replace(",", ".")
        except: 
            return "$0"

    def reset_session():
        limpiar_borrador_nube()
        st.cache_data.clear()
        st.query_params.clear()
        for key in list(st.session_state.keys()): 
            del st.session_state[key]
        st.rerun()

    def encontrar_imagen(n):
        for ext in ['.jpg', '.png', '.jpeg']:
            if os.path.exists(n + ext): 
                return n + ext
        return None

    st.markdown(f"""
    <style>
        .stTabs [aria-selected='true'] {{ 
            background-color: {COLOR_PRIMARIO} !important; 
            color: white !important; 
            border-radius: 4px 4px 0px 0px;
        }} 
        .stButton > button[kind='primary'] {{ 
            background-color: {COLOR_PRIMARIO} !important; 
            color: white !important; 
            font-weight: bold;
        }}
        .stContainer {{ 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 8px; 
            padding: 10px; 
            margin-bottom: 5px; 
        }}
        div[data-testid="stNumberInput"] input {{ 
            max-width: 100px; 
            text-align: center; 
        }}
    </style>
    """, unsafe_allow_html=True)

    df_precios = cargar_datos()

    # ==========================================
    # 6. CALCULADORA Y PDF 
    # ==========================================
    @st.dialog("🧮 Calculadora Rápida")
    def abrir_calculadora():
        calc_html = f"""
        <!DOCTYPE html><html><head><style>
            body {{ margin: 0; font-family: sans-serif; background: transparent; }}
            .calculator {{ background: #2d2d2d; border-radius: 10px; padding: 10px; }}
            .display {{ background: #eee; border-radius: 5px; margin-bottom: 10px; padding: 10px; text-align: right; font-size: 20px; font-weight: bold; color: #333; height: 30px;}}
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }}
            button {{ padding: 10px; border: none; border-radius: 5px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.1s; }}
            .num {{ background: #555; color: white; }} .num:hover {{ background: #666; }}
            .op {{ background: #eee; color: black; }} .op:hover {{ background: #d4d4d4; }}
            .clear {{ background: #a5a5a5; color: black; }} 
            .eq {{ background: {COLOR_PRIMARIO}; color: white; grid-column: span 2; }} 
        </style></head><body>
        <div class="calculator"><div class="display" id="disp">0</div><div class="grid">
            <button class="clear" onclick="clr()">C</button><button class="clear" onclick="del()">⌫</button><button class="op" onclick="app('/')">÷</button><button class="op" onclick="app('*')">×</button>
            <button class="num" onclick="app('7')">7</button><button class="num" onclick="app('8')">8</button><button class="num" onclick="app('9')">9</button><button class="op" onclick="app('-')">-</button>
            <button class="num" onclick="app('4')">4</button><button class="num" onclick="app('5')">5</button><button class="num" onclick="app('6')">6</button><button class="op" onclick="app('+')">+</button>
            <button class="num" onclick="app('1')">1</button><button class="num" onclick="app('2')">2</button><button class="num" onclick="app('3')">3</button><button class="num" style="grid-row: span 2;" onclick="app('.')">.</button>
            <button class="num" onclick="app('0')">0</button><button class="eq" onclick="calc()">=</button>
        </div></div>
        <script>
            let d = document.getElementById('disp');
            function app(v){{ if(d.innerText=='0')d.innerText=''; d.innerText+=v; }}
            function clr(){{ d.innerText='0'; }}
            function del(){{ d.innerText=d.innerText.slice(0,-1)||'0'; }}
            function calc(){{ try{{ d.innerText=eval(d.innerText); }}catch{{ d.innerText='Error'; }} }}
        </script></body></html>
        """
        components.html(calc_html, height=280)

    class PDF(FPDF):
        def __init__(self, correlativo="", official=False): 
            super().__init__()
            self.correlativo = correlativo
            self.is_official = official
            
        def header(self):
            # Adaptado a logo_christian
            logo = encontrar_imagen("logo_christian")
            if logo: 
                self.image(logo, x=10, y=10, w=70) 
                
            self.set_xy(130, 10)
            self.set_text_color(220, 0, 0)
            self.set_draw_color(220, 0, 0)
            self.set_line_width(0.4)
            
            self.set_font('Arial', 'B', 16)
            titulo = "COTIZACIÓN" if self.is_official else "PRESUPUESTO"
            self.cell(70, 10, titulo, 'LTR', 1, 'C') 
            
            self.set_x(130)
            self.set_font('Arial', 'B', 14)
            c_txt = f"N° {self.correlativo}" if self.correlativo != "BORRADOR" else "N° BORRADOR"
            self.cell(70, 10, c_txt, 'LBR', 1, 'C')
            
            self.set_text_color(0, 0, 0)
            self.set_draw_color(0, 0, 0)
            self.set_line_width(0.2)
            self.ln(15)
            
        def footer(self):
            self.set_y(-20)
            self.set_font('Arial', 'I', 8)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(2)
            self.cell(0, 4, f"Christian Alejandro Herrera Mardones | RUT: {RUT_EMPRESA} | {DIRECCION}", 0, 1, 'C')

    def generar_pdf_exacto(patente, marca, modelo, cliente_nombre, cliente_rut, items, total_neto, is_official, estado_trabajo, usuario_final_txt, observaciones, correlativo, fotos_adjuntas):
        pdf = PDF(correlativo=correlativo, official=is_official)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=30) 
        
        def fila_dinamica(lbl1, val1, lbl2, val2, is_last=False):
            start_y = pdf.get_y()
            pdf.set_font('Arial', 'B', 9)
            pdf.set_xy(10, start_y)
            pdf.cell(25, 6, lbl1, 0, 0, 'L')
            
            pdf.set_font('Arial', '', 9)
            pdf.set_xy(35, start_y)
            pdf.multi_cell(70, 6, f": {val1}", 0, 'L')
            y_left = pdf.get_y()
            
            y_right = start_y
            if lbl2: 
                pdf.set_font('Arial', 'B', 9)
                pdf.set_xy(105, start_y)
                pdf.cell(30, 6, lbl2, 0, 0, 'L')
                
                pdf.set_font('Arial', '', 9)
                pdf.set_xy(135, start_y)
                pdf.multi_cell(65, 6, f": {val2}", 0, 'L')
                y_right = pdf.get_y()
                
            my = max(y_left, y_right, start_y + 6)
            pdf.line(10, start_y, 10, my)
            pdf.line(200, start_y, 200, my)
            if is_last: 
                pdf.line(10, my, 200, my)
            pdf.set_xy(10, my)
            
        pdf.set_y(45)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(10, 37, 64)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 6, "  DATOS DEL CLIENTE", 1, 1, 'L', 1)
        pdf.set_text_color(0, 0, 0)
        
        fila_dinamica(" Señor(es)", str(cliente_nombre).upper(), " Fecha Emisión", datetime.now().strftime('%d/%m/%Y'))
        fila_dinamica(" RUT", str(cliente_rut).upper(), " Usuario Final", str(usuario_final_txt).upper(), is_last=True)
        pdf.ln(4)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(10, 37, 64)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 6, "  DATOS DEL VEHÍCULO", 1, 1, 'L', 1)
        pdf.set_text_color(0, 0, 0)
        
        fila_dinamica(" Marca", str(marca).upper(), " Patente", str(patente).upper())
        fila_dinamica(" Modelo", str(modelo).upper(), " Estado", str(estado_trabajo).upper(), is_last=True)
        pdf.ln(6)
        
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(10, 37, 64)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(115, 7, "Descripción", 1, 0, 'C', 1)
        pdf.cell(15, 7, "Cant.", 1, 0, 'C', 1)
        pdf.cell(30, 7, "Unitario", 1, 0, 'C', 1)
        pdf.cell(30, 7, "Total", 1, 1, 'C', 1)
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', '', 9)
        
        for i in items:
            x, y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(115, 6, i['Descripción'].upper(), 1, 'L')
            h = pdf.get_y() - y
            pdf.set_xy(x + 115, y)
            pdf.cell(15, h, str(i['Cantidad']), 1, 0, 'C')
            pdf.cell(30, h, format_clp(i['Unitario_Costo']), 1, 0, 'R')
            pdf.cell(30, h, format_clp(i['Total_Costo']), 1, 1, 'R')
            pdf.set_xy(x, y + h)
            
        pdf.ln(5)
        iv = total_neto * 0.19
        br = total_neto + iv
        
        pdf.set_x(140)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(30, 6, "SUB TOTAL", 1, 0, 'L')
        pdf.set_font('Arial', '', 9)
        pdf.cell(30, 6, format_clp(total_neto), 1, 1, 'R')
        
        pdf.set_x(140)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(30, 6, "I.V.A. (19%)", 1, 0, 'L')
        pdf.set_font('Arial', '', 9)
        pdf.cell(30, 6, format_clp(iv), 1, 1, 'R')
        
        pdf.set_x(140)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(10, 37, 64)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(30, 8, "TOTAL", 1, 0, 'L', 1)
        pdf.cell(30, 8, format_clp(br), 1, 1, 'R', 1)
        
        pdf.set_text_color(0, 0, 0)
        
        if observaciones: 
            pdf.ln(8)
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 6, "OBSERVACIONES / NOTAS:", 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, observaciones, 0, 'L')
            
        pdf.ln(15)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Padre las Casas, {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'C')
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, "Christian Alejandro Herrera Mardones", 0, 1, 'C')
        
        if fotos_adjuntas:
            for j, f in enumerate(fotos_adjuntas):
                if j % 4 == 0: 
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 14)
                    pdf.cell(0, 10, "REGISTRO FOTOGRÁFICO", 0, 1, 'C')
                try:
                    img = Image.open(f)
                    img = ImageOps.exif_transpose(img).convert('RGB')
                    img.thumbnail((600, 600))
                    temp = f"t_{j}.jpg"
                    img.save(temp, quality=60)
                    
                    p = j % 4
                    x = 15 + (p % 2) * 95
                    y = 60 + (p // 2) * 95
                    
                    pdf.image(temp, x=x, y=y, w=85, h=85)
                    os.remove(temp)
                except: 
                    pass
                    
        return pdf.output(dest='S').encode('latin-1')

    def render_ui_repuestos():
        st.subheader("🛒 Calculadora de Repuestos")
        st.info("Ingresa los costos internos. El sistema calculará automáticamente el precio final para el cliente.")
        
        c1, c2 = st.columns([3, 1])
        d_rep = c1.text_input("Descripción Repuesto", key="r_desc")
        q_rep = c2.number_input("Cant", 1, key="r_cant")
        
        c3, c4, c5 = st.columns(3)
        c_rep = c3.number_input("Costo Repuesto ($)", 0, step=1000, key="r_crep")
        c_env = c4.number_input("Costo Envío ($)", 0, step=1000, key="r_cenv")
        m_pct = c5.number_input("Margen de Ganancia (%)", min_value=0, max_value=100, value=30, key="r_marg")
        
        p_final = int((c_rep + c_env) * (1 + m_pct / 100.0))
        st.markdown(f"#### Precio Final a Cobrar: **{format_clp(p_final)}**")
        
        if st.button("➕ Añadir Repuesto"):
            if d_rep and p_final > 0:
                if 'lista_repuestos' not in st.session_state: 
                    st.session_state.lista_repuestos = []
                st.session_state.lista_repuestos.append({
                    "Descripción": d_rep, 
                    "Cantidad": q_rep, 
                    "Unitario_Costo": float(p_final), 
                    "Total_Costo": float(p_final * q_rep)
                })
                guardar_borrador_nube()
                st.rerun()
                
        if 'lista_repuestos' in st.session_state:
            st.markdown("###### Repuestos Añadidos:")
            for idx, i in enumerate(st.session_state.lista_repuestos):
                ca, cb = st.columns([5, 1], vertical_alignment="center")
                ca.text(f"• {i['Cantidad']}x {i['Descripción']} - {format_clp(i['Total_Costo'])}")
                if cb.button("🗑️", key=f"dr_{idx}"): 
                    st.session_state.lista_repuestos.pop(idx)
                    guardar_borrador_nube()
                    st.rerun()

    # ==========================================
    # 8. UI PRINCIPAL (FLUJO PASO A PASO)
    # ==========================================
    with st.sidebar:
        if st.button("🧮 Abrir Calculadora", use_container_width=True): 
            abrir_calculadora()
        st.markdown("---")
        if st.button("🗑️ Reiniciar Todo", type="primary", use_container_width=True): 
            reset_session()

    if 'check_borrador' not in st.session_state:
        st.session_state.check_borrador = True
        borrador = cargar_borrador_nube()
        if borrador: 
            st.session_state.borrador_pendiente = borrador

    if 'paso_actual' not in st.session_state: 
        st.session_state.paso_actual = 1

    # --- PANTALLA 1: INICIO ---
    if st.session_state.paso_actual == 1:
        col_centro = st.columns([1, 2, 1])
        
        with col_centro[1]:
            if 'borrador_pendiente' in st.session_state:
                st.error(f"⚠️ Borrador detectado para patente: **{st.session_state.borrador_pendiente.get('patente_confirmada', '')}**")
                ca, cb = st.columns(2)
                if ca.button("✅ Recuperar Trabajo", use_container_width=True): 
                    for k, v in st.session_state.borrador_pendiente.items():
                        st.session_state[k] = v
                    del st.session_state['borrador_pendiente']
                    st.rerun()
                if cb.button("🗑️ Descartar Borrador", use_container_width=True): 
                    limpiar_borrador_nube()
                    del st.session_state['borrador_pendiente']
                    st.rerun()
                st.markdown("---")
                    
            logo = encontrar_imagen("logo_christian") 
            if logo: 
                st.image(logo, width=200)
                
            st.title("Cotizador Taller")
            st.markdown("#### 1. Identificación del Vehículo")
            
            pat_texto = st.text_input("Buscar o Ingresar Patente", placeholder="Ej: HXRP10").upper()
            patente = pat_texto 
            
            if pat_texto and len(pat_texto) >= 2:
                df_p = cargar_directorio_patentes()
                if not df_p.empty:
                    lista_p = sorted(list(set([str(x).strip().upper() for x in df_p['Patente'].dropna().tolist() if str(x).strip()])))
                    matches = [p for p in lista_p if pat_texto in p and p != pat_texto]
                    
                    if matches:
                        sel_sug = st.selectbox("💡 Sugerencias (Selecciona para autocompletar):", ["(Mantener lo que escribí)"] + matches)
                        if sel_sug != "(Mantener lo que escribí)":
                            patente = sel_sug
            
            if 'busqueda_activa' not in st.session_state: 
                st.session_state.busqueda_activa = False
                st.session_state.patente_previa = ""
                st.session_state.auto_index = 0
                st.session_state.usuario_detectado = None
                
            if st.button("🔍 Buscar en Directorio", use_container_width=True):
                if not patente.strip(): 
                    st.error("⛔ Ingrese una patente primero.")
                else:
                    usuario, tipo = detectar_cliente_automatico(patente)
                    st.session_state.busqueda_activa = True
                    st.session_state.patente_previa = patente
                    st.session_state.usuario_detectado = usuario
                    
                    if usuario:
                        m = {
                            "SSAS (Servicio Salud)": 1, 
                            "SAMU": 2, 
                            "Hospital Temuco": 3, 
                            "Hospital Villarrica": 4, 
                            "Hospital Lautaro": 5, 
                            "Hospital Pitrufquén": 6, 
                            "Gendarmería de Chile": 7
                        }
                        st.session_state.auto_index = m.get(tipo, 8)
                    else: 
                        st.session_state.auto_index = 8 
                        
            if patente != st.session_state.get('patente_previa', ''): 
                st.session_state.busqueda_activa = False
                
            if st.session_state.get('busqueda_activa', False):
                if st.session_state.usuario_detectado:
                    st.success(f"✅ Vehículo reconocido: {st.session_state.usuario_detectado}") 
                else:
                    st.warning("⚠️ Patente no registrada en Directorio. Seleccione cliente manualmente.")
                    
            ops = (
                "--- Seleccione Institución ---", 
                "SSAS (Servicio Salud)", 
                "SAMU", 
                "Hospital Temuco", 
                "Hospital Villarrica", 
                "Hospital Lautaro", 
                "Hospital Pitrufquén", 
                "Gendarmería de Chile", 
                "Cliente Particular"
            )
            
            t_cli = st.selectbox("Institución / Cliente", ops, index=st.session_state.get('auto_index', 0))
            
            if st.button("🚀 COMENZAR COTIZACIÓN", type="primary", use_container_width=True):
                if not st.session_state.get('busqueda_activa', False): 
                    st.error("⛔ Debe pinchar 'Buscar en Directorio' antes de comenzar.")
                elif t_cli == "--- Seleccione Institución ---": 
                    st.error("⛔ Debe seleccionar una institución válida para continuar.")
                elif not patente: 
                    st.error("⛔ Debe ingresar una patente.")
                else:
                    st.query_params.update({"patente": patente, "cliente": t_cli, "paso": "2"})
                    
                    if st.session_state.usuario_detectado: 
                        final_usuario = st.session_state.usuario_detectado
                    else: 
                        if t_cli == "Cliente Particular":
                            final_usuario = "CLIENTE PARTICULAR"
                        elif t_cli == "Gendarmería de Chile":
                            final_usuario = "GENDARMERÍA DE CHILE"
                        else:
                            final_usuario = "HOSPITAL [ESPECIFICAR]"

                    st.session_state.update({
                        "patente_confirmada": patente, 
                        "tipo_cliente_confirmado": t_cli, 
                        "paso_actual": 2, 
                        "usuario_final_confirmado": final_usuario
                    })
                    guardar_borrador_nube()
                    st.rerun()

    # --- PANTALLA 2: COTIZADOR ---
    elif st.session_state.paso_actual == 2:
        t_cli = st.session_state.tipo_cliente_confirmado
        p_in = st.session_state.patente_confirmada
        
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1: 
            if st.button("⬅️ Volver", use_container_width=True): 
                st.session_state.paso_actual = 1
                st.query_params.clear()
                st.rerun()
                
        with c2:
            st.markdown(f"### 🚗 Cotizando: **{p_in}** ({t_cli})")
            
        categorias_a_mostrar = df_precios['Categoria'].unique() if t_cli != "Cliente Particular" else []
        
        st.markdown("#### 🏢 Datos del Cliente a Facturar")
        cf1, cf2, cf3 = st.columns([2, 1, 2])
        
        def_c = "KAUFMANN S.A." if t_cli != "Cliente Particular" else ""
        def_r = "92.475.000-6" if t_cli != "Cliente Particular" else ""
        
        cli_fac = cf1.text_input("Señor(es) / Razón Social", value=def_c, placeholder="Nombre de quien paga")
        rut_fac = cf2.text_input("RUT", value=def_r, placeholder="Opcional")
        us_final = cf3.text_input("Usuario Final / Hospital", value=st.session_state.usuario_final_confirmado)
        
        st.markdown("#### 🚙 Datos Específicos del Vehículo")
        cv1, cv2, cv3 = st.columns(3)
        
        lista_marcas = list(BASE_VEHICULOS.keys())
        if "--- AGREGAR OTRA MARCA ---" not in lista_marcas: 
            lista_marcas.append("--- AGREGAR OTRA MARCA ---")
            
        default_marca_idx = 0
        if t_cli != "Cliente Particular" and "Mercedes-Benz" in lista_marcas:
            default_marca_idx = lista_marcas.index("Mercedes-Benz")
            
        marca_sel = cv1.selectbox("Marca", lista_marcas, index=default_marca_idx, key="v_marca")
        
        if marca_sel == "--- AGREGAR OTRA MARCA ---":
            marca_final = cv1.text_input("Escriba la Marca:", placeholder="Ej: Motorhome", key="v_marca_man").upper()
            mod_lista = ["--- AGREGAR OTRO MODELO ---"]
        else:
            marca_final = marca_sel
            mod_lista = BASE_VEHICULOS.get(marca_sel, ["---"]).copy()
            if "--- AGREGAR OTRO MODELO ---" not in mod_lista: 
                mod_lista.append("--- AGREGAR OTRO MODELO ---")
                
        default_modelo_idx = 0
        if t_cli != "Cliente Particular" and "Sprinter" in mod_lista:
            default_modelo_idx = mod_lista.index("Sprinter")
            
        modelo_sel = cv2.selectbox("Modelo", mod_lista, index=default_modelo_idx, key="v_modelo")
        
        if modelo_sel == "--- AGREGAR OTRO MODELO ---":
            modelo_final = cv2.text_input("Escriba el Modelo:", placeholder="Ej: Ducato L3H2", key="v_modelo_man").upper()
        else:
            modelo_final = modelo_sel
            
        pat = cv3.text_input("Patente (Obligatoria)", value=p_in, key="v_pat")
        st.markdown("---")
        
        emojis = {
            "Luces y Exterior": "💡", 
            "Carrocería y Vidrios": "🚐", 
            "Interior Sanitario": "🏥", 
            "Climatización y Aire": "❄️", 
            "Asientos y Tapiz": "💺", 
            "Equipamiento y Radio": "📻", 
            "Cabina y Tablero": "📟", 
            "Camilla": "🚑", 
            "Seguridad y Calabozos": "🔒"
        }
        
        sel_final = []
        
        if t_cli == "Cliente Particular":
            tabs = st.tabs(["➕ Ingreso Manual", "🛒 Compra Repuestos"])
            with tabs[0]:
                st.info("ℹ️ Modo Cliente Particular: Ingrese ítems manualmente.")
                with st.container():
                    cc1, cc2, cc3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                    dm = cc1.text_input("Descripción del Trabajo")
                    qm = cc2.number_input("Cnt", min_value=0, value=1)
                    pm = cc3.number_input("Precio Unitario ($)", min_value=0, step=5000)
                    
                    if st.button("Agregar Ítem"): 
                        if dm and qm > 0 and pm > 0:
                            if 'lista_particular' not in st.session_state:
                                st.session_state.lista_particular = []
                            st.session_state.lista_particular.append({
                                "Descripción": dm, 
                                "Cantidad": qm, 
                                "Unitario_Costo": pm, 
                                "Total_Costo": pm * qm
                            })
                            guardar_borrador_nube()
                            st.rerun()
                            
                if 'lista_particular' in st.session_state and st.session_state.lista_particular:
                    st.markdown("#### Ítems Agregados:")
                    for idx, i in enumerate(st.session_state.lista_particular):
                        ca, cb = st.columns([5, 1], vertical_alignment="center")
                        ca.markdown(f"• {i['Cantidad']}x {i['Descripción']} - **{format_clp(i['Total_Costo'])}**")
                        if cb.button("🗑️", key=f"dp_{idx}"): 
                            st.session_state.lista_particular.pop(idx)
                            guardar_borrador_nube()
                            st.rerun()
                    sel_final = st.session_state.lista_particular
                    
            with tabs[1]: 
                render_ui_repuestos()
                
        else:
            nombres_tabs = [f"{emojis.get(c, '🔧')} {c}" for c in categorias_a_mostrar] + ["🛒 Compra Repuestos", "➕ Manual (Temp)"]
            tabs = st.tabs(nombres_tabs)
            
            mapa_columnas = {
                "SSAS (Servicio Salud)": 'Costo_SSAS', 
                "SAMU": 'Costo_SSAS', 
                "Hospital Temuco": 'Costo_Hosp_Temuco', 
                "Hospital Villarrica": 'Costo_Hosp_Villarrica', 
                "Hospital Lautaro": 'Costo_Hosp_Lautaro', 
                "Hospital Pitrufquén": 'Costo_Hosp_Pitrufquen', 
                "Gendarmería de Chile": 'Costo_Gend'
            }
            col_db = mapa_columnas.get(t_cli, 'Costo_SSAS')
            
            for i, cat in enumerate(categorias_a_mostrar):
                with tabs[i]:
                    df_cat = df_precios[df_precios['Categoria'] == cat]
                    items_v = df_cat[df_cat[col_db] > 0]
                    
                    if items_v.empty: 
                        st.info("⚠️ Esta categoría no aplica para el cliente seleccionado.")
                    else:
                        for idx, row in items_v.iterrows():
                            with st.container():
                                cc1, cc2, cc3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                                cc1.markdown(f"**{row['Trabajo']}**")
                                
                                k = f"q_{row['Trabajo']}_{idx}"
                                qty = cc2.number_input("", 0, 20, value=st.session_state.get(k, 0), key=k, label_visibility="collapsed", on_change=guardar_borrador_nube)
                                
                                p = float(row[col_db])
                                cc3.markdown(f"**{format_clp(p)}**")
                                
                                if qty > 0: 
                                    sel_final.append({
                                        "Descripción": row['Trabajo'], 
                                        "Cantidad": qty, 
                                        "Unitario_Costo": p, 
                                        "Total_Costo": p * qty
                                    })
                                    
            with tabs[-2]: 
                render_ui_repuestos()
                
            with tabs[-1]:
                with st.container():
                    st.subheader("Item Temporal")
                    cc1, cc2, cc3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                    de = cc1.text_input("Descripción del Trabajo (Manual)")
                    qe = cc2.number_input("Cant.", min_value=1, value=1, key="eq")
                    pe = cc3.number_input("Precio Unitario ($)", min_value=0, step=5000, key="ep")
                    
                    if st.button("Agregar Ítem Manual"): 
                        if de and pe > 0:
                            if 'items_manuales_extra' not in st.session_state:
                                st.session_state.items_manuales_extra = []
                            st.session_state.items_manuales_extra.append({
                                "Descripción": f"(Extra) {de}", 
                                "Cantidad": qe, 
                                "Unitario_Costo": pe, 
                                "Total_Costo": pe * qe
                            })
                            guardar_borrador_nube()
                            st.rerun()
                            
                if 'items_manuales_extra' in st.session_state and st.session_state.items_manuales_extra:
                    st.markdown("---")
                    st.markdown("###### Ítems Manuales:")
                    for idx, i in enumerate(st.session_state.items_manuales_extra):
                        ca, cb = st.columns([5, 1], vertical_alignment="center")
                        ca.text(f"• {i['Cantidad']}x {i['Descripción']}")
                        if cb.button("🗑️", key=f"de_{idx}"): 
                            st.session_state.items_manuales_extra.pop(idx)
                            guardar_borrador_nube()
                            st.rerun()
                            
                    sel_final.extend(st.session_state.items_manuales_extra)
                    
        if 'lista_repuestos' in st.session_state: 
            sel_final.extend(st.session_state.lista_repuestos)
            
        if sel_final:
            st.markdown("---")
            st.subheader("📑 Vista Previa de la Cotización")
            
            preview_data = []
            for item in sel_final:
                preview_data.append({
                    "Descripción": item["Descripción"],
                    "Cant.": item["Cantidad"],
                    "Unitario": format_clp(item["Unitario_Costo"]),
                    "Total": format_clp(item["Total_Costo"])
                })
            st.table(pd.DataFrame(preview_data))
            
            tn = sum(x['Total_Costo'] for x in sel_final)
            iv = tn * 0.19
            tf = tn + iv
            
            k1, k2, k3 = st.columns(3)
            k1.metric("SUB TOTAL", format_clp(tn))
            k2.metric("I.V.A. (19%)", format_clp(iv))
            k3.metric("TOTAL A PAGAR", format_clp(tf))
            
            obs = st.text_area("Notas / Observaciones:", height=100)
            st.markdown("### 📸 Fotografías")
            fotos = st.file_uploader("Adjuntar evidencia", accept_multiple_files=True, type=['jpg', 'png', 'jpeg'])
            est = st.radio("Estado:", ("En Espera de Aprobación", "Trabajo Realizado"))
            
            if 'presupuesto_generado' not in st.session_state:
                if st.button("💾 FINALIZAR Y GENERAR PRESUPUESTO", type="primary", use_container_width=True):
                    corr = obtener_y_registrar_correlativo(pat, us_final, format_clp(tf))
                    
                    marca_pdf = marca_final.replace("--- Seleccione Marca ---", "NO ESPECIFICADA")
                    modelo_pdf = modelo_final.replace("--- AGREGAR OTRO MODELO ---", "NO ESPECIFICADO")
                    es_formato_oficial = (cli_fac.strip().upper() == "KAUFMANN S.A.")
                    
                    nombre_pdf = f"Presupuesto {corr} - {pat}.pdf"
                    pdf_b = generar_pdf_exacto(
                        pat, marca_pdf, modelo_pdf, cli_fac, rut_fac, 
                        sel_final, tn, es_formato_oficial, est, us_final, obs, corr, fotos
                    )
                    
                    # --- RESPALDO AUTOMÁTICO VÍA EMAIL ---
                    asunto_resp = f"📁 RESPALDO NUBE: {nombre_pdf}"
                    mensaje_resp = f"Copia de seguridad automática.\n\nPatente: {pat}\nCliente: {cli_fac}\nInstitución: {t_cli}\nTotal a Pagar: {format_clp(tf)}\nEstado: {est}\n\nEl archivo PDF va adjunto."
                    destinatarios_resp = "c.h.servicioautomotriz@gmail.com, sistema.cotizador.gp@gmail.com"
                    
                    exito_resp, msj_resp = enviar_correo(destinatarios_resp, asunto_resp, mensaje_resp, pdf_b, nombre_pdf, EMAIL)
                    
                    st.session_state['presupuesto_generado'] = {
                        'pdf': pdf_b, 
                        'nombre': nombre_pdf,
                        'respaldo_ok': exito_resp,
                        'respaldo_msj': msj_resp
                    }
                    
                    limpiar_borrador_nube()
                    st.rerun()
            else:
                d = st.session_state['presupuesto_generado']
                st.success(f"✅ Presupuesto N° {d['nombre']} generado correctamente.")
                
                if d.get('respaldo_ok'):
                    st.info("☁️ Respaldo guardado exitosamente en los correos del taller.")
                else:
                    st.warning(f"⚠️ El PDF se generó, pero hubo un problema al enviar el respaldo: {d.get('respaldo_msj')}")
                
                cd1, cd2 = st.columns(2)
                with cd1: 
                    st.download_button("📥 DESCARGAR PDF", d['pdf'], d['nombre'], "application/pdf", type="primary", use_container_width=True)
                with cd2: 
                    if st.button("🔄 Nueva Cotización", use_container_width=True): 
                        reset_session()
                        
                st.markdown("---")
                with st.expander("✉️ Enviar por Correo Electrónico al Cliente", expanded=False):
                    st.info("Asegúrate de tener la contraseña de aplicación configurada en los Secrets.")
                    dir_c = cargar_directorio_correos()
                    
                    d_sel = st.multiselect("Destinatarios Predefinidos:", options=list(dir_c.keys()), default=[])
                    e_ad = st.text_input("Correos Adicionales (separados por coma):", placeholder="ejemplo@cliente.com")
                    e_as = st.text_input("Asunto:", value=f"{d['nombre'].replace('.pdf', '')} - C.H. Servicio Automotriz")
                    e_ms = st.text_area("Mensaje:", value=f"Estimado(a),\n\nAdjunto enviamos el presupuesto solicitado para la patente {pat}.\n\nSaludos cordiales,\nC.H. Servicio Automotriz")
                    
                    if st.button("📤 Enviar Correo al Cliente", type="primary"):
                        lc = [dir_c[n] for n in d_sel]
                        if e_ad: 
                            lc.extend([e.strip() for e in e_ad.split(',') if e.strip()])
                            
                        dfinal = ", ".join(lc)
                        
                        if dfinal:
                            with st.spinner(f"Enviando correo a: {dfinal}..."):
                                ex, m = enviar_correo(dfinal, e_as, e_ms, d['pdf'], d['nombre'], EMAIL)
                            if ex:
                                st.success(f"✅ Correo enviado exitosamente a: {dfinal}") 
                            else:
                                st.error(f"❌ {m}")
                        else:
                            st.warning("⚠️ Debes seleccionar o ingresar al menos un correo de destino.")

if __name__ == "__main__":
    render_app()
