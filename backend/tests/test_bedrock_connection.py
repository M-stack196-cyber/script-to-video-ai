import os

import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError


load_dotenv()

region = os.getenv("AWS_REGION", "us-east-1")
api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")

if not api_key:
    raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is not configured")

print(f"Region: {region}")
print("Bedrock API key found: YES")

try:
    client = boto3.client(
        service_name="bedrock",
        region_name=region,
    )

    response = client.list_foundation_models()
    models = response.get("modelSummaries", [])

    print("Bedrock connection: SUCCESS")
    print(f"Models returned: {len(models)}")

    print("\nAvailable models:")
    for model in models:
        print(
            f"- {model.get('providerName')} | "
            f"{model.get('modelName')} | "
            f"{model.get('modelId')}"
        )

except ClientError as exc:
    print("Bedrock connection: FAILED")
    print(f"Error code: {exc.response['Error'].get('Code')}")
    print(f"Message: {exc.response['Error'].get('Message')}")
