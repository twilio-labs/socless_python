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

__all__ = ["gen_id", "gen_datetimenow"]

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
