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
import json, os
from copy import deepcopy
import pytest
from moto import mock_stepfunctions, mock_sts, mock_iam

from socless.s3 import save_to_s3


bucket_name = os.environ['SOCLESS_VAULT']

def test_save_to_s3():
    file_id = 'test_file_one.json'
    content = {"Heres a file" : "Heres the value"}
    
    response = save_to_s3(file_id, content, bucket_name, True)

    #check bucket for item
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(file_id)
    data = obj.get()['Body'].read().decode('utf-8')

    assert json.loads(data) == content
    assert response['file_id'] == file_id
    assert response['full_path'] == f"{bucket_name}/{response['file_id']}"
    assert content == response['content']

def test_save_to_s3_fails_on_invalid_content():
    file_id = 'test_file_one.json'
    class Class_No_JSONSerialization:
        pass

    content = Class_No_JSONSerialization()

    with pytest.raises(TypeError):
        save_to_s3(file_id, content, bucket_name, True)

def test_save_to_s3_no_return_content():
    file_id = 'test_file_one.json'
    content = {"Heres a file" : "Heres the value"}
    
    response = save_to_s3(file_id, content, bucket_name)
    
    #check bucket for item
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(file_id)
    data = obj.get()['Body'].read().decode('utf-8')
    
    assert json.loads(data) == content
    assert response['file_id'] == file_id
    assert response['full_path'] == f"{bucket_name}/{response['file_id']}"

def test_save_to_s3_fails_on_missing_bucket():
    file_id = 'test_file_one.json'
    content = {"Heres a file" : "Heres the value"}
    
    with pytest.raises(Exception):
        response = save_to_s3(file_id, content, 'bad_bucket_name')

