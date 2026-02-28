import json
from plugin.framework.logging import debug_log

def _err(message):
    return json.dumps({"status": "error", "message": message})

def tool_set_track_changes(model, ctx, args):
    """Enable or disable change tracking in the document."""
    enabled = args.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("false", "0", "no")
    try:
        model.setPropertyValue("RecordChanges", bool(enabled))
        return json.dumps({"status": "ok", "record_changes": bool(enabled)})
    except Exception as e:
        debug_log("tool_set_track_changes error: %s" % e, context="Chat")
        return _err(str(e))

def tool_get_tracked_changes(model, ctx, args):
    """List all tracked changes (redlines) in the document."""
    try:
        recording = False
        try:
            recording = model.getPropertyValue("RecordChanges")
        except Exception:
            pass
        if not hasattr(model, "getRedlines"):
            return json.dumps({"status": "ok", "recording": recording,
                               "changes": [], "count": 0,
                               "message": "Document does not expose redlines API"})
        redlines = model.getRedlines()
        enum = redlines.createEnumeration()
        changes = []
        while enum.hasMoreElements():
            redline = enum.nextElement()
            entry = {}
            for prop in ("RedlineType", "RedlineAuthor",
                         "RedlineComment", "RedlineIdentifier"):
                try:
                    entry[prop] = redline.getPropertyValue(prop)
                except Exception:
                    pass
            try:
                dt = redline.getPropertyValue("RedlineDateTime")
                entry["date"] = "%04d-%02d-%02d %02d:%02d" % (
                    dt.Year, dt.Month, dt.Day, dt.Hours, dt.Minutes)
            except Exception:
                pass
            changes.append(entry)
        return json.dumps({"status": "ok", "recording": recording,
                           "changes": changes, "count": len(changes)})
    except Exception as e:
        debug_log("tool_get_tracked_changes error: %s" % e, context="Chat")
        return _err(str(e))

def tool_accept_all_changes(model, ctx, args):
    """Accept all tracked changes in the document."""
    try:
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        frame = model.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:AcceptAllTrackedChanges", "", 0, ())
        return json.dumps({"status": "ok",
                           "message": "All tracked changes accepted."})
    except Exception as e:
        debug_log("tool_accept_all_changes error: %s" % e, context="Chat")
        return _err(str(e))

def tool_reject_all_changes(model, ctx, args):
    """Reject all tracked changes in the document."""
    try:
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        frame = model.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:RejectAllTrackedChanges", "", 0, ())
        return json.dumps({"status": "ok",
                           "message": "All tracked changes rejected."})
    except Exception as e:
        debug_log("tool_reject_all_changes error: %s" % e, context="Chat")
        return _err(str(e))

TRACKING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_track_changes",
            "description": "Enable or disable track changes (change recording) in the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "True to enable track changes, False to disable.",
                    },
                },
                "required": ["enabled"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracked_changes",
            "description": (
                "List all tracked changes (redlines) in the document, including type, "
                "author, date, and comment."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "accept_all_changes",
            "description": "Accept all tracked changes in the document.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_all_changes",
            "description": "Reject all tracked changes in the document.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]
