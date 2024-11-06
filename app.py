import os
import aws_cdk as cdk

from mod_ehr.mod_ehr_stack import ModEhrStack

app = cdk.App()

ModEhrStack(app, "ModEhrStack",
    #env=cdk.Environment(account='123456789012', region='us-east-1'),
    )

app.synth()
