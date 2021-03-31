from socless import socless_template_string
from socless.paramresolver import ParameterResolver
from socless.exceptions import SoclessBootstrapError
from jinja2.exceptions import TemplateSyntaxError
import pytest

mock_context = {
    "safe_string": "Elliot Alderson",
    "unsafe_string": "<script>alert('Elliot Alderson')</script>",
    "dict": {
        "safe_string": "Elliot Alderson",
        "unsafe_string": "<script>alert('Elliot Alderson')</script>",
    },
    "unicodelist": ["hello", "world"],
}


def test_safe_string():
    assert (
        socless_template_string("Hello {context.safe_string}", mock_context)
        == "Hello Elliot Alderson"
    )


def test_unsafe_string():
    assert (
        socless_template_string("Hello {context.unsafe_string}", mock_context)
        == "Hello &lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"
        # == "Hello <script>alert('Elliot Alderson')</script>"
    )


def test_dictionary_reference():
    assert (
        socless_template_string("Hello {context.dict}", mock_context)
        == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "&lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"}"""
        # == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "<script>alert('Elliot Alderson')</script>"}"""
    )


def test_maptostr():
    assert socless_template_string(
        "{context.unicodelist|maptostr}", mock_context
    ) == "{}".format(["hello", "world"])


def test_socless_template_string_invalid_template():
    original_message = "Hello {code}"
    expected_message = "Hello "
    # NOTE: legacy_jinja had a bug that caused it to fail silently when a template was invalid
    # Since this PR re-implements legacy_jinja exactly as is, the bug is reintroduced
    # A future PR might fix it as needed but the ideal is to deprecate the functionality all together
    assert socless_template_string(original_message, mock_context) == expected_message
    # assert socless_template_string(original_message, mock_context) == original_message


def test_socless_template_string_after_jinja_resolve():
    string_parameter = "Hello {{context.dict}}"
    resolver = ParameterResolver(mock_context)
    resolved_parameter = resolver.resolve_reference(string_parameter)

    expected_resolved_param = """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "<script>alert('Elliot Alderson')</script>"}"""

    assert expected_resolved_param == resolved_parameter
    # assert expected_resolved_param == socless_template_string(
    #     resolved_parameter, mock_context
    # )

    # Legacy jinja used to fail on dicts because they looked like single curlies
    #
    with pytest.raises(TemplateSyntaxError):
        socless_template_string(resolved_parameter, mock_context)


def test_socless_template_string_after_jinja_resolve_multiple_templates():
    string_parameter = "Hello {{context.dict.safe_string}}, {{context.unicodelist}}"
    resolver = ParameterResolver(mock_context)
    resolved_parameter = resolver.resolve_reference(string_parameter)

    expected_resolved_param = """Hello Elliot Alderson, ['hello', 'world']"""

    assert expected_resolved_param == resolved_parameter
    assert expected_resolved_param == socless_template_string(
        resolved_parameter, mock_context
    )


# def test_socless_template_string_after_jinja_resolve_multiple_templates_if_one_is_malformed():
#     string_parameter = "Hello {context.dict.safe_string}, {context.dict.unicodelist}"
#     resolver = ParameterResolver(mock_context)
#     with pytest.raises(SoclessBootstrapError):
#         resolver.resolve_reference(string_parameter)
