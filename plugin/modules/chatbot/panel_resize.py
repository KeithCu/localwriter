import unohelper

from com.sun.star.awt import XWindowListener

from plugin.framework.logging import debug_log


class _PanelResizeListener(unohelper.Base, XWindowListener):
    """Adjusts panel layout on resize. Reads control sizes/gaps from the XDL;
    only the response area height changes to fill available space."""

    def __init__(self, controls):
        self._c = controls        # dict name -> control or None
        self._initial = None      # captured from XDL-loaded pixel positions
        self._in_relayout = False

    def windowResized(self, evt):
        r = evt.Source.getPosSize()
        debug_log("windowResized: W=%d H=%d" % (r.Width, r.Height), context="Chat")
        if self._in_relayout:
            debug_log("windowResized: skipped (in_relayout)", context="Chat")
            return
        try:
            self._in_relayout = True
            self._relayout(evt.Source)
        except Exception as e:
            debug_log("windowResized error: %s" % e, context="Chat")
        finally:
            self._in_relayout = False

    def windowMoved(self, evt):  # noqa: D401, D416
        """No-op for sidebar resize listener."""
        pass

    def windowShown(self, evt):  # noqa: D401, D416
        """No-op for sidebar resize listener."""
        pass

    def windowHidden(self, evt):  # noqa: D401, D416
        """No-op for sidebar resize listener."""
        pass

    def disposing(self, evt):  # noqa: D401, D416
        """No-op for sidebar resize listener."""
        pass

    def _capture_initial(self, win):
        """Snapshot XDL-loaded pixel positions/sizes of every control."""
        r = win.getPosSize()
        if r.Width <= 0 or r.Height <= 0:
            return
        info = {"win_w": r.Width, "win_h": r.Height, "ctrls": {}}
        resp = self._c.get("response")
        if resp:
            rr = resp.getPosSize()
            info["resp_bottom"] = rr.Y + rr.Height
        for name, ctrl in self._c.items():
            if ctrl:
                cr = ctrl.getPosSize()
                info["ctrls"][name] = (cr.X, cr.Y, cr.Width, cr.Height)
        self._initial = info

    def _relayout(self, win):
        r = win.getPosSize()
        w, h = r.Width, r.Height
        if w <= 0 or h <= 0:
            return

        if self._initial is None:
            self._capture_initial(win)

        if self._initial is None:
            debug_log("_relayout: no initial state, skip", context="Chat")
            return

        iw = self._initial["win_w"]
        ih = self._initial["win_h"]
        resp_bottom = self._initial.get("resp_bottom", 0)

        # Use anchoring/filling instead of scaling ratios to prevent feedback loops.
        # Controls in fluid_controls will stretch to fill width.
        # Buttons and labels stay fixed size and anchored left.
        fluid_controls = (
            "response",
            "query",
            "model_selector",
            "image_model_selector",
            "status",
            "aspect_ratio_selector",
        )

        top_of_bottom = h  # will track highest new_y below response
        for name, ctrl in self._c.items():
            if not ctrl or name == "response":
                continue
            orig = self._initial["ctrls"].get(name)
            if not orig:
                continue
            ox, oy, ow, oh = orig

            if name in fluid_controls:
                # Fill space to right margin
                new_x = ox
                margin_right = iw - (ox + ow)
                new_w = max(10, w - ox - margin_right)
            else:
                # Fixed size, anchored left
                new_x = ox
                new_w = ow

            if oy >= resp_bottom:
                # Anchor to bottom: preserve distance from bottom edge
                new_y = h - (ih - oy)
                cur = ctrl.getPosSize()
                if (
                    cur.X != new_x
                    or cur.Y != new_y
                    or cur.Width != new_w
                    or cur.Height != oh
                ):
                    ctrl.setPosSize(new_x, new_y, new_w, oh, 15)
                top_of_bottom = min(top_of_bottom, new_y)
            else:
                # Above response: stay anchored to top
                cur = ctrl.getPosSize()
                if (
                    cur.X != new_x
                    or cur.Y != oy
                    or cur.Width != new_w
                    or cur.Height != oh
                ):
                    ctrl.setPosSize(new_x, oy, new_w, oh, 15)

        # Second pass: stretch response area to fill remaining vertical gap
        resp_orig = self._initial["ctrls"].get("response")
        resp_ctrl = self._c.get("response")
        if resp_orig and resp_ctrl:
            rx, ry, rw, rh = resp_orig
            gap = resp_bottom - (ry + rh)  # original gap below response
            if gap < 0:
                gap = 2
            new_rh = max(30, top_of_bottom - gap - ry)

            # Fill width to right margin
            margin_right = iw - (rx + rw)
            new_rw = max(10, w - rx - margin_right)

            cur = resp_ctrl.getPosSize()
            if (
                cur.X != rx
                or cur.Y != ry
                or cur.Width != new_rw
                or cur.Height != new_rh
            ):
                resp_ctrl.setPosSize(rx, ry, new_rw, new_rh, 15)

