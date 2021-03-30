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
import boto3, os
from typing import Callable
from .logger import socless_log
from .utils import convert_empty_strings_to_none
from .exceptions import SoclessException, SoclessBootstrapError
from .aws_classes import LambdaContext
from .legacy_jinja import legacy_jinja_env
from jinja2.exceptions import TemplateSyntaxError, UndefinedError
from .paramresolver import ParameterResolver


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
    """DEPRECATED -- Render a templated string.
    Args:
        message (str): The templated string to render
        context (dict): The template parameters
    Returns:
        str: The rendered template
    """
    template = legacy_jinja_env.from_string(message)
    return template.render(context=context).replace("&#34;", '"').replace("&#39;", "'")
