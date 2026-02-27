"""Dialog utilities for LibreOffice UNO.

Provides helpers for message boxes, clipboard operations, rich dialogs
(with buttons, live updates, etc.), and XDL dialog loading.

Usage from modules::

    from plugin.framework.dialogs import msgbox, msgbox_with_copy, copy_to_clipboard
    from plugin.framework.uno_context import get_ctx

    msgbox(get_ctx(), "Title", "Hello world")
    msgbox_with_copy(get_ctx(), "URL", "Server running at:", "https://localhost:8766")

XDL dialog loading (used by ModuleBase helpers)::

    from plugin.framework.dialogs import load_module_dialog, load_framework_dialog

    dlg = load_framework_dialog("info_action")
    dlg.getControl("MessageText").getModel().Label = "Hello"
    dlg.execute()
    dlg.dispose()
"""

import logging
import threading

log = logging.getLogger("localwriter.dialogs")

EXTENSION_ID = "org.extension.localwriter"


# ── Simple message box ──────────────────────────────────────────────


def msgbox(ctx, title, message):
    """Show an info message box."""
    if not ctx:
        log.info("MSGBOX (no ctx) - %s: %s", title, message)
        return
    try:
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)
        frame = desktop.getCurrentFrame()
        if frame is None:
            log.info("MSGBOX (no frame) - %s: %s", title, message)
            return
        window = frame.getContainerWindow()
        toolkit = smgr.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        box = toolkit.createMessageBox(
            window, 1, 1, title, message)  # INFOBOX, OK button
        box.execute()
    except Exception:
        log.exception("MSGBOX fallback - %s: %s", title, message)


# ── Clipboard ────────────────────────────────────────────────────────


def copy_to_clipboard(ctx, text):
    """Copy text to system clipboard via LO API. Returns True on success."""
    if not ctx:
        return False
    try:
        import uno
        import unohelper
        from com.sun.star.datatransfer import XTransferable, DataFlavor

        smgr = ctx.ServiceManager
        clip = smgr.createInstanceWithContext(
            "com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)

        class _TextTransferable(unohelper.Base, XTransferable):
            def __init__(self, txt):
                self._text = txt

            def getTransferData(self, flavor):
                return self._text

            def getTransferDataFlavors(self):
                f = DataFlavor()
                f.MimeType = "text/plain;charset=utf-16"
                f.HumanPresentableName = "Unicode Text"
                f.DataType = uno.getTypeByName("string")
                return (f,)

            def isDataFlavorSupported(self, flavor):
                return "text/plain" in flavor.MimeType

        clip.setContents(_TextTransferable(text), None)
        log.info("Copied to clipboard: %s", text)
        return True
    except Exception:
        log.exception("Clipboard copy failed")
        return False


# ── Message box with Copy button ─────────────────────────────────────


def msgbox_with_copy(ctx, title, message, copy_text):
    """Show a dialog with a message and a Copy button."""
    if not ctx:
        log.info("MSGBOX_COPY (no ctx) - %s: %s", title, message)
        return
    try:
        import unohelper
        from com.sun.star.awt import XActionListener

        smgr = ctx.ServiceManager

        dlg_model = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        dlg_model.Title = title
        dlg_model.Width = 250
        dlg_model.Height = 80

        lbl = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlFixedTextModel")
        lbl.Name = "Msg"
        lbl.PositionX = 10
        lbl.PositionY = 6
        lbl.Width = 230
        lbl.Height = 42
        lbl.MultiLine = True
        lbl.Label = message
        dlg_model.insertByName("Msg", lbl)

        copy_btn = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlButtonModel")
        copy_btn.Name = "CopyBtn"
        copy_btn.PositionX = 10
        copy_btn.PositionY = 56
        copy_btn.Width = 75
        copy_btn.Height = 14
        copy_btn.Label = "Copy URL"
        dlg_model.insertByName("CopyBtn", copy_btn)

        ok_btn = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlButtonModel")
        ok_btn.Name = "OKBtn"
        ok_btn.PositionX = 190
        ok_btn.PositionY = 56
        ok_btn.Width = 50
        ok_btn.Height = 14
        ok_btn.Label = "OK"
        ok_btn.PushButtonType = 1  # OK
        dlg_model.insertByName("OKBtn", ok_btn)

        dlg = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        dlg.setModel(dlg_model)
        toolkit = smgr.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        dlg.createPeer(toolkit, None)

        class _CopyListener(unohelper.Base, XActionListener):
            def __init__(self, dialog, context, text):
                self._dlg = dialog
                self._ctx = context
                self._text = text

            def actionPerformed(self, ev):
                if copy_to_clipboard(self._ctx, self._text):
                    try:
                        self._dlg.getModel().getByName("CopyBtn").Label = \
                            "Copied!"
                    except Exception:
                        pass

            def disposing(self, ev):
                pass

        dlg.getControl("CopyBtn").addActionListener(
            _CopyListener(dlg, ctx, copy_text))

        dlg.execute()
        dlg.dispose()
    except Exception:
        log.exception("Copy dialog error")
        msgbox(ctx, title, message)


# ── Status dialog with live updates ──────────────────────────────────


def status_dialog(ctx, title, build_status_fn, copy_url_fn=None):
    """Show a status dialog that updates live via a background thread.

    Args:
        ctx: UNO component context.
        title: Dialog title.
        build_status_fn: Callable() -> str returning the status text.
            Called once immediately, then once more after a short delay
            for live probe results.
        copy_url_fn: Optional callable() -> str returning a URL to copy.
            If provided and returns non-empty, a Copy button is shown.
    """
    if not ctx:
        log.info("STATUS (no ctx) - %s", title)
        return
    try:
        import unohelper
        from com.sun.star.awt import XActionListener

        smgr = ctx.ServiceManager
        initial_text = build_status_fn()

        dlg_model = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        dlg_model.Title = title
        dlg_model.Width = 230
        dlg_model.Height = 110

        lbl = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlFixedTextModel")
        lbl.Name = "StatusText"
        lbl.PositionX = 10
        lbl.PositionY = 6
        lbl.Width = 210
        lbl.Height = 72
        lbl.MultiLine = True
        lbl.Label = initial_text
        dlg_model.insertByName("StatusText", lbl)

        # Copy button (disabled until copy_url_fn returns something)
        has_copy = copy_url_fn is not None
        if has_copy:
            copy_btn = dlg_model.createInstance(
                "com.sun.star.awt.UnoControlButtonModel")
            copy_btn.Name = "CopyBtn"
            copy_btn.PositionX = 10
            copy_btn.PositionY = 88
            copy_btn.Width = 65
            copy_btn.Height = 14
            copy_btn.Label = "Copy URL"
            copy_btn.Enabled = bool(copy_url_fn())
            dlg_model.insertByName("CopyBtn", copy_btn)

        ok_btn = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlButtonModel")
        ok_btn.Name = "OKBtn"
        ok_btn.PositionX = 170
        ok_btn.PositionY = 88
        ok_btn.Width = 50
        ok_btn.Height = 14
        ok_btn.Label = "OK"
        ok_btn.PushButtonType = 1
        dlg_model.insertByName("OKBtn", ok_btn)

        dlg = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        dlg.setModel(dlg_model)
        toolkit = smgr.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        dlg.createPeer(toolkit, None)

        # Wire copy button
        if has_copy:
            class _CopyListener(unohelper.Base, XActionListener):
                def __init__(self, dialog, context, url_fn):
                    self._dlg = dialog
                    self._ctx = context
                    self._url_fn = url_fn

                def actionPerformed(self, ev):
                    url = self._url_fn()
                    if url and copy_to_clipboard(self._ctx, url):
                        try:
                            self._dlg.getModel().getByName("CopyBtn").Label = \
                                "Copied!"
                        except Exception:
                            pass

                def disposing(self, ev):
                    pass

            dlg.getControl("CopyBtn").addActionListener(
                _CopyListener(dlg, ctx, copy_url_fn))

        # Background update
        import time

        def _probe_update():
            time.sleep(0.05)
            try:
                updated = build_status_fn()
                dlg_model.getByName("StatusText").Label = updated
                if has_copy:
                    url = copy_url_fn()
                    dlg_model.getByName("CopyBtn").Enabled = bool(url)
            except Exception:
                pass  # dialog already closed

        threading.Thread(target=_probe_update, daemon=True).start()

        dlg.execute()
        dlg.dispose()
    except Exception:
        log.exception("Status dialog error")
        msgbox(ctx, title, build_status_fn())


# ── About dialog ─────────────────────────────────────────────────────


def about_dialog(ctx):
    """Show the LocalWriter About dialog with a clickable GitHub link."""
    try:
        from plugin.version import EXTENSION_VERSION
    except ImportError:
        EXTENSION_VERSION = "?"

    if not ctx:
        log.info("ABOUT (no ctx)")
        return

    try:
        smgr = ctx.ServiceManager

        dlg_model = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        dlg_model.Title = "About LocalWriter"
        dlg_model.Width = 220
        dlg_model.Height = 90

        # Info text
        lbl = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlFixedTextModel")
        lbl.Name = "Info"
        lbl.PositionX = 10
        lbl.PositionY = 8
        lbl.Width = 200
        lbl.Height = 36
        lbl.MultiLine = True
        lbl.Label = (
            "LocalWriter\n"
            "Version: %s\n"
            "AI-powered extension for LibreOffice" % EXTENSION_VERSION
        )
        dlg_model.insertByName("Info", lbl)

        # Clickable hyperlink
        link = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlFixedHyperlinkModel")
        link.Name = "GitHubLink"
        link.PositionX = 10
        link.PositionY = 48
        link.Width = 200
        link.Height = 12
        link.Label = "GitHub: quazardous/localwriter"
        link.URL = "https://github.com/quazardous/localwriter"
        link.TextColor = 0x0563C1  # standard link blue
        dlg_model.insertByName("GitHubLink", link)

        ok_btn = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlButtonModel")
        ok_btn.Name = "OKBtn"
        ok_btn.PositionX = 160
        ok_btn.PositionY = 68
        ok_btn.Width = 50
        ok_btn.Height = 14
        ok_btn.Label = "OK"
        ok_btn.PushButtonType = 1
        dlg_model.insertByName("OKBtn", ok_btn)

        dlg = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        dlg.setModel(dlg_model)
        toolkit = smgr.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        dlg.createPeer(toolkit, None)
        dlg.execute()
        dlg.dispose()
    except Exception:
        log.exception("About dialog error")
        msgbox(ctx, "About LocalWriter",
               "LocalWriter %s\nhttps://github.com/quazardous/localwriter"
               % EXTENSION_VERSION)


# ── XDL dialog loading ──────────────────────────────────────────────


def load_module_dialog(module_name, dialog_name):
    """Load an XDL dialog from a module's directory.

    Returns an XDialog ready for execute()/dispose().
    """
    module_dir = module_name.replace(".", "_")
    xdl_path = "plugin/modules/%s/%s.xdl" % (module_dir, dialog_name)
    return _load_xdl(xdl_path)


def load_framework_dialog(dialog_name):
    """Load an XDL dialog from the framework's directory.

    Returns an XDialog ready for execute()/dispose().
    """
    xdl_path = "plugin/framework/%s.xdl" % dialog_name
    return _load_xdl(xdl_path)


def _load_xdl(relative_path):
    """Load an XDL file from the extension bundle via DialogProvider2."""
    from plugin.framework.uno_context import get_ctx

    ctx = get_ctx()
    smgr = ctx.getServiceManager()
    pip = ctx.getValueByName(
        "/singletons/com.sun.star.deployment.PackageInformationProvider")
    base = pip.getPackageLocation(EXTENSION_ID)
    url = base + "/" + relative_path
    dp = smgr.createInstanceWithContext(
        "com.sun.star.awt.DialogProvider2", ctx)
    return dp.createDialog(url)
