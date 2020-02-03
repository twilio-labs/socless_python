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
from tests.conftest import * #imports testing boilerplate
from socless.integrations import *
from socless.utils import gen_id, gen_datetimenow
from .helpers import mock_integration_handler, mock_integration_handler_return_string, MockLambdaContext, dict_to_item, pre_save_dummy_execution_results

#intialize testing data

MOCK_EXECUTION_ID = 'mock_execution_id'
MOCK_EVENT_ID = 'mock_event_id'
MOCK_INVESTIGATION_ID = 'mock_investigation_id'
MOCK_TASK_TOKEN = 'mock_task_token'
MOCK_STATE_NAME = "HelloWorld"


TEST_DATA = {
    "TEST_EXECUTION_DATA": {
        "datetime": "test_date_time", 
        "execution_id": "test_execution_context_id", 
        "investigation_id": "test_investigation_id", 
        "results": {
            "artifacts": {
                "execution_id": "test_execution_id"
                }, 
                "errors": {},
                "results":{}
            }
         },
    "TEST_EXECUTION_DATA_LIVE": {
        "datetime": "test_date_time", 
        "execution_id": "test_execution_context_id", 
        "investigation_id":"test_investigation_id", 
        "results": {
            "artifacts": {
                "execution_id": "test_execution_id"
                }, 
            "errors": {},
            "results":{},
            'execution_id':'test_execution_context_id'
            }
        },
    "TEST_STATE_HANDLER": {
        "execution_id": "test_state_handler",
        "investigation_id": "test_state_handler",
        "results": {
            "execution_id": "test_state_handler",
            "artifacts": {},
            "results":{}
            }
        },
    "EVENT_TESTING_DATA" : {
        "_testing": True,
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Sterling",
                "middlename": "Malory",
                "lastname": "Archer"
            }
        }
    },
    "EVENT_LIVE_DATA" : {
        "execution_id": "test_execution_context_id",
        "artifacts": {
            "execution_id": "test_execution_context_id",
        },
        "State_Config": {
            "Name": "test",
            "Parameters": {
                "firstname": "Lana",
                "lastname": "Kane"
            }
        }
    }
}

TEST_SFN_CONTEXT = {
	'task_token': MOCK_TASK_TOKEN,
	'sfn_context': {
		'execution_id': MOCK_EXECUTION_ID,
		'artifacts': {
			'event': {
				'id': MOCK_EVENT_ID,
				'created_at': 'some_point_in_time_and_space',
				'data_types': {},
				'details': {
                    "some": "randon text"
				},
				'event_type': 'Test Human Interaction Workflow',
				'event_meta': {},
				'investigation_id': MOCK_INVESTIGATION_ID,
				'status_': 'open',
				'is_duplicate': False
			},
			'execution_id': MOCK_EXECUTION_ID
		},
		'State_Config': {
			'Name': MOCK_STATE_NAME,
			'Parameters': {}
		}
	}
}

MOCK_DB_CONTEXT = {
  "datetime": "some_point_in_time_and_space",
  "execution_id": "mock_execution_id",
  "investigation_id": "mock_investigation_id",
  "results": {
    'artifacts': {
        'event': {
            'id': MOCK_EVENT_ID,
            'created_at': 'some_point_in_time_and_space',
            'data_types': {},
            'details': {
                "some": "randon text"
            },
            'event_type': 'Test Human Interaction Workflow',
            'event_meta': {},
            'investigation_id': MOCK_INVESTIGATION_ID,
            'status_': 'open',
            'is_duplicate': False
        },
        'execution_id': MOCK_EXECUTION_ID
    },
    "errors": {},
    "results": {}
  }
}

@pytest.fixture()
def root_obj():
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
    """Instantiates ParameterResolver class from root_obj for use in tests"""
    return ParameterResolver(root_obj)

@pytest.fixture()
def TestExecutionContext():
    """Instantiates ExecutionContext class for use in tests"""
    return ExecutionContext("test_execution_context_id")

def test_ParameterResolver_resolve_jsonpath(TestParamResolver, root_obj):
    assert TestParamResolver.resolve_jsonpath("$.artifacts.event.details.firstname") == root_obj['artifacts']['event']['details']['firstname']

def test_ParameterResolver_resolve_jsonpath_vault_token(TestParamResolver, root_obj):
    assert TestParamResolver.resolve_jsonpath("$.artifacts.event.details.vault_test") == "this came from the vault"

def test_ParameterResolver_resolve_vault_path(TestParamResolver):
    assert TestParamResolver.resolve_vault_path("vault:socless_vault_tests.txt") == "this came from the vault"

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

def test_ParameterResolver_resolve_parameters(TestParamResolver):
    # Test with static string, vault reference, JsonPath reference, and conversion
    parameters = {
        "firstname": "$.artifacts.event.details.firstname",
        "lastname": "$.artifacts.event.details.lastname",
        "middlename": "Malory",
        "vault.txt": "vault:socless_vault_tests.txt",
        "vault.json": "vault:socless_vault_tests.json!json"
    }
    assert TestParamResolver.resolve_parameters(parameters) == {"firstname": "Sterling", "lastname": "Archer", "middlename": "Malory", "vault.txt":"this came from the vault", "vault.json": {'hello':'world'}}

def test_ParameterResolver_apply_conversion_from(TestParamResolver):
    # Test convert from json
    assert TestParamResolver.apply_conversion_from('{"text":"hello"}',"json") == {"text":"hello"}

def test_ExecutionContext_bad_execution_id():
    execution = ExecutionContext('id_does_not_exist')
    
    with pytest.raises(Exception):
        execution.fetch_context()

def test_ExecutionContext_fetch_context(TestExecutionContext):
    #setup mock table and insert item for testing
    results_table_name = os.environ['SOCLESS_RESULTS_TABLE']
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=results_table_name,
        Item={
            "datetime": { "S":"test_date_time" },
            "execution_id": { "S":"test_execution_context_id" },
            "investigation_id": { "S":"test_investigation_id" },
            "results": dict_to_item({"artifacts": {"execution_id": "test_execution_id"}, "errors": {},"results":{}})
        }
    )

    assert TestExecutionContext.fetch_context() == TEST_DATA['TEST_EXECUTION_DATA']

def test_ExecutionContext_save_state_results():

    item_metadata = pre_save_dummy_execution_results()
    state_name = "test_ExecutionContext_save_state_results"
    result = {"exist": True}
    errors = {"error": "This is an error"}
    execution = ExecutionContext(item_metadata['execution_id'])
    execution.save_state_results(
                                    state_name=state_name,
                                    result= result,
                                    errors= errors
                                )
    results_table = boto3.resource('dynamodb').Table(os.environ['SOCLESS_RESULTS_TABLE'])
    saved_result = results_table.get_item(Key={'execution_id': item_metadata['execution_id']})
    assert saved_result['Item']['execution_id'] == item_metadata['execution_id']
    assert saved_result['Item']['investigation_id'] == item_metadata['investigation_id']
    assert saved_result['Item']['datetime'] == item_metadata['datetime']
    
def test_StateHandler_init_with_testing_event():
    
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
    assert state_handler.execution_id == testing_event.get('execution_id','')
    assert state_handler.context == testing_event
    assert state_handler.integration_handler == mock_integration_handler

def test_StateHandler_init_with_live_event():
    #insert test item into mocked table
    item_metadata = pre_save_dummy_execution_results()
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
        }
    }
    live_execution_event = {
        "datetime": item_metadata['datetime'], 
        "execution_id": item_metadata['execution_id'], 
        "investigation_id": item_metadata['investigation_id'], 
        "results": {
            "artifacts": {
                "execution_id": item_metadata['execution_id']
                }, 
            "errors": {},
            "results":{},
            'execution_id': item_metadata['execution_id']
            }
        }

    state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == live_event
    assert state_handler.testing == False
    assert state_handler.state_config == live_event['State_Config']
    assert state_handler.state_name == live_event['State_Config']['Name']
    assert state_handler.state_parameters == live_event['State_Config']['Parameters']
    assert state_handler.execution_id == live_event.get('execution_id','')
    assert state_handler.context == live_execution_event['results']
    assert state_handler.integration_handler == mock_integration_handler

def test_StateHandler_init_with_task_token_event():
    client = boto3.client('dynamodb')
    #  Setup DB context for the state handler
    client.put_item(
        TableName=os.environ['SOCLESS_RESULTS_TABLE'],
        Item=dict_to_item(MOCK_DB_CONTEXT,convert_root=False)
    )

    state_handler = StateHandler(TEST_SFN_CONTEXT, MockLambdaContext(), mock_integration_handler)
    assert state_handler.context['execution_id'] == TEST_SFN_CONTEXT['sfn_context']['artifacts']['execution_id']
    assert state_handler.context['task_token'] == TEST_SFN_CONTEXT['task_token']
    assert state_handler.context['state_name'] == TEST_SFN_CONTEXT['sfn_context']['State_Config']['Name']
    assert state_handler.context['artifacts'] == MOCK_DB_CONTEXT['results']['artifacts']
    assert state_handler.context['errors'] == MOCK_DB_CONTEXT['results']['errors']
    assert state_handler.context['results'] == MOCK_DB_CONTEXT['results']['results']

def test_StateHandler_init_with_live_event_without_State_Config():
    item_metadata = pre_save_dummy_execution_results()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        }
    }

    with pytest.raises(Exception):
        state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)

def test_StateHandler_init_with_live_event_without_Name():
    item_metadata = pre_save_dummy_execution_results()
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

    with pytest.raises(Exception):
        state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)

def test_StateHandler_init_with_live_event_without_Parameters():
    item_metadata = pre_save_dummy_execution_results()
    live_event = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id'],
        },
        "State_Config": {
            "Name": "test"
        }
    }

    with pytest.raises(Exception):
        state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)

def test_StateHandler_init_with_live_event_with_errors():
    #insert test item into mocked table
    item_metadata = pre_save_dummy_execution_results()
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
    live_execution_event = {
        "datetime": item_metadata['datetime'], 
        "execution_id": item_metadata['execution_id'], 
        "investigation_id": item_metadata['investigation_id'], 
        "results": {
            "artifacts": {
                "execution_id": item_metadata['execution_id']
                }, 
            "errors": {"error": "this is an error"},
            "results":{},
            'execution_id': item_metadata['execution_id']
            }
        }

    state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.event == live_event
    assert state_handler.testing == False
    assert state_handler.state_config == live_event['State_Config']
    assert state_handler.state_name == live_event['State_Config']['Name']
    assert state_handler.state_parameters == live_event['State_Config']['Parameters']
    assert state_handler.execution_id == live_event.get('execution_id','')
    assert state_handler.context == live_execution_event['results']
    assert state_handler.integration_handler == mock_integration_handler

def test_StateHandler_execute_with_testing_event():
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
    #insert test item into mocked table
    item_metadata = pre_save_dummy_execution_results()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results":{}
            }
        }
    event['State_Config'] = {"Name": "test", "Parameters":{"firstname":"Cyril", "lastname":"Figgis","middlename":"N/A"}}
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler)
    assert state_handler.execute() == event['State_Config']['Parameters']

def test_StateHandler_execute_with_live_event_without_execution_id():
    #insert test item into mocked table
    item_metadata = pre_save_dummy_execution_results()
    live_event = {
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results":{}
            }
        }
    live_event['State_Config'] = {"Name": "test", "Parameters":{"firstname":"Cyril", "lastname":"Figgis","middlename":"N/A"}}
    with pytest.raises(Exception):
        state_handler = StateHandler(live_event, MockLambdaContext(), mock_integration_handler)

def test_StateHandler_execute_with_live_event_include_context():
    item_metadata = pre_save_dummy_execution_results()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results":{}
            }
        }
    event['State_Config'] = {"Name": "test", "Parameters":{"firstname":"Cyril", "lastname":"Figgis","middlename":"N/A"}}
    expected_result = {
        "execution_id": item_metadata['execution_id'],
        "artifacts": {
            "execution_id": item_metadata['execution_id']
        },
        "firstname":"Cyril", 
        "lastname":"Figgis",
        "middlename":"N/A",
        "results":{},
        "errors": {}
    }
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler, include_event=True)
    assert state_handler.execute() == expected_result

def test_StateHandler_execute_with_live_event_return_non_dict():
    item_metadata = pre_save_dummy_execution_results()
    event = {
        "execution_id": item_metadata['execution_id'],
        "investigation_id": item_metadata['investigation_id'],
        "results": {
            "execution_id": item_metadata['execution_id'],
            "artifacts": {},
            "results":{}
            }
        }
    event['State_Config'] = {"Name": "test", "Parameters":{"firstname":"Cyril", "lastname":"Figgis","middlename":"N/A"}}
    state_handler = StateHandler(event, MockLambdaContext(), mock_integration_handler_return_string)
    with pytest.raises(Exception):
        result = state_handler.execute()