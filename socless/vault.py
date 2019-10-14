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
Vault module - Functions for interacting with the vault
"""
import boto3, os
from .utils import gen_id
__all__ = ['save_to_vault', 'fetch_from_vault', 'remove_from_vault']

VAULT_TOKEN = "vault:"
SOCLESS_VAULT = os.environ['SOCLESS_VAULT']


def save_to_vault(content, prefix=""):
    """Save content to the Vault

    Args:
        content (str): The string to save to the Socless vault
        prefix (str): The prefix of the object
    Returns:
        A dict containing the file_id (S3 Object path) and vault_id (Socless vault
        reference) of the saved content
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(SOCLESS_VAULT)
    file_id = gen_id()
    if prefix:
        file_id = prefix + file_id
    bucket.put_object(
        Key=file_id,
        Body=content)  #TODO: Should I try catch or let it fail here
    result = {
        "file_id": file_id,
        "vault_id": "{}{}".format(VAULT_TOKEN, file_id)
    }
    return result


def fetch_from_vault(file_id, content_only=False):
    """Fetch an item from the Vault

    Args:
        file_id (string): Path to object in the Vault
        content_only (bool): Set to 'True' to return the content of
            the Vault object and False to return content + metadata

    Returns:
        The string content of the Vault object if content_only is True.
        Otherwise, the content and metadata of the object
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(SOCLESS_VAULT)
    obj = bucket.Object(file_id)
    data = obj.get()['Body'].read().decode('utf-8')
    meta = {"content": data}
    if content_only:
        return meta["content"]
    return meta


def remove_from_vault(file_id):
    """Remove an item from the Vault

    Args:
        file_id (string): Path to object in the Vault

    Returns:
        dict: The response metadata of the attempt to remove the obejct from vault

    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(SOCLESS_VAULT)
    obj = bucket.Object(file_id)
    data = obj.delete()
    return data
