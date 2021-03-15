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
Function module - Functions for interacting with boto3 Lambda client
"""
from os import environ
from socless.exceptions import SoclessBootstrapError
import boto3
from botocore.exceptions import ClientError


__all__ = ["fetch_from_ssm"]


def fetch_from_ssm(paramter_name) -> str:
    """Fetch path from SSM Parameter Store."""

    ssm = boto3.client("ssm")

    try:
        param_response = ssm.get_parameter(Name=paramter_name, WithDecryption=True)
        return param_response["Parameter"]["Value"]
    except ClientError as e:
        raise SoclessBootstrapError(
            f"Unable to get ssm parameter at path {paramter_name} in {environ.get('AWS_REGION')}\n {e}"
        )
