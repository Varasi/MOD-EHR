# Via Ride-Booking Integration — Architecture

## Overview

Via is the transportation provider behind every ride in the system. Unlike Epic and Veradigm, Via is **not multi-tenant credentialed** — there is a single Via account (one client ID/secret/API key) shared across the entire deployment, configured once per environment rather than once per hospital.

The integration has two independent flows that both write into the same `ride` field on an Appointment record:

1. **On-demand booking** — a hospital staff member manually books a specific ride through the Book Trip page.
2. **Automatic ride matching** — a background job periodically scans existing appointments and links them to a ride the patient (or someone else) already has on the books with Via, without anyone booking anything through this app.

## Authentication & Credentials

`Via` (`health_connector_base/via.py`) authenticates with an OAuth2 `client_credentials` grant against a hardcoded Cognito token endpoint (`https://trip-api.auth.us-east-1.amazoncognito.com/oauth2/token`), using HTTP Basic Auth with the client ID/secret. Every subsequent call sends the resulting bearer token plus an `x-api-key` header to `https://us-east-1.trip-api.ridewithvia.com`.

- `via_client_id`, `via_client_secret`, and `via_api_key` are read from AWS Secrets Manager, one secret each, deployed once per environment (not per hospital) from the `SECRETS` block in the environment config yaml.
- The Via auth URL and API base URL are **hardcoded constants in `via.py`**, even though `via_auth_url`/`via_api_url` also exist as fields in the config template — those two config values are unused today.
- The OAuth token is cached only on the `Via` instance itself, and a fresh `Via()` instance is created on essentially every call site — so in practice the token is re-fetched on nearly every invocation rather than cached across Lambda invocations.
- `set_trip_request_body` also falls back to a `sub_service_name` secret when the caller doesn't supply one — this key isn't part of the standard config template's `SECRETS` block, so it has to be added to Secrets Manager by hand if you want that fallback to work.

## Flow 1: On-Demand Booking

Entry point: the **Book Trip** page (`bookTrip.html`/`.js`), reachable directly from the nav or via a "Book Ride" button on the Dashboard for any leg whose `trip_status` is `"Not Requested"`. Hidden for the `ViewOnly` role; otherwise available in every environment (it isn't gated to Development the way the Appointments/Patients/Logs pages are).

1. **Patient selection** — staff pick an existing patient (pre-fills name/phone/email/Via rider ID) or enter a guest's details manually. Arriving from the Dashboard's "Book Ride" button pre-fills the patient, direction, appointment address, and a time (with a 15-minute buffer added for return trips).
2. **Validate Patient** (`POST /api/validate_patient`) — before a trip can be requested, the frontend must successfully validate the rider against Via. The backend calls `Via().get_rider_validation()`, matching by rider ID, then email, then phone (checked in that precedence), and cross-checks whatever additional fields were supplied (name, phone, email) against Via's record — mismatches or zero/multiple matches come back as a 400 with a specific message (`NoSuchRiderError`, or a list of which fields didn't match). A successful validation also returns which of the rider's `sub_services` (`Health_Connector` / `NEMT`) applies, which the frontend carries forward silently and resubmits as `sub_service` on the actual booking call.
3. **Book Trip** (`POST /api/trip_booking`) — once validated, submitting the form:
   - Geocodes both the pickup and destination addresses via the Google Maps Geocoding API.
   - Builds a Via trip-request body: registered riders are booked by `rider_id`; guests are booked with inline `passenger_info` (name/phone/email) instead. Guest/PCA counts and a WAV (wheelchair-accessible vehicle) flag are translated into Via's `additional_passengers` and `trip_properties` fields. Direction (`To Appointment` vs `From Appointment`) determines whether the requested time is sent as `arrive_at` or `depart_at`.
   - Calls Via in sequence: `request_new_trip()` → `book_trip()` → `get_trip_details()`, returning the confirmed trip's origin/destination/status to the UI. Any failure at any step (including "no vehicle available") surfaces as a 500 with Via's message.
   - API Gateway's ~29s timeout can be reached before Via responds; the frontend treats a `504` as "probably still booking in the background — check the dashboard shortly" rather than a hard failure.

This flow **creates a new Via trip** — it's for booking a ride that doesn't exist yet. It does not, by itself, attach anything to an Appointment record; that link only appears once the automatic matching flow (below) notices the new trip.

## Flow 2: Automatic Ride Matching

This is the mechanism that actually populates an appointment's `ride` field without anyone manually booking through this app — it looks for a trip the patient already has with Via (booked directly with Via, or booked through Flow 1) and attaches it to the matching appointment leg.

Implemented by `get_matching_ride` (to-appointment leg) and `get_matching_return_ride` (from-appointment leg) in `datapopulator_lambda/lambda_handler.py`. For a given appointment and a list of the patient's current Via trips:

- **Time window:** a trip's `dropoff_eta` (to-appointment) or `pickup_eta` (from-appointment) must fall within a configurable window around the appointment's `start_time`/`end_time`. The window is controlled per-hospital by two Settings records, `prior_period` and `subsequent_period` (entered in minutes on the Settings page); if unset, it defaults to **90 minutes early / 15 minutes late**.
- **Location proximity:** the trip's dropoff (or pickup) coordinates must be within **1 km** of the appointment's address — checked by live-geocoding the appointment address via Google Maps on every candidate comparison.
- **Direction sanity check:** a candidate "to appointment" ride is rejected if its pickup point is actually closer to the appointment address than its dropoff point (i.e., it's heading away, not toward, the hospital) — and the mirror check for the return leg.
- Among all candidates that pass, the one with the smallest time difference wins.
- If no candidate matches, the leg falls back to the `VIA_RIDE_MOCK` placeholder (`trip_status: "Not Requested"`), which is what triggers the "Book Ride" button on the Dashboard.
- When a leg's matched `trip_id` is unchanged from a previous run, any `driver_info`/`vehicle_info` already recorded for it is preserved rather than being overwritten — this only matters once the trip is actually assigned a driver by Via, which happens after matching, not at match time.

### Where this runs

- **At Veradigm CSV ingestion** (`veradigm_with_via`): if the patient already has a `via_rider_id` linked *at the moment the file is processed*, the newly-created appointment is matched immediately using that rider's current trips. A brand-new patient created fresh from the same CSV row has no `via_rider_id` yet, so their appointment is saved unmatched.
- **On a ~2-minute EventBridge schedule** (`datapopulator_lambda`'s `process_all`): re-scans every appointment with status `Booked` and a future end time — Epic-sourced and Veradigm-sourced alike — and re-runs the matching for any patient who now has a `via_rider_id`, including ones linked after their appointment was first created.

> **Note on Epic + this Lambda:** `datapopulator_lambda` also has an `epic_with_via` method that, on paper, fetches live appointments from Epic's FHIR API on the same schedule — but it only runs when the `MOCK_DATA` environment variable is unset, and the CDK stack never sets it. `os.environ.get("MOCK_DATA", True)` evaluates to `True` unless that env var is present, so the deployed Lambda always uses `AppointmentsMapperWithViaMock`, whose `epic_with_via` override does ride-matching over already-stored appointments instead of calling Epic at all. In practice, all live Epic fetching happens through the separate `epic_data_populator_lambda`; this Lambda's scheduled tick is only ever doing ride-matching (`process_all`), regardless of provider.

## Data Model

`Appointment.ride` is a JSON attribute shaped as two independent legs:

```json
{
  "to_appointment": { "trip_status": "...", "pickup": {...}, "pickup_eta": ..., "dropoff": {...}, "dropoff_eta": ..., "driver_info": {...}, "vehicle_info": {...} },
  "from_appointment": { "...": "same shape" }
}
```

Each leg defaults to `{"trip_status": "Not Requested", "pickup": {}, "pickup_eta": "TBD", "dropoff": {}, "dropoff_eta": "TBD"}` until a match is found. `driver_info`/`vehicle_info` are only present once Via has assigned a driver to the matched trip, fetched via `get_ride_details()`.

## Efficiency Notes

- `Via.get_trips()` queries `/trips/get` once per status in `["CONFIRMED", "FINISHED", "ASSIGNED", "ARRIVED", "BOARDED"]` — five calls per rider per fetch — then calls `/trips/details/` once per trip returned across all five. A rider with several active trips can generate a double-digit number of Via API calls in a single matching pass.
- Every candidate-trip comparison during matching triggers a live Google Maps geocode of the appointment address (not cached), so the geocoding cost scales with `(appointments × candidate trips)` on every ~2-minute cycle, not just once per appointment.
- Matching only runs against patients with a `via_rider_id` linked and appointments still in `Booked` status with a future end time — patients never linked to Via, and appointments already resolved (completed/cancelled) or in the past, are excluded from every cycle.
