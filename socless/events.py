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
from .logger import socless_log
import os, boto3, simplejson as json, hashlib
from datetime import datetime
from .utils import gen_id, gen_datetimenow


EVENTS_TABLE = os.environ.get('SOCLESS_EVENTS_TABLE','')
DEDUP_TABLE = os.environ.get('SOCLESS_DEDUP_TABLE','')
event_table = boto3.resource('dynamodb').Table(EVENTS_TABLE)
dedup_table = boto3.resource('dynamodb').Table(DEDUP_TABLE)


class EventCreator():
    """Handles the creation of an Event
    """

    def __init__(self, event_info):
        self.event_info = event_info

        self.event_type = event_info.get('event_type')
        if not self.event_type:
            raise Exception("Error: event_type must be supplied")

        self.created_at = event_info.get('created_at')
        if not self.created_at:
            self.created_at = gen_datetimenow()
        else:
            try:
                datetime.strptime(self.created_at,'%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                raise Exception("Error: Supplied 'created_at' field is not ISO8601 millisecond-precision string, shifted to UTC")

        self.details = event_info.get('details',{})
        if not isinstance(self.details,dict):
            raise Exception("Error: Supplied 'details' is not a dictionary")

        self.data_types = event_info.get('data_types',{})
        if not isinstance(self.data_types,dict):
            raise Exception("Error: Supplied 'data_types' is not a dictionary")

        self.event_meta = event_info.get('event_meta',{})
        if not isinstance(self.event_meta,dict):
            raise Exception("Error: Supplied 'event_meta' is not a dictionary")

        self.playbook = event_info.get('playbook','')
        if not isinstance(self.playbook,str):
            raise Exception("Error: Supplied Playbook is not a string")

        self.dedup_keys = event_info.get('dedup_keys',[])
        if not isinstance(self.dedup_keys,list):
            raise Exception("Error: Supplied 'dedup_keys' field is not a list")

        self._id = gen_id()

        # Initialize with the assumption that the event is a new investigation
        self.investigation_id = self._id
        self.status_ = 'open'
        self.is_duplicate = False


    @property
    def dedup_hash(self):
        """Property that returns the deduplication hash.

        Using the keys in the 'dedup_keys' list, build a single string that 
        includes each associated value in the 'details' field for this event.

        This string will be the same for every event that is triggered
        with the exact event details and dedup_keys.

        Returns:
            A hashed string for deduplicating an event triggered twice.
        """
        sorted_dedup_vals = sorted([self.details[key].lower() for key in self.dedup_keys])
        dedup_signature = self.event_type.lower() + ''.join(sorted_dedup_vals)
        dedup_hash = hashlib.md5(dedup_signature.encode('utf-8')).hexdigest()
        return dedup_hash

    def deduplicate(self):
        """Deduplicates an event, setting the is_duplicate and investigation_id attributes
        Current deduplication algorithm is:
            hexdigest of md5( event_type + sorted(dedup_values) )
        """

        # Correct the assumption that the event is a new investigation if there is an open event currently mapped to the dedup hash
        self._cached_dedup_hash = self.dedup_hash
        dedup_mapping = dedup_table.get_item(Key={'dedup_hash': self._cached_dedup_hash}).get('Item')

        if dedup_mapping:
            current_investigation_id = dedup_mapping.get('current_investigation_id')
            if not current_investigation_id:
                socless_log.warn('unmapped dedup_hash detected in dedup table', {'dedup_hash': self._cached_dedup_hash})
                return
            current_investigation = event_table.get_item(Key={ 'id': current_investigation_id}).get('Item')
            if current_investigation and current_investigation['status_'] != 'closed':
                self.investigation_id = current_investigation['investigation_id']
                self.status_ = 'closed'
                self.is_duplicate = True

        return

    def create(self):
        """Create an event.

        Check if event is duplicate, if not then add it to the dedup table.
        """
        # Deduplicate the event if there are dedup keys set
        if self.dedup_keys:
            self.deduplicate()
            # Create/Update dedup_hash mapping if the event is an original
            if not self.is_duplicate:
                new_dedup_mapping = {
                    'dedup_hash': self._cached_dedup_hash,
                    'current_investigation_id': self.investigation_id
                }
                dedup_table.put_item(Item=new_dedup_mapping)
            else:
                pass
        else:
            pass

        # Create event entry and save it
        event = {
            'id': self._id,
            'created_at': self.created_at,
            'data_types': self.data_types,
            'details': self.details,
            'event_type': self.event_type,
            'event_meta': self.event_meta,
            'investigation_id': self.investigation_id,
            'status_': self.status_,
            'is_duplicate': self.is_duplicate
        }
        if self.playbook:
            event['playbook'] = self.playbook 
        event_table.put_item(Item=event)
        return event


class EventBatch():
    """Creates a batch of events and executes the appropriate playbook
    """

    def __init__(self, event_batch, lambda_context):
        """Initialize the EventBatch with data that is common to all events

        Args:
            event_batch (dict): A batch of events
            lambda_context (obj): Lambda context object
            dedup (bool): Toggle to enable/disable deduplication of events
        """
        # Initialize properties
        self.event_type = event_batch.get('event_type')

        self.created_at = event_batch.get('created_at')

        self.details = event_batch.get('details', [{}])
        for each in self.details:
            if not isinstance(each,dict):
                raise Exception("Error: Details must be a list of dictionaries")

        self.data_types = event_batch.get('data_types',{})

        self.event_meta = event_batch.get('event_meta',{})

        self.playbook = event_batch.get('playbook','')
        if not isinstance(self.playbook,str):
            raise Exception("Error: Supplied Playbook is not a string")

        self.dedup_keys = event_batch.get('dedup_keys',[])
        if not isinstance(self.dedup_keys,list):
            raise Exception("Error: Supplied 'dedup_keys' field is not a list")

        self.lambda_context = lambda_context

    def create_events(self):
        """
        Create events
        """
        execution_statuses = []

        for detection in self.details:
            event_info = {}
            event_info['created_at'] = self.created_at
            event_info['data_types'] = self.data_types
            event_info['details'] = detection
            event_info['event_type'] = self.event_type
            event_info['event_meta'] = self.event_meta
            event_info['dedup_keys'] = self.dedup_keys
            if self.playbook:
                event_info['playbook'] = self.playbook

            event = EventCreator(event_info).create()
            # Trigger execution of a playbook if playbook was supplied
            if self.playbook:
                execution_statuses.append(self.execute_playbook(event,event['investigation_id']))
        
        #! FIX: Will always return true, message is a list of individual
        #! playbook responses that may be true or false (error) responses
        return { "status":True, "message": execution_statuses }

    def execute_playbook(self,entry,investigation_id=''):
        """Execute a playbook for a SOCless event.
        Args:
            entry (dict): The event details
            investigation_id (str): The investigation_id to use
            playbook (str): The name of the playbook to execute
        Returns:
            dict: The execution_id, investigation_id and a status indicating if the playbook
                execution request was successful
        """
        meta = {'investigation_id':investigation_id, 'playbook': self.playbook}
        if not investigation_id:
            investigation_id = gen_id()
        RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
        playbook_input = {'artifacts':{},'results':{},'errors':{}}
        playbook_arn = "arn:aws:states:{region}:{accountid}:stateMachine:{stateMachineName}".format(
            region=os.environ['AWS_REGION'],
            accountid=self.lambda_context.invoked_function_arn.split(':')[4],
            stateMachineName=self.playbook
        )
        execution_id = gen_id()
        playbook_input['artifacts']['event'] = entry
        playbook_input['artifacts']['execution_id'] = execution_id
        results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)
        save_result_resp = results_table.put_item(Item={
            "execution_id": execution_id,
            "datetime": gen_datetimenow(),
            "investigation_id": investigation_id,
            "results": playbook_input
        })
        stepfunctions = boto3.client('stepfunctions')
        try:
            step_resp = stepfunctions.start_execution(
                name=execution_id,
                stateMachineArn=playbook_arn,
                input=json.dumps({
                    "execution_id": execution_id,
                    "artifacts": playbook_input['artifacts']
                }))
            socless_log.info('Playbook execution started',dict(meta, **{'statemachinearn': playbook_arn, 'execution_id': execution_id}))
        except Exception as e:
            socless_log.error('Failed to start statemachine execution',dict(meta, **{'statemachinearn': playbook_arn, 'execution_id': execution_id, 'error': f"{e}"}))
            return {"status": False, "message": f"Error: {e}"}
        return {"status": True, "message": {"execution_id": execution_id,"investigation_id": investigation_id}}

def create_events(event_details,context):
    """Use the EventBatch class to create events
    Args:
        event_details (dict): The details of the events
        context (obj): The Lambda context object
    Returns:
        dict containing the execution ids of the created events
    """
    event_batch = EventBatch(event_details,context)
    return event_batch.create_events()
