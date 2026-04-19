import streamlit as st
from fpdf import FPDF
from PIL import Image, ImageOps
from datetime import datetime
import os

def render_app():
    st.title("📸 Expediente de Garantías")
    st.info("Completa el checklist fotográfico. El sistema unificará la evidencia en un solo documento para el analista.")

    # ==========================================
    # 1. IDENTIFICACIÓN DE LA ORDEN
    # ==========================================
    with st.container(border=True):
        ot = st.text_input("Número de OT (Orden de Trabajo)", placeholder="Ej: 85432", key="garantia_ot").upper()
        tecnico = st.text_input("Nombre del Técnico", placeholder="Ej: Pedro", key="garantia_tec")

    # ==========================================
    # 2. CHECKLIST FOTOGRÁFICO
    # ==========================================
    st.markdown("### 📋 Checklist de Evidencia")
    st.write("Toca cada botón para abrir la cámara o seleccionar una foto de la galería.")

    # Diccionario con la guía exacta que me mencionaste
    requisitos = {
        "placa_vin": "1. Placa VIN",
        "tablero": "2. Tablero de Instrumentos (Mostrando Odómetro)",
        "libro": "3. Libro de Mantención Timbrado",
        "diagnostico": "4. Pantallazo Equipo Diagnóstico",
        "vehiculo": "5. Fotografía 3/4 del Vehículo",
        "repuesto": "6. Repuesto Involucrado (Viejo vs Nuevo)"
    }

    fotos_subidas = {}

    # Generamos una casilla de subida por cada requisito
    for key, label in requisitos.items():
        archivo = st.file_uploader(label, type=['jpg', 'jpeg', 'png'], key=f"file_{key}")
        if archivo:
            fotos_subidas[key] = archivo

    # ==========================================
    # 3. GENERACIÓN DEL EXPEDIENTE (PDF)
    # ==========================================
    st.divider()
    
    # Barra de progreso visual
    progreso = len(fotos_subidas) / len(requisitos)
    st.progress(progreso, text=f"Fotografías capturadas: {len(fotos_subidas)} de {len(requisitos)}")

    if st.button("💾 Generar Expediente de Garantía", type="primary", use_container_width=True):
        if not ot:
            st.error("⛔ Debes ingresar el número de OT para generar el documento.")
        elif len(fotos_subidas) < len(requisitos):
            st.warning("⚠️ Faltan fotografías por subir. Por favor, completa todo el checklist.")
        else:
            with st.spinner("Compilando expediente fotográfico... (Esto puede tomar unos segundos)"):
                try:
                    pdf = FPDF()
                    pdf.set_auto_page_break(auto=True, margin=15)

                    # --- PÁGINA 1: PORTADA ---
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 18)
                    pdf.set_text_color(0, 51, 102)
                    pdf.cell(0, 20, "EXPEDIENTE DE GARANTÍA", 0, 1, "C")
                    
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(50, 10, "Orden de Trabajo (OT):", 0, 0)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 10, ot, 0, 1)
                    
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(50, 10, "Técnico:", 0, 0)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 10, tecnico, 0, 1)

                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(50, 10, "Fecha de Captura:", 0, 0)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 10, datetime.now().strftime('%d/%m/%Y %H:%M'), 0, 1)
                    
                    pdf.line(10, 60, 200, 60)

                    # --- PÁGINAS DE FOTOS ---
                    for key, label in requisitos.items():
                        pdf.add_page()
                        # Título de la foto
                        pdf.set_font("Arial", "B", 14)
                        pdf.set_text_color(0, 51, 102)
                        pdf.cell(0, 10, label, 0, 1, "C")
                        pdf.ln(5)

                        # Procesamiento de la imagen
                        img = Image.open(fotos_subidas[key])
                        # Corregir rotación automática de celulares
                        img = ImageOps.exif_transpose(img) 
                        
                        # Redimensionar para que el PDF no pese 100MB
                        img.thumbnail((1000, 1000))
                        
                        # Guardado temporal
                        temp_path = f"temp_garantia_{key}.jpg"
                        img.convert('RGB').save(temp_path, format="JPEG", quality=85)

                        # Calcular proporciones para que no se salga de la hoja
                        ancho_max = 180
                        alto_max = 240
                        ancho_img, alto_img = img.size
                        ratio = min(ancho_max/ancho_img, alto_max/alto_img)
                        
                        nuevo_ancho = ancho_img * ratio
                        # Centrar imagen horizontalmente
                        x_pos = (210 - nuevo_ancho) / 2

                        pdf.image(temp_path, x=x_pos, w=nuevo_ancho)
                        
                        # Limpiar archivo temporal
                        os.remove(temp_path)

                    pdf_bytes = pdf.output(dest='S').encode('latin-1')

                    st.success("✅ Expediente compilado exitosamente.")
                    
                    # Botón de descarga gigante para el celular
                    st.download_button(
                        label=f"📥 DESCARGAR EXPEDIENTE (OT {ot})",
                        data=pdf_bytes,
                        file_name=f"Garantia_OT_{ot}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Ocurrió un error al procesar las imágenes: {e}")

if __name__ == "__main__":
    render_app()
