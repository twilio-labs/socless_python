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
from .helpers import MockLambdaContext, dict_to_item
from pprint import pprint
from copy import deepcopy
import pytest

from socless.events import EventCreator, EventBatch

MOCK_EVENT_BATCH = {
        "event_type": "ParamsToStateMachineTester",
        "details": [
            {"username": "ubalogun","type": "user","id":"1"},
            {"username": "ubalogun","type": "user","id":"2"},
            {"username": "ubalogun","type": "user","id":"1"}
        ],
        "playbook": "ParamsToStateMachineTester",
        "dedup_keys": ["username", "id"]
    }

MOCK_EVENT = {
    "event_info" : "",
    "event_type": "ParamsToStateMachineTester",
    "details" : {"username": "ubalogun","type": "user","id":"1"},
    "data_types" : {},
    "event_meta" : {},
    "playbook" : "",
    "dedup_keys" : [],
}

DEDUP_HASH_FOR_MOCK_EVENT = "a0d9bb01f16a80765a8736f00b3da8da"
MOCK_INVESTIGATION_ID = "mock_investigation_id"


def test_EventCreator():
    event_details = EventCreator(MOCK_EVENT)

    assert event_details.event_type == MOCK_EVENT['event_type']
    # assert event_details.created_at == None # created_at not supplied in mock
    assert event_details.details == MOCK_EVENT['details']
    assert event_details.data_types == {} # created_at not supplied in mock
    assert event_details.dedup_keys == MOCK_EVENT['dedup_keys']
    assert event_details.event_meta == {}
    assert event_details.playbook == MOCK_EVENT['playbook']

def test_EventCreator_invalid_event_type():
    edited_event_data = deepcopy(MOCK_EVENT)
    edited_event_data['event_type'] = ''

    with pytest.raises(Exception):
        event_details = EventCreator(edited_event_data)

def test_EventCreator_dedup_hash():
    event = EventCreator(MOCK_EVENT)
    assert event.dedup_hash == DEDUP_HASH_FOR_MOCK_EVENT

    edited_mock_event = deepcopy(MOCK_EVENT)
    edited_mock_event['dedup_keys'] = ['username']
    event = EventCreator(edited_mock_event)
    assert event.dedup_hash == "0caa90ad7b7fc101b90a8ce0f9638eb9"

def test_EventCreator_dedup_hash_invalid_key():
    edited_mock_event = deepcopy(MOCK_EVENT)
    edited_mock_event['dedup_keys'] = ['invalid_key']

    event = EventCreator(edited_mock_event)
    with pytest.raises(KeyError):
        event.dedup_hash

def test_deduplicate_unique():
    event = EventCreator(MOCK_EVENT)
    event.deduplicate()
    pass

def test_deduplicate_is_duplicate():
    #  Setup tables for this event
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=os.environ['SOCLESS_DEDUP_TABLE'],
        Item=dict_to_item({
                    "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT,
                    "current_investigation_id" : MOCK_INVESTIGATION_ID
                }
            , convert_root=False)
    )
    client.put_item(
        TableName=os.environ['SOCLESS_EVENTS_TABLE'],
        Item=dict_to_item({
                    "id": MOCK_INVESTIGATION_ID,
                    'investigation_id' : "already_running_id",
                    'status_' : 'open'
                }
            , convert_root=False)
    )

    event = EventCreator(MOCK_EVENT)
    event.deduplicate()
    assert event.is_duplicate == True
    assert event.status_ == 'closed'
    assert event.investigation_id == "already_running_id"

def test_deduplicate_is_duplicate_status_closed():
    #  Setup tables for this event
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=os.environ['SOCLESS_DEDUP_TABLE'],
        Item=dict_to_item({
                    "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT,
                    "current_investigation_id" : MOCK_INVESTIGATION_ID
                }
            , convert_root=False)
    )
    client.put_item(
        TableName=os.environ['SOCLESS_EVENTS_TABLE'],
        Item=dict_to_item({
                    "id": MOCK_INVESTIGATION_ID,
                    'investigation_id' : "already_running_id",
                    'status_' : 'closed'
                }
            , convert_root=False)
    )

    event = EventCreator(MOCK_EVENT)
    event.deduplicate()
    assert event.is_duplicate == False
    assert event.status_ == 'open'

def test_deduplicate_is_duplicate_no_investigation_id():
    #  Setup dedup_hash for this event (without investigation id)
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=os.environ['SOCLESS_DEDUP_TABLE'],
        Item=dict_to_item({
                    "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT
                }
            , convert_root=False)
    )

    # investigation_id NOT saved in dedup table, not duplicate
    event = EventCreator(MOCK_EVENT)
    event.deduplicate()
    assert event.status_ == 'open'
    assert event.is_duplicate == False

def test_deduplicate_is_unique():
    event = EventCreator(MOCK_EVENT)
    event.deduplicate()
    assert event.status_ == 'open'
    assert event.is_duplicate == False

def test_EventCreator_create():
    event = EventCreator(MOCK_EVENT)
    
    created_event = event.create()

    #check dedup table

    #check events table

    assert event.details == created_event['details']
    assert event.created_at == created_event['created_at']

def test_EventBatch():
    batched_event = EventBatch(MOCK_EVENT_BATCH, MockLambdaContext())

    assert batched_event.event_type == MOCK_EVENT_BATCH['event_type']
    assert batched_event.created_at == None # created_at not supplied in mock
    assert batched_event.details == MOCK_EVENT_BATCH['details']
    assert batched_event.data_types == {} # created_at not supplied in mock
    assert batched_event.dedup_keys == MOCK_EVENT_BATCH['dedup_keys']
    assert batched_event.event_meta == {}
    assert batched_event.playbook == MOCK_EVENT_BATCH['playbook']

def test_EventBatch_missing_details():
    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    del bad_mock_event_batch['details']
    del bad_mock_event_batch['playbook']

    batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

    assert batched_event.playbook == ""
    assert batched_event.details == [{}]

def test_EventBatch_invalid_details_type():
    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['details'] = 'bad_arg'

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

def test_EventBatch_invalid_playbook_type():
    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['playbook'] = ['bad_arg']

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

def test_EventBatch_invalid_dedup_keys_type():
    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['dedup_keys'] = 'bad_arg_type'

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())


def test_create_events():
    from socless.events import create_events

    create_events_result = create_events(MOCK_EVENT_BATCH, MockLambdaContext())

    assert create_events_result['status'] == True
