"""
Custom Streamlit theme and styling utilities with dark mode support
"""
import streamlit as st
import platform
import subprocess
from typing import Dict, Literal, Optional

# Theme type
ThemeMode = Literal["system", "light", "dark"]

# Light theme configuration - simplified for better readability
LIGHT_THEME = {
    "gradient_start": "#ffffff",  # Clean white
    "gradient_end": "#f3f4f6",    # Light gray
    "primary": "#2563eb",         # Blue 600 - better contrast
    "text": "#111827",            # Gray 900 - darker for readability
    "text_secondary": "#4b5563",  # Gray 600
    "background": "#ffffff",      # Pure white
    "card_background": "#ffffff", # Solid white
    "sidebar_bg": "#f9fafb",      # Gray 50
    "border": "#d1d5db",          # Gray 300
    "code_bg": "#1f2937",         # Gray 800
    "input_bg": "#ffffff",
}

# Dark theme configuration - simplified for better readability
DARK_THEME = {
    "gradient_start": "#111827",  # Gray 900
    "gradient_end": "#1f2937",    # Gray 800
    "primary": "#3b82f6",         # Blue 500
    "text": "#f9fafb",            # Gray 50 - lighter for readability
    "text_secondary": "#9ca3af",  # Gray 400
    "background": "#111827",      # Gray 900
    "card_background": "#1f2937", # Gray 800 - solid
    "sidebar_bg": "#1f2937",      # Gray 800
    "border": "#374151",          # Gray 700
    "code_bg": "#111827",         # Gray 900
    "input_bg": "#374151",        # Gray 700
}

# Default to light theme for backward compatibility
_current_theme: ThemeMode = "light"

# Legacy variables for backward compatibility
GRADIENT_START = LIGHT_THEME["gradient_start"]
GRADIENT_END = LIGHT_THEME["gradient_end"]
PRIMARY_COLOR = LIGHT_THEME["primary"]
TEXT_COLOR = LIGHT_THEME["text"]
BACKGROUND_COLOR = LIGHT_THEME["background"]
CARD_BACKGROUND = LIGHT_THEME["card_background"]

# Risk color mapping
RISK_COLORS: Dict[str, str] = {
    "low": "#22c55e",
    "medium": "#facc15",
    "high": "#f97316",
    "critical": "#dc2626",
}

# Risk emoji mapping
RISK_EMOJIS: Dict[str, str] = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}


def get_theme(theme_mode: ThemeMode = "light") -> Dict[str, str]:
    """Get the theme colors based on current mode

    Args:
        theme_mode: 'system', 'light', or 'dark'

    Returns:
        Theme color dictionary
    """
    # Resolve system mode to actual theme
    if theme_mode == "system":
        theme_mode = detect_system_theme()

    return DARK_THEME if theme_mode == "dark" else LIGHT_THEME


def set_theme_mode(mode: ThemeMode):
    """Set the global theme mode"""
    global _current_theme
    _current_theme = mode


def get_theme_mode() -> ThemeMode:
    """Get the current theme mode"""
    return _current_theme


def detect_system_theme() -> str:
    """
    Detect OS theme preference (light/dark) with full cross-platform support

    Returns:
        'light' or 'dark' based on OS theme setting
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceTheme"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if "Dark" in result.stdout:
                return "dark"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    elif system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as key:
                # AppsUseLightTheme: 0 = dark, 1 = light
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "dark" if value == 0 else "light"
        except (OSError, ImportError):
            pass

    elif system == "Linux":
        # Try multiple methods for Linux
        try:
            # GNOME via gsettings
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if "dark" in result.stdout.lower():
                return "dark"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        try:
            # Check KDE config file
            from pathlib import Path
            kdeglobals = Path.home() / ".config" / "kdeglobals"
            if kdeglobals.exists():
                content = kdeglobals.read_text()
                if "Theme=" in content:
                    for line in content.split("\n"):
                        if line.startswith("Theme="):
                            if "dark" in line.lower():
                                return "dark"
        except (OSError, IOError):
            pass

        try:
            # Check XDG_CURRENT_DESKTOP environment variable
            import os
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            if "kde" in desktop:
                # Try kreadconfig5 for KDE
                result = subprocess.run(
                    ["kreadconfig5", "--group", "KDE", "--key", "LookAndFeelPackage"],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if "dark" in result.stdout.lower():
                    return "dark"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Fallback to light mode
    return "light"


def apply_custom_theme(theme_mode: ThemeMode = "light"):
    """
    Apply custom gradient theme to Streamlit app with dark mode support

    Args:
        theme_mode: 'system', 'light', or 'dark' theme mode
    """
    # Resolve system theme to actual theme
    actual_theme = theme_mode
    if theme_mode == "system":
        actual_theme = detect_system_theme()

    theme = get_theme(actual_theme)
    set_theme_mode(actual_theme)

    custom_css = f"""
    <style>
    /* Main container background - no gradient for better readability */
    .main {{
        background-color: {theme['background']};
        min-height: 100vh;
    }}

    /* Sidebar background - solid color */
    [data-testid="stSidebar"] {{
        background-color: {theme['sidebar_bg']};
    }}

    /* Global text color */
    .main .stMarkdown, .main .stText, .main p, .main li, .main h1, .main h2, .main h3 {{
        color: {theme['text']} !important;
    }}

    /* Secondary text color */
    .main .stCaption, .caption {{
        color: {theme['text_secondary']} !important;
    }}

    /* Card styling */
    .custom-card {{
        background-color: {theme['card_background']};
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
        border: 1px solid {theme['border']};
    }}

    /* Risk badge styling */
    .risk-badge {{
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 700;
        text-align: center;
        display: inline-block;
        min-width: 100px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }}

    /* Animated fade-in effect */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(-10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .fade-in {{
        animation: fadeIn 0.5s ease-in;
    }}

    /* Enhanced code block */
    .stCode {{
        border-radius: 8px;
        border: 1px solid {theme['border']};
        background-color: {theme['code_bg']} !important;
    }}

    /* Code block text color */
    .stCode code {{
        color: {theme['text']} !important;
    }}

    /* Metric card enhancement */
    [data-testid="stMetricValue"] {{
        font-weight: 700;
        font-size: 1.5rem;
        color: {theme['text']} !important;
    }}

    [data-testid="stMetricDelta"] {{
        color: {theme['text_secondary']} !important;
    }}

    /* Button styling */
    .stButton > button {{
        border-radius: 8px;
        transition: all 0.3s ease;
    }}

    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.25);
    }}

    /* Form styling */
    .stForm {{
        background-color: {theme['card_background']};
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
        border: 1px solid {theme['border']};
    }}

    /* Input styling */
    .stTextArea > div > div, .stTextInput > div > div {{
        background-color: {theme['input_bg']} !important;
        border: 1px solid {theme['border']} !important;
        color: {theme['text']} !important;
    }}

    .stTextArea textarea, .stTextInput input {{
        background-color: {theme['input_bg']} !important;
        color: {theme['text']} !important;
    }}

    /* Selectbox styling */
    .stSelectbox > div > div {{
        background-color: {theme['input_bg']} !important;
        border: 1px solid {theme['border']} !important;
        color: {theme['text']} !important;
    }}

    /* Status container styling */
    [data-testid="stStatusWidget"] {{
        background-color: {theme['card_background']};
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid {theme['border']};
    }}

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: {theme['card_background']};
        padding: 8px;
        border-radius: 12px;
    }}

    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        background-color: transparent;
        color: {theme['text_secondary']};
    }}

    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background-color: {theme['primary']};
        color: white;
    }}

    /* Expander styling */
    .streamlit-expanderHeader {{
        background-color: {theme['card_background']};
        border: 1px solid {theme['border']};
        border-radius: 8px;
        color: {theme['text']} !important;
    }}

    .streamlit-expanderContent {{
        background-color: {theme['card_background']};
        border: 1px solid {theme['border']};
        border-radius: 8px;
    }}

    /* Info, success, warning, error boxes */
    .stAlert {{
        background-color: {theme['card_background']};
        border: 1px solid {theme['border']};
        border-radius: 8px;
    }}

    /* Divider */
    hr {{
        border-color: {theme['border']};
    }}

    /* Slider styling */
    .stSlider > div > div > div {{
        background-color: {theme['primary']};
    }}

    /* Hide Streamlit's automatic anchor links on headers */
    .stMarkdown h1 a:hover, .stMarkdown h2 a:hover, .stMarkdown h3 a:hover,
    .stMarkdown h4 a:hover, .stMarkdown h5 a:hover, .stMarkdown h6 a:hover,
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a,
    .stMarkdown h4 a, .stMarkdown h5 a, .stMarkdown h6 a,
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {{
        visibility: hidden !important;
        pointer-events: none !important;
        display: none !important;
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def refresh_theme():
    """Refresh the theme with current mode (call after theme change)"""
    apply_custom_theme(get_theme_mode())


def get_risk_color(risk: str) -> str:
    """
    Get color hex code for risk level

    Args:
        risk: Risk level string (low, medium, high, critical)

    Returns:
        Hex color code
    """
    return RISK_COLORS.get((risk or "").lower(), "#64748b")


def get_risk_emoji(risk: str) -> str:
    """
    Get emoji for risk level

    Args:
        risk: Risk level string (low, medium, high, critical)

    Returns:
        Emoji character
    """
    return RISK_EMOJIS.get((risk or "").lower(), "⚪")


def render_risk_badge(risk: str) -> str:
    """
    Render HTML risk badge

    Args:
        risk: Risk level string

    Returns:
        HTML string for risk badge
    """
    color = get_risk_color(risk)
    emoji = get_risk_emoji(risk)
    return f'<span class="risk-badge" style="background-color: {color}; color: white;">{emoji} {risk.upper()}</span>'


def render_metric_card(title: str, value: str, subtitle: str = "", color: str = None, theme_mode: ThemeMode = "light") -> str:
    """
    Render a styled metric card

    Args:
        title: Card title
        value: Main value to display
        subtitle: Optional subtitle text
        color: Accent color (default: uses theme primary)
        theme_mode: Current theme mode

    Returns:
        HTML string for metric card
    """
    theme = get_theme(theme_mode)
    if color is None:
        color = theme["primary"]

    # Convert color to lighter version for background
    color_light = color + "22"  # Adding alpha
    color_medium = color + "44"

    # Build subtitle HTML separately to avoid f-string backslash issues
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<div style="font-size: 0.8rem; color: {theme["text_secondary"]};">{subtitle}</div>'

    return f"""
    <div style="background: linear-gradient(135deg, {color_light} 0%, {color_medium} 100%);
                border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
                border-left: 4px solid {color};">
        <div style="font-size: 0.85rem; color: {theme['text_secondary']}; font-weight: 600;">{title}</div>
        <div style="font-size: 2rem; font-weight: 700; color: {color}; margin: 0.5rem 0;">{value}</div>
        {subtitle_html}
    </div>
    """


def get_gradient_text(text: str, start_color: str = None, end_color: str = None, theme_mode: ThemeMode = "light") -> str:
    """
    Create gradient text effect

    Args:
        text: Text to apply gradient to
        start_color: Start gradient color (default: uses theme)
        end_color: End gradient color (default: uses theme)
        theme_mode: Current theme mode

    Returns:
        HTML string with gradient text
    """
    theme = get_theme(theme_mode)
    if start_color is None:
        start_color = theme["gradient_start"]
    if end_color is None:
        end_color = theme["gradient_end"]

    return f"""
    <span style="background: linear-gradient(90deg, {start_color}, {end_color});
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 700;">
        {text}
    </span>
    """
