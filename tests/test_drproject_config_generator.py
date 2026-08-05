"""Unit tests for the DRProject.config generator (SPEC-012)."""

import xml.etree.ElementTree as ET

import pytest

from backend.generators.drproject_config import (
    TEMPLATE_PATH,
    generate_drproject_config,
)
from backend.schemas.stop_config import AliasConfig, SelectionConfig, StopConfig, TimeWindowConfig, VolumeAnswer
from backend.schemas.truck_config import DepotSummary, VolumeSpec

FIXTURE_TEMPLATE_PATH = "fixtures/drproject-config/DRProject.config"


@pytest.fixture(scope="module")
def template_root() -> ET.Element:
    return ET.parse(FIXTURE_TEMPLATE_PATH).getroot()


@pytest.fixture
def base_config() -> StopConfig:
    return StopConfig(
        depots=[DepotSummary(address="1 Depot Way", city="Columbus", state="OH", zip="43215", truck_count=3)],
        weeks=4,
        volumes=[VolumeSpec(name="Cube", capacity=1800)],
        selection=SelectionConfig(mode="radius", radius_miles=50),
        stop_count=10,
        fixed_time_minutes=15,
        volume_answers=[VolumeAnswer(name="Cube", mode="fixed", value=25)],
        frequency_values=[1, 0.5],
        time_window=TimeWindowConfig(mode="fixed", open1=800, close1=1700, pattern_scope="week"),
        seed=5,
    )


def _stop_element(xml_bytes: bytes) -> ET.Element:
    root = ET.fromstring(xml_bytes)
    configuration = root.find("Configuration")
    assert configuration is not None
    stop = configuration.find("Stop")
    assert stop is not None
    return stop


def _text(stop: ET.Element, tag: str) -> str:
    child = stop.find(tag)
    assert child is not None and child.text is not None
    return child.text


def _quantity_names(stop: ET.Element) -> list[str]:
    quantities = stop.find("Quantities")
    assert quantities is not None
    return [q.findtext("Name") for q in quantities.findall("Quantity")]


class TestFieldSubstitution:
    def test_defaults_when_no_aliases(self, base_config, template_root):
        content = generate_drproject_config(base_config, template_root=template_root)
        stop = _stop_element(content)
        assert _text(stop, "ID1") == "Store #"
        assert _text(stop, "ID2") == "ID2"
        assert _text(stop, "Name") == "Name"
        assert _quantity_names(stop) == ["Cube"]

    def test_aliases_and_multiple_volumes(self, base_config, template_root):
        base_config.aliases = AliasConfig(
            id1="Acct#",
            id2="Order#",
            id3="SKU",
            name="Customer",
            address_2="Suite",
            contact="Rep",
            phone="Tel",
        )
        base_config.volumes = [
            VolumeSpec(name="Cube", capacity=1800),
            VolumeSpec(name="Weight", capacity=44000),
        ]
        base_config.volume_answers = [
            VolumeAnswer(name="Cube", mode="fixed", value=25),
            VolumeAnswer(name="Weight", mode="fixed", value=500),
        ]

        stop = _stop_element(generate_drproject_config(base_config, template_root=template_root))
        assert _text(stop, "ID1") == "Acct#"
        assert _text(stop, "ID2") == "Order#"
        assert _text(stop, "ID3") == "SKU"
        assert _text(stop, "Name") == "Customer"
        assert _text(stop, "Address2") == "Suite"
        assert _quantity_names(stop) == ["Cube", "Weight"]


class TestSanitization:
    def test_machine_paths_are_empty(self, base_config, template_root):
        root = ET.fromstring(generate_drproject_config(base_config, template_root=template_root))
        for tag in ("DistanceFile", "StopFile", "TruckFile", "DRTrackUserName", "DRTrackPassWord"):
            for element in root.iter(tag):
                assert element.text in (None, ""), f"{tag} should be empty, got {element.text!r}"


class TestDeterminism:
    def test_identical_input_produces_identical_bytes(self, base_config, template_root):
        first = generate_drproject_config(base_config, template_root=template_root)
        second = generate_drproject_config(base_config, template_root=template_root)
        assert first == second


class TestStructuralParity:
    def test_non_substituted_preferences_preserved(self, base_config, template_root):
        """Preferences subtree passes through except sanitized path elements."""
        generated = ET.fromstring(generate_drproject_config(base_config, template_root=template_root))

        gen_general = generated.find("Preferences/General/DistOptions")
        tmpl_general = template_root.find("Preferences/General/DistOptions")
        assert gen_general is not None and tmpl_general is not None
        assert gen_general.text == tmpl_general.text == "Miles"

    def test_bundled_runtime_template_exists(self):
        assert TEMPLATE_PATH.exists()

    def test_output_is_well_formed_xml_with_declaration(self, base_config, template_root):
        content = generate_drproject_config(base_config, template_root=template_root)
        assert content.startswith(b"<?xml version=")
        assert b"encoding=" in content.split(b"\n", 1)[0]
        ET.fromstring(content)
