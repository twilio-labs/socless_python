from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EventTableItem:
    id: str
    investigation_id: str
    status_: str
    is_duplicate: bool
    created_at: str
    event_type: str
    playbook: Optional[str]
    details: dict
    data_types: dict
    event_meta: dict


@dataclass
class DedupTableItem:
    current_investigation_id: str
    dedup_hash: str


@dataclass
class MessageResponsesTableItem:
    message_id: str  # PK : callback id for message responses
    await_token: str  # used to start next step in step_functions
    receiver: str  # step_functions step name
    fulfilled: bool  # has await_token been used
    message: str  # message sent to user while waiting for their response
    execution_id: str
    investigation_id: str
    datetime: str


@dataclass
class PlaybookArtifacts:
    event: EventTableItem
    execution_id: str


@dataclass
class PlaybookInput:
    execution_id: str
    artifacts: PlaybookArtifacts
    results: dict
    errors: dict


@dataclass
class StateConfig:
    Name: str
    Parameters: dict


@dataclass
class SoclessContext:
    execution_id: Optional[str] = None
    artifacts: Optional[dict] = None
    results: Optional[dict] = None
    errors: Optional[dict] = field(default_factory=dict)
    task_token: Optional[str] = None
    state_name: Optional[str] = None
