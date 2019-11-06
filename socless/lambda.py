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
Lambda module - Functions for interacting with boto3 Lambda client
"""
import boto3, os
from botocore.exceptions import ClientError
__all__ = ['get_function_meta_data']

def get_function_meta_data(function_name, quanlifier=""):
    try:
        client = boto3.client('lambda')
        response = client.get_function(
            FunctionName=function_name,
            Qualifier=quanlifier
        )
    except ClientError as e:
        print("Unexpected error: %s" % e)

    return response
