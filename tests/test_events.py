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
from .helpers import MockLambdaContext
from pprint import pprint
from copy import deepcopy
import pytest

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

def test_EventBatch():
    from socless.events import EventBatch

    batched_event = EventBatch(MOCK_EVENT_BATCH, MockLambdaContext())

    assert batched_event.event_type == MOCK_EVENT_BATCH['event_type']
    assert batched_event.created_at == None # created_at not supplied in mock
    assert batched_event.details == MOCK_EVENT_BATCH['details']
    assert batched_event.data_types == {} # created_at not supplied in mock
    assert batched_event.dedup_keys == MOCK_EVENT_BATCH['dedup_keys']
    assert batched_event.event_meta == {}
    assert batched_event.playbook == MOCK_EVENT_BATCH['playbook']

def test_EventBatch_missing_details():
    from socless.events import EventBatch

    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    del bad_mock_event_batch['details']
    del bad_mock_event_batch['playbook']

    batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

    assert batched_event.playbook == ""
    assert batched_event.details == [{}]

def test_EventBatch_incorrect_details_type():
    from socless.events import EventBatch

    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['details'] = 'bad_arg'

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

def test_EventBatch_incorrect_playbook_type():
    from socless.events import EventBatch

    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['playbook'] = ['bad_arg']

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

def test_EventBatch_incorrect_dedup_keys_type():
    from socless.events import EventBatch

    bad_mock_event_batch = deepcopy(MOCK_EVENT_BATCH)
    bad_mock_event_batch['dedup_keys'] = 'bad_arg_type'

    with pytest.raises(Exception):
        batched_event = EventBatch(bad_mock_event_batch, MockLambdaContext())

def test_create_events():
    from socless.events import create_events

    create_events_result = create_events(MOCK_EVENT_BATCH, MockLambdaContext())

    assert create_events_result['status'] == True
