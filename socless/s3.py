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
import boto3, os
from botocore.exceptions import ClientError
__all__ = ['save_to_s3']

def save_to_s3(file_id, content, bucket_name, return_content=False):
    """Save content to a S3 bucket

    Args:
        file_id (str): s3 object key
        content (str): content of the Object
        bucket_name (str): name of the bucket
        return_content (bool): true or false to return the content; set to false by default
    Returns:
        A dict containing the file_id (S3 Object path) and vault_id (Socless vault
        reference) of the saved content
    """

    bucket = boto3.resource('s3').Bucket(bucket_name)
    bucket.put_object(Key=file_id,Body=content)

    if return_content:
        return {
            "file_id": file_id,
            "full_path": "{}/{}".format(bucket_name, file_id),
            "content": content
            }

    return {
        "file_id": file_id,
        "full_path": "{}/{}".format(bucket_name, file_id)
        }