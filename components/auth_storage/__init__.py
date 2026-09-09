"""
Client-side persistent auth storage component.
Provides isolated, browser-specific storage using localStorage and cookies.
"""
import os
from typing import Any, Dict, Optional
import streamlit as st
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))
_auth_storage_component = components.declare_component(
    "auth_storage",
    path=_COMPONENT_DIR
)


def sync_auth_storage(
    action: str = "sync",
    token: Optional[str] = None,
    key: str = "_auth_storage_sync"
) -> Optional[Dict[str, Any]]:
    """
    Client-side persistent auth storage bridge.
    
    Actions:
      - 'sync': queries client browser for any stored persistent session token.
      - 'save': saves the encrypted persistent session token in the client's browser.
      - 'clear': deletes the persistent session token from the client's browser.
    """
    try:
        return _auth_storage_component(
            action=action,
            token=token,
            key=key,
            default=None
        )
    except Exception:
        return None
