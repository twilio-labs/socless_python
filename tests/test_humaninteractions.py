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

from tests.conftest import *  # imports testing boilerplate
from socless import init_human_interaction, end_human_interaction
from .helpers import (
    MockLambdaContext,
    mock_integration_handler,
    dict_to_item,
    mock_execution_results_table_entry,
    mock_sfn_db_context,
)
from socless.utils import gen_id, gen_datetimenow
from socless.integrations import StateHandler
from unittest import TestCase
import pytest


def test_init_human_interaction():
    # test init_human_interaction() normally to assert the item gets saved is the same as expected
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    state_handler = StateHandler(
        sfn_context, MockLambdaContext(), mock_integration_handler
    )
    message_id = init_human_interaction(state_handler.context, test_message)

    mock_message_response_entry = dict_to_item(
        {
            "await_token": sfn_context["task_token"],
            "execution_id": sfn_context["sfn_context"]["execution_id"],
            "fulfilled": False,
            "investigation_id": sfn_context["sfn_context"]["artifacts"]["event"][
                "investigation_id"
            ],
            "message": test_message,
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
        },
        convert_root=False,
    )

    client = boto3.client("dynamodb")
    init_message_response_entry = client.get_item(
        TableName=os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"],
        Key={"message_id": dict_to_item(message_id)},
    )["Item"]
    mock_message_response_entry["datetime"] = init_message_response_entry["datetime"]
    mock_message_response_entry["message_id"] = dict_to_item(message_id)

    assert mock_message_response_entry == init_message_response_entry


def test_init_human_interaction_fails_on_invalid_execute_context_key():
    # test init_human_interaction() to make it fail on invalid execute context key
    # it's expected to raise an exception for KeyError
    bad_context = {"hello": "world"}
    test_message = {"greeting": "Hello, World"}
    with pytest.raises(Exception):
        message_id = init_human_interaction(bad_context, test_message)


def test_init_human_interaction_fails_on_generic_exceptions():
    # test init_human_interaction() to make it fail on exceptions other than KeyError
    bad_context = {
        "task_token": 1.0,  # It expects a string, and a float number should make it fail
        "execution_id": gen_id(),
        "artifacts": {
            "event": {
                "id": gen_id(),
                "created_at": gen_datetimenow(),
                "data_types": {},
                "details": {"some": "randon text"},
                "event_type": "Test sfn",
                "event_meta": {},
                "investigation_id": gen_id(),
                "status_": "open",
                "is_duplicate": False,
            },
            "execution_id": gen_id(),
        },
        "state_name": gen_id(),
        "Parameters": {},
    }
    test_message = {"greeting": "Hello, World"}

    with pytest.raises(Exception):
        message_id = init_human_interaction(bad_context, test_message)


def test_end_human_interaction():
    # moto step function send_task_success is not implemented yet
    # test end_human_interaction normally to assert it works as expected
    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    db_context = sfn_item_metadata["db_context"]
    state_name = sfn_context["sfn_context"]["State_Config"]["Name"]
    state_handler = StateHandler(
        sfn_context, MockLambdaContext(), mock_integration_handler
    )
    message_id = init_human_interaction(state_handler.context, test_message)
    with pytest.raises(Exception, match="^response_delivery_failed"):
        end_human_interaction(message_id, test_response)
    client = boto3.client("dynamodb")
    updated_db_context = client.get_item(
        TableName=os.environ["SOCLESS_RESULTS_TABLE"],
        Key={"execution_id": dict_to_item(sfn_item_metadata["execution_id"])},
    )["Item"]

    db_context["results"]["results"][state_name] = test_response
    db_context["results"]["results"]["_Last_Saved_Results"] = test_response
    assert dict_to_item(db_context, convert_root=False) == updated_db_context


def test_end_human_interaction_fails_on_failed_query():
    # test end_human_interaction() fails failed query. Expecting it to raise an exception
    test_response = {"response": "Hello, back"}
    with pytest.raises(Exception, match="^message_id_query_failed"):
        end_human_interaction(1.0, test_response)


def test_end_human_interaction_fails_on_nonexistent_message_id():
    # test end_human_interaction() on message id that doesn't exist. Expecting it to raise an exception
    test_response = {"response": "Hello, back"}
    with pytest.raises(Exception, match="message_id_not_found"):
        end_human_interaction(gen_id(), test_response)


def test_end_human_interaction_fails_on_used_message_id():
    # test end_human_interaction() fails on message id that has already been used. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    state_handler = StateHandler(
        sfn_context, MockLambdaContext(), mock_integration_handler
    )
    message_id = init_human_interaction(state_handler.context, test_message)
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.update_item(
        Key={"message_id": message_id},
        UpdateExpression="SET fulfilled = :fulfilled",
        ExpressionAttributeValues={":fulfilled": True},
    )
    with pytest.raises(Exception, match="message_id_used"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_fails_on_await_token_not_found():
    # test end_human_interaction() fails on await_token doesn't exist in the saved item. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    message_id = gen_id()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": gen_datetimenow(),
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "execution_id": sfn_item_metadata["execution_id"],
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
        }
    )
    with pytest.raises(Exception, match="await_token_not_found"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_fails_on_execution_id_not_found():
    # test end_human_interaction() fails on execution_id doesn't exist in the saved item. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    message_id = gen_id()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": gen_datetimenow(),
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
            "await_token": sfn_item_metadata["task_token"],
        }
    )
    with pytest.raises(Exception, match="execution_id_not_found"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_fails_on_receiver_not_found():
    # test end_human_interaction() fails on receiver doesn't exist in the saved item. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    message_id = gen_id()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": gen_datetimenow(),
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "execution_id": sfn_item_metadata["execution_id"],
            "await_token": sfn_item_metadata["task_token"],
        }
    )
    with pytest.raises(Exception, match="receiver_not_found"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_fails_on_execution_results_not_found():
    # test end_human_interaction() fails on execution_results doesn't exist in the saved item. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    message_id = gen_id()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": gen_datetimenow(),
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "execution_id": gen_id(),
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
            "await_token": sfn_item_metadata["task_token"],
        }
    )
    with pytest.raises(Exception, match="execution_results_not_found"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_fails_on_response_delivery_failed():
    # moto step function send_task_success is not implemented yet. Therefore, this is the last line of test that interacts with humaninteraction.py can be written
    # test end_human_interaction() fails on response_deliver_failed. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    state_handler = StateHandler(
        sfn_context, MockLambdaContext(), mock_integration_handler
    )
    message_id = init_human_interaction(state_handler.context, test_message)
    with pytest.raises(Exception, match="^response_delivery_failed"):
        end_human_interaction(message_id, test_response)


def test_end_human_interaction_update_item():
    # moved blocks of code that can't be tested automatically to here
    # test end_human_interaction() to make sure updated item is as expected

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    message_id = gen_id()
    date_time = gen_datetimenow()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": date_time,
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "execution_id": sfn_item_metadata["execution_id"],
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
            "await_token": sfn_item_metadata["task_token"],
        }
    )
    response_table.update_item(
        Key={"message_id": message_id},
        UpdateExpression="SET fulfilled = :fulfilled, response_payload = :response_payload",
        ExpressionAttributeValues={
            ":fulfilled": True,
            ":response_payload": test_response,
        },
    )
    updated_item = response_table.get_item(Key={"message_id": message_id})["Item"]
    expected_item = {
        "message_id": message_id,
        "datetime": date_time,
        "investigation_id": sfn_item_metadata["investigation_id"],
        "message": test_message,
        "fulfilled": True,
        "execution_id": sfn_item_metadata["execution_id"],
        "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
        "await_token": sfn_item_metadata["task_token"],
        "response_payload": test_response,
    }
    assert expected_item == updated_item


def test_end_human_interaction_fails_on_update_item_exception():
    # moved blocks of code that can't be tested automatically to here
    # test end_human_interaction() to fail on update item. Expecting it to raise an exception

    test_response = {"response": "Hello, back"}
    test_message = {"greeting": "Hello, World"}
    sfn_item_metadata = mock_sfn_db_context()
    sfn_context = sfn_item_metadata["sfn_context"]
    message_id = gen_id()
    date_time = gen_datetimenow()
    response_table = boto3.resource("dynamodb").Table(
        os.environ["SOCLESS_MESSAGE_RESPONSE_TABLE"]
    )
    response_table.put_item(
        Item={
            "message_id": message_id,
            "datetime": date_time,
            "investigation_id": sfn_item_metadata["investigation_id"],
            "message": test_message,
            "fulfilled": False,
            "execution_id": sfn_item_metadata["execution_id"],
            "receiver": sfn_context["sfn_context"]["State_Config"]["Name"],
            "await_token": sfn_item_metadata["task_token"],
        }
    )
    try:
        response_table.update_item(
            Key={"message_id": message_id},
            UpdateExpression="SET fulfilled = :fulfilled, response_payload = :response_payload",
            ExpressionAttributeValues={":fulfilled": True, ":response_payload": 1.0},
        )
    except Exception as e:
        triggered_exception = True
    assert triggered_exception == True
