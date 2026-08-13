# MOD-EHR API Documentation

This document provides comprehensive details on the MOD-EHR REST APIs and its Authentication/Authorization architecture.

**Base URL:** All endpoints are served under the `api` stage, e.g. `https://<your-domain>/api/<resource>`.

All endpoints require authentication via AWS API Gateway's Cognito User Pools Authorizer, **with one exception**: `GET /api/epic/{id}` (Section 9) has no authorizer attached and is reachable without a token. That endpoint is marked "not being used" and should either be secured or removed before relying on it. Everywhere else, the `X-Id-Token` header is heavily utilized for evaluating custom claims.

---

## Authentication & Tenant Isolation Architecture (auth.py)

The backend API operates securely within a multi-tenant environment. To achieve robust security and maintain clean Lambda Handlers, authorization and tenant isolation are handled centrally via the `@require_tenant_isolation` decorator defined in `auth.py`.

### Why it is used

- **DRY (Don't Repeat Yourself) Principle**: Centralizes security logic so that individual Lambda functions (`HospitalsAPIHandler`, `PatientAPIHandler`, etc.) focus purely on business logic rather than parsing tokens and rejecting malicious payload scenarios.
- **Multi-Tenant Data Isolation**: Prevents horizontal privilege escalation. A user belonging to "Tenant A" must be strictly prohibited from reading, updating, or deleting records belonging to "Tenant B".
- **Role-Based Access Control (RBAC)**: Ensures high-risk API operations (like managing hospital onboarding configurations or listing all hospitals) are restricted exclusively to administrators.

### What it does

- **Token Parsing**: Intercepts the request and retrieves the target tenant ID (`custom:hospital_id`) either from the API Gateway Authorizer claims or by manually decoding the custom `X-Id-Token` header.
- **Role Evaluation**: A caller is treated as admin when their token's `custom:hospital_id` equals the literal string `"admin"`.
- **Target Extraction**: Evaluates the API Gateway event payload (checking path parameters, query strings, and JSON body parameters) to figure out which `hospital_id` the requester is attempting to access.
- **Rules Enforcement**: Checks the extracted request target against the user's validated tenant token. If the user is not an admin, and the target tenant does not match the token's tenant, the request is rejected with a `403 Forbidden` response. It also validates endpoint rules against the `ADMIN_RESTRICTED_ROUTES` map (currently just `POST/PUT/DELETE /hospitals`) to reject non-admins, and blocks non-admins from any `GET` request that doesn't include a `hospital_id`.
- **Context Injection**: Injects `event["is_admin"]` and `event["user_hospital_id"]` into the request payload before passing it to the target lambda handler, so downstream code can use these pre-verified variables without re-parsing the JWT.

> **Not every endpoint uses this decorator.** `POST /api/validate_patient` and `POST /api/trip_booking` (Sections 7–8) are **not** wrapped in `@require_tenant_isolation` and never read `hospital_id` — see those sections for what that means in practice.

> **List endpoints are scoped to Via-linked records.** `GET /api/appointments`, `GET /api/patients`, and `GET /api/dashboard` all filter to patients that have a non-empty `via_rider_id`. A patient/appointment that hasn't been linked to a Via rider will not appear in these list responses, even though it exists in the database.

---

## 1. Hospitals API

This API handles all CRUD operations related to onboarding and managing hospital tenants.

### GET /api/hospitals

**Description**: Retrieves a list of all provisioned hospital tenants.
**Authorization**: Admin only.
**Input**: No path or query parameters.

**Output (200 OK)**:
```json
[
  {
    "id": "tenant_a",
    "name": "General Hospital",
    "subdomain": "tenant-a",
    "timezone": "America/Chicago",
    "status": "ACTIVE"
  }
]
```

### POST /api/hospitals

**Description**: Provisions a new hospital tenant.
**Authorization**: Admin only.

**Request Body**:
```json
{
  "id": "tenant_a",
  "name": "General Hospital",
  "subdomain": "tenant-a",
  "timezone": "America/Chicago",
  "location": "Des Moines, IA",
  "provider": "veradigm",
  "s3_subfolder_name": "tenant_a_uploads",
  "sftp_username": "tenant_a_admin",
  "sftp_password": "SecurePassword123!"
}
```

- `location` is validated with a live Google Maps geocoding lookup at save time — it must be a resolvable address, not an arbitrary label.
- `epic_client_id`, `epic_private_key`, `epic_jwks_url`, `epic_jwks_kid`, and `sftp_password` are moved into AWS Secrets Manager and are **not** stored in the hospital's DynamoDB record.
- `s3_subfolder_name` and `sftp_username` are stored in **both** Secrets Manager and the DynamoDB record.

**Output (200 OK)**:
```json
{
  "id": "tenant_a",
  "name": "General Hospital",
  "subdomain": "tenant-a",
  "status": "PENDING"
}
```

### GET /api/hospitals/{id}

**Description**: Get configuration details for a specific hospital. Non-admins can only fetch the hospital matching their ID token.
**Input**: Path parameter `id` (e.g., `tenant_a`).

**Output (200 OK)**:
```json
{
  "id": "tenant_a",
  "name": "General Hospital",
  "timezone": "America/Chicago",
  "status": "ACTIVE"
}
```

### PUT /api/hospitals/{id}

**Description**: Update configuration parameters or secrets for an existing hospital.
**Authorization**: Admin only.
**Input**: Path parameter `id`.

**Request Body**:
```json
{
  "name": "General Hospital Updated",
  "timezone": "America/New_York"
}
```

**Output (200 OK)**: Returns the updated hospital record.

### DELETE /api/hospitals/{id}

**Description**: Delete a hospital, wiping its DB records, provisioned SFTP users, and Secrets Manager records.
**Authorization**: Admin only.
**Input**: Path parameter `id`.
**Output (204 No Content)**.

---

## 2. Appointments API

This API manages patient appointments. Appointments may be retrieved via third-party systems (Epic/Veradigm) or created/updated manually. Every appointment also carries a ride-booking object (see the `ride` note below) used by the two-leg (to-appointment / from-appointment) transportation workflow.

### GET /api/appointments

**Description**: Get a list of appointments, filtered to patients with a linked `via_rider_id`.
**Input**: Query parameter `hospital_id` — required for non-admins (enforced by the auth decorator); admins may omit it or pass `hospital_id=admin` to fetch across all tenants.

**Output (200 OK)**:
```json
[
  {
    "id": "APP98765",
    "hospital_id": "tenant_a",
    "patient_name": "John Doe",
    "patient_id": "P12345",
    "location": "Main Clinic",
    "start_time": "2026-03-25T09:00:00.000+0000",
    "end_time": "2026-03-25T10:00:00.000+0000",
    "status": "Scheduled",
    "provider": "epic",
    "ride": { "...": "two-leg pickup/dropoff ride details" }
  }
]
```

> The full record also includes `patient_first_name`, `patient_last_name`, `patient_phone_no`, `patient_email`, `coordinator_notes`, `alt_transport_confirmed_to`, and `alt_transport_confirmed_from`. `location` is geo-validated the same way as the Hospitals API — a plain facility name like `"Main Clinic"` must still resolve through Google's geocoder.

### POST /api/appointments

**Description**: Create a new appointment record manually.

**Request Body**:
```json
{
  "hospital_id": "tenant_a",
  "patient_name": "John Doe",
  "patient_id": "P12345",
  "location": "Main Clinic",
  "start_time": "2026-03-25T09:00:00.000+0000",
  "end_time": "2026-03-25T10:00:00.000+0000",
  "status": "Scheduled",
  "provider": "epic"
}
```

**Output (200 OK)**: Returns the generated appointment object, including its new UUID `id`.

### GET /api/appointments/{id} (not being used)

**Description**: Retrieve details for a single appointment.
**Input**: Path parameter `id`; query parameter `hospital_id` (required for tenant isolation checks by non-admins).
**Output (200 OK)**: A single appointment JSON object.

### PUT /api/appointments/{id}

**Description**: Update an existing appointment. `hospital_id` and `id` cannot be changed via this call; any other field present on the model can be updated.

**Request Body**:
```json
{
  "id": "APP98765",
  "hospital_id": "tenant_a",
  "status": "Completed"
}
```

**Output (200 OK)**: Returns the updated appointment JSON object.

### DELETE /api/appointments/{id}

**Description**: Delete a specific appointment.
**Input**: Path parameter `id`; query parameter `hospital_id` (required for the tenant isolation check).
**Output (204 No Content)**.

---

## 3. Patients API

This API manages patient demographics and maps them to their respective integrations (e.g., Via Rider mappings).

### GET /api/patients

**Description**: Get a list of patients that have a linked `via_rider_id`.
**Input**: Query parameter `hospital_id` (required for non-admins).

**Output (200 OK)**:
```json
[
  {
    "patient_id": "P12345",
    "name": "Jane Smith",
    "hospital_id": "tenant_a",
    "provider": "veradigm",
    "via_rider_id": "VIA-7654321"
  }
]
```

### POST /api/patients

**Description**: Register a new patient. `patient_id` is required.

**Request Body**:
```json
{
  "patient_id": "P12345",
  "name": "Jane Smith",
  "hospital_id": "tenant_a",
  "provider": "veradigm",
  "via_rider_id": "VIA-7654321"
}
```

**Output (200 OK)**: Returns the newly created patient JSON object.

### GET /api/patients/{patient_id}

**Description**: Retrieve details for a specific patient.
**Input**: Path parameter `patient_id`; query parameter `hospital_id` (required for non-admins).
**Output (200 OK)**: A single patient JSON object.

### PUT /api/patients/{patient_id}

**Description**: Update a patient record (e.g., attaching a `via_rider_id`). `hospital_id` and `patient_id` cannot be changed via this call.

**Request Body**:
```json
{
  "id": "P12345",
  "hospital_id": "tenant_a",
  "via_rider_id": "VIA-9999999"
}
```

**Output (200 OK)**: Returns the updated patient JSON object.

### DELETE /api/patients/{patient_id} (not being used)

**Description**: Delete a patient record.
**Input**: Path parameter `patient_id`; query parameter `hospital_id` (required for non-admins).
**Output (204 No Content)**.

---

## 4. Settings API

Manage system or tenant-specific settings (such as branding configs, integration endpoints, etc.).

### GET /api/settings

**Description**: Retrieve the settings mapping for a hospital.
**Input**: Query parameter `hospital_id` (required — without it, no results are returned for non-admins, and no settings are queried for the caller).

**Output (200 OK)**:
```json
[
  {
    "name": "branding_config",
    "hospital_id": "tenant_a",
    "value": "{\"color\":\"#0055A4\",\"logo_url\":\"s3://...\"}"
  }
]
```

### POST /api/settings/{name}

**Description**: Create or update the value of a specific setting key.
**Input**: Path parameter `name` — the unique string identifier for the setting (e.g., `branding_config`).

**Request Body**:
```json
{
  "hospital_id": "tenant_a",
  "name": "subsequent_period",
  "value": "16"
}
```

> `value` is stored as a **string** attribute in DynamoDB. Numeric-looking values must be sent as strings (e.g., `"16"`, not `16`) or the write will fail.

**Output (200 OK)**: Returns the newly written JSON record.

---

## 5. Logs API

Allows visibility into Veradigm/SFTP data ingestion logs for files uploaded to the tenant's drop folder.

### GET /api/logs

**Description**: Get SFTP file upload logs in a paginated, DataTables-style response.
**Input**:
- Query parameter `hospital_id` (required for non-admins; pass `hospital_id=admin` to scan across all tenants)
- Optional: `search` (case-insensitive substring match on file name), `draw`, `start`, `length` (paging controls)

**Output (200 OK)**:
```json
{
  "draw": 1,
  "recordsTotal": 1,
  "recordsFiltered": 1,
  "data": [
    {
      "name": "tenant_a_uploads/appointments_0319.csv",
      "server_last_modified": 1710845813,
      "hospital_id": "tenant_a"
    }
  ]
}
```

> The log record only contains `hospital_id`, `name`, and `server_last_modified` (plus internal audit timestamps) — there is currently no `status`/ingestion-outcome field on this record.

---

## 6. Dashboard API

General data endpoints for initial portal loads.

### GET /api/dashboard

**Description**: Get the day's appointments (filtered to Via-linked patients) for the main dashboard interface.
**Input**: Query parameter `hospital_id` — **required for every caller**, including admins; the handler reads it directly from the query string and does not fall back to the caller's token if it's omitted.

**Output (200 OK)**: An array of today's appointment objects (same shape as the Appointments API), scoped to `hospital_id` (or across all tenants if `hospital_id=admin`).

---

## 7. Validate Passenger API

### POST /api/validate_patient

**Description**: Validates that a passenger exists in the external Via system and that their input details match the registered records before booking.

> This endpoint does **not** enforce tenant isolation — it is authenticated (a valid Cognito token is required by API Gateway) but performs no `hospital_id` scoping, since it only proxies a lookup against the shared Via account.

**Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `via_rider_id` | String | Optional | The unique rider ID in the Via system. |
| `email` | String | Optional | The email address of the passenger. |
| `phone` | String | Optional | The phone number of the passenger (numbers only). |
| `first_name` | String | Optional | First name of the passenger. |
| `last_name` | String | Optional | Last name of the passenger. |

**Output (200 OK)**: Returned when a single matching passenger is successfully validated.
```json
{
  "rider_id": "12345",
  "first_name": "John",
  "last_name": "Doe",
  "email_address": "john.doe@example.com",
  "e164_phone_number": "+1 555-555-5555"
}
```

**400 Bad Request**: Returned if details do not match, or if multiple/no passengers are found.

Example (no match):
```json
{ "message": "NoSuchRiderError" }
```

Example (mismatched fields):
```json
{ "message": "Email, Phone fields are incorrect. Please check and try again." }
```

---

## 8. Book Trip API

### POST /api/trip_booking

**Description**: Geocodes pickup and destination addresses, maps passenger configurations (including accessibility and guest counts), and requests/books a new trip in the Via system.

> Like the Validate Passenger API, this endpoint does **not** enforce tenant isolation — it is authenticated but has no `hospital_id` scoping.

**Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `via_rider_id` | String | Optional | Required for registered riders. Leave empty for guests. |
| `first_name` | String | Optional | First name of the guest passenger (if booking as guest). |
| `last_name` | String | Optional | Last name of the guest passenger (if booking as guest). |
| `email` | String | Optional | Email of the guest passenger (if booking as guest). |
| `phone` | String | Optional | Phone number of the guest passenger (if booking as guest). |
| `trip_direction` | String | Yes | Either `"To Appointment"` or `"From Appointment"`. |
| `appt_time` | String | Yes | ISO string representation of the target time. |
| `pickup_address` | String | Yes | Street address for the pickup location. |
| `destination_address` | String | Yes | Street address for the destination. |
| `guest_count` | Integer | Optional | Number of standard guest passengers. |
| `guest_wav_count` | Integer | Optional | Number of wheelchair-accessible guest passengers. |
| `pca_count` | Integer | Optional | Number of Personal Care Assistants (PCAs). |
| `pca_wav_count` | Integer | Optional | Number of wheelchair-accessible PCAs. |
| `requires_wav` | Boolean | Optional | Set to `true` if the primary rider requires a WAV. |
| `additional_notes_pickup` | String | Optional | Driver instructions for the pickup point. |
| `additional_notes_dropoff` | String | Optional | Driver instructions for the dropoff point. |

**Output (200 OK)**: Returned when a trip is successfully created and confirmed.
```json
{
  "message": "Trip booked successfully",
  "data": {
    "trip_id": "987654",
    "trip_status": "CONFIRMED",
    "origin": {
      "address": "123 Main St, Ames, IA",
      "lat": 42.0308,
      "lng": -93.6319
    },
    "destination": {
      "address": "456 Hospital Rd, Ames, IA",
      "lat": 42.0255,
      "lng": -93.6234
    }
  }
}
```

**500 Internal Server Error**: Returned if geocoding, trip request, or booking confirmation fails.
```json
{ "message": "Failed to book trip: No vehicle available for the requested time" }
```

---

## 9. Epic Integration API (not being used)

Helper endpoint to trigger or investigate Epic FHIR integration sandbox tasks.

### GET /api/epic/{id}

**Description**: Manually trigger or check Epic integration sync status/details for a specific tenant.
**Authorization**: **None** — this is the one route with no Cognito authorizer attached at the API Gateway level.
**Input**: Path parameter `id` (the `hospital_id` of the Epic tenant).
**Output (200 OK)**: A status payload from the Epic Integration lambda.
