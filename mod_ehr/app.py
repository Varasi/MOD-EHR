#!/usr/bin/env python3
import os

import aws_cdk as cdk
import boto3
from config import Config
from healthconnect_poc.healthconnect_poc_stack import HealthconnectPocStack

config = Config(os.environ.get("ENVIRONMENT", "uat"))
# config = Config(os.environ.get("ENVIRONMENT", "development"))
# config = Config(os.environ.get("ENVIRONMENT", "production"))
app = cdk.App()

healthconnect_poc_stack = HealthconnectPocStack(
    app,
    f"{config.ENVIRONMENT.title()}HealthconnectPocStack",
    config=config,
    env=cdk.Environment(
        account=boto3.client("sts").get_caller_identity()["Account"],
        region=config.REGION,
    ),
)

app.synth()
