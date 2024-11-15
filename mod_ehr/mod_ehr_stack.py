from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb_,
    aws_lambda as lambda_,
    aws_apigateway as apigw_,
    aws_cognito as cognito_,
    aws_iam as iam
)

from constructs import Construct

class ModEhrStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        table_name1 = 'development_appointment_table'
        Appointment = dynamodb_.TableV2(
            self,
            'MODEHRAppoitmentTable',
            table_name=table_name1,
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(), 
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='id',
                type=dynamodb_.AttributeType.STRING
            )
        )
        table_name2 = 'development_dashboard_table'
        Dashboard = dynamodb_.TableV2(
            self,
            'MODEHRDashboardTable',
            table_name=table_name2,
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(), 
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='id',
                type=dynamodb_.AttributeType.STRING
            )
        )
        table_name3 = 'development_patients_table'
        Patients = dynamodb_.TableV2(
            self,
            'MODEHRPatientsTable',
            table_name=table_name3,
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(), 
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='via_rider_id',
                type=dynamodb_.AttributeType.STRING
            )
        )
        table_name4 = 'development_settings_table'
        Settings = dynamodb_.TableV2(
            self,
            'MODEHRSettingsTable',
            table_name=table_name4,
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(), 
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='name',
                type=dynamodb_.AttributeType.STRING
            )
        )

        my_layer = lambda_.LayerVersion(
            self, 
            "MODEHRLayer",
            code=lambda_.Code.from_asset("common"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="A layer with custom dependencies"
        )

        

        dashboard_handler = lambda_.Function(
            self,
            'MODEHRDashboardHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/dashboard_lambda"),
            handler='health_connector.dashboard_handler',
            layers=[my_layer]
        )
        datapopulator_handler = lambda_.Function(
            self,
            'MODEHRDataPopulatorHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/datapopulator_lambda"),
            handler='lambda_handler.data_populator',
            layers=[my_layer]
        )
        appoitments_handler = lambda_.Function(
            self,
            'MODEHRAppointmentsHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/appointments_lambda"),
            handler='lambda_handler.appointments_handler',
            layers=[my_layer]
        )
        epic_handler = lambda_.Function(
            self,
            'MODEHREpicHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/epic_appointments"),
            handler='lambda_handler.epic_handler',
            layers=[my_layer]
        )
        patients_handler = lambda_.Function(
            self,
            'MODEHRPatientsHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/patients_lambda"),
            handler='lambda_handler.patients_handler',
            layers=[my_layer]
        )
        settings_handler = lambda_.Function(
            self,
            'MODEHRSettingsHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda_functions/settings_lambda"),
            handler='lambda_handler.settings_handler',
            layers=[my_layer]
        )
        Dashboard.grant_read_data(dashboard_handler)
        Appointment.grant_read_write_data(appoitments_handler)
        Settings.grant_read_write_data(settings_handler)
        Patients.grant_read_write_data(patients_handler)


        user_pool = cognito_.UserPool(
            self,
            'MODEHRUserPool',
            account_recovery=cognito_.AccountRecovery.EMAIL_ONLY,
            auto_verify=cognito_.AutoVerifiedAttrs(
                email=True
            ),
            user_pool_name='mod_ehr_user_pool',
            self_sign_up_enabled=False,
            sign_in_aliases=cognito_.SignInAliases(
                # email=True,
                username = True
            ),
            user_invitation=cognito_.UserInvitationConfig(
                email_subject='Health Connector Invitation',
                email_body='Your username is {username} and temporary password is {####}'
            )
        )
        
        user_pool_client = cognito_.UserPoolClient(
            self, "MODEHRUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name= 'MODEHRUserPoolClient',
            generate_secret=False,
            auth_flows=cognito_.AuthFlow(
                admin_user_password=True,
                # refresh_token=True,
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito_.OAuthSettings(
                flows=cognito_.OAuthFlows(
                    # implicit_code_grant=True,
                    authorization_code_grant=True,
                    # client_credentials=True
                ),
                # scopes=[
                #     cognito_.OAuthScope.OPENID,
                #     cognito_.OAuthScope.EMAIL
                # ]
            ),
            supported_identity_providers=[
                cognito_.UserPoolClientIdentityProvider.COGNITO
            ]
        )
      
        identity_pool = cognito_.CfnIdentityPool(
            self, "MODEHRIdentityPool",
            identity_pool_name="MODEHRIdentityPool",
            allow_unauthenticated_identities=False,  # Do not allow unauthenticated identities
            cognito_identity_providers=[
                cognito_.CfnIdentityPool.CognitoIdentityProviderProperty(
                    # provider_name=f"cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
                    # client_id=user_pool_client.user_pool_client_id
                    client_id=user_pool_client.user_pool_client_id,
                    provider_name=user_pool.user_pool_provider_name
                )
            ]
        )
        role = iam.Role(
            self,
            "UserManagementAdminRole",
            role_name = "UserManagementAdmin",
            assumed_by=iam.FederatedPrincipal(
                federated="cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity"
            ),
            description="Role for authenticated users in the specified Cognito identity pool"
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:*"],
                resources=["*"],
                effect=iam.Effect.ALLOW
            )
        )
        cognito_.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=identity_pool.ref,
            roles={
                "authenticated": role.role_arn
            }
        )

        UserManagementAdmin = cognito_.CfnUserPoolGroup(
            self, "UserManagementAdminGroup",
            group_name="UserManagementAdmin",
            user_pool_id=user_pool.user_pool_id,
            role_arn=role.role_arn
        )
        AppointmentsAdmin = cognito_.CfnUserPoolGroup(
            self, "AppointmentsAdminGroup",
            group_name="AppointmentsAdmin",
            user_pool_id=user_pool.user_pool_id
        )
        DallasCountyHealthDepartmentHealthNavigators = cognito_.CfnUserPoolGroup(
            self, "DallasCountyHealthDepartmentHealthNavigatorsGroup",
            group_name="DallasCountyHealthDepartmentHealthNavigators",
            user_pool_id=user_pool.user_pool_id
        )
        HealthcareFacilityStaff = cognito_.CfnUserPoolGroup(
            self, "HealthcareFacilityStaffGroup",
            group_name="HealthcareFacilityStaff",
            user_pool_id=user_pool.user_pool_id
        )
        HIRTAOperationsStaff = cognito_.CfnUserPoolGroup(
            self, "HIRTAOperationsStaffGroup",
            group_name="HIRTAOperationsStaff",
            user_pool_id=user_pool.user_pool_id
        )


        api_stage_name = 'dev'
        api = apigw_.RestApi(
            self,
            'MODEHRApi',
            default_cors_preflight_options=apigw_.CorsOptions(
                allow_origins=apigw_.Cors.ALL_ORIGINS,
                allow_methods=apigw_.Cors.ALL_METHODS,
                allow_headers=["Authorization", "Content-Type"]
            ), 
            rest_api_name='mod_ehr_api',
            deploy=True,
            deploy_options=apigw_.StageOptions(
                stage_name=api_stage_name,
                metrics_enabled=True,
            ),
        ) 
        api_path = api.root.add_resource('api')
        appointment_api_path = api_path.add_resource('appointments')
        patients_api_path = api_path.add_resource('patients')
        dashboard_api_path = api_path.add_resource('dashboard')
        setting_api_path = api_path.add_resource('setting')
        appointment_id_api_path = appointment_api_path.add_resource('{id}')

        # authorizer = apigw_.CognitoUserPoolsAuthorizer(
        #     self,
        #     "CognitoAuthorizer",
        #     cognito_user_pools=[user_pool],
        #     # identity_source='method.request.header.Authorizer'
        # )

        appointment_api_path.add_method(
            'GET',
            apigw_.LambdaIntegration(
                appoitments_handler
            ),
            # authorizer=authorizer
        )
        appointment_api_path.add_method(
            'POST',
            apigw_.LambdaIntegration(
                appoitments_handler
            ),
            # authorizer=authorizer
        )
        appointment_id_api_path.add_method(
            'PUT',
            apigw_.LambdaIntegration(
                appoitments_handler
            ),
            # authorizer=authorizer
        )
        appointment_id_api_path.add_method(
            'DELETE',
            apigw_.LambdaIntegration(
                appoitments_handler
            ),
            # authorizer=authorizer
        )
        appointment_id_api_path.add_method(
            'GET',
            apigw_.LambdaIntegration(
                appoitments_handler
            ),
            # authorizer=authorizer
        )
        patients_api_path.add_method(
            'GET',
            apigw_.LambdaIntegration(
                patients_handler
            )
            # authorizer=authorizer
        )
        patients_api_path.add_method(
            'POST',
            apigw_.LambdaIntegration(
                patients_handler
            ),
            # authorizer=authorizer
        )
        dashboard_api_path.add_method(
            'GET',
            apigw_.LambdaIntegration(
                dashboard_handler
            )
            # authorizer=authorizer
        )
        setting_api_path.add_method(
            'GET',
            apigw_.LambdaIntegration(
                settings_handler
            ),
            # authorizer=authorizer
        )
        setting_api_path.add_method(
            'POST',
            apigw_.LambdaIntegration(
                settings_handler
            ),
            # authorizer=authorizer
        )
        

        







        