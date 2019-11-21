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

from tests.conftest import * # imports testing boilerplate
from socless import init_human_interaction, end_human_interaction
from .helpers import MockLambdaContext, mock_integration_handler, dict_to_item
from socless.integrations import StateHandler
from unittest import TestCase
import pytest


# Initialize Testing Data
MOCK_EXECUTION_ID = 'mock_execution_id'
MOCK_EVENT_ID = 'mock_event_id'
MOCK_INVESTIGATION_ID = 'mock_investigation_id'
MOCK_TASK_TOKEN = 'mock_task_token'
MOCK_STATE_NAME = "HelloWorld"

TEST_MESSAGE = {
    "greeting": "Hello, World"
}

TEST_RESPONSE = {
    "response": "Hello, back"
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

MOCK_MESSAGE_RESPONSE_ENTRY = dict_to_item({
  "await_token": TEST_SFN_CONTEXT['task_token'],
  "execution_id": TEST_SFN_CONTEXT['sfn_context']['execution_id'],
  "fulfilled": False,
  "investigation_id": TEST_SFN_CONTEXT['sfn_context']['artifacts']['event']['investigation_id'],
  "message": TEST_MESSAGE,
  "receiver": TEST_SFN_CONTEXT['sfn_context']['State_Config']['Name'],
},convert_root=False)


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

@pytest.fixture
def state_handler():
    client = boto3.client('dynamodb')
    #  Setup DB context for the state handler
    client.put_item(
        TableName=os.environ['SOCLESS_RESULTS_TABLE'],
        Item=dict_to_item(MOCK_DB_CONTEXT,convert_root=False)
    )

    state_handler = StateHandler(TEST_SFN_CONTEXT, MockLambdaContext(), mock_integration_handler)
    return state_handler


def test_init_human_interaction(state_handler):
    message_id  = init_human_interaction(state_handler.context, TEST_MESSAGE)

    client = boto3.client('dynamodb')
    init_message_response_entry = client.get_item(
        TableName=os.environ['SOCLESS_MESSAGE_RESPONSE_TABLE'],
        Key={'message_id': dict_to_item(message_id)})['Item']

    MOCK_MESSAGE_RESPONSE_ENTRY['datetime'] = init_message_response_entry['datetime']
    MOCK_MESSAGE_RESPONSE_ENTRY['message_id'] = dict_to_item(message_id)
    assert MOCK_MESSAGE_RESPONSE_ENTRY == init_message_response_entry


def test_end_human_interaction(state_handler):
    # test end_human_interaction to the best of our ability, given motos sfn limitations
    message_id  = init_human_interaction(state_handler.context, TEST_MESSAGE)
    with TestCase().assertRaises(Exception) as cm:
        end_human_interaction(message_id, TEST_RESPONSE)

    raised_exception = cm.exception
    assert str(raised_exception) == 'response_delivery_failed'

    client = boto3.client('dynamodb')
    UPDATED_DB_CONTEXT = client.get_item(
        TableName=os.environ['SOCLESS_RESULTS_TABLE'],
        Key={'execution_id': dict_to_item(MOCK_EXECUTION_ID)})['Item']

    MOCK_DB_CONTEXT['results']['results'][MOCK_STATE_NAME] = TEST_RESPONSE
    MOCK_DB_CONTEXT['results']['results']['_Last_Saved_Results'] = TEST_RESPONSE

    assert dict_to_item(MOCK_DB_CONTEXT,convert_root=False) == UPDATED_DB_CONTEXT
