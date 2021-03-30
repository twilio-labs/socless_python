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
import dataclasses
from socless.models import EventTableItem
from tests.conftest import *  # imports testing boilerplate
from .helpers import MockLambdaContext, dict_to_item
import json, os
import pytest
from moto import mock_stepfunctions, mock_iam
from socless.utils import gen_datetimenow
from socless.exceptions import SoclessEventsError

from socless.events import (
    InitialEvent,
    CompleteEvent,
    create_events,
    get_playbook_arn,
    setup_socless_global_state_from_running_step_functions_execution,
)

account_id = os.environ["MOTO_ACCOUNT_ID"]

playbook_definition = (
    '{"Comment": "An example of the Amazon States Language using a choice state.",'
    '"StartAt": "DefaultState",'
    '"States": '
    '{"DefaultState": {"Type": "Fail","Error": "DefaultStateError","Cause": "No Matches!"}}}'
)

iam_trust_policy_document = {
    "Version": "2012-10-17",
    "Statement": {
        "Effect": "Allow",
        "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
        "Action": "sts:AssumeRole",
    },
}

MOCK_EVENT = {
    "created_at": gen_datetimenow(),
    "event_type": "ParamsToStateMachineTester",
    "details": {"username": "ubalogun", "type": "user", "id": "1"},
    "data_types": {},
    "event_meta": {},
    "playbook": "ParamsToStateMachineTester",
    "dedup_keys": ["username"],
}

MOCK_EVENT_BATCH = {
    **MOCK_EVENT,
    "details": [
        {"username": "ubalogun", "type": "user", "id": "1"},
        {"username": "ubalogun", "type": "user", "id": "2"},
        {"username": "ubalogun", "type": "user", "id": "1"},
    ],
    "dedup_keys": ["username", "id"],
}

DEDUP_HASH_FOR_MOCK_EVENT = "0caa90ad7b7fc101b90a8ce0f9638eb9"
DEDUP_HASH_FOR_EVENT_DUPLICATE_TEST = "a88c7944f007e92a7776bd3550c39265"
MOCK_INVESTIGATION_ID = "mock_investigation_id"
MOCK_PLAYBOOK_NAME = "ParamsToStateMachineTester"


def setup_for_step_functions_and_return_client(playbook_name: str):
    iam_client = boto3.client("iam", region_name="us-east-1")
    iam_role_arn = iam_client.role_arn = iam_client.create_role(
        RoleName="new-user",
        AssumeRolePolicyDocument=json.dumps(iam_trust_policy_document),
    )["Role"]["Arn"]

    sf_client = boto3.client("stepfunctions")
    sf_client.create_state_machine(
        name=playbook_name,
        definition=str(playbook_definition),
        roleArn=iam_role_arn,
    )
    return sf_client


def test_InitialEvent_with_normal_data():
    event = InitialEvent(**MOCK_EVENT)
    assert event.dedup_hash == DEDUP_HASH_FOR_MOCK_EVENT


def test_CompleteEvent_to_EventTableItem():
    initial_event = InitialEvent(**MOCK_EVENT)
    complete_event = CompleteEvent(initial_event)
    item = complete_event.to_EventTableItem

    assert item.id == complete_event.metadata._id
    assert isinstance(item, EventTableItem)
    assert item.__dict__ == dataclasses.asdict(item)


def test_CompleteEvent__deduplicate():
    # setup duplicate
    client = boto3.client("dynamodb")
    client.put_item(
        TableName=os.environ["SOCLESS_DEDUP_TABLE"],
        Item=dict_to_item(
            {
                "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT,
                "current_investigation_id": MOCK_INVESTIGATION_ID,
            },
            convert_root=False,
        ),
    )
    client.put_item(
        TableName=os.environ["SOCLESS_EVENTS_TABLE"],
        Item=dict_to_item(
            {
                "id": MOCK_INVESTIGATION_ID,
                "investigation_id": "already_running_id",
                "status_": "open",
            },
            convert_root=False,
        ),
    )

    # test _deduplicate()
    complete_event = CompleteEvent(**MOCK_EVENT)
    complete_event._deduplicate()
    assert complete_event.metadata.status_ == "closed"
    assert complete_event.metadata.is_duplicate
    assert complete_event.metadata.investigation_id == "already_running_id"


def test_CompleteEvent__deduplicate_fails_when_dedup_key_not_in_details():
    # setup duplicate
    client = boto3.client("dynamodb")
    client.put_item(
        TableName=os.environ["SOCLESS_DEDUP_TABLE"],
        Item=dict_to_item(
            {
                "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT,
                "current_investigation_id": MOCK_INVESTIGATION_ID,
            },
            convert_root=False,
        ),
    )
    client.put_item(
        TableName=os.environ["SOCLESS_EVENTS_TABLE"],
        Item=dict_to_item(
            {
                "id": MOCK_INVESTIGATION_ID,
                "investigation_id": "already_running_id",
                "status_": "open",
            },
            convert_root=False,
        ),
    )

    # test _deduplicate() with a missing dedup key
    modified_event = {**MOCK_EVENT, "dedup_keys": ["invalid_key"]}
    complete_event = CompleteEvent(**modified_event)
    with pytest.raises(KeyError, match="invalid_key"):
        complete_event._deduplicate()


def test_CompleteEvent__deduplicate_with_missing_investigation_id():
    # setup duplicate
    client = boto3.client("dynamodb")
    client.put_item(
        TableName=os.environ["SOCLESS_DEDUP_TABLE"],
        Item=dict_to_item(
            {
                "dedup_hash": DEDUP_HASH_FOR_MOCK_EVENT,
                # "current_investigation_id": MOCK_INVESTIGATION_ID,
            },
            convert_root=False,
        ),
    )

    # test _deduplicate()
    complete_event = CompleteEvent(**MOCK_EVENT)
    complete_event._deduplicate()
    assert complete_event.metadata.status_ == "open"
    assert not complete_event.metadata.is_duplicate


@mock_stepfunctions
@mock_iam
def test_CompleteEvent_start_playbook():
    # setup playbook
    sf_client = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    # test
    initial_event = InitialEvent(**MOCK_EVENT)
    complete_event = CompleteEvent(initial_event)

    playbook_arn = get_playbook_arn(complete_event.event.playbook, MockLambdaContext())
    complete_event.deduplicate_and_update_dedup_table()
    complete_event.put_in_events_table()
    exec_report = complete_event.start_playbook(playbook_arn, sf_client)

    assert not exec_report.error


@mock_stepfunctions
@mock_iam
def test_create_events():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    results = create_events(event_details=MOCK_EVENT, context=MockLambdaContext())
    assert (
        results["events"][0]["metadata"]["investigation_id"]
        == results["execution_reports"][0]["investigation_id"]
    )
    assert not results["execution_reports"][0]["error"]
    assert results["execution_reports"][0]["error"] == ""


@mock_stepfunctions
@mock_iam
def test_create_events_without_dedup_keys():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    modified_event = {**MOCK_EVENT, "dedup_keys": []}
    results = create_events(event_details=modified_event, context=MockLambdaContext())
    assert (
        results["events"][0]["metadata"]["investigation_id"]
        == results["execution_reports"][0]["investigation_id"]
    )
    assert not results["execution_reports"][0]["error"]
    assert results["execution_reports"][0]["error"] == ""


@mock_stepfunctions
@mock_iam
def test_create_events_fails_when_playbook_is_not_deployed():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    modified_event = {**MOCK_EVENT, "playbook": "doesnt exist"}
    with pytest.raises(
        SoclessEventsError, match="1 of 1 events failed to start playbooks."
    ):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_with_multiple_details_and_duplicates():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    results = create_events(event_details=MOCK_EVENT_BATCH, context=MockLambdaContext())
    assert (
        results["events"][0]["metadata"]["investigation_id"]
        == results["execution_reports"][0]["investigation_id"]
    )
    assert len(results["events"]) == len(results["execution_reports"])


@mock_stepfunctions
@mock_iam
def test_create_events_with_details_as_dict_not_list():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)

    results = create_events(event_details=MOCK_EVENT, context=MockLambdaContext())
    assert (
        results["events"][0]["metadata"]["investigation_id"]
        == results["execution_reports"][0]["investigation_id"]
    )
    assert len(results["events"]) == len(results["execution_reports"])


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_created_at():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "created_at": "bad_date"}
    with pytest.raises(Exception):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_details_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "details": "should_be_list_or_dict"}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_data_types_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "data_types": "should_be_list_or_dict"}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_event_meta_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "event_meta": "should_be_list_or_dict"}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_event_type_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "event_type": []}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_playbook_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "playbook": []}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_create_events_fails_with_invalid_dedup_keys_type():
    # setup playbook
    _ = setup_for_step_functions_and_return_client(MOCK_PLAYBOOK_NAME)
    modified_event = {**MOCK_EVENT, "dedup_keys": ""}
    with pytest.raises(TypeError):
        _ = create_events(event_details=modified_event, context=MockLambdaContext())


@mock_stepfunctions
@mock_iam
def test_setup_socless_global_state_from_running_step_functions_execution():
    execution_id = "A_running_exec_id"
    playbook_name = MOCK_PLAYBOOK_NAME
    playbook_event_details = MOCK_EVENT["details"][0]

    result = setup_socless_global_state_from_running_step_functions_execution(
        execution_id, playbook_name, playbook_event_details
    )

    assert result["artifacts"]["event"]["details"] == playbook_event_details
    assert result["execution_id"] == execution_id
