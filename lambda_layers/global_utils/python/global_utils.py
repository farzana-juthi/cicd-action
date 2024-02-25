import decimal
import json
import os
import sys
import random
import datetime
import time
from typing import List, Any, Dict
import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from ksuid import ksuid

# ========================== boto3 clients & resources ==========================
s3_client = boto3.client("s3")
ses_client = boto3.client("ses")
dynamodb_client = boto3.client("dynamodb")
dynamodb_resource = boto3.resource("dynamodb")
s3_resource = boto3.resource("s3")
lambda_client = boto3.client("lambda")

cognito_idp_client = boto3.client("cognito-idp")
cognito_identity_client = boto3.client("cognito-identity")
kms_client = boto3.client("kms")
iam_client = boto3.client("iam")

# ========================== environment variables ==========================
region = os.environ.get("AWS_REGION", None)
stage_name = os.environ.get("STAGE_NAME", None)

primary_table_name = os.environ.get("PRIMARY_TABLE_NAME", None)
user_bucket_name = os.environ.get("ALL_BUCKET_NAME", None)
userpool_id = os.environ.get("USER_POOL_ID", None)
userpool_client_id = os.environ.get("USER_POOL_CLIENT_ID", None)


# if custom_key_arn:
#     encryption_client = aws_encryption_sdk.EncryptionSDKClient(
#         commitment_policy=CommitmentPolicy.FORBID_ENCRYPT_ALLOW_DECRYPT
#     )
#     kms_key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
#         key_ids=[
#             custom_key_arn,
#         ]
#     )
#
#
# def decrypt_code(code):
#     decrypted_plaintext, decryptor_header = encryption_client.decrypt(
#         source=base64.b64decode(code), key_provider=kms_key_provider
#     )
#     return decrypted_plaintext.decode()

# ========================== Generic response ==========================
def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        # should float be used? rounding, precision issues
        # return float(obj)
        return str(obj)
    raise TypeError


def get_response(
        status=400, error=True, code="GENERIC", message="NA", data={}, headers={}
):
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }
    final_headers = {**default_headers, **headers}
    return {
        "statusCode": status,
        "headers": final_headers,
        "body": json.dumps(
            {"error": error, "code": code, "message": message, "data": data},
            default=str,
        ),  # default=decimal_default),
    }

def put_db_item(item, table_name=primary_table_name):
    table = dynamodb_resource.Table(table_name)
    db_response = table.put_item(Item=item)
    return db_response

def get_db_item(pk_sk_key, table_name=primary_table_name):
    table = dynamodb_resource.Table(table_name)
    db_response = table.get_item(
        Key=pk_sk_key
    )
    return db_response.get("Item")

def email_phone_exists(parsed_body) -> bool:
    response = dynamodb_client.get_item(
        TableName=primary_table_name,
        Key={
            "PK": {"S": "EXISTING_EMAIL"},
            "SK": {"S": f"{parsed_body.emailOrPhone}"},
        },
    )

    return "Item" in response

def batch_write_items(items):
    transaction_items = [
        {
            item_action["action"]: {
                "TableName": primary_table_name,
                item_action["identifier"]: convert_to_dynamodb(item_action["item"]),
            }
        } for item_action in items
    ]

    response = dynamodb_client.transact_write_items(
        TransactItems=transaction_items
    )
    return response

def batch_read_items(item_keys):
    get_items = [
        {
            "Get": {
                "Key": convert_to_dynamodb(key),
                "TableName": primary_table_name
            }
        } for key in item_keys
    ]
    response = dynamodb_client.transact_get_items(
        TransactItems=get_items
    )

    items = []
    if "Responses" in response:
        for item in response["Responses"]:
            items.append(convert_to_json(item.get("Item")))

    return items

def update_cognito_profile(cognito_user, identity_id):
    if "profile" not in cognito_user or cognito_user.get("profile", "") == "":
        print("profile not available, setting...")
        response = cognito_idp_client.admin_update_user_attributes(
            UserPoolId=userpool_id,
            Username=cognito_user.get("username"),
            UserAttributes=[
                {"Name": "profile", "Value": identity_id},
            ],
        )
        print("update profile response: ", response)
        cognito_user["profile"] = identity_id

    # update_cognito_user_profile_db(cognito_user)
    return cognito_user.get("profile")

def convert_to_json(dynamodb_item):
    deserializer = TypeDeserializer()
    return {
        k: deserializer.deserialize(v)
        for k, v in dynamodb_item.items()
    }

def convert_to_dynamodb(json_item):
    serializer = TypeSerializer()
    return {
        k: serializer.serialize(v)
        for k, v in json_item.items()
    }

# ========================== auth utils ==========================

# ========================== Exceptions ==========================

class CustomValidationError(Exception):
    pass

class DuplicateUserError(Exception):
    pass

class DuplicateCategoryError(Exception):
    pass

class InvalidUserError(Exception):
    pass

class CategoryNotFoundError(Exception):
    pass



