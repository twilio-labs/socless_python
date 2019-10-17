from moto import mock_s3, mock_dynamodb2
import boto3, pytest, os

@pytest.fixture(scope='function')
def aws_credentials():
   """Mocked AWS Credentials for moto."""
   os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
   os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
   os.environ['AWS_SECURITY_TOKEN'] = 'testing'
   os.environ['AWS_SESSION_TOKEN'] = 'testing'

@pytest.fixture(scope='function')
def s3(aws_credentials):
   with mock_s3():
      yield boto3.client('s3')

@pytest.fixture(scope='function')
def dynamodb(aws_credentials):
   with mock_dynamodb2():
      yield boto3.client('dynamodb')

def setup_vault():
   bucket_name = os.environ['SOCLESS_VAULT']
   client = boto3.client('s3')
   client.create_bucket(Bucket=bucket_name)
   client.put_object(Bucket=bucket_name, Key="socless_vault_tests.txt", Body="this came from the vault")
   client.put_object(Bucket=bucket_name, Key="socless_vault_tests.json", Body='{"hello":"world"}')
   return client

def setup_tables():
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