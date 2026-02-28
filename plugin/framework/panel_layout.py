"""Programmatic sidebar panel layout helpers.

Creates UNO container windows and controls without XDL files, avoiding
cross-VCL-backend rendering issues (GTK vs Qt vs Win32).
"""


def create_panel_window(ctx, parent_window):
    """Create a UnoControlContainer peered to *parent_window*.

    Returns a container that supports ``addControl()`` / ``getControl()``,
    equivalent to what ``ContainerWindowProvider.createContainerWindow()``
    returns from an XDL file.
    """
    smgr = ctx.getServiceManager()
    model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlContainerModel", ctx)
    model.BackgroundColor = -1  # inherit / transparent

    container = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlContainer", ctx)
    container.setModel(model)

    toolkit = smgr.createInstanceWithContext(
        "com.sun.star.awt.Toolkit", ctx)
    container.createPeer(toolkit, parent_window)

    container.setVisible(True)
    parent_rect = parent_window.getPosSize()
    if parent_rect.Width > 0 and parent_rect.Height > 0:
        container.setPosSize(
            0, 0, parent_rect.Width, parent_rect.Height, 15)

    return container


def add_control(ctx, container, name, service_name, model_props=None):
    """Add a named control to *container*.

    *service_name* is the short UNO control type, e.g. ``"Edit"``,
    ``"FixedText"``, ``"Button"``.  Creates the matching
    ``UnoControl<service_name>Model`` + ``UnoControl<service_name>``.

    Returns ``(control, model)`` tuple.
    """
    smgr = ctx.getServiceManager()
    model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControl%sModel" % service_name, ctx)
    if model_props:
        for k, v in model_props.items():
            setattr(model, k, v)

    ctrl = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControl%s" % service_name, ctx)
    ctrl.setModel(model)
    container.addControl(name, ctrl)
    return ctrl, model
