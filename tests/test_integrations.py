# Copyright 2018 Twilio, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
import boto3, pytest, os
from tests.conftest import *  # imports testing boilerplate
from moto import mock_ssm
from socless.integrations import ParameterResolver, StateHandler, ExecutionContext, resolve_string_parameter
from socless.utils import gen_id
from socless.exceptions import SoclessBootstrapError
from .helpers import mock_integration_handler, mock_integration_handler_return_string, MockLambdaContext, mock_sfn_db_context, mock_execution_results_table_entry
from socless import socless_template_string


@pytest.fixture()
def root_obj():
    # setup root_obj for use in tesing TestParamResolver

    return {
        "artifacts": {
            "event": {
                "details": {
                    "firstname": "Sterling",
                    "middlename": "Malory",
                    "lastname": "Archer",
                    "vault_test" : "vault:socless_vault_tests.txt"
                }
            }
        }
    }


@pytest.fixture()
def TestParamResolver(root_obj):
    #Instantiates ParameterResolver class from root_obj for use in tests
    return ParameterResolver(root_obj)


def test_resolve_jsonpath(root_obj):
    resolved = resolve_string_parameter("$.artifacts.event.details.firstname", root_obj)
    assert resolved == root_obj['artifacts']['event']['details']['firstname']


def test_resolve_jsonpath_vault_token(root_obj):
    resolved = resolve_string_parameter("$.artifacts.event.details.vault_test", root_obj)
    assert resolved == "this came from the vault"


def test_resolve_vault_path():
    resolved = resolve_string_parameter("vault:socless_vault_tests.txt", {})
    assert resolved == "this came from the vault"


def test_resolve_template_with_conversion():
    resolved = resolve_string_parameter("vault:socless_vault_tests.json!json", {})
    assert resolved == {'hello': 'world'}


def test_resolve_template_preformatted_fromjson():
    resolved = resolve_string_parameter("""{ '{"foo": "bar"}' |fromjson}""", {})
    assert resolved == {'foo' : 'bar'}


def test_resolve_template_preformatted_fromjson_invalid_json():
    with pytest.raises(SoclessBootstrapError):
        resolve_string_parameter("""{ '{"foo": "bar" : bas}' |fromjson}""", {})


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
    resolved = resolve_string_parameter(f"{{secret('{TEST_SECRET_PATH}')}}", {})
    assert resolved == "test_parameter_for_socless"


def test_ParameterResolver_resolve_reference(TestParamResolver):
    # Test with string value
    assert TestParamResolver.resolve_reference("Hello") == "Hello"
    # Test with JsonPath reference
    assert TestParamResolver.resolve_reference("$.artifacts.event.details.middlename") == "Malory"
    # Test with vault reference
    assert TestParamResolver.resolve_reference("vault:socless_vault_tests.txt") == "this came from the vault"
    # Test with dictionary reference
    assert TestParamResolver.resolve_reference({"firstname": "$.artifacts.event.details.firstname"}) == {"firstname": "Sterling"}
    # Test with not dict or string reference
    assert TestParamResolver.resolve_reference(['test']) == ["test"]
    # Test with list containing nested parameters
    assert TestParamResolver.resolve_reference([{"firstname": "$.artifacts.event.details.firstname"}, "$.artifacts.event.details.lastname"]) == [{"firstname": "Sterling"}, "Archer"]


def test_ParameterResolver_resolve_parameters(TestParamResolver):
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
                "lastname": "$.artifacts.event.details.lastname"
            }
        ],
    }
    assert TestParamResolver.resolve_parameters(parameters) == {"firstname": "Sterling", "lastname": "Archer", "middlename": "Malory", "vault.txt": "this came from the vault", "vault.json": {'hello': 'world'}, "acquaintances": [{"firstname": "Malory", "lastname": "Archer"}]}


def test_ParameterResolver_resolve_strings_with_invalid_jinja(TestParamResolver):
    # Test with string value
    test_string = "something {with something else.} and another thing."
    assert TestParamResolver.resolve_reference(test_string) == test_string


def test_ExecutionContext_init():
    # test ExecutionContext init to assert the execution_id is the same one as expected
    execution_id = gen_id()
    execution_context = ExecutionContext(execution_id)
    assert execution_context.execution_id == execution_id


def test_ExecutionContext_fetch_context():
    # test ExecutionContext fetch_context to assert fetched context is as expected
    item_metadata = mock_execution_results_table_entry()
    expected_result = {
        "datetime": item_metadata['datetime'],
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            'artifacts': {
                'event': {
                    'id': item_metadata['id'],
                    'created_at': item_metadata['datetime'],
                    'data_types': {},
                    'details': {
                        "some": "randon text"
                    },
                    'event_type': 'Test integrations',
                    'event_meta': {},
                    'investigation_id': item_metadata['investigation_id'],
                    'status_': 'open',
                    'is_duplicate': False
                },
                'execution_id': item_metadata['execution_id']
            },
            "errors": {},
            "results": {}
        }
    }
    execution_context = ExecutionContext(item_metadata['execution_id'])
    assert execution_context.fetch_context() == expected_result


def test_ExecutionContext_fetch_context_fails_on_execution_id_not_existing():
    # test ExecutionContext fetch_context to fail when execution_id doesn't exist in dynamodb. Expecing it to raise an exception
    execution = ExecutionContext(gen_id())
    with pytest.raises(Exception, match="^Error: Unable to get execution_id"):
        execution.fetch_context()


def test_ExecutionContext_save_state_results():
    # test ExecutionContext save state results to assert saved item is as expected
    item_metadata = mock_execution_results_table_entry()
    state_name = "test_ExecutionContext_save_state_results"
    result = {"exist": True}
    errors = {"error": "This is an error"}
    execution = ExecutionContext(item_metadata['execution_id'])
    execution.save_state_results(
        state_name=state_name,
        result=result,
        errors=errors
    )
    results_table = boto3.resource('dynamodb').Table(os.environ['SOCLESS_RESULTS_TABLE'])
    saved_result = results_table.get_item(Key={'execution_id': item_metadata['execution_id']})
    assert saved_result['Item']['execution_id'] == item_metadata['execution_id']
    assert saved_result['Item']['investigation_id'] == item_metadata['investigation_id']
    assert saved_result['Item']['datetime'] == item_metadata['datetime']


def test_StateHandler_init_with_testing_event():
    # test StateHandler init with testing event to assert variables are as expected

    testing_event = {
        "_testing": True,
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Sterling",
                "middlename": "Malory",
                "lastname": "Archer"
            }
        }
    }

    state_handler = StateHandler(testing_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == testing_event
    assert state_handler.testing == testing_event['_testing']
    assert state_handler.state_config == testing_event['State_Config']
    assert state_handler.state_name == testing_event['State_Config']['Name']
    assert state_handler.state_parameters == testing_event['State_Config']['Parameters']
    assert state_handler.execution_id == testing_event.get('execution_id', '')
    assert state_handler.context == testing_event
    assert state_handler.integration_handler == mock_integration_handler


def test_StateHandler_init_with_live_event():
    # test StateHandler init with live event to assert variables are as expected

    item_metadata = mock_execution_results_table_entry()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        },
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Lana",
                "lastname": "Kane"
            }
        },
        "errors": {"error": "this is an error"}
    }
    exepected_event = {
        "datetime": item_metadata['datetime'],
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            'artifacts': {
                'event': {
                    'id': item_metadata['id'],
                    'created_at': item_metadata['datetime'],
                    'data_types': {},
                    'details': {
                        "some": "randon text"
                    },
                    'event_type': 'Test integrations',
                    'event_meta': {},
                    'investigation_id': item_metadata['investigation_id'],
                    'status_': 'open',
                    'is_duplicate': False
                },
                'execution_id': item_metadata['execution_id']
            },
            'execution_id': item_metadata['execution_id'],
            "errors": {"error": "this is an error"},
            "results": {}
        }
    }

    state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == live_event
    assert state_handler.testing == False
    assert state_handler.state_config == live_event['State_Config']
    assert state_handler.state_name == live_event['State_Config']['Name']
    assert state_handler.state_parameters == live_event['State_Config']['Parameters']
    assert state_handler.execution_id == live_event.get('execution_id', '')
    assert state_handler.context == exepected_event['results']
    assert state_handler.integration_handler == mock_integration_handler


def test_StateHandler_init_with_task_token_event():
    # test StateHandler init with taksk token event to assert variables are as expected
    sfn_item_metadata = mock_sfn_db_context()
    state_handler_db_context = sfn_item_metadata['db_context']
    sfn_context = sfn_item_metadata['sfn_context']
    state_handler = StateHandler(sfn_context, MockLambdaContext(), mock_integration_handler)
    assert state_handler.context['execution_id'] == sfn_context['sfn_context']['artifacts']['execution_id']
    assert state_handler.context['task_token'] == sfn_context['task_token']
    assert state_handler.context['state_name'] == sfn_context['sfn_context']['State_Config']['Name']
    assert state_handler.context['artifacts'] == state_handler_db_context['results']['artifacts']
    assert state_handler.context['errors'] == state_handler_db_context['results']['errors']
    assert state_handler.context['results'] == state_handler_db_context['results']['results']


def test_StateHandler_init_with_live_event_with_errors():
    # test StateHandler init with live event that contains error messages to assert variables are as expected
    item_metadata = mock_execution_results_table_entry()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        },
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Lana",
                "lastname": "Kane"
            }
        },
        "errors": {"error": "this is an error"}
    }
    exepected_event = {
        "datetime": item_metadata['datetime'],
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            'artifacts': {
                'event': {
                    'id': item_metadata['id'],
                    'created_at': item_metadata['datetime'],
                    'data_types': {},
                    'details': {
                        "some": "randon text"
                    },
                    'event_type': 'Test integrations',
                    'event_meta': {},
                    'investigation_id': item_metadata['investigation_id'],
                    'status_': 'open',
                    'is_duplicate': False
                },
                'execution_id': item_metadata['execution_id']
            },
            'execution_id': item_metadata['execution_id'],
            "errors": {"error": "this is an error"},
            "results": {}
        }
    }

    state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == live_event
    assert state_handler.testing == False
    assert state_handler.state_config == live_event['State_Config']
    assert state_handler.state_name == live_event['State_Config']['Name']
    assert state_handler.state_parameters == live_event['State_Config']['Parameters']
    assert state_handler.execution_id == live_event.get('execution_id', '')
    assert state_handler.context == exepected_event['results']
    assert state_handler.integration_handler == mock_integration_handler


def test_StateHandler_init_without_state_config_and_artififacts_for_direct_invoke():
    # test StateHandler init with testing event to assert variables are as expected

    direct_invoke_event = {
        "firstname": "Sterling",
        "middlename": "Malory",
        "lastname": "Archer"
    }

    expected_direct_invoke_response = {
        "_testing" : True,
        "State_Config": {
            "Name": "direct_invoke",
            "Parameters": {
                "firstname": "Sterling",
                "middlename": "Malory",
                "lastname": "Archer"
            }
        }
    }

    state_handler = StateHandler(direct_invoke_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == expected_direct_invoke_response
    assert state_handler.testing == expected_direct_invoke_response['_testing']
    assert state_handler.state_config == expected_direct_invoke_response['State_Config']
    assert state_handler.state_name == expected_direct_invoke_response['State_Config']['Name']
    assert state_handler.state_parameters == expected_direct_invoke_response['State_Config']['Parameters']
    assert state_handler.execution_id == expected_direct_invoke_response.get('execution_id', '')
    assert state_handler.context == expected_direct_invoke_response
    assert state_handler.integration_handler == mock_integration_handler


def test_StateHandler_init_fails_on_live_event_missing_Name():
    # test StateHandler init with live event that doesn't have Name to make it fail. Expecting it to raise an exception

    item_metadata = mock_execution_results_table_entry()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        },
        "State_Config": {
            "Parameters": {
                "firstname": "Lana",
                "lastname": "Kane"
            }
        }
    }

    with pytest.raises(SoclessBootstrapError, match="`Name` not set in State_Config"):
        StateHandler(live_event, MockLambdaContext(), mock_integration_handler)


def test_StateHandler_init_fails_on_live_event_missing_Parameters():
    # test StateHandler init with live event that doesn't have Parameters to make it fail. Expecting it to raise an exception

    item_metadata = mock_execution_results_table_entry()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        },
        "State_Config": {
            "Name": "test"
        }
    }

    with pytest.raises(SoclessBootstrapError, match="`Parameters` not set in State_Config"):
        StateHandler(live_event, MockLambdaContext(), mock_integration_handler)


def test_StateHandler_execute_with_testing_event():
    # test StateHanlder execute with testing event

    testing_event = {
        "_testing": True,
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Sterling",
                "middlename": "Malory",
                "lastname": "Archer"
            }
        }
    }
    state_handler = StateHandler(testing_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.execute() == testing_event['State_Config']['Parameters']


def test_StateHandler_execute_with_live_event():
    # test StateHandler execute with live event

    item_metadata = mock_execution_results_table_entry()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results": {}
        }
    }
    event['State_Config'] = {"Name": "test", "Parameters": {"firstname": "Cyril", "lastname": "Figgis", "middlename": "N/A"}}
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.execute() == event['State_Config']['Parameters']


def test_StateHandler_execute_with_live_event_include_context():
    # test StateHandler execute with live event that has include_context set to True

    item_metadata = mock_execution_results_table_entry()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results": {}
        }
    }
    event['State_Config'] = {"Name": "test", "Parameters": {"firstname": "Cyril", "lastname": "Figgis", "middlename": "N/A"}}
    expected_result = {
        'artifacts': {
            'event': {
                'id': item_metadata['id'],
                'created_at': item_metadata['datetime'],
                'data_types': {},
                'details': {
                    "some": "randon text"
                },
                'event_type': 'Test integrations',
                'event_meta': {},
                'investigation_id': item_metadata['investigation_id'],
                'status_': 'open',
                'is_duplicate': False
            },
            'execution_id': item_metadata['execution_id']
        },
        "firstname": "Cyril",
        "lastname": "Figgis",
        "middlename": "N/A",
        'execution_id': item_metadata['execution_id'],
        "results": {},
        "errors": {}
    }
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler, include_event=True)
    assert state_handler.execute() == expected_result


def test_StateHandler_execute_fails_on_live_event_missing_execution_id():
    # test StateHandler execute to fail on live event that doesn't have execution_id. Expecting it to raise an exception

    item_metadata = mock_execution_results_table_entry()
    live_event = {
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results": {}
        }
    }
    live_event['State_Config'] = {"Name": "test", "Parameters": {"firstname": "Cyril", "lastname": "Figgis", "middlename": "N/A"}}
    with pytest.raises(Exception, match="Execution id not found in non-testing context"):
        StateHandler(live_event, MockLambdaContext(), mock_integration_handler)


def test_StateHandler_execute_with_live_event_returning_non_dict():
    # test StateHandler execute with live event to fail when an integration doesn't return a dict. Expecting it to raise an exception

    item_metadata = mock_execution_results_table_entry()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results": {}
        }
    }
    event['State_Config'] = {"Name": "test", "Parameters": {"firstname": "Cyril", "lastname": "Figgis", "middlename": "N/A"}}
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler_return_string)
    with pytest.raises(Exception, match="Result returned from the integration handler is not a Python dictionary. Must be a Python dictionary"):
        state_handler.execute()


def test_socless_bootstrap_can_be_imported():
    from socless import socless_bootstrap # noqa: F401, E261


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
        # == "Hello &lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"
        == "Hello <script>alert('Elliot Alderson')</script>"
    )


def test_dictionary_reference():
    assert (
        socless_template_string("Hello {context.dict}", mock_context)
        # == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "&lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"}"""
        == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "<script>alert('Elliot Alderson')</script>"}"""
    )


def test_maptostr():
    assert socless_template_string(
        "{context.unicodelist|maptostr}", mock_context
    ) == "{}".format(["hello", "world"])


def test_socless_template_string_invalid_template():
    original_message = "Hello {code}"
    assert (
        socless_template_string(original_message, mock_context)
        == original_message
    )


def test_socless_template_string_after_jinja_resolve():
    string_parameter = "Hello {context.dict}"
    resolver = ParameterResolver(mock_context)
    resolved_parameter = resolver.resolve_reference(string_parameter)

    expected_resolved_param = """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "<script>alert('Elliot Alderson')</script>"}"""

    assert expected_resolved_param == resolved_parameter
    assert expected_resolved_param == socless_template_string(resolved_parameter, mock_context)


def test_socless_template_string_after_jinja_resolve_multiple_templates():
    string_parameter = "Hello {context.dict.safe_string}, {context.unicodelist}"
    resolver = ParameterResolver(mock_context)
    resolved_parameter = resolver.resolve_reference(string_parameter)

    expected_resolved_param = """Hello Elliot Alderson, ['hello', 'world']"""

    assert expected_resolved_param == resolved_parameter
    assert expected_resolved_param == socless_template_string(resolved_parameter, mock_context)


def test_socless_template_string_after_jinja_resolve_multiple_templates_if_one_is_malformed():
    string_parameter = "Hello {context.dict.safe_string}, {context.dict.unicodelist}"
    resolver = ParameterResolver(mock_context)
    with pytest.raises(SoclessBootstrapError):
        resolver.resolve_reference(string_parameter)
