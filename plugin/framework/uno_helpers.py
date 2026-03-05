"""Shared UNO UI helpers for dialogs and sidebar (LibreOffice control quirks)."""
import unohelper
from com.sun.star.awt import XActionListener


def get_optional(root_window, name):
    """Return control by name or None if missing. Use for optional XDL controls.
    
    Useful for backward-compatible dialogs where controls may not exist in all versions.
    """
    try:
        return root_window.getControl(name)
    except Exception:
        return None


def is_checkbox_control(ctrl):
    """Return True if the control is a checkbox (UnoControlCheckBox or has State/setState).
    
    Handles LibreOffice checkbox quirks: checks service type, control methods, and model properties.
    """
    if not ctrl:
        return False
    try:
        if ctrl.supportsService("com.sun.star.awt.UnoControlCheckBox"):
            return True
        if hasattr(ctrl, "setState") or hasattr(ctrl, "getState"):
            return True
        if hasattr(ctrl.getModel(), "State"):
            return True
    except Exception:
        pass
    return False


def get_checkbox_state(ctrl):
    """Return checkbox state 0 or 1. Prefer control getState(), else model.State.
    
    Handles both control-level getState() and model-level State property.
    """
    if not ctrl:
        return 0
    try:
        if hasattr(ctrl, "getState"):
            return ctrl.getState()
        if hasattr(ctrl.getModel(), "State"):
            return ctrl.getModel().State
    except Exception:
        pass
    return 0


def set_checkbox_state(ctrl, value):
    """Set checkbox state to 0 or 1. Prefer control setState(), else model.State.
    
    Handles both control-level setState() and model-level State property.
    """
    if not ctrl:
        return
    try:
        if hasattr(ctrl, "setState"):
            ctrl.setState(value)
        elif hasattr(ctrl.getModel(), "State"):
            ctrl.getModel().State = value
    except Exception:
        pass


class TabListener(unohelper.Base, XActionListener):
    """Listener for tab buttons in multi-page XDL dialogs.
    
    Usage: dlg.getControl("btn_tab_name").addActionListener(TabListener(dlg, page_number))
    
    The XDL dialog must use dlg:page attributes on controls, and the dialog's Step
    property controls which page is visible.
    """
    def __init__(self, dialog, page):
        self._dlg = dialog
        self._page = page
    
    def actionPerformed(self, ev):
        """Switch to the specified page when button is clicked."""
        self._dlg.getModel().Step = self._page
    
    def disposing(self, ev):
        """Required by XActionListener interface."""
        pass
