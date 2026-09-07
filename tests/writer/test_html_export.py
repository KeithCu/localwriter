from plugin.tests.testing_utils import setup_uno_mocks

setup_uno_mocks()

from plugin.writer.html_export import xtext_to_content


def test_xtext_to_content_none_is_empty():
    assert xtext_to_content(None, object(), object()) == ""
