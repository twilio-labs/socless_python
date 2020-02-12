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
"""
Helpers
"""
import os
from socless.utils import gen_id, gen_datetimenow
import boto3

account_id = os.environ['MOTO_ACCOUNT_ID']


class MockLambdaContext:
    """Mock Lambda context object
    """

    invoked_function_arn = f"arn:aws:lambda:us-west-2:{account_id}:function:_socless_playground"


def mock_integration_handler(context={}, firstname='', middlename='', lastname=''):
    """Mock integration handler object for testing. The first argument context shouldn't be used. It's there for StateHandler class from integrations.py to use when include_context flag is set to True
    """
    result = {
        "firstname": firstname,
        "middlename": middlename,
        "lastname": lastname
    }
    if context:
        context.update(result)
        return context
    return result

def mock_integration_handler_return_string(firstname='', middlename='', lastname=''):
    """Mock integration handler to return a string. It can be used to test StateHandler's error handling since it's supposed to raise an exception when an integration returns non-dict
    """
    return 'No dict'

def dict_to_item(raw,convert_root=True):
    """Convert a dictionary object to a DynamoDB Item format for put_object

    Args:
        raw (dict): The python type to convert
        convert_root (bool): If a dictionary,

    """
    if isinstance(raw, dict):
        item = {
            'M': {
                k: dict_to_item(v)
                for k, v in raw.items()
            }
        }
    elif isinstance(raw, list):
        item =  {
            'L': [dict_to_item(v) for v in raw]
        }
    elif isinstance(raw, str):
        item =  {'S': raw}
        # item =  {'S': raw if raw else None} #replace empty strings with None
    elif isinstance(raw,bool):
        item =  {'BOOL': raw}
    elif isinstance(raw, int):
        item =  {'N': str(raw)}

    return item if convert_root else item['M']

def mock_execution_results_table_entry():
    # setup db context for execution results table entry

    random_id = gen_id()
    execution_id = gen_id()
    investigation_id = gen_id()
    date_time = gen_datetimenow()
    context = {
            "datetime": date_time,
            "execution_id": execution_id,
            "investigation_id": investigation_id,
            "results": {
                'artifacts': {
                    'event': {
                        'id': random_id,
                        'created_at': date_time,
                        'data_types': {},
                        'details': {
                            "some": "randon text"
                        },
                        'event_type': 'Test integrations',
                        'event_meta': {},
                        'investigation_id': investigation_id,
                        'status_': 'open',
                        'is_duplicate': False
                    },
                    'execution_id': execution_id
                },
                "errors": {},
                "results": {}
            }
        }
    results_table_name = os.environ['SOCLESS_RESULTS_TABLE']
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=results_table_name,
        Item=dict_to_item(
            context,
            convert_root=False
        )
    )
    return {'id': random_id,
            "execution_id": execution_id,
            "investigation_id": investigation_id,
            "datetime": date_time,
            'context': context}

def mock_sfn_db_context():
    # setup db context for step function

    item_metadata = mock_execution_results_table_entry()
    task_token = gen_id()
    sfn_context = {
            'task_token': task_token,
            'sfn_context': {
                'execution_id': item_metadata['execution_id'],
                'artifacts': {
                    'event': {
                        'id': item_metadata['id'],
                        'created_at': item_metadata['datetime'],
                        'data_types': {},
                        'details': {
                            "some": "randon text"
                        },
                        'event_type': 'Test sfn',
                        'event_meta': {},
                        'investigation_id': item_metadata['investigation_id'],
                        'status_': 'open',
                        'is_duplicate': False
                    },
                    'execution_id': item_metadata['execution_id']
                },
                'State_Config': {
                    'Name': "Test state name",
                    'Parameters': {}
                }
            }
        }
    return {'id': item_metadata['id'],
            'task_token': task_token,
            "execution_id": item_metadata['execution_id'],
            "investigation_id": item_metadata['investigation_id'],
            "datetime": item_metadata['datetime'],
            'sfn_context': sfn_context,
            'db_context': item_metadata['context']}