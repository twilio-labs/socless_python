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

class MockLambdaContext:
    """Mock Lambda context object
    """

    invoked_function_arn = "arn:aws:lambda:us-west-2:200000000:function:_socless_playground"


def mock_integration_handler(firstname='', middlename='', lastname=''):
    """Mock integration handler object for testing
    """
    return {
        "firstname": firstname,
        "middlename": middlename,
        "lastname": lastname
    }

def dict_to_item(raw):
    """Convert a dictionary to a DynamoDB Item format for put_object."""
    if isinstance(raw, dict):
        return {
            'M': {
                k: dict_to_item(v)
                for k, v in raw.items()
            }
        }
    elif isinstance(raw, list):
        return {
            'L': [dict_to_item(v) for v in raw]
        }
    elif isinstance(raw, str):
        return {'S': raw}
    elif isinstance(raw, int):
        return {'N': str(raw)}