from aws_cdk import(
    Stack,
    Environment,
)
from constructs import Construct
from aws_cdk.pipelines import CodePipeline, CodePipelineSource, ShellStep
from mod_ehr_stage.mod_ehr_stage import ModEhrStage

class ModEhrPipeline(Stack):
    def __init__(self, scope: Construct, construct_id: str, pipeline_stage_name: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        pipeline = CodePipeline(
            self,
            "ModEhrPipeline",
            pipeline_name="ModEhrPipeline",
            synth=ShellStep("Synth",
                            input=CodePipelineSource.connection(repo_string="Varasi/MOD-EHR",branch="subdev2",connection_arn="arn:aws:codeconnections:ap-south-1:443370714691:connection/04cac864-65e8-4c03-8a97-bfeadb938484"),
                            commands=["npm install -g aws-cdk",
                                "python -m pip install -r requirements.txt",
                                "cdk synth",
                                #   "mkdir -p common/python/lib/python3.11/site-packages",
                                #   "ls",
                                #   "pip install -r lambda/requirements.txt --target common/python/lib/python3.11/site-packages",
                                #   "cd common",
                                #   "pwd",
                                #   "zip python.zip python",
                                #   "cd ..",
                                #   "cd common/python/lib/python3.11/site-packages",
                                #   "ls",
                                #   "pwd",
                                #   "cd ../../../../.."
                                ]
                            )
        )
    
        pipeline.add_stage(ModEhrStage(self,pipeline_stage_name, env_name=env_name))