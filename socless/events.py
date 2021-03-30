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
Classes and modules for creating and managing events
"""
from socless.models import EventTableItem, PlaybookArtifacts, PlaybookInput
from socless.exceptions import SoclessEventsError, SoclessNotFoundError
from typing import List, Optional, Union
from .logger import socless_log
import os, boto3, simplejson as json, hashlib
from dataclasses import dataclass, asdict
from .utils import gen_id, gen_datetimenow, validate_iso_datetime


EVENTS_TABLE = os.environ.get("SOCLESS_EVENTS_TABLE", "")
DEDUP_TABLE = os.environ.get("SOCLESS_DEDUP_TABLE", "")
event_table = boto3.resource("dynamodb").Table(EVENTS_TABLE)
dedup_table = boto3.resource("dynamodb").Table(DEDUP_TABLE)


def get_playbook_arn(playbook_name, lambda_context):
    return "arn:aws:states:{region}:{accountid}:stateMachine:{stateMachineName}".format(
        region=os.environ["AWS_REGION"],
        accountid=lambda_context.invoked_function_arn.split(":")[4],
        stateMachineName=playbook_name,
    )


def setup_results_table_for_playbook_execution(
    execution_id: str, investigation_id: str, playbook_input_as_dict: dict
):
    results_table = boto3.resource("dynamodb").Table(
        os.environ.get("SOCLESS_RESULTS_TABLE")
    )
    results_table.put_item(
        Item={
            "execution_id": execution_id,
            "datetime": gen_datetimenow(),
            "investigation_id": investigation_id,
            "results": playbook_input_as_dict,
        }
    )


def get_investigation_id_from_dedup_table(dedup_hash: str) -> str:
    """Check dedup_table for an investigation_id using the dedup_hash.
    Raises:
        SoclessNotFoundError if dedup_table item is malformed or doesnt exist.
    Logs a warning if a dedup_hash is found but doesn't contain any investigation_id.
    """
    key = {"dedup_hash": dedup_hash}
    dedup_mapping = dedup_table.get_item(Key=key).get("Item")

    if dedup_mapping:
        try:
            return dedup_mapping["current_investigation_id"]
        except KeyError:
            socless_log.warn(
                "Item without 'current_investigation_id' found in dedup table",
                key,
            )
            raise SoclessNotFoundError("No investigation_id found in dedup_mapping")
    else:
        raise SoclessNotFoundError("dedup_hash not found in dedup_table")


def get_investigation_id_from_existing_unclosed_event(
    current_investigation_id,
) -> str:
    current_investigation = event_table.get_item(
        Key={"id": current_investigation_id}
    ).get("Item")
    if current_investigation and current_investigation["status_"] != "closed":
        return current_investigation["investigation_id"]
    else:
        raise SoclessNotFoundError("No open investigation found")


@dataclass
class StartExecutionReport:
    investigation_id: str
    execution_id: str
    playbook: str
    statemachinearn: str
    error: Optional[str]


@dataclass
class InitialEvent:
    created_at: str
    event_type: str
    playbook: Optional[str]
    details: dict
    data_types: dict
    event_meta: dict
    dedup_keys: list

    def __post_init__(self):
        """TypeCheck the event attributes"""
        validate_iso_datetime(self.created_at)
        if not isinstance(self.details, dict):
            raise TypeError("Error: Supplied 'details' is not a dictionary")
        if not isinstance(self.data_types, dict):
            raise TypeError("Error: Supplied 'data_types' is not a dictionary")
        if not isinstance(self.event_meta, dict):
            raise TypeError("Error: Supplied 'event_meta' is not a dictionary")
        if not isinstance(self.event_type, str):
            raise TypeError("Error: Supplied 'event_type' is not a string")
        if not isinstance(self.playbook, str):
            raise TypeError("Error: Supplied Playbook is not a string")
        if not isinstance(self.dedup_keys, list):
            raise TypeError("Error: Supplied 'dedup_keys' field is not a list")

    @property
    def dedup_hash(self) -> str:
        """Property that returns the deduplication hash.

        Using the keys in the 'dedup_keys' list, build a single string that
        includes each associated value in the 'details' field for this event.

        This string will be the same for every event that is triggered
        with the exact event details and dedup_keys.

        Returns:
            A hashed string for deduplicating an event triggered twice.
        """
        sorted_dedup_vals = sorted(
            [self.details[key].lower() for key in self.dedup_keys]
        )
        dedup_signature = self.event_type.lower() + "".join(sorted_dedup_vals)
        dedup_hash = hashlib.md5(dedup_signature.encode("utf-8")).hexdigest()
        return dedup_hash


class EventMetadata:
    def __init__(self):
        new_id = gen_id()
        self._id = new_id
        self.investigation_id = new_id
        self.execution_id = gen_id()
        self.status_ = "open"
        self.is_duplicate = False

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "investigation_id": self.investigation_id,
            "execution_id": self.execution_id,
            "status_": self.status_,
            "is_duplicate": self.is_duplicate,
        }


class CompleteEvent:
    """A container for an event, its metadata, and methods to interact with the event.
    Attributes:
        `event` : InitialEvent class, contains specific event details
        `metadata`: EventMetadata class, contains investigation_id, dedup status, etc.
    """

    def __init__(
        self, initial_event: Union[InitialEvent, None] = None, **initial_event_args
    ) -> None:
        """Methods:
        `to_EventTableItem`: returns formatted event data for input to events_table
        `deduplicate_and_update_dedup_table`: check dedup_table & event_table to see if this event exists, mutate self.metadata and update dedup_table accordingly
        `put_in_events_table`: put event in events_table (does NOT deuplicate automatically)
        `start_playbook` :
        """
        if not initial_event:
            self.event = InitialEvent(**initial_event_args)
        else:
            self.event: InitialEvent = initial_event
        # init with assumption of not-duplicate EventMetadata
        self.metadata = EventMetadata()

    def to_dict(self):
        return {"event": self.event.__dict__, "metadata": self.metadata.to_dict()}

    @property
    def to_EventTableItem(self) -> EventTableItem:
        return EventTableItem(
            id=self.metadata._id,
            investigation_id=self.metadata.investigation_id,
            status_=self.metadata.status_,
            is_duplicate=self.metadata.is_duplicate,
            created_at=self.event.created_at,
            data_types=self.event.data_types,
            details=self.event.details,
            event_type=self.event.event_type,
            event_meta=self.event.event_meta,
            playbook=self.event.playbook,
        )

    @property
    def to_PlaybookInput(self) -> PlaybookInput:
        return PlaybookInput(
            execution_id=self.metadata.execution_id,
            artifacts=PlaybookArtifacts(
                execution_id=self.metadata.execution_id, event=self.to_EventTableItem
            ),
            results={},
            errors={},
        )

    def _deduplicate(self):
        """Use InitialEvent and DynamoDB to mutate whether EventMetadata is duplicate or not.

        This is not built into any `init` functions because some events may explicitly
        opt out of deduplication depending on where they are created from
        Notes:
            Depends on dedup_table & event_table.
        """
        if not self.event.dedup_keys:
            return
        try:
            # check if duplicate
            temp_investigation_id = get_investigation_id_from_dedup_table(
                self.event.dedup_hash
            )
            self.metadata.investigation_id = (
                get_investigation_id_from_existing_unclosed_event(temp_investigation_id)
            )
            self.metadata.status_ = "closed"
            self.metadata.is_duplicate = True
        except SoclessNotFoundError:
            # event is not duplicate
            pass

    def deduplicate_and_update_dedup_table(self):
        """Check if event is duplicate, if not then add it to the dedup table.
        Notes:
            Depends on dedup_table & event_table.
        """
        # Deduplicate the event if there are dedup keys set
        if self.event.dedup_keys:
            self._deduplicate()
            # Create/Update dedup_hash mapping if the event is an original
            if not self.metadata.is_duplicate:
                new_dedup_mapping = {
                    "dedup_hash": self.event.dedup_hash,
                    "current_investigation_id": self.metadata.investigation_id,
                }
                dedup_table.put_item(Item=new_dedup_mapping)

    def put_in_events_table(self):
        """Combine event and metadata, then input into socless event_table.
        NOTE: does not check if event is duplicate
        """
        event_table_item = self.to_EventTableItem
        event_table.put_item(Item=event_table_item.__dict__)

    def start_playbook(
        self, playbook_arn, stepfunctions_client
    ) -> StartExecutionReport:
        """Create playbook input, save data to results_table & attempt to start execution
        NOTE: depends on results_table
        """
        playbook_input = self.to_PlaybookInput
        playbook_input_as_dict = asdict(playbook_input)

        setup_results_table_for_playbook_execution(
            self.metadata.execution_id,
            self.metadata.investigation_id,
            playbook_input_as_dict,
        )

        report = StartExecutionReport(
            investigation_id=self.metadata.investigation_id,
            playbook=str(self.event.playbook),
            statemachinearn=playbook_arn,
            execution_id=self.metadata.execution_id,
            error="",
        )
        try:
            stepfunctions_client.start_execution(
                name=self.metadata.execution_id,
                stateMachineArn=playbook_arn,
                input=json.dumps(playbook_input_as_dict),
            )
            socless_log.info("Playbook execution started", report.__dict__)
        except Exception as e:
            report.error = str(e)
            socless_log.error(
                "Failed to start statemachine execution",
                report.__dict__,
            )
        return report


def create_events(event_details: dict, context):
    """Deduplicate and start playbooks from an intial event or list of event details."""
    # setup event_details formats
    event_details.setdefault("created_at", gen_datetimenow())
    # convert "details" to a list of "details" objects (for backwards compatibility)
    if not isinstance(event_details["details"], list):
        event_details["details"] = [event_details["details"]]

    # format events from list or single details dict
    complete_events_list: List[CompleteEvent] = []
    for details_dict in event_details["details"]:
        complete_events_list.append(
            CompleteEvent(
                **{
                    "details": details_dict,
                    "created_at": event_details["created_at"],
                    "event_type": event_details["event_type"],
                    "playbook": event_details["playbook"],
                    "data_types": event_details.get("data_types", {}),
                    "event_meta": event_details.get("event_meta", {}),
                    "dedup_keys": event_details.get("dedup_keys", []),
                }
            )
        )

    stepfunctions_client = boto3.client("stepfunctions")
    playbook_arn = get_playbook_arn(event_details["playbook"], context)
    execution_reports: List[StartExecutionReport] = []
    for complete_event in complete_events_list:
        complete_event.deduplicate_and_update_dedup_table()
        complete_event.put_in_events_table()
        exec_report = complete_event.start_playbook(playbook_arn, stepfunctions_client)
        execution_reports.append(exec_report)

    # check for failures
    failures = [report for report in execution_reports if report.error]
    if len(failures) > 0:
        raise SoclessEventsError(
            f"{len(failures)} of {len(execution_reports)} events failed to start playbooks.\n Failure Reports: \n {failures}"
        )

    return {
        "events": [event.to_dict() for event in complete_events_list],
        "execution_reports": [report.__dict__ for report in execution_reports],
    }


def setup_socless_global_state_from_running_step_functions_execution(
    execution_id, playbook_name, playbook_event_details
):
    """Convert a regular StepFunctions execution to a SOCless compatible execution.

    The execution_id & playbook_name can be accessed via the StepFunctions context object using the
        "variable.$" : "$$.variable" syntax inside the StateMachine definition.

    playbook_event_details will take the entire json object passed to the state machine input and use it as the
        event details (usually accessed via {{context.artifacts.event.details.<var_name>}} socless syntax)

    NOTE: deduplication is ignored for these executions.
    """
    event = CompleteEvent(
        InitialEvent(
            details=playbook_event_details,
            created_at=gen_datetimenow(),
            event_type=playbook_name,
            playbook=playbook_name,
            data_types={},
            event_meta={},
            dedup_keys=[],
        )
    )
    event.metadata.execution_id = execution_id

    event.put_in_events_table()
    playbook_input_as_dict = asdict(event.to_PlaybookInput)

    return playbook_input_as_dict
