import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
from bot.config import Config

FLASK_URL = "http://localhost:5000"

st.set_page_config(
    page_title="Carousel Bot",
    page_icon="📱",
    layout="wide",
)

st.title("📱 Instagram Carousel Preview")
st.markdown("---")


def latest_session_status():
    try:
        resp = requests.get(f"{FLASK_URL}/latest-session", timeout=5)
        return resp.json()
    except requests.ConnectionError:
        return {"status": "error", "error": "Cannot connect to Flask backend"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


with st.sidebar:
    st.header("Configuración")
    st.markdown("### Instrucciones")
    st.markdown(
        "1. Envía un tema por WhatsApp al bot\n"
        "2. El bot generará las ideas con GPT-4o-mini\n"
        "3. Las imágenes se crearán con Nano Banana 2\n"
        "4. Revisa el resultado aquí\n"
        "5. Publica en Instagram con un clic"
    )

status_data = latest_session_status()
user_number = status_data.get("user_number", "") if isinstance(status_data, dict) else ""

if status_data["status"] in ("generating", "no_session"):
    st_autorefresh(interval=3000, key="carousel_autorefresh")

if status_data["status"] == "no_session":
    st.info("👋 Envía un mensaje por WhatsApp para empezar a generar un carrusel.")
    st.markdown("Ejemplo: *'Ideas para un post sobre marketing de contenidos'*")

elif status_data["status"] == "generating":
    st.warning("⏳ Generando carrusel... Las imágenes se están creando.")
    st.progress(0.6, text="Generando slides con IA...")

elif status_data["status"] == "error":
    st.error("❌ Ocurrió un error al generar el carrusel. Intenta de nuevo.")

elif status_data["status"] == "published":
    slides = status_data.get("slides", [])
    topic = status_data.get("topic", "")
    media_id = status_data.get("carousel_container_id", "")

    st.success(f"✅ **Publicado en Instagram!** 🎉")
    st.markdown(f"**Tema:** {topic}")
    st.markdown(f"**Media ID:** {media_id}")
    st.markdown("---")

    for i, slide in enumerate(slides):
        img_url = slide.get("image_url", "")
        if img_url.startswith("/"):
            img_url = f"{FLASK_URL}{img_url}"
        col1, col2 = st.columns([1, 3])
        with col1:
            if img_url:
                st.image(img_url, use_container_width=True)
        with col2:
            st.markdown(f"**Slide {i+1}**")
            st.markdown(f"*{slide.get('caption', '')}*")
        st.divider()

elif status_data["status"] == "ready":
    slides = status_data.get("slides", [])
    main_caption = status_data.get("main_caption", "")
    call_to_action = status_data.get("call_to_action", "")
    topic = status_data.get("topic", "")

    st.success(f"✅ Carrusel listo: **{topic}**")
    st.markdown(f"**Caption principal:** {main_caption}")

    if call_to_action:
        st.markdown(f"**🎯 CTA:** {call_to_action}")

    st.divider()

    for i, slide in enumerate(slides):
        img_url = slide.get("image_url", "")
        if img_url.startswith("/"):
            img_url = f"{FLASK_URL}{img_url}"
        col1, col2 = st.columns([1, 3])
        with col1:
            if img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.warning("🖼️ Imagen no disponible")
        with col2:
            st.markdown(f"**Slide {i+1}**")
            st.markdown(f"*{slide.get('caption', '')}*")
        st.divider()

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        if st.button("🚀 Publicar en Instagram", type="primary", use_container_width=True):
            if not user_number:
                st.error("No se pudo identificar el usuario")
            else:
                with st.spinner("Publicando en Instagram..."):
                    resp = requests.post(
                        f"{FLASK_URL}/publish",
                        json={"user_number": user_number},
                        timeout=60,
                    )
                    result = resp.json()
                    if "error" in result:
                        st.error(f"❌ {result['error']}")
                    else:
                        st.success(f"✅ Publicado! Media ID: {result['media_id']}")
                        st.rerun()

    with col2:
        if st.button("🔄 Nuevo", use_container_width=True):
            st.info("Envía un nuevo tema por WhatsApp.")

    with col3:
        if st.button("❌ Rechazar", use_container_width=True):
            st.info("Carrusel rechazado.")

else:
    st.json(status_data)

st.markdown("---")
st.caption("Instagram Carousel Bot | Proof of Concept")
