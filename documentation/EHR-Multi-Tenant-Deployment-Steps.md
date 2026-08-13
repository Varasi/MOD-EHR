# EHR Multi-Tenant Deployment Guide

This guide walks through deploying the EHR Multi-Tenant stack (backend Lambda functions, API Gateway, Cognito, DynamoDB, CloudFront + S3 dashboard website) from a clean machine.

---

## Prerequisites

- **Python 3.11** (Lambda layers are built specifically for `--python-version 3.11`)
- **Node.js + npm** (required for the dashboard build and the AWS CDK CLI)
- **AWS CDK CLI**: `npm install -g aws-cdk`
- **AWS CLI v2**
- **WSL2 with Ubuntu** (used to build Linux-compatible Lambda layers)
- An AWS account/IAM user with permissions to deploy CloudFormation, Lambda, API Gateway, Cognito, DynamoDB, S3, CloudFront, VPC, Secrets Manager, and Transfer Family (SFTP) resources

---

## 1. Clone and Set Up the Local Environment

1. Clone the repository to your local machine.
2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Navigate to the project directory (`mod_ehr`) and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 2. Configure the Environment File

1. Create a `<environment>.yaml` file in the `mod_ehr/configs` directory (e.g. `production.yaml`, `uat.yaml`, or `development.yaml` — the filename must match the environment name you deploy with). Use `sample_config_env.yaml` at the repo root as a template.
2. Fill in the required values:
   - `ACCOUNT.ACCOUNT_ID`, `ACCOUNT.REGION`
   - `ENV.CIDR`, `ENV.DOMAIN`, `ENV.DOMAIN_PREFIX`, `ENV.BUCKET_NAME`
   - `SECRETS.google_map_api_key`, `via_client_id`, `via_client_secret`, `via_api_key`, `via_auth_url`, `via_api_url`

   > The `VARIABLES.SFTP_USERNAME`, `VARIABLES.SSH_KEYS`, and `ENV.CLIENT_IP` fields in the template are not currently used by the deployed stack — the SFTP server is provisioned with a Lambda-based custom identity provider (per-hospital credentials from DynamoDB and Secrets Manager) rather than the static SSH keys/IP allow-list those fields would configure. They can be left blank.
3. **Select which config file is loaded.** `app.py` picks the config via the `ENVIRONMENT` environment variable and defaults to `"production"` if it isn't set:
   ```python
   config = Config(os.environ.get("ENVIRONMENT", "production"))
   ```
   Set `ENVIRONMENT=development` (or `uat`) before running any `cdk` command, or edit the default in `app.py` to match the config file you created.
4. **Parallel/versioned deployments.** `app.py` also reads a `STACK_VERSION` environment variable (default `"v2"`), which is appended to the stack name and most resource names (S3 bucket, DynamoDB tables, etc.). Set `STACK_VERSION` if you need to deploy a second, independent copy of the stack side by side — for example, to run a second tenant environment without colliding with existing resource names.

## 3. Build Lambda Layers (via WSL/Ubuntu)

The `.sh` scripts are authored on Windows, so they need Unix line endings before they'll run in WSL.

1. Check whether a Linux distro is installed:
   ```bash
   wsl --list --verbose
   ```
   If nothing is installed:
   ```bash
   wsl --install -d Ubuntu
   ```
2. Open the Ubuntu terminal and navigate to the project directory:
   ```bash
   cd /mnt/<path_to_mod_ehr>
   ```
   (replace the path with your project directory)
3. If `pip` and `zip` aren't installed in Ubuntu:
   ```bash
   sudo apt update
   sudo apt install python3-pip
   sudo apt install zip
   ```
4. Convert line endings and make the script executable:
   ```bash
   sudo apt install dos2unix
   dos2unix deploy.sh
   chmod +x deploy.sh
   ```
5. Run the script to build the Lambda layers. This installs the layer dependencies for `manylinux2014_x86_64` / Python 3.11 and produces `requirements.zip` and `health_connector_base.zip`:
   ```bash
   bash deploy.sh
   ```

   **Faster iteration:** if you only need to update the shared `health_connector_base` package code (no changes to `lambda_functions/requirements.txt`), run `deploy_base_functions.sh` instead. It re-zips `health_connector_base.zip` directly without reinstalling all pip dependencies, which is much quicker:
   ```bash
   dos2unix deploy_base_functions.sh
   chmod +x deploy_base_functions.sh
   bash deploy_base_functions.sh
   ```

## 4. Configure the AWS CLI

Back in your Windows terminal:

```bash
aws configure
```

Enter your AWS Access Key ID, Secret Access Key, region (must match `ACCOUNT.REGION` in your config yaml), and output format (e.g. `json`).

## 5. First CDK Deploy (Backend Infrastructure)

```bash
cdk bootstrap
cdk deploy
```

> **Note:** `deploy_frontend_assets()` in `healthconnect_poc_stack.py` bundles `dashboard_website/dist`, which doesn't exist until the frontend is built (Step 6). If this first deploy fails because that folder is missing, temporarily comment out the `self.create_cloudfront_dist()` and `self.deploy_frontend_assets()` calls near the top of the stack's `__init__` method, run `cdk deploy`, then uncomment them again before Step 7.

After the deployment completes, get the API endpoint, User Pool ID, Client ID, Identity Pool ID, and other outputs from the AWS CloudFormation console or the `cdk deploy` output.

## 6. Build the Dashboard Website

1. Install frontend dependencies:
   ```bash
   cd dashboard_website
   npm install
   ```
2. Update `deploy_website.sh` with the values obtained in Step 5:
   ```bash
   REGION="<region>"
   POOL_ID="<user pool id>"
   CLIENT_ID="<userpool webclient id>"
   IDENTITY_POOL_ID="<identity pool id>"
   GOOGLE_MAPS_KEY="<google maps api key>"
   BASE_URL="<https://your-domain.example.com>"
   CUSTOM_DOMAIN="<.your-domain.example.com>"   # also update the CUSTOM_DOMAIN variable in common.js
   ENVIRONMENT="<production|uat|development>"
   HIRTA_CONTACT="<support contact number>"
   ```
   > Keep real AWS credentials and API keys out of version control — inject them at deploy time (environment variables, a secrets manager, or a local untracked file) rather than committing them into `deploy_website.sh`.
3. In the Ubuntu terminal:
   ```bash
   chmod +x deploy_website.sh
   dos2unix deploy_website.sh
   bash deploy_website.sh
   ```
   This runs `npx webpack --mode production` with the variables above baked in via `webpack.config.js`'s `DefinePlugin`, producing `dashboard_website/dist`.

## 7. Redeploy the Stack with Website Assets

```bash
cdk deploy
```

This uploads `dashboard_website/dist` to the S3 bucket and invalidates the CloudFront distribution (`deploy_frontend_assets()` in `healthconnect_poc_stack.py`).

After completion, the dashboard is reachable at the CloudFront/S3 URL from the `cdk deploy` output.

## 8. Test the API

Use Postman or cURL against the API endpoint from the `cdk deploy` output.

## 9. Create the Admin User (Cognito)

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <cognito_user_pool_id> \
  --username admin@gmail.com \
  --user-attributes Name=custom:hospital_id,Value=admin \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <cognito_user_pool_id> \
  --username admin@gmail.com \
  --password 'Admin@1234' \
  --permanent

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <cognito_user_pool_id> \
  --username admin@gmail.com \
  --group-name UserManagementAdmin
```

The stack creates three Cognito groups: `UserManagementAdmin`, `BookingAdmin`, and `ViewOnly`. Assign additional users to whichever group matches their intended role.

## 10. Configure a Custom Domain (CloudFront + Route53)

1. Request and validate an ACM certificate for your domain in **us-east-1** — CloudFront requires certificates to be issued in that region regardless of your stack's deployment region.
2. In the CloudFront console, open the distribution created by the stack (the one with the S3 bucket and API Gateway as origins) and click **Add domain**. Enter:
   ```
   <domain>
   *.<domain>
   ```
3. On the next step, attach the validated TLS certificate and add the domain to the distribution.
4. Update the dashboard's API base URL to use `<domain>` instead of the CloudFront default domain.
5. **Route the domain via Route53:**
   - If the domain is registered in Route53 under the same account, click **Route domain to CloudFront** → **Setup Routing Automatically**.
   - If registered with a third-party registrar, copy the CloudFront-provided DNS names and add them in that registrar's DNS settings.

## 11. First Login

Log in at `admin.<your_domain>` with the admin credentials created in Step 9, then go to **Hospital and User Management** to create tenants and users.
