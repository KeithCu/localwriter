"""Build-time utilities for generating XCS/XCU from module manifests.

This module is used by ``scripts/generate_manifest.py`` at build time.
It is NOT used at runtime (the runtime reads ``_manifest.py`` instead).
"""

import xml.etree.ElementTree as ET

_NS = {
    "oor": "http://openoffice.org/2001/registry",
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

_XCS_TYPE_MAP = {
    "boolean": "xs:boolean",
    "int": "xs:int",
    "float": "xs:double",
    "string": "xs:string",
}

# Register namespace prefixes so ET uses oor: instead of ns0:
for prefix, uri in _NS.items():
    ET.register_namespace(prefix, uri)


def _qn(ns, local):
    """Qualified name helper: _qn('oor', 'name') -> '{uri}name'."""
    return f"{{{_NS[ns]}}}{local}"


def _indent(elem, level=0):
    """Add pretty-print indentation to an ElementTree (stdlib has no indent before 3.9)."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent


def _to_xml_string(root):
    """Serialize an Element to a pretty XML string with declaration."""
    _indent(root)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def generate_xcs(module_name, config_fields):
    """Generate XCS (schema) XML for a module's config fields."""
    safe = module_name.replace(".", "_")
    package = f"org.localwriter.{safe}"

    root = ET.Element(_qn("oor", "component-schema"), {
        _qn("oor", "name"): safe,
        _qn("oor", "package"): package,
    })
    # Force xmlns:xs declaration (used in oor:type attribute values)
    root.set("xmlns:xs", _NS["xs"])

    component = ET.SubElement(root, "component")
    grp = ET.SubElement(component, "group", {_qn("oor", "name"): safe})

    for field_name, schema in config_fields.items():
        xcs_type = _XCS_TYPE_MAP.get(schema["type"], "xs:string")
        desc_text = schema.get("description", "") or schema.get("label", "")

        prop = ET.SubElement(grp, "prop", {
            _qn("oor", "name"): field_name,
            _qn("oor", "type"): xcs_type,
        })
        info = ET.SubElement(prop, "info")
        desc = ET.SubElement(info, "desc")
        desc.text = desc_text

    return _to_xml_string(root)


def generate_xcu(module_name, config_fields):
    """Generate XCU (defaults) XML for a module's config fields."""
    safe = module_name.replace(".", "_")
    package = f"org.localwriter.{safe}"

    root = ET.Element(_qn("oor", "component-data"), {
        _qn("oor", "name"): safe,
        _qn("oor", "package"): package,
    })

    node = ET.SubElement(root, "node", {_qn("oor", "name"): safe})

    for field_name, schema in config_fields.items():
        xcu_type = _XCS_TYPE_MAP.get(schema["type"], "xs:string")
        default = schema.get("default", "")

        if schema["type"] == "boolean":
            val_text = "true" if default else "false"
        else:
            val_text = str(default)

        prop = ET.SubElement(node, "prop", {_qn("oor", "name"): field_name})
        value = ET.SubElement(prop, "value", {_qn("xsi", "type"): xcu_type})
        value.text = val_text

    return _to_xml_string(root)
