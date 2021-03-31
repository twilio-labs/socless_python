import boto3, pytest, os
from moto import mock_ssm
from socless.integrations import StateHandler, ExecutionContext
from socless.exceptions import SoclessBootstrapError
from socless.paramresolver import ParameterResolver, resolve_string_parameter


@pytest.fixture()
def root_obj():
    # setup root_obj for use in tesing ParamResolverTestObj

    return {
        "artifacts": {
            "event": {
                "details": {
                    "firstname": "Sterling",
                    "middlename": "Malory",
                    "lastname": "Archer",
                    "vault_test": "vault:socless_vault_tests.txt",
                }
            }
        }
    }


@pytest.fixture()
def ParamResolverTestObj(root_obj):
    # Instantiates ParameterResolver class from root_obj for use in tests
    return ParameterResolver(root_obj)


def test_resolve_jsonpath(root_obj):
    resolved = resolve_string_parameter("$.artifacts.event.details.firstname", root_obj)
    assert resolved == root_obj["artifacts"]["event"]["details"]["firstname"]


def test_resolve_jsonpath_vault_token(root_obj):
    resolved = resolve_string_parameter(
        "$.artifacts.event.details.vault_test", root_obj
    )
    assert resolved == "this came from the vault"


def test_resolve_vault_path():
    resolved = resolve_string_parameter("vault:socless_vault_tests.txt", {})
    assert resolved == "this came from the vault"


def test_resolve_template_with_conversion():
    resolved = resolve_string_parameter("vault:socless_vault_tests.json!json", {})
    assert resolved == {"hello": "world"}


def test_resolve_template_with_conversion_as_context_syntax():
    #TODO: Remove this comment. Its here to remind me I modified this test
    resolved = resolve_string_parameter(
        "{{context.results.Test_Step.file_id | vault | fromjson}}",
        {"results": {"Test_Step": {"file_id": "socless_vault_tests.json"}}},
    )
    assert resolved == {"hello": "world"}


def test_resolve_template_preformatted_fromjson():
    #TODO: Remove this comment. Its here to remind me I modified this test
    resolved = resolve_string_parameter("""{{ '{"foo": "bar"}' |fromjson}}""", {})
    assert resolved == {"foo": "bar"}


def test_resolve_template_preformatted_fromjson_invalid_json():
    #TODO: Remove this comment. Its here to remind me I modified this test
    with pytest.raises(SoclessBootstrapError):
        resolve_string_parameter("""{{ '{"foo": "bar" : bas}' |fromjson}}""", {})


@mock_ssm
def test_resolve_string_with_secret():
    TEST_SECRET_PATH = "/socless/test/mock_secret"
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
    ssm_client.put_parameter(
        Name=TEST_SECRET_PATH,
        Description="A test parameter",
        Value="test_parameter_for_socless",
        Type="SecureString",
    )
    resolved = resolve_string_parameter(f"{{{{secret('{TEST_SECRET_PATH}')}}}}", {})
    assert resolved == "test_parameter_for_socless"


def test_ParameterResolver_resolve_reference(ParamResolverTestObj):
    # Test with string value
    assert ParamResolverTestObj.resolve_reference("Hello") == "Hello"
    # Test with JsonPath reference
    assert (
        ParamResolverTestObj.resolve_reference("$.artifacts.event.details.middlename")
        == "Malory"
    )
    # Test with vault reference
    assert (
        ParamResolverTestObj.resolve_reference("vault:socless_vault_tests.txt")
        == "this came from the vault"
    )
    # Test with dictionary reference
    assert ParamResolverTestObj.resolve_reference(
        {"firstname": "$.artifacts.event.details.firstname"}
    ) == {"firstname": "Sterling"}
    # Test with not dict or string reference
    assert ParamResolverTestObj.resolve_reference(["test"]) == ["test"]
    # Test with list containing nested parameters
    assert ParamResolverTestObj.resolve_reference([{"firstname": "$.artifacts.event.details.firstname"}, "$.artifacts.event.details.lastname"]) == [{"firstname": "Sterling"}, "Archer"]


def test_ParameterResolver_resolve_parameters(ParamResolverTestObj):
    # Test with static string, vault reference, JsonPath reference, and conversion
    parameters = {
        "firstname": "$.artifacts.event.details.firstname",
        "lastname": "$.artifacts.event.details.lastname",
        "middlename": "Malory",
        "vault.txt": "vault:socless_vault_tests.txt",
        "vault.json": "vault:socless_vault_tests.json!json",
        "acquaintances": [
            {
                "firstname": "$.artifacts.event.details.middlename",
                "lastname": "$.artifacts.event.details.lastname",
            }
        ],
    }
    assert ParamResolverTestObj.resolve_parameters(parameters) == {
        "firstname": "Sterling",
        "lastname": "Archer",
        "middlename": "Malory",
        "vault.txt": "this came from the vault",
        "vault.json": {"hello": "world"},
        "acquaintances": [{"firstname": "Malory", "lastname": "Archer"}],
    }


def test_ParameterResolver_resolve_strings_with_invalid_jinja(ParamResolverTestObj):
    # Test with string value
    #TODO: Remove this comment. Its here to remind me I modified this test
    test_string = "something {{with something else.}} and another thing."
    assert ParamResolverTestObj.resolve_reference(test_string) == test_string



def test_ParameterResolver_retains_single_curlies(ParamResolverTestObj):
    """This test asserts that the jinja_env configuration"""
    test_string = "[A-Z]{16}"
    assert ParamResolverTestObj.resolve_reference(test_string) == test_string
