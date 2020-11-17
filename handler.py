import boto3
from datetime import datetime
import hashlib
import json
import os

def get_value_from_ssm(env_var:str) -> str:
    return ssm_client.get_parameter(Name=os.getenv(env_var, None))['Parameter']['Value']

# Service Names
SERVICE_1='example-service-1'
SERVICE_2='example-service-2'


# Boto Clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
sqs_client = boto3.client('sqs')
ssm_client = boto3.client('ssm')


INBOUND_QUEUE_URL=get_value_from_ssm(env_var='SSM_PARAMETER_INBOUND_QUEUE_URL')
S3_BUCKET=get_value_from_ssm(env_var='SSM_PARAMETER_S3_BUCKET_NAME')
SNS_TOPIC_ARN=get_value_from_ssm(env_var='SSM_PARAMETER_SNS_TOPIC_ARN')

def json_to_string(json_object):
    return str(json.dumps(json_object))

def get_md5sum_of_object(json_object: object) -> str:
    return hashlib.md5(json.dumps(json_object, sort_keys=True).encode(encoding='UTF-8')).hexdigest()

def get_timestamp() -> int:
    return int(datetime.utcnow().timestamp())

def write_to_s3(service_name: str, json_object: object):
    key = f"{service_name}/{get_timestamp()}_{get_md5sum_of_object(json_object)}"
    s3_client.put_object(
        Body=json_to_string(json_object),
        Bucket=S3_BUCKET,
        Key=key)

def send_to_inbound_queue(service_name: str, json_object: object):
    message = {
        'origin': service_name,
        'body': json_object
    }
    sqs_client.send_message(
        QueueUrl=INBOUND_QUEUE_URL,
        MessageBody=json_to_string(message)
    )

def default_transform(event):
    return event

def service_to_sync_helper(service_name: str, event: object, transform_function: object) -> None:

    print("BEGIN:  service_to_sync_helper")
    print(f"Processing event from Service: {service_name} - {event}")

    # Save the incoming data to S3
    write_to_s3(service_name=service_name, json_object=event)

    # Add your data processing here
    output_data=transform_function(event)

    # Send the input data to the inbound message queue
    send_to_inbound_queue(service_name=service_name, json_object=output_data)
    print("END:  service_to_sync_helper")

def from_service_1(event, context):

    service_to_sync_helper(
        service_name=SERVICE_1,
        event=event,
        transform_function=default_transform
    )

    return 200

def from_service_2(event, context):

    service_to_sync_helper(
        service_name=SERVICE_2,
        event=event,
        transform_function=default_transform
    )

    return 200

def sync_to_service_helper(service_name: str, event: object, transform_function: object):
    print(f"sync_to_service_helper: service_name = {service_name}")
    print(f"event = {event}")

    for record in event['Records']:
        json_object = json.loads(record['body'])
        print(f'json_object={json_object}')
        if service_name == json_object['origin']:
            print(f"{service_name} is source of this event.  Skipping")
            next
        else:
            print('TODO: Process the record')

def to_service_1(event, context):
    sync_to_service_helper(
        service_name=SERVICE_1,
        event=event,
        transform_function=default_transform
    )

def to_service_2(event, context):
    sync_to_service_helper(
        service_name=SERVICE_2,
        event=event,
        transform_function=default_transform
    )

def publish_to_sns(json_object: object) -> None:
    print(f"Sending message to SNS Topic {SNS_TOPIC_ARN}")
    response = sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Message=json_to_string(json_object)
    )
    print(f"publish response = {response}")

def delete_message_from_queue(queue_url: str, record: object) -> None:
    print(f"Deleting message {record['receiptHandle']} from queue {INBOUND_QUEUE_URL}")
    sqs_client.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=record['receiptHandle']
    )

def sync_service(event, context):
    print("BEGIN: sync_service")
    for record in event['Records']:
        print(f"record = {json.dumps(record)}")
        
        # Process the record, then publish the result to sns
        print(f'CHRIS:  Add the hook here')

        publish_to_sns(json_object=record['body'])

        delete_message_from_queue(queue_url=INBOUND_QUEUE_URL, record=record)
    print("END: sync_service")
