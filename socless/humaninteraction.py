# Copyright 2018 Twilio, Inc
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
"""
humaninteraction.py - Classes, function and libraries to support SOCless' Human Interaction Workflow
"""
import os, boto3, json
from botocore.exceptions import ClientError
from .utils import gen_id, gen_datetimenow
from .integrations import ExecutionContext
from .logger import socless_log_then_raise

def init_human_interaction(execution_context, message_draft, message_id=''):
    """Initialize the human interaction worfklow by saving the Human Interaction Task Token
    to SOCless Message Responses Table

    Args:
        execution_context (dict): The playbook execution context object that contains the task token
        message_draft (string):  The message you intend to send. This will be stored in alongside the task token in the SOCless
            Message Responses Table for record keeping purposes. You still have to send the message yourself in your integration
        message_id (string): The ID to use to track both the interaction request and the human's response


    Returns:
        A message_id to embed in your message such that is returned as part of the human's response.
        It serves as a call_back ID to help SOCless match the users response to the right playbook execution
    """
    if not message_id:
        message_id = gen_id(6)

    RESPONSE_TABLE = os.environ['SOCLESS_MESSAGE_RESPONSE_TABLE']
    response_table = boto3.resource('dynamodb').Table(RESPONSE_TABLE)
    try:
        investigation_id = execution_context['artifacts']['event']['investigation_id']
        execution_id = execution_context['execution_id']
        receiver = execution_context['state_name']
        task_token = execution_context['task_token']
        response_table.put_item(Item={
            "message_id": message_id,
            "datetime": gen_datetimenow(),
            "investigation_id": investigation_id,
            "message": message_draft,
            "fulfilled": False,
            "execution_id": execution_id,
            "receiver": receiver,
            "await_token": task_token
            })
    except KeyError as e:
        socless_log_then_raise(f"Failed to initialize human response workflow because {e} does not exist in the execution_context.")
    except Exception as e:
        socless_log_then_raise(f"Failed to initialize human response workflow because {e}")
    return message_id


def end_human_interaction(message_id, response_body):
    """Completes a human interaction by returning the human's response to
        the appropriate playbook execution

    Args:
        message_id (str): The ID in the human's response that identifies the interaction
        response_body (dict): The human's response

    Raises:
        Exception: A blanket exception raised with either of the below message codes
            message_id_query_failed - Query to retrieve the Message response entry failed
            message_id_not_found - Supplied message_id does not exist in the execution results table
            message_id_used - message_id has already been used
            await_token_not_found - Await token not available in the Message Responses Table. It may not have been retrieved yet or retrieval failed
            execution_id_not_found - No execution id found in the Message responses table
            receiver_not_found - No receiver was set in the Message Responses Table
            execution_results_query_failed - Query to retrieve the relevant execution context failed
            execution_results_not_found - No execution context was found for the message code
            response_delivery_timed_out - Timeout when attempting to deliver the response to the relevant playbook execution
            response_delivery_failed - Failed to deliver the response to the appropriate playbook execution
            message_status_update_failed - Failed to to mark the message as fulfilled
    """

    try:
        responses_table = boto3.resource('dynamodb').Table(os.environ['SOCLESS_MESSAGE_RESPONSE_TABLE'])
        response = responses_table.get_item(Key={"message_id": message_id})
    except Exception as e:
        socless_log_then_raise('message_id_query_failed', {'error': f"{e}"})

    item = response.get('Item',{})
    if not item:
        socless_log_then_raise('message_id_not_found')

    token_used  = item.get('fulfilled', False)
    if token_used:
        socless_log_then_raise('message_id_used')

    await_token = item.get('await_token')
    if not await_token:
        socless_log_then_raise('await_token_not_found')

    execution_id = item.get('execution_id')
    if not execution_id:
        socless_log_then_raise('execution_id_not_found')

    receiver = item.get('receiver')
    if not receiver:
        socless_log_then_raise('receiver_not_found')

    try:
        execution_context = ExecutionContext(execution_id)
        execution_results = execution_context.fetch_context()['results']
    except Exception as e:
        socless_log_then_raise('execution_results_not_found')


    execution_results['execution_id'] = execution_id
    # README: Below code includes state_name with result so that parameters can be passed to choice state in the same way
    # they are passed to integrations (i.e. with $.results.State_Name.parameters)
    # However, it maintain current status quo so that Choice states in current playbooks don't break
    # TODO: Once Choice states in current playbooks have been updated to the new_style, update this code so result's are only nested under state_name
    resp_body_with_state_name = {receiver: response_body}
    resp_body_with_state_name.update(response_body)
    execution_results['results'] = resp_body_with_state_name
    stepfunctions = boto3.client('stepfunctions')
    execution_context.save_state_results(receiver,response_body)
    try:
        stepfunctions.send_task_success(taskToken=await_token,output=json.dumps(execution_results))
    except ClientError as e:
        sfn_error_code = e.response.get('Error',{}).get('Code')
        if sfn_error_code == 'TaskTimedOut':
            socless_log_then_raise('response_delivery_timed_out',{'error': f'{e}'})
        else:
            socless_log_then_raise('response_delivery_failed', {'error': f"{e}"})
    except Exception as e:
        socless_log_then_raise('response_delivery_failed', {'error': f"{e}"})

    try:
        responses_table.update_item(Key={"message_id": message_id},
        UpdateExpression="SET fulfilled = :fulfilled, response_payload = :response_payload",
        ExpressionAttributeValues={
            ":fulfilled": True,
            ":response_payload": resp_body_with_state_name
            }
        )
    except Exception as e:
        socless_log_then_raise('message_status_update_failed', {'error': f"{e}"})
    return
