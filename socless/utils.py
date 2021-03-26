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
utils.py - Contains utility functions
"""
import uuid
from datetime import datetime

__all__ = ["gen_id", "gen_datetimenow", "convert_empty_strings_to_none"]


def gen_id(limit=36):
    """Generate an id

    Args:
        limit (int): length of the id

    Returns:
        str: id of length limit
    """
    return str(uuid.uuid4())[:limit]


def gen_datetimenow():
    """Generate current timestamp in ISO8601 UTC format

    Returns:
        string: current timestamp in ISO8601 UTC format
    """
    return datetime.utcnow().isoformat() + "Z"


def validate_iso_datetime(iso_datetime: str):
    """Raises Exception if not correct format"""
    try:
        datetime.strptime(iso_datetime, "%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        raise Exception(
            "Error: Supplied 'created_at' field is not ISO8601 millisecond-precision string, shifted to UTC"
        )


def convert_empty_strings_to_none(nested_dict):
    converted_dict = {}
    if isinstance(nested_dict, dict):
        for k, v in nested_dict.items():
            if isinstance(v, dict):
                converted_dict[k] = convert_empty_strings_to_none(v)
            elif isinstance(v, list):
                converted_dict[k] = [convert_empty_strings_to_none(l_v) for l_v in v]
            elif isinstance(v, str):
                converted_dict[k] = v if v else None
            else:
                converted_dict[k] = v
    return converted_dict
