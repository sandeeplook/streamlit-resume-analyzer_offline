"""
Application configuration.

This offline edition needs no API keys - everything runs locally in Python.
Settings are still read from Streamlit secrets first, then environment
variables, in case you want to tune limits without editing code.
"""
import os
import streamlit as st


def _get(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


class Settings:
    def __init__(self) -> None:
        self.app_name: str = _get("APP_NAME", "AI Resume Verification & JD Match Analyzer")
        self.max_upload_size_mb: int = int(_get("MAX_UPLOAD_SIZE_MB", "10"))
        self.allowed_extensions = [".pdf", ".docx"]
        self.analysis_engine_label: str = "Offline rule-based analyzer (no external API)"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@st.cache_resource
def get_settings() -> Settings:
    return Settings()
