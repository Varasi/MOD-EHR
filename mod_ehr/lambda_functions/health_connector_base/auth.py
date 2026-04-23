import json
import base64

# --- Authorization Configuration ---
# Define routes that require 'admin' role for specific methods.
# Add future admin-only routes here to keep your code sorted!
ADMIN_RESTRICTED_ROUTES = {
    "/hospitals": ["POST", "PUT", "DELETE"],
    # Example: "/settings": ["POST", "DELETE"]
}


def _decode_jwt_payload(token):
    try:
        if token.lower().startswith("bearer "):
            token = token[7:]
        payload_b64 = token.split('.')[1]
        # Add padding
        payload_b64 += '=' * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
    except Exception as e:
        print(f"Error decoding token: {e}")
        return {}


def _extract_tenant_from_request(event, resource_path):
    """
    Extracts the target hospital_id (tenant) from the API Gateway event.
    Checks path parameters, query parameters, and body.
    """
    path_params = event.get("pathParameters") or {}
    
    # 1. Path parameters
    tenant_from_api = path_params.get("hospital_id")
    if not tenant_from_api and resource_path.startswith("/hospitals/{id}"):
        tenant_from_api = path_params.get("id")
        
    # 2. Query string parameters
    if not tenant_from_api:
        query_params = event.get("queryStringParameters") or {}
        tenant_from_api = query_params.get("hospital_id")
        
    # 3. Body parameters
    if not tenant_from_api and event.get("body"):
        try:
            body = json.loads(event["body"])
            if isinstance(body, dict):
                tenant_from_api = body.get("hospital_id")
        except Exception:
            pass
            
    return tenant_from_api


def _check_authorization(is_admin, http_method, resource_path, tenant_from_api):
    """
    Centralized Role-Based Access Control rules for the APIs.
    Returns an error message string if forbidden, or None if allowed.
    """
    if is_admin:
        return None  # Admins pass all role checks

    # 1. Check against restricted admin-only routes
    for route_prefix, restricted_methods in ADMIN_RESTRICTED_ROUTES.items():
        if resource_path.startswith(route_prefix) and http_method in restricted_methods:
            return "Forbidden: Only admins can perform this action."

    # 2. Block non-admins from making global/unfiltered GET requests
    if http_method == "GET":
        if resource_path == "/hospitals":
            return "Forbidden: Non-admins cannot list all hospitals."
        if not tenant_from_api:
            return "Forbidden: GET request for non-admins must contain the required hospital_id parameter."

    return None  # Authorized


def require_tenant_isolation(func):
    """
    Decorator to enforce tenant isolation on API requests.
    Compares the tenant_id from the Cognito JWT token with the one requested in the API.
    """
    def wrapper(event, context):
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        tenant_from_token = claims.get("custom:hospital_id")
        
        # If not in APIGW claims (e.g., using Access Token), decode the token payload ourselves from x-id-token:id-token
        if not tenant_from_token:
            headers = event.get("headers") or {}
            id_token_header = headers.get("X-Id-Token") or headers.get("x-id-token")
            if id_token_header:
                decoded_claims = _decode_jwt_payload(id_token_header)
                tenant_from_token = decoded_claims.get("custom:hospital_id") or decoded_claims.get("hospital_id")
                
        if not tenant_from_token:
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Unauthorized: No tenant identifier found in token."})
            }

        is_admin = tenant_from_token == "admin"
        http_method = event.get("httpMethod", "").upper()
        resource_path = event.get("resource", "")
        
        # Extract target tenant from the API Request
        tenant_from_api = _extract_tenant_from_request(event, resource_path)

        # --- 1. Check General Role-Based Authorization Rules ---
        auth_error = _check_authorization(is_admin, http_method, resource_path, tenant_from_api)
        if auth_error:
            return {
                "statusCode": 403,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": auth_error})
            }
        
        # --- 2. Enforce Strict Tenant Isolation (Cross-Tenant Access Check) ---
        if not is_admin:
            if tenant_from_api and tenant_from_token != tenant_from_api:
                return {
                    "statusCode": 403,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": f"Forbidden: Tenant isolation enforced. Token tenant '{tenant_from_token}' does not match API tenant '{tenant_from_api}'."})
                }
            
            if not tenant_from_api:
                return {
                    "statusCode": 403,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "Forbidden: Missing hospital_id parameter or invalid request."})
                }

        # Inject contextual variables so inner handlers do not need to parse again
        event["is_admin"] = is_admin
        event["user_hospital_id"] = tenant_from_token

        return func(event, context)
    return wrapper
