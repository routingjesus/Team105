"""DRProject.config XML generator (SPEC-012).

Loads the bundled golden template from ``backend/data/DRProject.config``,
substitutes wizard-driven ``Configuration/Stop`` fields, clears
machine-specific path elements, and serializes UTF-8 XML.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.schemas.stop_config import AliasConfig, StopConfig

TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "DRProject.config"

# Stop-field display names when the wizard supplies no alias (matches stop generator defaults).
_STOP_FIELD_DEFAULTS: dict[str, str] = {
    "ID1": "Store #",
    "ID2": "ID2",
    "ID3": "ID3",
    "Name": "Name",
    "Address2": "Address2",
    "Address": "Address",
    "Contact": "Contact",
    "Phone": "Phone",
}

# AliasConfig attribute for each Configuration/Stop child element.
_ALIAS_ATTR_BY_TAG: dict[str, str] = {
    "ID1": "id1",
    "ID2": "id2",
    "ID3": "id3",
    "Name": "name",
    "Address2": "address_2",
    "Contact": "contact",
    "Phone": "phone",
}

# Elements always emitted empty — environment-specific, never wizard input.
_EMPTY_ALWAYS_TAGS: frozenset[str] = frozenset(
    {
        "DistanceFile",
        "StopFile",
        "TruckFile",
        "RecentFilePath1",
        "RecentFilePath2",
        "RecentFilePath3",
        "RecentFilePath4",
        "RecentFilePath5",
        "RecentFilePath6",
        "RecentFilePath7",
        "RecentFilePath8",
        "RecentFilePath9",
        "RecentFilePath10",
        "RecentProjectPath1",
        "RecentProjectPath2",
        "RecentProjectPath3",
        "RecentProjectPath4",
        "RecentProjectPath5",
        "RecentProjectPath6",
        "RecentProjectPath7",
        "RecentProjectPath8",
        "RecentProjectPath9",
        "RecentProjectPath10",
        "SetEqCode",
        "ApplyBnd",
        "DRTrackUserName",
        "DRTrackPassWord",
    }
)


def _alias_text(tag: str, aliases: AliasConfig | None) -> str:
    default = _STOP_FIELD_DEFAULTS[tag]
    attr = _ALIAS_ATTR_BY_TAG.get(tag)
    if attr is None or aliases is None:
        return default
    value = getattr(aliases, attr, None)
    return value if value else default


def _set_stop_identity_fields(stop: ET.Element, config: StopConfig) -> None:
    aliases = config.aliases
    for tag in _STOP_FIELD_DEFAULTS:
        child = stop.find(tag)
        if child is not None:
            child.text = _alias_text(tag, aliases)


def _set_quantities(stop: ET.Element, config: StopConfig) -> None:
    quantities = stop.find("Quantities")
    if quantities is None:
        return
    for child in list(quantities):
        quantities.remove(child)
    for volume in config.volumes:
        quantity = ET.SubElement(quantities, "Quantity")
        name_el = ET.SubElement(quantity, "Name")
        name_el.text = volume.name


def _clear_machine_paths(root: ET.Element) -> None:
    for element in root.iter():
        if element.tag in _EMPTY_ALWAYS_TAGS:
            element.text = None


def _load_template_tree() -> ET.Element:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"DRProject.config template not found at {TEMPLATE_PATH}. "
            "This bundled file is a deployment prerequisite."
        )
    return ET.parse(TEMPLATE_PATH).getroot()


def generate_drproject_config(config: StopConfig, *, template_root: ET.Element | None = None) -> bytes:
    """Return UTF-8 XML bytes for a DRProject.config from wizard answers."""
    root = copy.deepcopy(template_root if template_root is not None else _load_template_tree())

    configuration = root.find("Configuration")
    if configuration is not None:
        stop = configuration.find("Stop")
        if stop is not None:
            _set_stop_identity_fields(stop, config)
            _set_quantities(stop, config)

    _clear_machine_paths(root)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
