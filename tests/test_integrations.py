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
from socless.integrations import *
from .helpers import mock_integration_handler, MockLambdaContext

#TODO: Document pytests.ini enviroment variables

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
            "results": {}
        }
    },
    "TEST_EXECUTION_DATA_LIVE": {
        "datetime": "test_date_time",
        "execution_id": "test_execution_context_id",
        "investigation_id": "test_investigation_id",
        "results": {
            "artifacts": {
                "execution_id": "test_execution_id"
            },
            "errors": {},
            "results": {},
            'execution_id': 'test_execution_context_id'
        }
    },
    "TEST_STATE_HANDLER": {
        "execution_id": "test_state_handler",
        "investigation_id": "test_state_handler",
        "results": {
            "execution_id": "test_state_handler",
            "artifacts": {},
            "results": {}
        }
    }
}


class TestParameterResolver:
    """Test the ParameterResolver class
    """
    #TODO: Document requirements for testing: socless_vault_tests.txt and socless_vault_tests.json in the vault

    root_obj = {
        "artifacts": {
            "event": {
                "details": {
                    "firstname": "Sterling",
                    "middlename": "Malory",
                    "lastname": "Archer"
                }
            }
        }
    }

    resolver = ParameterResolver(root_obj)

    def test_resolve_jsonpath(self):
        assert self.resolver.resolve_jsonpath(
            "$.artifacts.event.details.firstname"
        ) == self.root_obj['artifacts']['event']['details']['firstname']

    def test_resolve_vault_path(self):
        assert self.resolver.resolve_vault_path(
            "vault:socless_vault_tests.txt") == "this came from the vault"

    def test_resolve_reference(self):
        # Test with string value
        assert self.resolver.resolve_reference("Hello") == "Hello"
        # Test with JsonPath reference
        assert self.resolver.resolve_reference(
            "$.artifacts.event.details.middlename") == "Malory"
        # Test with vault reference
        assert self.resolver.resolve_reference(
            "vault:socless_vault_tests.txt") == "this came from the vault"
        # Test with dictionary reference
        assert self.resolver.resolve_reference(
            {"firstname": "$.artifacts.event.details.firstname"}) == {
                "firstname": "Sterling"
            }

    def test_resolve_parameters(self):
        # Test with static string, vault reference, JsonPath reference, and conversion
        parameters = {
            "firstname": "$.artifacts.event.details.firstname",
            "lastname": "$.artifacts.event.details.lastname",
            "middlename": "Malory",
            "vault.txt": "vault:socless_vault_tests.txt",
            "vault.json": "vault:socless_vault_tests.json!json"
        }
        assert self.resolver.resolve_parameters(parameters) == {
            "firstname": "Sterling",
            "lastname": "Archer",
            "middlename": "Malory",
            "vault.txt": "this came from the vault",
            "vault.json": {
                'hello': 'world'
            }
        }

    def test_apply_conversion_from(self):
        # Test convert from json
        assert self.resolver.apply_conversion_from('{"text":"hello"}',
                                                   "json") == {
                                                       "text": "hello"
                                                   }


class TestExecutionContext:
    """Test the ExecutionContext class
    """

    execution_context = ExecutionContext("test_execution_context_id")

    def test_fetch_context(self):
        #TODO: Document the requirements for this test: The test_execution_id object that needs to be placed in the execution results table
        assert self.execution_context.fetch_context(
        ) == TEST_DATA['TEST_EXECUTION_DATA']


class TestStateHandler:
    """Test StateHandler class
    """

    event_testing = {
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

    event_live = {
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

    def test_init_with_event_testing(self):
        state_handler = StateHandler(self.event_testing, MockLambdaContext(),
                                     mock_integration_handler)
        assert state_handler.event == self.event_testing
        assert state_handler.testing == self.event_testing['_testing']
        assert state_handler.state_config == self.event_testing['State_Config']
        assert state_handler.state_name == self.event_testing['State_Config'][
            'Name']
        assert state_handler.state_parameters == self.event_testing[
            'State_Config']['Parameters']
        assert state_handler.execution_id == self.event_testing.get(
            'execution_id', '')
        assert state_handler.context == self.event_testing
        assert state_handler.integration_handler == mock_integration_handler

    def test_execute_with_event_testing(self):
        state_handler = StateHandler(self.event_testing, MockLambdaContext(),
                                     mock_integration_handler)
        assert state_handler.execute(
        ) == self.event_testing['State_Config']['Parameters']

    def test_init_with_event_live(self):
        state_handler = StateHandler(self.event_live, MockLambdaContext(),
                                     mock_integration_handler)
        assert state_handler.event == self.event_live
        assert state_handler.testing == False
        assert state_handler.state_config == self.event_live['State_Config']
        assert state_handler.state_name == self.event_live['State_Config'][
            'Name']
        assert state_handler.state_parameters == self.event_live[
            'State_Config']['Parameters']
        assert state_handler.execution_id == self.event_live.get(
            'execution_id', '')
        assert state_handler.context == TEST_DATA['TEST_EXECUTION_DATA_LIVE'][
            'results']
        assert state_handler.integration_handler == mock_integration_handler

    def test_execute_with_event_testing(self):
        event = TEST_DATA['TEST_STATE_HANDLER']
        event['State_Config'] = {
            "Name": "test",
            "Parameters": {
                "firstname": "Cyril",
                "lastname": "Figgis",
                "middlename": "N/A"
            }
        }
        state_handler = StateHandler(event, MockLambdaContext(),
                                     mock_integration_handler)
        assert state_handler.execute() == event['State_Config']['Parameters']
