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

from socless.vault import save_to_vault, fetch_from_vault, remove_from_vault


bucket_name = os.environ['SOCLESS_VAULT']

def test_save_to_vault():
    content = "Test_Content"
    response = save_to_vault(content)

    #check bucket for item
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(response['file_id'])
    data = obj.get()['Body'].read().decode('utf-8')

    assert response['vault_id'] == f"vault:{response['file_id']}"
    assert data == content
    

def test_save_to_vault_with_prefix():
    content = "Test_Content"
    prefix = "test_prefix"
    response = save_to_vault(content, prefix)

    #check bucket for item
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(response['file_id'])
    data = obj.get()['Body'].read().decode('utf-8')

    assert prefix in response['vault_id']
    assert response['vault_id'] == f"vault:{response['file_id']}"
    assert data == content

def test_fetch_from_vault():
    # setup by adding test item in vault
    content = "Test_Content"
    setup = save_to_vault(content)
    file_id = setup['file_id']

    response = fetch_from_vault(file_id)

    assert response['content'] == content

def test_fetch_from_vault_content_only():
    # setup by adding test item in vault
    content = "Test_Content"
    setup = save_to_vault(content)
    file_id = setup['file_id']

    response = fetch_from_vault(file_id, True)

    assert response == content

def test_fetch_from_vault_fails_with_wrong_file_id():
    # setup by adding test item in vault
    content = "Test_Content"
    setup = save_to_vault(content)
    file_id = setup['file_id']

    with pytest.raises(Exception):
        response = fetch_from_vault('bad_file_id')

def test_remove_from_vault():
    # setup by adding test item in vault
    content = "Test_Content"
    setup = save_to_vault(content)
    file_id = setup['file_id']

    response = remove_from_vault(file_id)

    assert response['ResponseMetadata']['HTTPStatusCode'] == 204

    # response code is always 204, manually check if item was deleted
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(file_id)
    with pytest.raises(Exception):
        data = obj.get()['Body'].read().decode('utf-8')
