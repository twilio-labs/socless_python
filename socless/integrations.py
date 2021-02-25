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
Classes and modules for Integrations
"""
import boto3, simplejson as json, os
import re
from typing import Any, Callable
from .logger import socless_log
from .vault import fetch_from_vault
from .utils import convert_empty_strings_to_none
from .exceptions import SoclessException, SoclessBootstrapError
from .aws_classes import LambdaContext
from .jinja import jinja_env

VAULT_TOKEN = "vault:"
PATH_TOKEN = "$."
CONVERSION_TOKEN = "!"
vault_pattern = re.compile(r"(vault:)(\S+(?=\s|$))(.*)")


class ParameterResolver:
    """Evaluates parameter references for integrations"""

    def __init__(self, root_obj):
        self.root_obj = root_obj

    def resolve_jsonpath(self, path):
        """Resolves a JsonPath reference to the actual value referenced.
        Does not support the full JsonPath specification

        Args:
            path: The JsonPath reference e.g. $.artifacts.investigation_id
        Returns:
            The referenced element. May be any Python built-in type
        """
        _, _, post = path.partition(PATH_TOKEN)
        keys = post.split(".")
        obj_copy = self.root_obj.copy()
        for key in keys:
            try:
                value = obj_copy.get(key)
            except AttributeError:
                raise SoclessException(
                    f"Unable to resolve key {key}, parent object does not exist. Full path: {path}"
                )
            if isinstance(value, str) and value.startswith(VAULT_TOKEN):
                _, _, file_id = value.partition(VAULT_TOKEN)
                actual = fetch_from_vault(file_id, content_only=True)
            else:
                actual = value
            obj_copy = actual
        return obj_copy

    def resolve_vault_path(self, path):
        """Resolves a vault reference to the actual vault file content

        This handles vault references e.g `vault:file_name` that are passed
        in as parameters to Socless integrations. It fetches and returns the content
        of the Vault object with name `file_name` in the vault.

        Args:
            path (str): The vault reference
        Returns:
            str: The content of the referenced Vault object
        """
        _, _, file_id = path.partition(VAULT_TOKEN)
        data = fetch_from_vault(file_id, content_only=True)
        return data

    def resolve_reference(self, reference_path):
        """Evaluate a reference path and return the referenced value

        Args:
            reference_path: The reference to evaluate may be any Python
                built-in type
        Returns:
            The resulting value. May be any Python built-in type
        """

        if isinstance(reference_path, str):
            backwards_compatible = convert_legacy_reference_to_template(reference_path)
            return resolve_template(
                template_string=backwards_compatible,
                root_object=self.root_obj,
            )
        elif isinstance(reference_path, dict):
            resolved_dict = {}
            for key, value in list(reference_path.items()):
                resolved_dict[key] = self.resolve_reference(value)
            return resolved_dict
        elif isinstance(reference_path, list):
            resolved_list = []
            for item in reference_path:
                resolved_list.append(self.resolve_reference(item))
            return resolved_list
        else:
            return reference_path

        if reference_path.startswith(PATH_TOKEN):
            reference, _, conversion = reference_path.partition(CONVERSION_TOKEN)
            resolved = self.resolve_jsonpath(reference)
        elif reference_path.startswith(VAULT_TOKEN):
            reference, _, conversion = reference_path.partition(CONVERSION_TOKEN)
            _, _, file_id = reference.partition(VAULT_TOKEN)
            resolved = fetch_from_vault(file_id, content_only=True)
        else:
            return reference_path

        if conversion:
            resolved = self.apply_conversion_from(resolved, conversion)
        return resolved

    def resolve_parameters(self, parameters):
        """Resolve a set of parameter references to their actual vaules

        Args:
            parameters (dict): Parameter references to resolve
        Returns:
            a dictionary containing resolved parameter references
        """
        actual_params = {}
        for parameter, reference in list(parameters.items()):
            actual_params[parameter] = self.resolve_reference(reference)
        return actual_params

    def apply_conversion_from(self, data, conversion):
        """Convert the data type of a parameter

        Handles conversion of the datatype of a parameter intended for an integration

        Args:
            data (str): The data to convert
            conversion (str): The conversion to apply
        Returns:
            str: The converted data
        """
        if conversion == "json":
            return json.loads(data)
        else:
            raise NotImplementedError("Conversion only supports 'json'")


def resolve_template(template_string: str, root_object: dict) -> Any:
    template = jinja_env.from_string(template_string)

    rendered = template.render(context=root_object)
    if isinstance(rendered, str):
        rendered = rendered.replace("&#34;", '"').replace("&#39;", "'")
    return rendered


def convert_legacy_reference_to_template(reference_path: str):
    """Allow backwards compatibility for legacy socless parameter reference to jinja templates.
    `resolve_template` jinja translation is supported by this function that converts
    legacy references to valid jinja templates according to the table below:

        Legacy Reference   | Converted Jinja template
        ----------------   | ------------------------
        “$.<ref_path>”     |  “{context.<ref_path>}”
        “vault:<vault-id>” |  “vault-id | fromvault}”
        "<something>!json" |  "{<something> | fromjson}"
    """
    try:
        needs_brackets = False
        template = reference_path
        if template.endswith("!json"):
            needs_brackets = True
            template = template.replace("!json", " |fromjson")
        if template.startswith(PATH_TOKEN):
            needs_brackets = True
            template = template.replace("$.", "context.")

        vault_matches = re.search(vault_pattern, template)
        if vault_matches:
            needs_brackets = True
            template = f"vault('{vault_matches.group(2)}') {vault_matches.group(3)}"

        if needs_brackets:
            template = "{" + template + "}"

        return template
    except (TypeError, KeyError) as e:
        raise SoclessException(
            f"Unable to convert reference type {type(reference_path)} to template - {e}"
        )


class ExecutionContext:
    """The execution context object"""

    def __init__(self, execution_id):
        self.execution_id = execution_id

    def fetch_context(self):
        """Fetch execution context from the Execution Results table

        Args:
            execution_id (str): The execution id for a playbook execution instance
        Returns:
            dict: The execution result object
        """
        RESULTS_TABLE = os.environ.get("SOCLESS_RESULTS_TABLE")
        results_table = boto3.resource("dynamodb").Table(RESULTS_TABLE)
        item_resp = results_table.get_item(
            Key={"execution_id": self.execution_id}, ConsistentRead=True
        )

        item = item_resp.get("Item", {})
        if not item:
            raise Exception(
                f"Error: Unable to get execution_id {self.execution_id} from {RESULTS_TABLE}."
            )

        return item

    def save_state_results(self, state_name, result, errors={}):
        """Save the results of a State's execution to the Execution results table
        Args:
            state_name (str): The name of the state
            result (obj): The result to save
        """
        RESULTS_TABLE = os.environ.get("SOCLESS_RESULTS_TABLE")
        results_table = boto3.resource("dynamodb").Table(RESULTS_TABLE)

        error_expression = ""
        expression_attributes = {":r": result}
        if errors:
            # if Timeout, Error cause is empty string.
            errors = convert_empty_strings_to_none(errors)
            error_expression = ",#results.errors = :e"
            expression_attributes[":e"] = errors

        results_table.update_item(
            Key={"execution_id": self.execution_id},
            UpdateExpression=f"SET #results.#results.#name = :r, #results.#results.#last_results = :r {error_expression}",
            ExpressionAttributeValues=expression_attributes,
            ExpressionAttributeNames={
                "#results": "results",
                "#name": state_name,
                "#last_results": "_Last_Saved_Results",
            },
        )


class StateHandler:
    """Controls the execution of an integration for a given state in a Playbook"""

    def __init__(self, event, lambda_context, integration_handler, include_event=False):
        """
        Args:
            event (dict): The input passed to the Lambda function by the service that triggered it
            lambda_context (obj): The Lambda context object
            integration_handler (func): The function that implements the integrations business logic
            include_playbook_context (bool): Set to `True` to make the full context object of the executing playbook available to the integration
        """
        # TODO: Figure out how to handle include_event
        if "task_token" in event:
            self.task_token = event["task_token"]
            self.event = event["sfn_context"]
        else:
            self.task_token = ""
            self.event = event

        self.testing = bool(self.event.get("_testing"))
        self.execution_id = self.event.get("execution_id", "")

        try:
            self.state_config = self.event["State_Config"]
        except KeyError:
            # not triggered from socless playbook (direct invoke via CLI, Test console, etc.)
            if "execution_id" not in self.event and "artifacts" not in self.event:
                socless_log.info(
                    "No State_Config was passed to the integration, likely due to invocation \
from outside of a SOCless playbook. Running this lambda in test mode."
                )
                self.testing = True
                self.state_config = {"Name": "direct_invoke", "Parameters": self.event}
                self.event = {
                    "_testing": True,
                    "State_Config": self.state_config,  # maybe this will fix it?
                }
            else:
                raise SoclessBootstrapError(
                    "No `State_Config` was passed to the integration"
                )

        try:
            self.state_name = self.state_config["Name"]
        except KeyError:
            raise SoclessBootstrapError("`Name` not set in State_Config")

        try:
            self.state_parameters = self.state_config["Parameters"]
        except KeyError:
            raise SoclessBootstrapError("`Parameters` not set in State_Config")

        if self.testing:
            self.context = self.event
        else:
            if self.execution_id:
                self.execution_context = ExecutionContext(self.execution_id)
                self.context = self.execution_context.fetch_context()["results"]
                self.context["execution_id"] = self.execution_id
                if "errors" in self.event:
                    self.context["errors"] = self.event["errors"]
                if self.task_token:
                    self.context["task_token"] = self.task_token
                    self.context["state_name"] = self.state_name
            else:
                raise SoclessBootstrapError(
                    "Execution id not found in non-testing context"
                )

        self.integration_handler = integration_handler
        self.include_event = include_event
        # TODO: Find a way to maintain the execution_id between lambdas

    def execute(self):
        """Execute the integration to fulfil the assigned state"""

        resolver = ParameterResolver(self.context)
        actual_params = resolver.resolve_parameters(self.state_parameters)

        if self.include_event:
            result = self.integration_handler(self.context, **actual_params)
        else:
            result = self.integration_handler(**actual_params)

        if not isinstance(result, dict):
            raise SoclessBootstrapError(
                "Result returned from the integration handler is not a Python dictionary. Must be a Python dictionary"
            )

        if not self.testing:
            self.execution_context.save_state_results(
                self.state_name, result, errors=self.context.get("errors", {})
            )

        return result


def socless_bootstrap(
    event: dict, context: LambdaContext, handler: Callable, include_event=False
):
    """Setup and run an integration's business logic

    Args:
        event (dict): The Lambda event object
        context (obj): The Lambda context object
        handler (func): The handler for the integration
        include_event (bool): Indicates whether to make the full event object available
            to the handler
    Returns:
        Dict containing the result of executing the integration
    """

    state_handler = StateHandler(event, context, handler, include_event=include_event)
    result = state_handler.execute()
    # README: Below code includes state_name with result so that parameters can be passed to choice state in the same way
    # they are passed to integrations (i.e. with $.results.State_Name.parameters)
    # However, maintain current status quo so that Choice states in current playbooks don't break
    # TODO: Once Choice states in current playbooks have been updated to the new_style, update this code so result's are only nested under state_name
    result_with_state_name = {state_handler.state_name: result}
    result_with_state_name.update(result)
    event["results"] = result_with_state_name
    return event


def socless_template_string(message, context):
    """Render a templated string

    Args:
        message (str): The templated string to render
        context (dict): The template parameters

    Returns:
        str: The rendered template
    """
    resolved = resolve_template(message, context)
    return str(resolved)
