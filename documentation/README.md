# MOD-EHR ("Health Connector") — System Documentation

## Overview

MOD-EHR is a multi-tenant platform that coordinates non-emergency medical transportation for hospital patients. It isn't a general clinical EHR (it doesn't store diagnoses, medications, or clinical notes) — it sits alongside a hospital's real EHR, pulling in just enough appointment and patient data to answer one question: **does this patient have a ride to and from their appointment, and if not, can we get them one?**

Each hospital is a tenant. A single shared deployment serves every tenant, but every record — patients, appointments, settings, logs — is tied to a `hospital_id` and strictly isolated at query time, so hospitals never see each other's data even though they share the same infrastructure. Each tenant also gets its own subdomain and branding, so the app looks and feels dedicated to them.

Appointments reach the system three ways:
- **Epic** — polled live from a hospital's Epic FHIR API on a schedule.
- **Veradigm** — CSV files a hospital's Veradigm system drops onto an SFTP server.
- **Manual entry** — typed in directly by hospital staff (Development environments only today — see the [Admin and Tenant Users Guide](Admin-and-Tenant-Users-Guide.md)).

Once an appointment exists, the system tries to match it to a ride the patient already has booked with **Via** (the transportation provider), or lets staff book one on the spot. Every appointment can have two independent legs — a ride *to* it and a ride *from* it — each matched and tracked separately.

## Key Features

- **Multi-Tenant Data Isolation** — every table is partitioned by `hospital_id`, and a shared authorization layer (`auth.py`'s tenant-isolation decorator) checks every API request's Cognito token against the tenant it's trying to touch, rejecting cross-tenant access.
- **Role-Based Access** — three roles, all enforced via Cognito groups: **User Management Admin** (manages users for a hospital, or for the whole platform if their hospital is the reserved `admin` tenant), **Booking Admin** (day-to-day ride/appointment coordination), and **View Only** (read-only).
- **Appointment & Ride Coordination** — the core of the app: appointments, patient-to-Via-rider linking, and automatic ride matching against a configurable time window and location proximity, with a two-leg (to/from) structure per appointment.
- **Tenant-Specific Branding** — each hospital gets its own subdomain and a per-tenant logo/config, served from the same underlying application.
- **Automated Data Ingestion** — live polling for Epic tenants, event-driven CSV processing for Veradigm tenants, both landing in the same DynamoDB tables.
- **Centralized Administration** — a separate admin portal for onboarding hospitals, provisioning credentials, and managing users across every tenant.

## Target Users

- **Hospital Staff** (Booking Admin / View Only) — the primary end users. They work entirely inside their hospital's own subdomain, coordinating rides for their patients' appointments.
- **Platform Admins** (User Management Admin at the `admin` tenant) — onboard new hospitals, provision Epic/Veradigm/Via credentials, and manage users across every tenant from the admin portal.

## System Architecture

The application is fully serverless, built on AWS and deployed with the CDK.

- **Frontend** — a single-page app hosted on S3 and served through CloudFront, which also routes wildcard tenant subdomains and proxies `/api/*` requests to the backend.
- **Auth** — a single Amazon Cognito User Pool for every tenant. A custom `custom:hospital_id` claim on each user's token is what tenant isolation is actually built on — not separate user pools per hospital.
- **API Layer** — API Gateway, secured with a Cognito authorizer on (almost) every route, in front of one Lambda function per resource.
- **Backend Compute** — AWS Lambda for every piece of business logic: CRUD APIs, ride booking, Epic polling, Veradigm CSV processing, and the SFTP identity provider.
- **Database** — Amazon DynamoDB: five tables (Hospitals, Appointments, Patients, Settings, SFTP Logs), all partitioned by `hospital_id` (Hospitals is partitioned by its own `id`). See [EHR-Database-Architecture.md](EHR-Database-Architecture.md).
- **Integrations**:
  - **Epic** — SMART on FHIR backend service auth (per-hospital JWKS), polled on a schedule. See [EPIC-Integration-Setup-Process.md](EPIC-Integration-Setup-Process.md).
  - **Veradigm** — AWS Transfer Family SFTP server with a Lambda-backed custom identity provider, S3 + EventBridge triggering CSV processing. See [Veradigm-Integration-Multi-Tenant.md](Veradigm-Integration-Multi-Tenant.md).
  - **Via** — a single, shared (not per-tenant) account used both for on-demand ride booking and for automatically matching existing appointments to rides. See [Via-Integration-Architecture.md](Via-Integration-Architecture.md).
- **Secrets** — AWS Secrets Manager: one secret per hospital for Epic/Veradigm credentials, and a handful of shared secrets (Via, Google Maps) used across every tenant.

## Data Flow

**1. User access & API flow**
A user logs in at their hospital's subdomain → Cognito issues a JWT carrying their `custom:hospital_id` → the frontend sends that token to API Gateway → the target Lambda reads the tenant from the token and scopes every DynamoDB read/write to it.

**2. Epic polling flow**
An EventBridge rule invokes the Epic data-populator Lambda every few minutes → it finds every hospital flagged as an Epic tenant → for each, it authenticates using that hospital's Epic credentials (from Secrets Manager) and pulls appointments for patients who are linked to Via → new/updated appointments are written to DynamoDB.

**3. Veradigm ingestion flow**
A Veradigm system uploads a CSV over SFTP into its hospital's designated S3 subfolder → the upload fires an S3 event through EventBridge → the data-populator Lambda resolves which hospital the subfolder belongs to, parses and validates the CSV, and batch-writes appointment and patient records tagged with that `hospital_id`.

**4. Ride-matching flow**
On its own schedule, a Lambda re-scans open appointments and, for any patient linked to a Via rider, checks Via for a trip that lines up with the appointment's time and location — attaching it to the appointment if found, or leaving it open for staff to book manually from the Dashboard.

## Documentation Index

| Doc | What's in it |
|---|---|
| [EHR-Multi-Tenant-Deployment-Steps.md](EHR-Multi-Tenant-Deployment-Steps.md) | Deploying the stack from scratch — environment setup, Lambda layers, CDK deploy, dashboard build, custom domain. |
| [EHR-Database-Architecture.md](EHR-Database-Architecture.md) | The five DynamoDB tables, their keys/GSIs, and how queries stay tenant-isolated. |
| [API-Documentation.md](API-Documentation.md) | Every REST endpoint — auth model, request/response shapes, per-endpoint authorization rules. |
| [EPIC-Integration-Setup-Process.md](EPIC-Integration-Setup-Process.md) | Registering a hospital with Epic: credentials, SSH/JWKS setup, the incoming API list. |
| [Veradigm-Integration-Multi-Tenant.md](Veradigm-Integration-Multi-Tenant.md) | Onboarding a Veradigm provider, the required CSV format, and the SFTP-to-DynamoDB data flow. |
| [Via-Integration-Architecture.md](Via-Integration-Architecture.md) | How rides get booked on-demand vs. automatically matched to appointments. |
| [Admin-and-Tenant-Users-Guide.md](Admin-and-Tenant-Users-Guide.md) | Using the admin portal (tenants, users) and the tenant dashboard (day-to-day ride coordination). |
| [Domain-Settings-Multi-Tenant-EHR-Setup.md](Domain-Settings-Multi-Tenant-EHR-Setup.md) | Pointing a custom domain at the deployment — ACM certificates, CloudFront, DNS records. |

**New here?** Read this page first, then the deployment guide if you're standing up an environment, or the Admin and Tenant Users Guide if you're just using one.
