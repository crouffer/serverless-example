import boto3
import json
import os

# Service Names
SERVICE_1='example-service-1',
SERVICE_2='example-service-2'


# Boto Clients
s3_client = boto3.client('S3')
sns_client = boto3.client('SNS')
sqs_client = boto3.client('SQS')
ssm_client = boto3.client('SSM')


INBOUND_QUEUE_URL=get_value_from_ssm(env_var='SSM_PARAMETER_S3_QUEUE_URL')
S3_BUCKET=get_value_from_ssm(env_var='SSM_PARAMETER_S3_BUCKET_NAME')
SNS_TOPIC_ARN=get_value_from_ssm(env_var='SSM_PARAMETER_SNS_TOPIC_ARN')

def json_to_string(json_object):
    return str(json.dumps(json_object))

def get_value_from_ssm(env_var:str) -> str:
    return ssm_client.get_parameter(Name=os.getenv(env_var, None))['Value']

def write_to_s3(key: str, json_object: object):
    s3_client.put_object(
        Body=json_to_string(json_object),
        Bucket=S3_BUCKET,
        Key=key)

def send_to_inbound_queue(service_name: str, json_object: object):
    sqs_client.send_message(
        QueueUrl=INBOUND_QUEUE_URL,
        MessageBody=json_to_string(json_object))
    )

def default_transform(event):
    return event

def service_to_sync_helper(service_name: str, event: object, transform_function: object) -> None:

    print("BEGIN:  service_to_sync_helper")
    print(f"Processing event from Service: {service_name} - {event}")
    key = f"{service_name}/{event['Id']}"

    # Save the incoming data to S3
    write_to_s3(key=key, json_object=event)

    # Add your data processing here
    output_data=transform_function(event)

    # Send the input data to the inbound message queue
    send_to_inbound_queue(service_name=service_name, json_object=output_data)
    print("END:  service_to_sync_helper")

def from_service_mapper_1(event, context):

    service_to_sync_helper(
        service_name=SERVICE_1,
        event=event,
        transform_function=default_transform
    )

    return 200

def from_service_mapper_2(event, context):

    service_to_sync_helper(
        service_name=SERVICE_2,
        event=event,
        transform_function=default_transform
    )

    return 200

def publish_to_sns(json_object: object) -> None:
    sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Message=json_to_string(json_object)
    )

def sync_service(event, context):
    send_to_sns(json_object=event)
