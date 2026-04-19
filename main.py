import streamlit as st
import time
from streamlit_cookies_controller import CookieController

# Configuración inicial (debe ser lo primero)
st.set_page_config(page_title="Gabo Central de Gestión", layout="wide")

# 1. INICIALIZAR EL CONTROLADOR DE COOKIES
controller = CookieController()
time.sleep(0.1) # Pequeña pausa para asegurar que el controlador lea el navegador

# 2. REVISAR EL "BOLETO" (COOKIE)
# Buscamos si el navegador ya tiene una sesión guardada de antes
usuario_guardado = controller.get("usuario_gabo_apps")

# Si el boleto existe y es un usuario válido, lo dejamos pasar directo
if usuario_guardado and usuario_guardado in st.secrets.get("usuarios", {}):
    st.session_state["logueado"] = True
    st.session_state["perfil"] = usuario_guardado

# 3. FUNCIÓN DE LOGIN
def login():
    st.title("🔐 Acceso Centralizado")
    with st.container(border=True):
        user = st.text_input("Usuario").lower()
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", type="primary", use_container_width=True):
            if user in st.secrets["usuarios"] and password == st.secrets["usuarios"][user]:
                # Guardamos el boleto por 30 días (2592000 segundos)
                controller.set("usuario_gabo_apps", user, max_age=2592000)
                
                st.session_state["logueado"] = True
                st.session_state["perfil"] = user
                time.sleep(0.5) # Dar tiempo a que el navegador guarde la cookie
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

# 4. LÓGICA DE NAVEGACIÓN Y AISLAMIENTO
if "logueado" not in st.session_state:
    login()
else:
    perfil = st.session_state["perfil"]
    
    # Barra lateral con botón de salida
    with st.sidebar:
        st.write(f"👤 Sesión: **{perfil.capitalize()}**")
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            # Destruimos el boleto para que no vuelva a entrar solo
            controller.remove("usuario_gabo_apps")
            del st.session_state["logueado"]
            time.sleep(0.5)
            st.rerun()

    # --- EL FILTRO DE SEGURIDAD (Cuidado con los espacios aquí) ---
    if perfil == "cristian":
        import taller_cristian
        taller_cristian.render_app()
        
    elif perfil == "pascual":
        import taller_pascual
        taller_pascual.render_app()
        
    elif perfil == "gabo":
        menu = st.selectbox("Seleccione Aplicación:", [
            "C.H. Automotriz", 
            "Pascual Parabrisas", 
            "Pautas Maxus",
            "Expediente Garantías"
        ])
        st.markdown("---")
        
        if menu == "C.H. Automotriz":
            import taller_cristian
            taller_cristian.render_app()
        elif menu == "Pascual Parabrisas":
            import taller_pascual
            taller_pascual.render_app()
        elif menu == "Pautas Maxus":
            import mantenimiento
            mantenimiento.render_app()
        elif menu == "Expediente Garantías":
            import garantias
            garantias.render_app()

    elif perfil == "cristian":
        import taller_cristian
        taller_cristian.render_app()

    elif perfil == "pascual":
        import taller_pascual
        taller_pascual.render_app()

    # --- NUEVO ACCESO PARA LOS TÉCNICOS ---
    elif perfil == "taller":
        import garantias
        garantias.render_app()
