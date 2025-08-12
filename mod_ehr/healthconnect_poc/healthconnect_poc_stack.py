from aws_cdk import CfnOutput, Duration, RemovalPolicy, SecretValue, Size, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamo_db
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as event_bridge
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_transfer as transfer
from aws_cdk.aws_lambda_event_sources import S3EventSourceV2
from constructs import Construct


class HealthconnectPocStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, config, **kwargs):
        self.config = config
        super().__init__(scope, construct_id, **kwargs)
        # self.import_certificate()
        # IAM ROLES
        self.create_roles()
        self.create_lambda_invoke_policy()
        self.create_dynamodb_table()
        # VPC
        self.create_vpc()
        self.create_sftp()
        # AWS LAMDBA
        self.create_lambda_layer()
        self.create_appointments_lambda()
        self.create_settings_lambda()
        self.create_data_populator_lambda()
        self.create_dashboard_lambda()
        self.create_epic_lambda()
        self.create_patients_lambda()
        self.create_logs_lambda()
        # Secret Manager
        self.create_secrets()
        # Cognito
        self.create_cognitouser_pool()
        self.create_user_pool_domain()
        self.create_groups()
        self.create_web_user_pool_client()
        self.create_identity_pool()
        self.create_api_gateway()
        # S3 Bucket
        self.create_bucket()
        self.create_cloudfront_dist()
        self.add_bucket_policy()
        self.add_event_bridge_scheduler()
        # Output
        self.print_output()

    def create_sftp(self):
        subnet_ids = [subnet.subnet_id for subnet in self.vpc.public_subnets]
        address_allocation_ids = []
        for subnet_id in self.vpc.public_subnets:
            elastic_ip = ec2.CfnEIP(
                scope=self,
                id=f"TransferElasticIPAssociation{subnet_id.availability_zone}",
                domain="vpc",
            )
            address_allocation_ids.append(elastic_ip.attr_allocation_id)
        self.sftp_security_group = ec2.SecurityGroup(
            scope=self,
            id="SftpSecurityGroup",
            vpc=self.vpc,
            description="Security group for SFTP server",
        )
        self.sftp_security_group.add_ingress_rule(
            (
                ec2.Peer.any_ipv4()
                if self.config.ENVIRONMENT == "development"
                else ec2.Peer.ipv4(self.config.CLIENT_IP)
            ),
            ec2.Port.tcp(22),
            "SSH Access to SFTP server from IPv4 addresses",
        )
        self.sftp_bucket = s3.Bucket(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SFTPBucket",
            bucket_name=f"{self.config.ENVIRONMENT.lower()}-sftp-server-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )
        self.sftp_role = iam.Role(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SFTPRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
            ],
        )
        self.sftp_server = transfer.CfnServer(
            self,
            "SFTPServer",
            endpoint_type="VPC",
            identity_provider_type="SERVICE_MANAGED",
            logging_role=self.sftp_role.role_arn,
            endpoint_details=transfer.CfnServer.EndpointDetailsProperty(
                address_allocation_ids=address_allocation_ids,
                security_group_ids=[self.sftp_security_group.security_group_id],
                subnet_ids=subnet_ids,
                vpc_id=self.vpc.vpc_id,
            ),
        )
        self.sftp_user = transfer.CfnUser(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SFTPUser",
            server_id=self.sftp_server.attr_server_id,
            user_name=self.config.SFTP_USERNAME,
            role=self.sftp_role.role_arn,
            home_directory_type="PATH",
            home_directory=f"/{self.sftp_bucket.bucket_name}/",
            ssh_public_keys=self.config.SSH_KEYS,
        )

    @property
    def sftp_endpoint(self):
        return f"{self.sftp_server.attr_server_id}.server.transfer.{self.config.REGION}.amazonaws.com"

    def create_dynamodb_table(self):
        self.dashboard_table = dynamo_db.TableV2(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}DashboardTable",
            table_name=f"{self.config.ENVIRONMENT.lower()}_dashboard_table",
            contributor_insights=True,
            point_in_time_recovery=True,
            partition_key=dynamo_db.Attribute(
                name="id", type=dynamo_db.AttributeType.STRING
            ),
        )
        self.dashboard_table.grant_full_access(self.LambdaExecutionRole)
        self.appointment_table = dynamo_db.TableV2(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}AppointmentTable",
            table_name=f"{self.config.ENVIRONMENT.lower()}_appointment_table",
            contributor_insights=True,
            point_in_time_recovery=True,
            partition_key=dynamo_db.Attribute(
                name="id", type=dynamo_db.AttributeType.STRING
            ),
        )
        self.appointment_table.grant_full_access(self.LambdaExecutionRole)
        self.patients_table = dynamo_db.TableV2(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}PatientsTable",
            table_name=f"{self.config.ENVIRONMENT.lower()}_patients_table",
            contributor_insights=True,
            point_in_time_recovery=True,
            partition_key=dynamo_db.Attribute(
                name="patient_id", type=dynamo_db.AttributeType.STRING
            ),
        )
        self.patients_table.grant_full_access(self.LambdaExecutionRole)
        self.settings_table = dynamo_db.TableV2(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SettingsTable",
            table_name=f"{self.config.ENVIRONMENT.lower()}_settings_table",
            contributor_insights=True,
            point_in_time_recovery=True,
            partition_key=dynamo_db.Attribute(
                name="name", type=dynamo_db.AttributeType.STRING
            ),
        )
        self.settings_table.grant_full_access(self.LambdaExecutionRole)
        self.sftp_logs_table = dynamo_db.TableV2(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SFTPLogsTable",
            table_name=f"{self.config.ENVIRONMENT.lower()}_ftp_logs_table",
            contributor_insights=True,
            point_in_time_recovery=True,
            partition_key=dynamo_db.Attribute(
                name="name", type=dynamo_db.AttributeType.STRING
            ),
        )
        self.sftp_logs_table.grant_full_access(self.LambdaExecutionRole)

    def create_vpc(self):
        self.vpc = ec2.Vpc(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}VPC",
            ip_addresses=ec2.IpAddresses.cidr(self.config.CIDR),
            max_azs=3,
            nat_gateways=1,
        )

    @property
    def _elasticache_endpoint(self) -> str:
        return f"rediss://:{self.config.REDIS_AUTH_TOKEN}@{self.elasti_cache.attr_primary_end_point_address}:6379/0"

    def create_bucket(self):
        self.bucket = s3.Bucket(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}Bucket",
            bucket_name=self.config.BUCKET_NAME,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
            ),
            #for deploying the dashboard website in s3 for development/testing
            # website_index_document='index.html',
            # public_read_access=True,
            # block_public_access=s3.BlockPublicAccess(
            #     block_public_acls=False,
            #     block_public_policy=False,
            #     ignore_public_acls=False,
            #     restrict_public_buckets=False,
            # ),
        )
        s3_deployment.BucketDeployment(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}BucketDeployment",
            sources=[s3_deployment.Source.asset("dashboard_website/dist")],
            destination_bucket=self.bucket,
            cache_control=[s3_deployment.CacheControl.no_cache()],
        )

    def create_cloudfront_dist(self):
        self.s3_oai = cloudfront.OriginAccessIdentity(
            self, f"HealthConnector{self.config.ENVIRONMENT.title()}OAI"
        )
        self._s3_origin = origins.S3Origin(
            origin_access_identity=self.s3_oai, bucket=self.bucket
        )
        self.cloudfront_distribution = cloudfront.Distribution(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=self._s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            ),
            # domain_names=[self.config.DOMAIN],
            # certificate=self.certificate,
            default_root_object="index.html",
        )
        self.cloudfront_distribution.add_behavior(
            path_pattern="/api/*",
            origin=origins.RestApiOrigin(
                self.api, origin_path="", read_timeout=Duration.seconds(60)
            ),
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
        )

    @property
    def cloudfront_arn(self) -> str:
        return f"arn:aws:cloudfront::{self.config.ACCOUNT_ID}:distribution/{self.cloudfront_distribution.distribution_id}"

    def add_bucket_policy(self):
        policy_document_deny = {
            "Effect": "Deny",
            "Principal": {"AWS": self.s3_oai._arn()},
            "Action": "s3:*",
            "Resource": f"{self.bucket.bucket_arn}/data/*",
        }
        bucket_policy_deny = iam.PolicyStatement.from_json(policy_document_deny)
        self.bucket.add_to_resource_policy(bucket_policy_deny)

    def import_certificate(self):
        self.certificate = acm.Certificate.from_certificate_arn(
            self,
            id=f"HealthConnector{self.config.ENVIRONMENT.title()}Certificate",
            certificate_arn=self.config.CERTIFICATE_ARN,
        )

    def create_lambda_invoke_policy(self):
        self.lambda_invoke_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW, actions=["lambda:InvokeFunction"], resources=["*"]
        )
        self.LambdaExecutionRole.add_to_policy(self.lambda_invoke_policy)

    def create_roles(self):
        for role, role_config in self.config.ROLES.items():
            created_role = iam.Role(
                self,
                f"HealthConnector{self.config.ENVIRONMENT.title()}{role}",
                assumed_by=iam.ServicePrincipal(role_config["ASSUMED_BY"]),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy)
                    for managed_policy in role_config["POLICIES"]
                ],
                role_name=f"{self.config.ENVIRONMENT}-{role}",
            )
            setattr(self, role, created_role)

    def create_secrets(self):
        for secret_name, secret_value in self.config.SECRETS.items():
            secret_name = f"{self.config.ENVIRONMENT.lower()}-{secret_name}"
            secret = secretsmanager.Secret(
                self,
                secret_name,
                secret_name=secret_name,
                secret_string_value=SecretValue(secret_value),
            )
            secret.grant_read(self.LambdaExecutionRole)

    def create_lambda_layer(self):
        self.requirements_layer = aws_lambda.LayerVersion(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}Layer",
            code=aws_lambda.Code.from_asset("requirements.zip"),
            layer_version_name="requirements_layer",
            compatible_architectures=[aws_lambda.Architecture.X86_64],
        )
        self.base_layer = aws_lambda.LayerVersion(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}BaseLayer",
            code=aws_lambda.Code.from_asset("health_connector_base.zip"),
            layer_version_name="base_layer",
            compatible_architectures=[aws_lambda.Architecture.X86_64],
        )

    def create_dashboard_lambda(self):
        self.dashboard_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}DashboardHandler",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}DashboardHandler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/dashboard_lambda"),
            handler="health_connector.dashboard_handler",
            role=self.LambdaExecutionRole,
            environment={
                "BUCKET_NAME": "health-connector-poc",
                "PATH": "data/dashboard.json",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
            vpc=self.vpc,
            layers=[self.requirements_layer, self.base_layer],
            timeout=Duration.minutes(10),
        )

    def create_appointments_lambda(self):
        self.appointments_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}AppointmentsHandler",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}AppointmentsHandler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/appointments_lambda"),
            handler="lambda_handler.appointments_handler",
            role=self.LambdaExecutionRole,
            vpc=self.vpc,
            layers=[self.requirements_layer, self.base_layer],
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
        )

    def create_data_populator_lambda(self):
        self.data_populator_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}DataPopulator",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}DataPopulator",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/datapopulator_lambda"),
            handler="lambda_handler.data_populator",
            role=self.LambdaExecutionRole,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
            layers=[self.requirements_layer, self.base_layer],
            vpc=self.vpc,
            timeout=Duration.minutes(10),
            ephemeral_storage_size=Size.gibibytes(1),
            memory_size=1024,
        )

        self.data_populator_lambda.add_event_source(
            S3EventSourceV2(
                self.sftp_bucket,
                events=[s3.EventType.OBJECT_CREATED],
                filters=[s3.NotificationKeyFilter(suffix=".csv")],
            )
        )

    def create_epic_lambda(self):
        self.epic_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}EpicLambda",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}EpicLambda",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/epic_appointments"),
            handler="lambda_handler.epic_handler",
            role=self.LambdaExecutionRole,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
            layers=[self.requirements_layer, self.base_layer],
            vpc=self.vpc,
            timeout=Duration.minutes(10),
            ephemeral_storage_size=Size.gibibytes(1),
            memory_size=1024,
        )

    def create_patients_lambda(self):
        self.patients_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}PatientLambda",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}PatientLambda",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/patients_lambda"),
            handler="lambda_handler.patients_handler",
            role=self.LambdaExecutionRole,
            layers=[self.requirements_layer, self.base_layer],
            vpc=self.vpc,
            timeout=Duration.minutes(10),
            ephemeral_storage_size=Size.gibibytes(1),
            memory_size=1024,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
        )

    def create_settings_lambda(self):
        self.settings_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}SettingsLambda",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}SettingsLambda",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/settings_lambda"),
            handler="lambda_handler.settings_handler",
            role=self.LambdaExecutionRole,
            layers=[self.requirements_layer, self.base_layer],
            vpc=self.vpc,
            timeout=Duration.minutes(10),
            ephemeral_storage_size=Size.gibibytes(1),
            memory_size=1024,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
        )

    def create_logs_lambda(self):
        self.logs_lambda = aws_lambda.Function(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}LogsLambda",
            function_name=f"HealthConnector{self.config.ENVIRONMENT.title()}LogsLambda",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambda_functions/logs_lambda"),
            handler="lambda_handler.lambda_handler",
            role=self.LambdaExecutionRole,
            layers=[self.requirements_layer, self.base_layer],
            vpc=self.vpc,
            timeout=Duration.minutes(10),
            ephemeral_storage_size=Size.gibibytes(1),
            memory_size=1024,
            environment={
                "KMS_AVAILABLE": "True",
                "ENVIRONMENT": self.config.ENVIRONMENT.upper(),
            },
        )

    def add_event_bridge_scheduler(self):
        self.event_bridge_rule = event_bridge.Rule(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}EventBridgeRule",
            rule_name=f"HealthConnector{self.config.ENVIRONMENT.title()}EventBridgeRule",
            schedule=event_bridge.Schedule.rate(Duration.minutes(2)),
            enabled=True,
            targets=[
                targets.LambdaFunction(
                    handler=self.data_populator_lambda, max_event_age=Duration.hours(1)
                )
            ],
        )

    def create_api_gateway(self):
        self.api_stage = apigw.StageOptions(
            stage_name="api", metrics_enabled=True, data_trace_enabled=True
        )
        self.api = apigw.RestApi(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}Api",
            rest_api_name=f"health_connector_{self.config.ENVIRONMENT.lower()}",
            deploy=True,
            deploy_options=self.api_stage,
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )
        self.apigw_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}Authorizer",
            cognito_user_pools=[self.user_pool],
            identity_source=apigw.IdentitySource.header("Authorization"),
        )
        # dashboard
        self.dashboard_resource = self.api.root.add_resource("dashboard")
        self.dashboard_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.dashboard_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        # appointments
        self.appointment_resource = self.api.root.add_resource("appointments")
        self.appointment_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.appointments_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.appointment_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.appointments_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.appointment_detail_resource = self.appointment_resource.add_resource(
            "{id}"
        )
        self.appointment_detail_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.appointments_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.appointment_detail_resource.add_method(
            "PUT",
            apigw.LambdaIntegration(self.appointments_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.appointment_detail_resource.add_method(
            "DELETE",
            apigw.LambdaIntegration(self.appointments_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.epic_resource = self.api.root.add_resource("epic")
        self.epic_detail_resource = self.epic_resource.add_resource("{id}")
        self.epic_detail_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.epic_lambda, proxy=True),
            # authorizer=self.apigw_authorizer,
            # authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.patient_resource = self.api.root.add_resource("patients")
        self.patient_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.patients_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.patient_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.patients_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.patient_detail_resource = self.patient_resource.add_resource(
            "{patient_id}"
        )
        self.patient_detail_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.patients_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.patient_detail_resource.add_method(
            "PUT",
            apigw.LambdaIntegration(self.patients_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.patient_detail_resource.add_method(
            "DELETE",
            apigw.LambdaIntegration(self.patients_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.settings_resource = self.api.root.add_resource("settings")
        self.settings_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.settings_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.settings_detail_resource = self.settings_resource.add_resource("{name}")
        self.settings_detail_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.settings_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )
        self.logs_resource = self.api.root.add_resource("logs")
        self.logs_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.logs_lambda, proxy=True),
            authorizer=self.apigw_authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )

    def create_cognitouser_pool(self):
        self.user_pool = cognito.UserPool(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}UserPool",
            user_pool_name=f"health_connector_{self.config.ENVIRONMENT.lower()}_user_pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
        )

    def create_groups(self):
        self.user_pools_groups = [
            "HIRTAOperationsStaff",
            "HealthcareFacilityStaff",
            "DallasCountyHealthDepartmentHealthNavigators",
            "AppointmentsAdmin",
            "UserManagementAdmin",
        ]
        for group in self.user_pools_groups:
            cognito.CfnUserPoolGroup(
                self,
                f"HealthConnector{self.config.ENVIRONMENT.title()}{group}Group",
                group_name=group,
                user_pool_id=self.user_pool.user_pool_id,
            )

    def create_user_pool_domain(self):
        self.userpool_domain = cognito.UserPoolDomain(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}UserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=self.config.DOMAIN_PREFIX
            ),
        )

    def create_web_user_pool_client(self):
        self.web_user_pool_client = cognito.UserPoolClient(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}UserPoolWebClient",
            user_pool=self.user_pool,
            user_pool_client_name="health_connector_user_pool_web_client",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    implicit_code_grant=True, authorization_code_grant=True
                ),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=[f"https://{self.config.DOMAIN}/"],
            ),
        )

    def create_identity_pool(self):
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}IdentityPool",
            identity_pool_name=f"health_connector_{self.config.ENVIRONMENT.lower()}_identity_pool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.web_user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name,
                )
            ],
        )
        self.usermanagement_role = iam.Role(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}UserManagementRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            role_name=f"HealthConnector{self.config.ENVIRONMENT.title()}UserManagementRole",
        )
        self.usermanagement_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        self.usermanagement_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:ListUsers",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminDisableUser",
                    "cognito-idp:AdminEnableUser",
                    "cognito-idp:ListGroups",
                    "cognito-idp:AdminResetUserPassword",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:ChangePassword",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminRemoveUserFromGroup",
                ],
                resources=[self.user_pool.user_pool_arn],
            )
        )
        self.usermanagement_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cognito-identity:GetCredentialsForIdentity"],
                resources=[
                    f"arn:aws:cognito-identity:{self.region}:{self.account}:identitypool/{self.identity_pool.ref}"
                ],
            )
        )
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            f"HealthConnector{self.config.ENVIRONMENT.title()}IdentityPoolRoleAttach",
            identity_pool_id=self.identity_pool.ref,
            roles={"authenticated": self.usermanagement_role.role_arn},
            # role_mappings={}
        )

    def print_output(self):
        CfnOutput(self, "CognitoPoolID", value=self.user_pool.user_pool_id)
        CfnOutput(
            self,
            "WebUserPoolClientID",
            value=self.web_user_pool_client.user_pool_client_id,
        )
        CfnOutput(self, "IdentityPoolId", value=self.identity_pool.ref)
        CfnOutput(self, "CdnUrl", value=self.cloudfront_distribution.domain_name)
        CfnOutput(self, "SFTPEndpoint", value=self.sftp_endpoint)
