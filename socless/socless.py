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
Socless Core
Contains functions that are used accross Socless
"""
import boto3, os, uuid, simplejson as json, inspect
from botocore.exceptions import ClientError
from datetime import datetime
from .jinja import jinja_env
from .integrations import StateHandler

#TODO: Deprecate socless_credentials
__all__ = ['socless_bootstrap', 'socless_log','socless_gen_id','socless_credentials','fetch_from_vault', 'socless_template_string', 'socless_execute_playbook',
            'socless_dispatch_outbound_message', 'socless_create_events','socless_save_state_execution_result',
            'socless_fetch_execution_result','socless_save_to_vault', 'socless_post_human_response', 'socless_log_then_raise']


VAULT_TOKEN = "vault:"
PATH_TOKEN = "$."
CONVERSION_TOKEN = "!"

class socless_log:
    ERROR = 'ERROR'
    INFO =  'INFO'
    WARN = WARNING = 'WARN'
    DEBUG = 'DEBUG'
    CRITICAL = 'CRITICAL'

    @classmethod
    def __log(cls,level,message,extra={}):
        """
        Writes a log message
        """
        if not message:
            raise ValueError("Message must be provided")

        if not isinstance(extra,dict):
            raise ValueError("Extra must be a dictionary")
        payload = {
            "context": {
                "time": "{}Z".format(datetime.utcnow().isoformat()),
                "aws_region": os.environ.get('AWS_REGION',''),
                "function_name": os.environ.get('AWS_LAMBDA_FUNCTION_NAME',''),
                "execution_env": os.environ.get('AWS_EXECUTION_ENV',''),
                "memory_size": os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE',''),
                "function_version": os.environ.get('AWS_LAMBDA_FUNCTION_VERSION',''),
                "function_log_group": os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME',''),
                "source": "Socless",
                "level": level,
                "lineno": inspect.currentframe().f_back.f_back.f_lineno
            },
            "body":{
                "message": message,
                "extra": extra
            }
        }
        return json.dumps(payload)

    @classmethod
    def info(self,message,extra={}):
        """
        Write a log message with level info
        """
        print((self.__log(self.INFO,message,extra)))

    @classmethod
    def error(self,message,extra={}):
        """
        Write an error message
        """
        print((self.__log(self.ERROR, message,extra)))

    @classmethod
    def debug(self,message,extra={}):
        """
        Write a debug message
        """
        print((self.__log(self.DEBUG, message, extra)))

    @classmethod
    def critical(self, message, extra={}):
        """
        Write a critical message
        """
        print((self.__log(self.CRITICAL, message, extra)))

    @classmethod
    def warn(self, message, extra={}):
        """
        Write a warning message
        """
        print((self.__log(self.WARN, message, extra)))

def socless_gen_id(limit=36):
    """Generate an id

    Args:
        limit (int): length of the id

    Returns:
        str: id of length limit
    """
    return str(uuid.uuid4())[:limit]

def socless_gen_datetimenow():
    """Generate current timestamp in ISO8601 UTC format

    Returns:
        string: current timestamp in ISO8601 UTC format
    """
    return datetime.utcnow().isoformat() + "Z"

def _fetch_from_s3(bucket_name, path):
    """Fetch the contents of an S3 object

    Args:
        bucket_name (str): The S3 bucket name
        path (str): The path to the S3 object

    Returns:
        str: The content of the S3 object in string format
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(path)
    data = obj.get()['Body'].read().decode('utf-8')
    return data

def socless_save_to_vault(content):
    """Save content to the Vault

    Args:
        content (str): The string to save to the Socless vault
    Returns:
        A dict containing the file_id (S3 Object path) and vault_id (Socless vault
        reference) of the saved content
    """
    #TODO Implement input type checking on content. It should be none empty and a string
    SOCLESS_VAULT = os.environ.get("SOCLESS_VAULT")
    #TODO: Figure out if I'd like to raise an error if there's no VAULT environment variable
    vault = boto3.resource('s3').Bucket(SOCLESS_VAULT)
    file_id = socless_gen_id()
    vault.put_object(Key=file_id,Body=content) #TODO: Should I try catch or let it fail here
    result = {
    "file_id": file_id,
    "vault_id": "{}{}".format(VAULT_TOKEN,file_id)
    }
    return result

def socless_credentials(creds_name):
    """Fetch a credential from the Credentials bucket.

    This function is currently deprecated

    Args:
        creds_name (str): Path to credential in S3 Creds bucket

    Returns:
        str: The credentials
    """
    creds = _fetch_from_s3('socless-credentials',creds_name)
    return creds

def fetch_from_vault(file_id,content_only=False):
    """Fetch an item from the Vault

    Args:
        file_id (string): Path to object in the Vault
        content_only (bool): Set to 'True' to return the content of
            the Vault object and False to return content + metadata

    Returns:
        The string content of the Vault object if content_only is True.
        Otherwise, the content and metadata of the object

    """
    data = _fetch_from_s3(os.environ.get('SOCLESS_VAULT'),file_id)
    meta = {
    "content": data
    }
    if content_only:
        return meta["content"]
    return meta

def socless_template_string(message,context):
    """Render a templated string

    Args:
        message (str): The templated string to render
        context (dict): The template parameters

    Returns:
        str: The rendered template
    """
    template = jinja_env.from_string(message)
    return template.render(context=context).replace("&#34;",'"').replace("&#39;","'")


def resolve_vault_path(path):
    """Resolves a vault reference to the actual vault file content

    This handles vault references e.g `vault:file_name` that are passed
    in as parameters to Socless integrations. It fetches and returns the content
    of the Vault object with name `file_name` in the vault.

    Args:
        path (str): The vault reference
    Returns:
        str: The content of the referenced Vault object
    """
    _, __, file_id = path.partition(VAULT_TOKEN)
    data = fetch_from_vault(file_id,content_only=True)
    return data


def apply_conversion_from(data,conversion):
    """Convert the data type of a parameter

    Handles conversion of the datatype of a parameter intended for an integration

    Args:
        data (str): The data to convert
        conversion (str): The conversion to apply
    Returns:
        str: The converted data
    """
    if conversion == "json":
        print(data)
        return json.loads(data)


def resolve_jsonpath(path, obj):
    """Resolves a JsonPath reference to the actual value referenced.
    This implementation does not support the full JsonPath specification

    Args:
        path (str): The JsonPath reference e.g. $.artifacts.investigation_id
        obj (dict): The reference object
    Returns:
        The Json element that results from evaluating the JsonPath reference
        against the reference object
    """
    pre, sep, post = path.partition(PATH_TOKEN)
    keys = post.split('.')
    obj_copy = obj.copy()
    for key in keys:
        value = obj_copy.get(key)
        if isinstance(value,str) and value.startswith(VAULT_TOKEN):
            actual = resolve_vault_path(value)
        else:
            actual = value
        obj_copy = actual
    return obj_copy


def fetch_actual_parameters(path,obj):
    """Resolve the parameter reference passed to an Integration
    to it's actual value.

    This handles the transformation of parameter references passed to
    integrations (e.g $.artifacts.event or vault:file_name) to their
    actual value

    Args:
        path (str): The path to the parameter e.g
        obj (dict): The root object to traverse for the actual parameter value
    Returns:
        The resolved parameter value.
    """

    if not isinstance(path,str):
        if isinstance(path,dict):
            resolved_dict = {}
            for key, value in list(path.items()):
                resolved_dict[key] = fetch_actual_parameters(value,obj)
            return resolved_dict
        else:
            return path

    if not (path.startswith(VAULT_TOKEN) or path.startswith(PATH_TOKEN)):
        return path

    reference, _ , conversion = path.partition(CONVERSION_TOKEN)

    if reference.startswith(PATH_TOKEN):
        resolved =  resolve_jsonpath(reference,obj)
    elif reference.startswith(VAULT_TOKEN):
        resolved =  resolve_vault_path(reference)

    if conversion:
        resolved = apply_conversion_from(resolved,conversion)
    return resolved


def parse_parameters(event,context):
    """Fetches the parameter specific to an integration from
    the Input object

    Args:
        event (dict): The Input object that contains the parameter
            mapping an integration
    Returns:
        A dictionary containing the actual parameter values the integration needs
    """
    CONTEXT_KEY = 'this'
    PARAMETERS_KEY = 'parameters'
    task_state = event.get(CONTEXT_KEY)
    param_obj = event.get(PARAMETERS_KEY).get(task_state)
    actual_params = {}
    for key,value in list(param_obj.items()):
        actual_params[key] = fetch_actual_parameters(value,event)
    return actual_params


def socless_execute_playbook(playbook, entry,investigation_id=''):
    """Trigger the execution of a playbook

    Args:
        playbook (str): The name of the playbook to execute
        entry (dict): The triggering event
        investigation_id (str): The investigation_id of the investigation the playbook
            addresses
    Returns:
        dict: The execution_id, investigation_id and a status indicating if the playbook
            execution request was successful
    """
    meta = {'investigation_id':investigation_id, 'playbook': playbook}
    if not investigation_id:
        investigation_id = socless_gen_id()
    PLAYBOOKS_TABLE = os.environ.get('SOCLESS_PLAYBOOKS_TABLE')
    RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
    playbook_table = boto3.resource('dynamodb').Table(PLAYBOOKS_TABLE)
    try:
        query_result = playbook_table.get_item(Key={'StateMachine': playbook}).get('Item',False)
    except Exception as e:
        socless_log.error("Playbook table query failed",dict(meta, **{'error': f"{e}"}))
        return {"status": True, "message": {"investigation_id": investigation_id}}

    if not query_result:
        socless_log.warn("Playbook not found",meta)
        return {"status":False, "message": "No playbook with name {} found".format(playbook)}
    else:
        playbook_input = query_result.get('Input')
        playbook_arn = query_result.get('Arn')
        execution_id = socless_gen_id()
        playbook_input['artifacts']['event'] = entry
        playbook_input['artifacts']['execution_id'] = execution_id
        results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)
        save_result_resp = results_table.put_item(Item={
            "execution_id": execution_id,
            "datetime": socless_gen_datetimenow(),
            "investigation_id": investigation_id,
            "results": playbook_input
        })
        stepfunctions = boto3.client('stepfunctions')
        try:
            step_resp = stepfunctions.start_execution(
                name=execution_id,
                stateMachineArn=playbook_arn,
                input=json.dumps({
                    "execution_id": execution_id,
                    "artifacts": playbook_input['artifacts']
                }))
            socless_log.info('Playbook execution started',dict(meta, **{'statemachinearn': playbook_arn, 'execution_id': execution_id}))
        except Exception as e:
            socless_log.error('Failed to start statemachine execution',dict(meta, **{'statemachinearn': playbook_arn, 'execution_id': execution_id, 'error': f"{e}"}))
            return {"status": False, "message": f"Error: {e}"}
    return {"status": True, "message": {"execution_id": execution_id,"investigation_id": investigation_id}}


def socless_dispatch_outbound_message(receiver,message_id,investigation_id,execution_id,message):
    """Dispatch an outbound message and save it in the Message Response Table

    """
    message_meta = {'investigation_id':investigation_id, 'execution_id': execution_id, 'receiver': receiver}
    RESPONSE_TABLE = os.environ.get('SOCLESS_MESSAGE_RESPONSE_TABLE')
    STORE_ACTIVITY_TOKEN_ARN = os.environ.get('SAVE_MESSAGE_RESPONSE_MACHINE')
    response_table = boto3.resource('dynamodb').Table(RESPONSE_TABLE)
    try:
        response_table.put_item(Item={
            "message_id": message_id,
            "datetime": "{}Z".format(datetime.utcnow().isoformat()),
            "investigation_id": investigation_id,
            "message": message,
            "fulfilled": False,
            "execution_id": execution_id,
            "receiver": receiver
            })
        socless_log.info("Saved outbound message",)
    except Exception as e:
        socless_log_then_raise("Failed to save outbound message",message_meta)
    stepfunctions = boto3.client('stepfunctions')
    store_activity_token_input = {"receiver":receiver, "message_id":message_id}
    store_activity_token_id = socless_gen_id()
    try:
        stepfunctions.start_execution(stateMachineArn=STORE_ACTIVITY_TOKEN_ARN, input=json.dumps(store_activity_token_input), name = store_activity_token_id)
        socless_log.info('Dispatched outbound message',message_meta)
    except Exception as e:
        socless_log_then_raise('Failed to dispatch outbound message',{'error': f"{e}", 'message_id': message_id})
    return True

def socless_log_then_raise(error_string, extras={}):
    """Log an error then raise an exception
    Args:
        error_string (str): The error message to log and raise
        extras (dict): Additional key value pairs to log
    Raises:
        Exception - Only raises the standard `Exception` error
    """
    socless_log.error(error_string, extras)
    raise Exception(error_string)


def socless_post_human_response(message_id,response_body):
    """Post human response to execution results table and the playbook
    that initated the human response workflow

    Args:
        message_id (str): The message id of the response
        response_body (dict): the response body

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
    #TODO: Log an error for every exception raised
    try:
        responses_table = boto3.resource('dynamodb').Table(os.environ['MESSAGE_RESPONSES_TABLE'])
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
        results_table = boto3.resource('dynamodb').Table(os.environ['RESULTS_TABLE'])
        results_resp = results_table.get_item(Key={"execution_id": execution_id},ProjectionExpression="results.artifacts")
    except Exception as e:
        socless_log_then_raise('execution_results_query_failed', {'error': f'{e}'})

    execution_results = results_resp.get('Item',{}).get('results',{})
    if not execution_results:
        socless_log_then_raise('execution_results_not_found')

    execution_results['execution_id'] = execution_id
    # README: Below code includes state_name with result so that parameters can be passed to choice state in the same way
    # they are passed to integrations (i.e. with $.results.State_Name.parameters)
    # However, maintain current status quo so that Choice states in current playbooks don't break
    # TODO: Once Choice states in current playbooks have been updated to the new_style, update this code so result's are only nested under state_name
    resp_body_with_state_name = {receiver: response_body}
    resp_body_with_state_name.update(response_body)
    execution_results['results'] = resp_body_with_state_name
    stepfunctions = boto3.client('stepfunctions')
    socless_save_state_execution_result(execution_id,receiver,resp_body_with_state_name)
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

def socless_create_events(event_data,dedup=True):
    """Turns raw event data into an Socless event

    Args:
        event (dict): Raw event data
        dedup (bool): Toggle to enable/disable deduplication of events
    Returns:
        Dict w/ investigation_id and status of event creation attempt
    """
    event_type = event_data.get('event_type')
    if not event_type:
        raise Exception("Error: event_type must be supplied")

    created_at = event_data.get('created_at')
    if not created_at:
        created_at = socless_gen_datetimenow()
    else:
        try:
            datetime.strptime(created_at,'%Y-%m-%dT%H:%M:%S.%fZ')
        except:
            raise Exception("Error: Supplied 'created_at' field is not ISO8601 millisecond-precision string, shifted to UTC")

    details = event_data.get('details')
    if not details:
        details = [{}]
    if not isinstance(details,list):
        raise Exception("Error: Supplied 'details' is not a list of dictionaries")

    data_types = event_data.get('data_types')
    if not data_types:
        data_types = {}
    if not isinstance(data_types,dict):
        raise Exception("Error: Supplied 'data_types' is not a dictionary")

    event_meta = event_data.get('event_meta')
    if not event_meta:
        event_meta = {}
    if not isinstance(event_meta,dict):
        raise Exception("Error: Supplied 'event_meta' is not a dictionary")

    playbook = event_data.get('playbook')
    if not playbook:
        playbook = ''
    if not isinstance(playbook,str):
        raise Exception("Error: Supplied Playbook is not a string")

    dedup_keys = event_data.get('dedup_keys')
    if not dedup_keys:
        dedup_keys = []
    if not isinstance(dedup_keys,list):
        raise Exception("Error: Supplied 'dedup_keys' field is not a list")

    EVENTS_TABLE = os.environ.get('SOCLESS_EVENTS_TABLE')
    event_table = boto3.resource('dynamodb').Table(EVENTS_TABLE)

    for detection in details:
        if not isinstance(detection,dict):
            raise Exception("Error: 1 event supplied in 'details' was not a dictionary")
        entry = {}
        _id = socless_gen_id()
        entry['id'] = _id
        entry['created_at'] = created_at
        entry['data_types'] = data_types
        entry['details'] = detection
        entry['event_type'] = event_type
        entry['event_meta'] = event_meta
        investigation_id = _id

        if dedup_keys:
            dedup_fields = { key: detection[key] for key in dedup_keys }
            event_expression = "event_type = :event_type and status_ <> :status_"
            dedup_expression = " and ".join(["details.{key} = :{key}".format(key=key) for key in dedup_fields])
            if dedup_expression:
                FilterExpression = event_expression + " and " + dedup_expression
            else:
                FilterExpression = event_expression
            ExpressionAttributeValues = { ':event_type': event_type, ':status_': 'closed'}
            for key, value in list(dedup_fields.items()):
                ExpressionAttributeValues[":{}".format(key)] = value
            try:
                scan_results = event_table.scan(FilterExpression=FilterExpression,ExpressionAttributeValues=ExpressionAttributeValues)
                while 'LastEvaluatedKey' in scan_results and scan_results['Count'] == 0:
                    scan_results = event_table.scan(FilterExpression=FilterExpression,ExpressionAttributeValues=ExpressionAttributeValues,ExclusiveStartKey=scan_results['LastEvaluatedKey'])
            except Exception as e:
                raise Exception(f"Scanning event table for duplicates failed, {e}")

            if not scan_results['Items']:
                entry['status_'] = 'open'
                entry['is_duplicate'] = False
                entry['investigation_id'] = investigation_id
            else:
                entry['status_'] = 'closed'
                entry['is_duplicate'] = True
                entry['investigation_id'] = scan_results['Items'][0]['investigation_id']
        else:
            entry['status_'] = 'open'
            entry['investigation_id'] = investigation_id
            entry['is_duplicate'] = False
        # Save entry to database
        save_entry_resp = event_table.put_item(Item=entry)
        # Trigger execution of a playbook if playbook was supplied
        if playbook:
            socless_execute_playbook(playbook,entry,investigation_id)
    return {"status":True, "message":investigation_id}

def socless_save_state_execution_result(execution_id,state_name,result):
    """Save the result of a Playbook state execution

    Args:
        execution_id (string): ID of the executing playbook instance
        state_name (string): Name of the state to save results for
        result (dict): The results to save
    """
    meta = {'execution_id': execution_id, 'state_name': 'state_name'}
    RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
    results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)
    try:
        results_table.update_item(
                    Key={
                        "execution_id": execution_id
                        },
                    UpdateExpression='SET #results.#results.#name = :r, #results.#results.#last_results = :r',
                    ExpressionAttributeValues={
                        ':r': result
                    },
                    ExpressionAttributeNames={
                        "#results": "results",
                        "#name": state_name,
                        "#last_results": '_Last_Saved_Results'
                    }
                )
    except Exception as e:
        socless_log.error("Failed to save state execution results", dict(meta, **{'error': f"{e}"}))

def socless_fetch_execution_result(execution_id,state_name):
    """Fetch Playbook execution result object

    Args:
        execution_id (str): The execution id of the playbook instance
        state_name (str): The name of the state making the request
    Returns:
        dict: An execution result object
    """
    meta = {'execution_id': execution_id, 'state_name': state_name}
    RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
    results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)
    try:
        item_resp = results_table.get_item(Key={
            'execution_id': execution_id
        })
    except Exception as e:
        socless_log.error('Failed to retrieve execution results for state', meta)
        return {
            "status": "error",
            "message": f"{e}"
        }
    item = item_resp.get("Item",{})
    if not item:
        socless_log.error('Execution not found', meta)
        raise Exception("Error: Unable to get execution_id {} from {}".format(execution_id,RESULTS_TABLE))
    return item


def socless_bootstrap(event,context,handler,include_event=False):
    """Setup and run an integration's business logic

    Args:
        event (dict): The Lambda event object
        context (obj): The Lambda context object
        handler (func): The handler for the integration
        include_event (bool): Indicates whether to make the full event object available
            to the handler
    Returns:
        Dict containing the result of executing the integration
    """
    state_handler = StateHandler(event,context,handler,include_event=include_event)
    result = state_handler.execute()
    # README: Below code includes state_name with result so that parameters can be passed to choice state in the same way
    # they are passed to integrations (i.e. with $.results.State_Name.parameters)
    # However, maintain current status quo so that Choice states in current playbooks don't break
    # TODO: Once Choice states in current playbooks have been updated to the new_style, update this code so result's are only nested under state_name
    result_with_state_name = {state_handler.state_name: result}
    result_with_state_name.update(result)
    event['results'] = result_with_state_name
    return event
