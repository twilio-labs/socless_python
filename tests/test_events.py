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
from socless.events import create_events
from .helpers import MockLambdaContext
from moto import mock_dynamodb2

import boto3, os

import responses # because moto breaks requests
responses.add_passthru('https://')# moto+requests needs this
responses.add_passthru('http://')# 

boto3.setup_default_session() # use moto instead of boto

@mock_dynamodb2
def test_create_events():
    event = {
        "event_type": "ParamsToStateMachineTester",
        "details": [
            {"username": "ubalogun","type": "user","id":"1"},
            {"username": "ubalogun","type": "user","id":"2"},
            {"username": "ubalogun","type": "user","id":"1"}
        ],
        "playbook": "ParamsToStateMachineTester",
        "dedup_keys": ["username", "id"]
    }

    #setup tables
    from pprint import pprint
    pprint(os.environ)

    results_table_name = os.environ['SOCLESS_EVENTS_TABLE']
    client = boto3.client('dynamodb')
    events_table = client.create_table(
        TableName=results_table_name,
        KeySchema=[{'AttributeName': 'id','KeyType': 'HASH'}],
        AttributeDefinitions=[])
    
    results_table_name = os.environ['SOCLESS_RESULTS_TABLE']
    results_table = client.create_table(
        TableName='socless_execution_results',
        
        KeySchema=[{'AttributeName': 'execution_id','KeyType': 'HASH'}],
        AttributeDefinitions=[])
    


    assert create_events(event,MockLambdaContext())['status'] == True
