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
    """Mock integration handler object for testing
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
    """Mock integration handler object for testing
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

def pre_save_dummy_execution_resutls():
    execution_id = gen_id()
    investigation_id = gen_id()
    date_time = gen_datetimenow()
    results_table_name = os.environ['SOCLESS_RESULTS_TABLE']
    client = boto3.client('dynamodb')
    client.put_item(
        TableName=results_table_name,
        Item={
            "datetime": { "S": date_time },
            "execution_id": { "S": execution_id },
            "investigation_id": { "S":investigation_id },
            "results": dict_to_item({"artifacts": {"execution_id": execution_id}, "errors": {},"results":{}})
        }
    )
    return {"execution_id": execution_id,
            "investigation_id": investigation_id,
            "datetime": date_time}
