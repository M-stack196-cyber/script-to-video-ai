import os

import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError


load_dotenv(dotenv_path=".env")

region = os.getenv("AWS_REGION", "us-east-1")
model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")

if not model_id:
    raise RuntimeError("BEDROCK_TEXT_MODEL_ID is not configured")

print(f"Region: {region}")
print(f"Text model: {model_id}")

client = boto3.client(
    "bedrock-runtime",
    region_name=region,
)

messages = [
    {
        "role": "user",
        "content": [
            {
                "text": (
                    "You are the scene planner for an AI video generator. "
                    "Reply with exactly one short sentence confirming that "
                    "you can convert an advertising script into video scenes."
                )
            }
        ],
    }
]

try:
    response = client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={
            "maxTokens": 100,
            "temperature": 0.2,
        },
    )

    response_text = response["output"]["message"]["content"][0]["text"]

    print("Claude invocation: SUCCESS ✅")
    print("Response:")
    print(response_text)

except ClientError as exc:
    print("Claude invocation: FAILED ❌")
    print("Error code:", exc.response["Error"].get("Code"))
    print("Message:", exc.response["Error"].get("Message"))
