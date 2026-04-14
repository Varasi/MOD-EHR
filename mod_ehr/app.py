#!/usr/bin/env python3
import os

import aws_cdk as cdk
import boto3
from config import Config
from healthconnect_poc.healthconnect_poc_stack import HealthconnectPocStack

# config = Config(os.environ.get("ENVIRONMENT", "uat"))
# config = Config(os.environ.get("ENVIRONMENT", "development"))
config = Config(os.environ.get("ENVIRONMENT", "production"))
app = cdk.App()

# Append a version suffix for parallel deployments (e.g., "v2")
version_suffix = os.environ.get("STACK_VERSION", "v2")
stack_name = f"{config.ENVIRONMENT.title()}EHRMultitenantStack-{version_suffix}"

healthconnect_poc_stack = HealthconnectPocStack(
    app,
    stack_name,
    config=config,
    version_suffix=version_suffix,
    env=cdk.Environment(
        account=boto3.client("sts").get_caller_identity()["Account"],
        region=config.REGION,
    ),
)

app.synth()
