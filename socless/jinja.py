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
Code for Jinja2 which Socless uses for templating strings
"""
from socless.exceptions import SoclessBootstrapError
from typing import Any
import json, os
from jinja2.nativetypes import NativeEnvironment
from jinja2 import select_autoescape, StrictUndefined
from .vault import fetch_from_vault


# Jinja Environment Configuration
#! this fails to escape <script>, escaping works with Environment
jinja_env = NativeEnvironment(
    autoescape=select_autoescape(
        ["html", "xml"], default_for_string=True, default=True
    ),
    variable_start_string="{",  # this defines the start tokens for a jinja template
    variable_end_string="}",  # this is the end token for a jinja template
    undefined=StrictUndefined,  # This configures Jinjas behaviour when a template user provides an undefined reference
    ### StrictUndefined here ensures that if the user references something that
    # Doesn't actually exist in the context, an error is raised
    # Without StrictUndefined, invalid references fail silently
    # More on undefined types here https://jinja.palletsprojects.com/en/2.11.x/api/#undefined-types
)


def maptostr(target_list):
    """Casts a list of python types to a list of strings
    Args:
        target_list (list): list containing python types
    Returns:
        List containing strings
    Note:
        May no longer be needed in Python3
    """
    return [str(each) for each in target_list]


def vault(vault_id: str):
    # A custom jinja Function which returns the content of a socless vault
    # we expect it to be called as {vault( context.vault_id) }  and return the same value
    # that current vault:vault-id would return
    return fetch_from_vault(vault_id, content_only=True)


def fromjson(string_json: str) -> Any:
    # This is a custom jinja Filter which expects stringified json and returns
    # the output of calling json.loads on it.
    try:
        return json.loads(string_json)
    except json.decoder.JSONDecodeError as e:
        raise SoclessBootstrapError(
            f"JSONDecodeError in `fromjson` Jinja filter/function. Error: {e} |\n String: {string_json}"
        )


def env(env_var_name: str) -> str:
    banned_env_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]
    if env_var_name in banned_env_vars:
        raise SoclessBootstrapError(f"Cannot access disallowed env var: {env_var_name}")

    try:
        return os.environ[env_var_name]
    except KeyError:
        raise SoclessBootstrapError(f"Environment Variable {env_var_name} not found")


# Add Custom Functions
custom_functions = {"vault": vault, "fromjson": fromjson, "env": env}

# Add Custom Filters
custom_filters = {"maptostr": maptostr, **custom_functions}

# Register Custom Filters
jinja_env.filters.update(custom_filters)
# Register Custom Functions
jinja_env.globals.update(custom_functions)


def render_jinja_from_string(template_string: str, root_object: dict) -> Any:
    template_obj = jinja_env.from_string(template_string)
    return template_obj.render(context=root_object)
