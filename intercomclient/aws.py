import boto3
import logging

LOG = logging.getLogger(__name__)


class DynamoDBClient:
    def __init__(self, boto3_client):
        self.client = boto3.client("dynamodb")

    def auth_check(self) -> list[str]:
        paginator = self.client.get_paginator("list_tables")
        page_iterator = paginator.paginate(Limit=10)
        table_names = []

        for page in page_iterator:
            for table_name in page.get("TableNames", []):
                print(f"- {table_name}")
                table_names.append(table_name)

        if not table_names:
            LOG.warning("You don't have any DynamoDB tables in your account.")

        return table_names

    def upload_events(self) -> None:
        pass
