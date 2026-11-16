"""Qadam entry point: python -m streamlit run app.py."""
from pathlib import Path
from importlib.util import find_spec

import streamlit as st

# Compatibility imports for earlier course examples.
from algorithms.astar import astar
from environments.grid_world import step, make_world, manhattan
from ui.cache import simulate


FRONTEND = Path(__file__).resolve().parent / "frontend"
LABELS = {
    "kk": ("Баптаулар мәзірі", "Тақырып", "Ашық", "Қараңғы", "Поляр шұғыласы"),
    "ru": ("Меню настроек", "Тема", "Светлая", "Тёмная", "Полярное сияние"),
    "en": ("Settings menu", "Theme", "Light", "Dark", "Northern Lights"),
}
THEME_COLORS = {
    "Light": ("#f1f5f9", "#ffffff", "#0f172a", "#475569", "#cbd5e1"),
    "Dark": ("#090D16", "#1e293b", "#f8fafc", "#cbd5e1", "#334155"),
    "Aurora": ("#121026", "#26203f", "#faf7ff", "#d6cbed", "#56496f"),
}


def set_theme(value):
    if value in THEME_COLORS:
        st.session_state["qadam_theme"] = value


def custom_css(theme):
    """Return complete shell CSS; Leaflet has its own isolated stylesheet."""
    if theme not in THEME_COLORS:
        theme = "Dark"
    bg, panel, text, muted, border = THEME_COLORS[theme]
    tokens = {
        "BG": bg,
        "PANEL": panel,
        "TEXT": text,
        "MUTED": muted,
        "BORDER": border,
        "SCHEME": "light" if theme == "Light" else "dark",
        "ACTIVE": f"qadam_{theme.lower()}",
    }
    css = (FRONTEND / "shell.css").read_text(encoding="utf-8")
    for key, value in tokens.items():
        css = css.replace(f"__{key}__", value)
    return css


def main():
    st.set_page_config(
        page_title="Qadam · Астана", page_icon="🧭", layout="wide",
        initial_sidebar_state="collapsed",
    )
    theme = st.session_state.setdefault("qadam_theme", "Dark")
    lang = st.session_state.setdefault("qadam_language", "kk")
    labels = LABELS.get(lang, LABELS["kk"])
    st.markdown(f"<style>{custom_css(theme)}</style>", unsafe_allow_html=True)

    if find_spec("geopy") is None:
        st.error("Мекенжай іздеу үшін geopy орнатыңыз / Install geopy for address search")
        st.code('python -m pip install "geopy>=2.4,<3"', language="bash")
        st.stop()

    with st.container(key="qadam_theme_menu"):
        with st.popover(labels[0]):
            st.selectbox(
                "Тіл / Язык / Language", ["kk", "ru", "en"],
                format_func=lambda code: {"kk": "Қазақша", "ru": "Русский", "en": "English"}[code],
                key="qadam_language",
            )
            st.caption(labels[1])
            st.button("☀ " + labels[2], key="qadam_light", on_click=set_theme,
                      args=("Light",), use_container_width=True)
            st.button("☾ " + labels[3], key="qadam_dark", on_click=set_theme,
                      args=("Dark",), use_container_width=True)
            st.button("✦ " + labels[4], key="qadam_aurora", on_click=set_theme,
                      args=("Aurora",), use_container_width=True)

    with st.sidebar:
        mode = st.radio("Карта режимі", ["Астана · нақты карта", "Grid World · оқу режимі"])
    if mode == "Астана · нақты карта":
        from ui.navigation import main as astana_main
        astana_main()
    else:
        from ui.grid_page import grid_main
        grid_main()


if __name__ == "__main__":
    main()
