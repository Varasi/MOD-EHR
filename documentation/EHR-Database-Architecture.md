# MOD-EHR Multi-Tenant System Database Architecture

## 1. Overview

The MOD-EHR application uses Amazon DynamoDB, a serverless NoSQL database, for its primary data storage. The architecture is built around a multi-tenant model where each healthcare provider (hospital) is a distinct tenant.

The core principle of the database design is data isolation, achieved by using `hospital_id` as the Partition Key for almost all tables. This ensures that queries are naturally scoped to a single tenant, providing both security and performance benefits. Admin access is modeled as a sentinel value — a caller is treated as admin when their Cognito token's `custom:hospital_id` claim equals the literal string `"admin"`; there is no real "admin" tenant row in the Hospitals table.

All tables are provisioned with on-demand capacity (`PAY_PER_REQUEST`, the CDK `TableV2` default) and have Point-In-Time Recovery (PITR) and Contributor Insights enabled.

Every table's records also carry `created` and `modified` UTC timestamp attributes, set automatically on write.

**Table naming:** each table name includes an optional version suffix controlled by the `STACK_VERSION` environment variable used at deploy time (see the deployment guide) — e.g. `development_hospitals_table_v2`, not just `development_hospitals_table`. The suffix is empty only if `STACK_VERSION` is explicitly set to an empty string.

---

## 2. Table Schemas

The application uses the following five DynamoDB tables:

### 2.1. Hospitals Table

- **Table Name:** `{env}_hospitals_table{version_suffix}` (e.g., `development_hospitals_table_v2`)
- **Purpose:** Stores the primary configuration for each hospital tenant. This table acts as the central registry for all tenants in the system.

**Schema**
- **Primary Key:**
  - Partition Key (PK): `id` (String) — the unique identifier for the hospital (e.g., `tenant_a`).
- **GSIs:** None.

**Key Attributes**
- `id`: The unique hospital ID.
- `name`: The display name of the hospital.
- `subdomain`: The subdomain used for tenant-specific branding and URL routing.
- `timezone`: The hospital's local timezone (defaults to `"CT"`).
- `location`: The hospital's address. Validated against a live Google Maps geocoding lookup on save — it must be a resolvable address, not an arbitrary label.
- `provider`: The EHR provider type (`epic` or `veradigm`).
- `status`: The current status of the hospital (e.g., `ACTIVE`, `PENDING`).
- `s3_subfolder_name`: (For Veradigm) the name of the S3 subfolder for SFTP uploads.
- `sftp_username`: (For Veradigm) the username for the SFTP server.

**Note on Secrets:** Highly sensitive credentials like `sftp_password`, `epic_client_id`, `epic_private_key`, `epic_jwks_url`, and `epic_jwks_kid` are not stored in this table — they aren't even fields on the underlying data model. They're kept exclusively in AWS Secrets Manager, with the secret's name linked to the hospital ID. `s3_subfolder_name` and `sftp_username`, by contrast, are written to **both** Secrets Manager and this table.

### 2.2. Appointments Table

- **Table Name:** `{env}_appointment_table{version_suffix}`
- **Purpose:** Stores all patient appointment records, including their matched transportation (ride) details. This is a high-volume table.

**Schema**
- **Primary Key:**
  - Partition Key (PK): `hospital_id` (String) — isolates appointments by tenant.
  - Sort Key (SK): `id` (String) — a UUID generated on creation.
- **GSIs:**
  1. `patient_id-index` — Partition Key: `patient_id` (String). Allows efficiently querying all appointments for a specific patient across hospitals.
  2. `hospital_id-end_time-index` — Partition Key: `hospital_id` (String), Sort Key: `end_time` (UTC DateTime). Allows efficiently querying a hospital's appointments sorted by end time; the dashboard uses this to fetch today's appointments.

**Key Attributes**
- `hospital_id`: The tenant identifier.
- `id`: The appointment's unique ID.
- `patient_id`: The identifier for the patient associated with the appointment.
- `patient_name`: The full name of the patient.
- `patient_first_name`, `patient_last_name`, `patient_phone_no`, `patient_email`: Additional patient contact details captured on the appointment record itself.
- `start_time` / `end_time`: The appointment's time window.
- `location`: The address or location of the appointment. Geo-validated the same way as the Hospitals table's `location` field.
- `status`: The appointment status (e.g., `Scheduled`, `Completed`).
- `provider`: The source EHR system for the appointment (`epic` or `veradigm`, defaults to `epic`).
- `ride`: A JSON object containing matched transportation details from Via, structured around two legs (to-appointment / from-appointment) with pickup and dropoff details for each.
- `coordinator_notes`: Free-text notes entered by a ride coordinator.
- `alt_transport_confirmed_to` / `alt_transport_confirmed_from`: Booleans tracking whether alternate transportation has been confirmed for each leg.

### 2.3. Patients Table

- **Table Name:** `{env}_patients_table{version_suffix}`
- **Purpose:** Stores patient records and maintains the mapping between a patient's EHR identifier and their Via Rider ID.

**Schema**
- **Primary Key:**
  - Partition Key (PK): `hospital_id` (String) — isolates patients by tenant.
  - Sort Key (SK): `patient_id` (String) — the patient's unique ID within their hospital system.
- **GSIs:** None.

**Key Attributes**
- `hospital_id`: The tenant identifier.
- `patient_id`: The patient's unique ID.
- `name`: The patient's full name.
- `via_rider_id`: The corresponding rider ID from the Via transportation system. Patients without a `via_rider_id` set are excluded from the application's list/dashboard queries (see [Data Flow](#3-data-flow-and-access-patterns)).
- `provider`: The source EHR system for the patient record (`epic` or `veradigm`).

### 2.4. Settings Table

- **Table Name:** `{env}_settings_table{version_suffix}`
- **Purpose:** Stores tenant-specific configurations and settings, such as UI branding colors or ride-matching time windows.

**Schema**
- **Primary Key:**
  - Partition Key (PK): `hospital_id` (String) — isolates settings by tenant.
  - Sort Key (SK): `name` (String) — the name of the setting (e.g., `branding_config`).
- **GSIs:** None.

**Key Attributes**
- `hospital_id`: The tenant identifier.
- `name`: The setting's name.
- `value`: The value of the setting, stored as a **string** attribute. Numeric or structured values (e.g., a branding config) must be written as strings — a raw JSON number will fail to save under this schema.

### 2.5. SFTP Logs Table

- **Table Name:** `{env}_ftp_logs_table{version_suffix}`
- **Purpose:** Records metadata for each file uploaded to the SFTP server for Veradigm tenants, providing a basic audit trail of what was received and when.

**Schema**
- **Primary Key:**
  - Partition Key (PK): `hospital_id` (String) — isolates logs by tenant.
  - Sort Key (SK): `name` (String) — the full S3 key of the uploaded file (e.g., `tenant_a_folder/appointments.csv`).
- **GSIs:** None.

**Key Attributes**
- `hospital_id`: The tenant identifier.
- `name`: The file name/key.
- `server_last_modified`: A numeric timestamp indicating when the file was last modified on the server.

> This table does **not** have a per-file ingestion-status attribute (e.g., processed/failed) today — it only records that a file exists and when it was last modified.

---

## 3. Data Flow and Access Patterns

- **Tenant Isolation:** Primary queries for appointments, patients, settings, and logs are executed as a `Query` operation with `hospital_id` as the partition key — the most efficient way to retrieve data in DynamoDB, and it enforces strict data separation between tenants.
- **Filtering to Via-linked records:** Beyond partition-key isolation, the application layer further filters appointment, patient, and dashboard queries to records where `via_rider_id` is present and non-empty. This is an application-level `filter_condition` on the query/scan, not a separate index — patients (and their appointments) that haven't been linked to a Via rider are excluded from these results even though they still exist in the table.
- **Admin Access:** Callers whose token carries `hospital_id=admin` bypass the tenant-scoped query pattern:
  - Hospitals and Patients lists use a full table `Scan`.
  - Appointments, however, are not scanned directly — the admin path scans the Patients table for Via-linked patients, then queries the `patient_id-index` GSI per matching patient to assemble the appointment list. This avoids a full scan of the (high-volume) Appointments table.
- **Appointment Lookups:**
  - To show a hospital's appointments ending within a given time window (e.g., today's appointments for the dashboard), the application queries the `hospital_id-end_time-index` GSI on the appointments table.
  - To find all appointments for a single patient, the application queries the `patient_id-index` GSI.
- **Data Ingestion:** the `datapopulator_lambda` (for Veradigm) and `epic_data_populator_lambda` (for Epic) perform batch write operations to save appointment and patient records to their respective tables after fetching data from the source EHR system.
