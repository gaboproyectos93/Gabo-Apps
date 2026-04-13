import streamlit as st

# Configuración inicial (debe ser lo primero)
st.set_page_config(page_title="Gabo Central de Gestión", layout="wide")

# 1. FUNCIÓN DE LOGIN
def login():
    st.title("🔐 Acceso Centralizado")
    with st.container(border=True):
        user = st.text_input("Usuario").lower()
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", type="primary", use_container_width=True):
            if user in st.secrets["usuarios"] and password == st.secrets["usuarios"][user]:
                st.session_state["logueado"] = True
                st.session_state["perfil"] = user
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

# 2. LÓGICA DE NAVEGACIÓN
if "logueado" not in st.session_state:
    login()
else:
    perfil = st.session_state["perfil"]
    
    # Barra lateral de salida
    with st.sidebar:
        st.write(f"👤 Sesión: **{perfil.capitalize()}**")
        if st.button("Cerrar Sesión"):
            del st.session_state["logueado"]
            st.rerun()

    # --- EL FILTRO DE SEGURIDAD (AISLAMIENTO) ---
    if perfil == "cristian":
        import taller_cristian
        taller_cristian.render_app()
        
    elif perfil == "pascual":
        import taller_pascual
        taller_pascual.render_app()
        
    elif perfil == "gabo":
        menu = st.selectbox("Seleccione Aplicación:", ["C.H. Automotriz", "Pascual Parabrisas", "App Nueva 1", "App Nueva 2", "App Nueva 3"])
        if menu == "C.H. Automotriz":
            import taller_cristian
            taller_cristian.render_app()
        elif menu == "Pascual Parabrisas":
            import taller_pascual
            taller_pascual.render_app()
        else:
            st.info(f"🏗️ La aplicación '{menu}' está en desarrollo.")
