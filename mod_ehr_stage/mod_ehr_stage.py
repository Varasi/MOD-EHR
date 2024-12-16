from aws_cdk import (
    Stage,
)
from constructs import Construct
from mod_ehr.mod_ehr_stack import ModEhrStack


class ModEhrStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, env_name: str , **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        modehrstack = ModEhrStack(self,'ModEhrStack', env_name=env_name)