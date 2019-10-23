from moto import mock_s3, mock_dynamodb2
import boto3, pytest, os


@pytest.fixture(scope='function')
def aws_credentials():
   """Mocked AWS Credentials for moto.
   
   Instantiate fake AWS Credentials that will be used to start up moto/boto3
   for tests. This fixture will be called by other fixtures to initialize
   their respective boto3 clients (s3, dynamodb, ssm, etc..) which are used for
   each each testing function that needs to interact with AWS.
   """
   os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
   os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
   os.environ['AWS_SECURITY_TOKEN'] = 'testing'
   os.environ['AWS_SESSION_TOKEN'] = 'testing'

@pytest.fixture(scope='function')
def s3(aws_credentials):
   """A fixture for any test that will use s3.
   This uses moto's mock_s3 decorator and our fake AWS creds to create 
   a mock boto s3 client within the local mock AWS test environment. 
   
   This fixture will need to be used by passed in as a parameter to any
   test that uses s3. Also add the mock_s3 decorator to the 
   test definition to doubly ensure moto is used.
   """
   with mock_s3():
      yield boto3.client('s3')

@pytest.fixture(scope='function')
def dynamodb(aws_credentials):
   """A fixture for any test that will use dynamoDB.
   This uses moto's mock_dynamoDB decorator and our fake AWS creds to create 
   a mock boto dynamoDB client within the local mock AWS test environment. 

   This fixture will need to be passed in as a parameter to any
   test that uses dynamoDB. Also add the mock_dynamodb2 decorator to the 
   test definition to doubly ensure moto is used.
   """
   with mock_dynamodb2():
      yield boto3.client('dynamodb')

def setup_vault():
   """A helper function to instantiate the SOCless vault bucket with test files.

      To use this, pass the s3 fixture above as a parameter to the test 
   definition, then call this function inside the test to setup the SOCless bucket.

   Returns:
      boto3 s3 client
   """
   bucket_name = os.environ['SOCLESS_VAULT']
   client = boto3.client('s3')
   client.create_bucket(Bucket=bucket_name)
   client.put_object(Bucket=bucket_name, Key="socless_vault_tests.txt", Body="this came from the vault")
   client.put_object(Bucket=bucket_name, Key="socless_vault_tests.json", Body='{"hello":"world"}')
   return client

def setup_tables():
   """A helper function to instantiate SOCless dynamoDB tables.
   
   To use this, pass the dynamodb fixture above as a parameter to the test 
   definition, then call this function inside the test to setup SOCless tables.

   Returns:
      boto3 dynamodb client in case you need to put_object for tests.
   """
   client = boto3.client('dynamodb')

   events_table_name = os.environ['SOCLESS_EVENTS_TABLE']
   events_table = client.create_table(
      TableName=events_table_name,
      KeySchema=[{'AttributeName': 'id','KeyType': 'HASH'}],
      AttributeDefinitions=[])
   
   results_table_name = os.environ['SOCLESS_RESULTS_TABLE']
   results_table = client.create_table(
      TableName=results_table_name,
      KeySchema=[{'AttributeName': 'execution_id','KeyType': 'HASH'}],
      AttributeDefinitions=[])
   
   dedup_table_name = os.environ['SOCLESS_DEDUP_TABLE']
   dedup_table = client.create_table(
      TableName=dedup_table_name,
      KeySchema=[{'AttributeName': 'dedup_hash','KeyType': 'HASH'}],
      AttributeDefinitions=[])

   return client