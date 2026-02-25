"""Writer track-changes tools."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class SetTrackChanges(ToolBase):
    """Enable or disable change tracking."""

    name = "set_track_changes"
    intent = "review"
    description = "Enable or disable track changes (change recording) in the document."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable track changes, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        enabled = kwargs.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() not in ("false", "0", "no")
        ctx.doc.setPropertyValue("RecordChanges", bool(enabled))
        return {"status": "ok", "record_changes": bool(enabled)}


class GetTrackedChanges(ToolBase):
    """List all tracked changes (redlines) in the document."""

    name = "get_tracked_changes"
    intent = "review"
    description = (
        "List all tracked changes (redlines) in the document, "
        "including type, author, date, and comment."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        recording = False
        try:
            recording = doc.getPropertyValue("RecordChanges")
        except Exception:
            pass

        if not hasattr(doc, "getRedlines"):
            return {
                "status": "ok",
                "recording": recording,
                "changes": [],
                "count": 0,
                "message": "Document does not expose redlines API.",
            }

        redlines = doc.getRedlines()
        enum = redlines.createEnumeration()
        changes = []
        while enum.hasMoreElements():
            redline = enum.nextElement()
            entry = {}
            for prop in (
                "RedlineType", "RedlineAuthor",
                "RedlineComment", "RedlineIdentifier",
            ):
                try:
                    entry[prop] = redline.getPropertyValue(prop)
                except Exception:
                    pass
            try:
                dt = redline.getPropertyValue("RedlineDateTime")
                entry["date"] = "%04d-%02d-%02d %02d:%02d" % (
                    dt.Year, dt.Month, dt.Day, dt.Hours, dt.Minutes
                )
            except Exception:
                pass
            changes.append(entry)

        return {
            "status": "ok",
            "recording": recording,
            "changes": changes,
            "count": len(changes),
        }


class AcceptAllChanges(ToolBase):
    """Accept all tracked changes in the document."""

    name = "accept_all_changes"
    intent = "review"
    description = "Accept all tracked changes in the document."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        # UNO dispatcher is the reliable way to accept all redlines.
        smgr = ctx.ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx.ctx
        )
        frame = ctx.doc.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:AcceptAllTrackedChanges", "", 0, ()
        )
        return {"status": "ok", "message": "All tracked changes accepted."}


class RejectAllChanges(ToolBase):
    """Reject all tracked changes in the document."""

    name = "reject_all_changes"
    intent = "review"
    description = "Reject all tracked changes in the document."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        smgr = ctx.ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx.ctx
        )
        frame = ctx.doc.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:RejectAllTrackedChanges", "", 0, ()
        )
        return {"status": "ok", "message": "All tracked changes rejected."}
