from tests.conftest import *  # imports testing boilerplate
from moto import mock_ssm
from socless.ssm import fetch_from_ssm


@mock_ssm
def test_fetch_parameter():
    test_secret_path = "/socless/test/mock_secret"
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
    ssm_client.put_parameter(
        Name=test_secret_path,
        Description="A test parameter",
        Value="test_parameter_for_socless",
        Type="SecureString",
    )

    param = fetch_from_ssm(test_secret_path)
    assert param == "test_parameter_for_socless"