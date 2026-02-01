from intercomclient.aws import DynamoDBClient


class TestDynamoDBClient:
    def test_auth_check(self):
        client = DynamoDBClient(boto3_client=None)
        assert client.auth_check() is not None
