# WriterAgent - AI Writing Assistant for LibreOffice
from plugin.testing_runner import native_test
from plugin.tests.testing_utils import with_native_doc


def _exec_tool(doc, ctx, name, args):
    from plugin.main import get_tools
    from plugin.framework.tool import ToolContext
    tctx = ToolContext(doc, ctx, "draw", {}, "test")
    res = get_tools().execute(name, tctx, **args)
    return res


@native_test
@with_native_doc("draw")
def test_draw_form_lifecycle(ctx, doc):
    # 1. Create a control
    res = _exec_tool(doc, ctx, "form_create_control", {"control": "checkbox", "name": "MyCheck", "label": "Agree"})
    assert res["status"] == "ok", f"create_form_control failed: {res}"
    
    # 2. List controls
    res = _exec_tool(doc, ctx, "form_list_controls", {})
    assert res["status"] == "ok", f"list_form_controls failed: {res}"
    assert res["count"] == 1
    assert res["controls"][0]["name"] == "MyCheck"
    
    shape_index = res["controls"][0]["index"]
    
    # 3. Edit control
    res = _exec_tool(doc, ctx, "form_edit_control", {"index": shape_index, "name": "UpdatedCheck", "label": "Confirmed"})
    assert res["status"] == "ok", f"edit_form_control failed: {res}"
    
    res = _exec_tool(doc, ctx, "form_list_controls", {})
    assert res["controls"][0]["name"] == "UpdatedCheck"
    
    # 4. Delete control
    res = _exec_tool(doc, ctx, "form_delete_control", {"index": shape_index})
    assert res["status"] == "ok", f"delete_form_control failed: {res}"
    
    res = _exec_tool(doc, ctx, "form_list_controls", {})
    assert res["count"] == 0


@native_test
@with_native_doc("draw")
def test_generate_form_draw(ctx, doc):
    # Test that generate_form is registered for Draw
    from plugin.main import get_tools
    tools = get_tools()
    gen_tool = tools.get("form_generate")
    assert gen_tool is not None
    assert "com.sun.star.drawing.DrawingDocument" in gen_tool.uno_services


@native_test
@with_native_doc("draw")
def test_draw_form_edit_delete_by_name_and_checkbox_state(ctx, doc):
    """Name addressing survives a non-control shape sitting at index 0."""
    from plugin.draw.bridge import DrawBridge

    bridge = DrawBridge(doc)
    page = bridge.get_active_page()
    deco = bridge.create_shape("com.sun.star.drawing.RectangleShape", 100, 100, 2000, 1000, page=page)
    deco.Name = "NotAControl"

    res = _exec_tool(doc, ctx, "form_create_control", {"control": "checkbox", "name": "GMPCheck", "label": "Approved"})
    assert res["status"] == "ok", res

    listed = _exec_tool(doc, ctx, "form_list_controls", {})
    assert listed["status"] == "ok"
    assert listed["count"] == 1
    ctrl = listed["controls"][0]
    assert ctrl["name"] == "GMPCheck"
    assert ctrl["type"] == "checkbox"
    assert ctrl["index"] != 0  # decorative rectangle is first
    assert ctrl.get("state") in (0, 1, 2)

    edited = _exec_tool(doc, ctx, "form_edit_control", {"name": "GMPCheck", "state": 1, "label": "Signed"})
    assert edited["status"] == "ok", edited

    listed2 = _exec_tool(doc, ctx, "form_list_controls", {})
    ctrl2 = listed2["controls"][0]
    assert ctrl2["name"] == "GMPCheck"
    assert ctrl2["label"] == "Signed"
    assert ctrl2["state"] == 1

    deleted = _exec_tool(doc, ctx, "form_delete_control", {"name": "GMPCheck"})
    assert deleted["status"] == "ok", deleted
    assert _exec_tool(doc, ctx, "form_list_controls", {})["count"] == 0


@native_test
@with_native_doc("draw")
def test_draw_tree_blank_and_fill_draw_fields(ctx, doc):
    """Paper-form blanks in get_draw_tree; fill by name; miss is per-field fail."""
    from plugin.draw.bridge import DrawBridge

    bridge = DrawBridge(doc)
    page = bridge.get_active_page()
    label = bridge.create_shape("com.sun.star.drawing.TextShape", 500, 500, 3000, 800, page=page)
    label.setString("Lot:")
    label.Name = "LotLabel"
    blank = bridge.create_shape("com.sun.star.drawing.TextShape", 3600, 500, 4000, 800, page=page)
    blank.setString("")
    blank.Name = "LotField"

    tree_res = _exec_tool(doc, ctx, "get_draw_tree", {})
    assert tree_res["status"] == "ok", tree_res
    by_name = {n.get("name"): n for n in tree_res.get("tree", []) if n.get("name")}
    assert "LotField" in by_name
    assert by_name["LotField"].get("blank") is True
    assert by_name["LotField"].get("fillable") is True
    assert by_name["LotField"].get("label_hint") == "Lot:"

    filled = _exec_tool(
        doc,
        ctx,
        "fill_draw_fields",
        {"fields": [{"name": "LotField", "value": "LOT-42"}, {"name": "NoSuch", "value": "x"}]},
    )
    assert filled["filled"] == 1, filled
    assert filled["failed"] == 1, filled
    assert blank.getString() == "LOT-42"

    named = _exec_tool(doc, ctx, "shape_upsert", {"action": "edit", "name": "LotField", "text": "LOT-99"})
    assert named["status"] == "ok", named
    assert blank.getString() == "LOT-99"
