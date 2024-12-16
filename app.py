import os
import aws_cdk as cdk

from mod_ehr_pipeline.mod_ehr_pipeline import ModEhrPipeline

app = cdk.App()
ModEhrPipeline(app,"ModEhrPipeline",
        env=cdk.Environment(account='443370714691', region='ap-south-1'),
        pipeline_stage_name="dev",
        env_name="dev"
    )
# ModEhrPipeline(app,"ModEhrPipeline",
#         env=cdk.Environment(account='443370714691', region='ap-south-1'),
#         pipeline_stage_name="test",
#         env_name="test"
#     )
# ModEhrPipeline(app,"ModEhrPipeline",
#         env=cdk.Environment(account='443370714691', region='ap-south-1'),
#         pipeline_stage_name="prod",
#         env_name="prod"
#     )



app.synth()
