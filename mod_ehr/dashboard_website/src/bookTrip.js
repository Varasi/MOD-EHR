import {
    getAccessToken,
    logoutUser,
    getUserGroup,
    tablePaginationNavigationHandler,
    preRender,
    postRender,
    BASE_URL,
    HIRTA_CONTACT,
    toggleSideNavBar,
    getAccesstokenAndCustomAttribute,
    loadTenantBranding,
    CUSTOM_DOMAIN,
    getIdToken,
    toggleAlertMessage,
    GOOGLE_MAPS_KEY
} from "./common";
import { DateTime } from "luxon"; 

$(document).ready(async function () {
    $('head').append(`<script src = "https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}&libraries=places&callback=googleMapsAutoComplete" async defer></script>`);
    $("#assistance-text-dashboard").append(HIRTA_CONTACT);
    $("#result-hirta-contact").text(HIRTA_CONTACT);
    const [accessToken, hospital_id] = await getAccesstokenAndCustomAttribute("custom:hospital_id");
    const idToken = await getIdToken();
    const hostname = window.location.hostname;
    const dns_tenant = hostname.split('.')[0];
    const config = await loadTenantBranding(hospital_id);
    
    if (config.subdomain !== dns_tenant) {
        alert("You are not authorized for this hospital.");
        await logoutUser();
        window.location.replace(`https://${config.subdomain}${CUSTOM_DOMAIN}/dashboard.html`);
    }
    // preRender();
    toggleSideNavBar();
    const userRole = await getUserGroup();
    if (userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
        $("#appointments-nav").removeClass("d-none").addClass("visible");
        $("#patients-nav").removeClass("d-none").addClass("visible");
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("d-none").addClass("visible");
    }else{
        $("#user-management-nav").removeClass("visible").addClass("d-none");
    }
    if (hospital_id === "admin") {
        $("#hospitals-nav").removeClass("d-none").addClass("visible");
    } else {
        $("#hospitals-nav").removeClass("visible").addClass("d-none");
        
    }
    $("#logout").click(logoutUser);

     // 1. Initialize Select2 for the patient search dropdown
    $('#patientSearch').select2({
        theme: 'bootstrap-5',
        width: '100%',
        placeholder: "Search for name or patient ID...",
        allowClear: true
    });
    let patientsList = [];

    // 2. Fetch patients from the API
    try {
        $('#timeLoader').removeClass("d-none")
        const response = await fetch(`${BASE_URL}/api/patients/?hospital_id=${hospital_id}`, {
            headers: {
                'Authorization': accessToken,
                'X-Id-Token': idToken
            }
        });
        if (response.ok) {
            patientsList = await response.json();
            // Populate the dropdown
            patientsList.forEach(patient => {
                const option = new Option(`${patient.name} (${patient.patient_id})`, patient.patient_id, false, false);
                $(option).attr('data-via-rider-id', patient.via_rider_id || '');
                $('#patientSearch').append(option);
            });
            $('#patientSearch').val(null).trigger('change');
            $('#timeLoader').addClass("d-none")
        }
    } catch (error) {
        console.error("Error fetching patients:", error);
        toggleAlertMessage("Error fetching patients. Please try again.", "danger");
        $('#timeLoader').addClass("d-none")
    } finally{
        $('#timeLoader').addClass("d-none")
    }

    // Fills all patient form fields from a patient object.
    // Called both from the change handler and from the prefill path.
    function applyPatientToForm(patient) {
        const nameParts = patient.name.split(' ');
        $('#patientFirstName').val(nameParts[0] || '').removeClass('is-invalid');
        $('#patientLastName').val(nameParts.slice(1).join(' ') || '').removeClass('is-invalid');
        $('#patientphone').val(patient.phone || '').removeClass('is-invalid');
        $('#patientEmail').val(patient.email || '').removeClass('is-invalid');
        if (!patient.email) {
            $('#patientEmailCheck').prop('checked', true);
            $('#patientEmail').prop('disabled', true);
        } else {
            $('#patientEmailCheck').prop('checked', false);
            $('#patientEmail').prop('disabled', false);
        }
        $('#viaRiderId').val(patient.via_rider_id || '');
        if (patient.address || patient.home_address) {
            const addr = patient.address || patient.home_address;
            if ($('#tripDirection').val() === 'To Appointment') {
                if (!$('#tripPickupAddress').val()) $('#tripPickupAddress').val(addr);
            } else {
                if (!$('#tripDestinationAddress').val()) $('#tripDestinationAddress').val(addr);
            }
        }
    }

    // 3. Auto-fill form fields when a patient is selected
    $('#patientSearch').on('change', function() {
        const selectedId = $(this).val();
        if (selectedId) {
            const patient = patientsList.find(p => String(p.patient_id) === String(selectedId));
            if (patient) applyPatientToForm(patient);
        } else {
            // Clear the fields when the dropdown is cleared/unselected
            $('#patientFirstName').val('').removeClass('is-invalid');
            $('#patientLastName').val('').removeClass('is-invalid');
            $('#patientphone').val('').removeClass('is-invalid');
            $('#patientEmail').val('').removeClass('is-invalid');
            $('#patientEmailCheck').prop('checked', false);
            $('#patientEmail').prop('disabled', false);
            $('#viaRiderId').val('');
        }
    });
    // remove validated tag if input is chnaged
    $('.patient-input').on('input', function () {
        $('#patientValidatedMsg').addClass('d-none');
    });

    // 4. Disable email input if "Patient does not have an email address" is checked
    $('#patientEmailCheck').on('change', function() {
        $('#patientEmail').prop('disabled', $(this).is(':checked'));
        if ($(this).is(':checked')) {
            $('#patientEmail').val('');
        }
    });

    // 5. Update the text display when "Trip Direction" changes
    $('#tripDirection').on('change', function() {
        const direction = $(this).val();
        const $display = $('#tripDirectionDisplay');
        const $timeLabel = $('label[for="tripDropoffTime"]');
        const $timeHelp = $('#tripDropoffTime').next('.form-text');

        if (direction === 'To Appointment') {
            $display.removeClass('from-appt').addClass('to-appt');
            $display.find('.direction-label').text('To Appointment');
            $timeLabel.html('Requested Dropoff Time <span class="text-danger">*</span>');
            $timeHelp.text('Time patient needs to arrive by');
        } else {
            $display.removeClass('to-appt').addClass('from-appt');
            $display.find('.direction-label').text('From Appointment');
            $timeLabel.html('Requested Pickup Time <span class="text-danger">*</span>');
            $timeHelp.text('Time patient needs to be picked up');
        }
    });

    // 6. Clear Form logic
    $('#clearFormBtn').on('click', function() {
        $('input[type="text"], input[type="email"], input[type="tel"], input[type="time"], textarea').val('');
        $('input[type="text"], input[type="email"], input[type="tel"], input[type="time"], textarea').val('').removeClass('is-invalid');
        $('#patientSearch').val(null).trigger('change');
        $('#patientEmailCheck').prop('checked', false).trigger('change');
        $('#tripDirection').val('To Appointment').trigger('change');
        $('#mobilityEquipment').val('None');
        $('#patientValidatedMsg').addClass('d-none');
        $('#viaRiderId').val('');
    });

    // 7. Validate Patient logic
    $('#validatePatientBtn').on('click', async function() {
        let isValid = true;
        $('#patientValidatedMsg').addClass('d-none');
        $('#validatePatientBtn').prop('disabled', true);
        const checkField = (selector) => {
            const el = $(selector);
            if (!el.val() || !el.val().trim()) {
                el.addClass('is-invalid');
                isValid = false;
            } else {
                el.removeClass('is-invalid');
            }
        };

        checkField('#patientFirstName');
        checkField('#patientLastName');
        checkField('#patientphone');
        
        if (!$('#patientEmailCheck').is(':checked')) {
            checkField('#patientEmail');
        } else {
            $('#patientEmail').removeClass('is-invalid');
        }

        if (isValid) {
            
            $('#patientLoading').removeClass('d-none');
            const patientData = {
                first_name: $('#patientFirstName').val(),
                last_name: $('#patientLastName').val(),
                phone: '+1'+ $('#patientphone').val(),
                email: $('#patientEmailCheck').is(':checked') ? null : $('#patientEmail').val(),
                via_rider_id: $('#viaRiderId').val() || null
            };
            
            console.log("Sending patient details to backend for validation:", patientData);
            
            // API call to send the validated patient data to the backend
            
            try {
                const response = await fetch(`${BASE_URL}/api/validate_patient`, {
                    method: 'POST',
                    headers: {
                        'Authorization': await getAccessToken(),
                        'X-Id-Token': await getIdToken(),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(patientData)
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.message);  
                }
                $('#patientValidatedMsg').removeClass('d-none');
                $('#patientLoading').addClass('d-none');
                toggleAlertMessage("Patient validated successfully!", "success");
            } catch (error) {
                $('#patientValidatedMsg').addClass('d-none');
                $('#patientLoading').addClass('d-none');
                if (error.message === "NoSuchRiderError"){
                    toggleAlertMessage("Rider not found. Please check the details and try again.", "danger")
                }else if(error.message.includes("fields are incorrect")){
                    toggleAlertMessage(error.message, "danger");
                }else{
                    toggleAlertMessage("Failed to validate patient. Please check the details and try again.", "danger");
                }
            }
        } else {
            $('#patientValidatedMsg').addClass('d-none');
            toggleAlertMessage("Please fill in all required fields.","danger");
        }
        $('#validatePatientBtn').prop('disabled', false);
    });

    // Remove validation styling when typing
    $('input[type="text"], input[type="email"], input[type="tel"]').on('input', function() {
        $(this).removeClass('is-invalid');
    });

    // postRender();
    //submit form logic
    $('#submitTripBtn').on('click', async function() {
        // 1. Check if patient is validated
        if ($('#patientValidatedMsg').hasClass('d-none')) {
            toggleAlertMessage("Please validate the patient before submitting.", "danger");
            return;
        }

        // 2. Check required trip fields
        let isValid = true;
        const checkField = (selector) => {
            const el = $(selector);
            if (!el.val() || !el.val().trim()) {
                el.addClass('is-invalid');
                isValid = false;
            } else {
                el.removeClass('is-invalid');
            }
        };

        checkField('#tripPickupAddress');
        checkField('#tripDropoffTime');
        checkField('#tripDestinationAddress');

        if (!isValid) {
            toggleAlertMessage("Please fill in all required trip details.", "danger");
            return;
        }

        const timeValue = $('#tripDropoffTime').val();
        let epoch = null;
        let dt = null;
        if(timeValue){
            const today = new Date().toLocaleDateString('en-CA', { timeZone: "America/Chicago" });
            dt = DateTime.fromFormat(
                `${today} ${timeValue}`,
                "yyyy-MM-dd HH:mm",
                { zone: "America/Chicago" }
            );
            console.log("Correct time:", dt.toString());
            epoch = Math.floor(dt.toSeconds());
        }

        // 3. Gather all values for the backend
        const tripRequestData = {
            hospital_id: hospital_id,
            first_name: $('#patientFirstName').val(),
            last_name: $('#patientLastName').val(),
            phone: '+1' + $('#patientphone').val(),
            email: $('#patientEmailCheck').is(':checked') ? null : $('#patientEmail').val(),
            via_rider_id: $('#viaRiderId').val() || null,
            trip_direction: $('#tripDirection').val(),
            pickup_address: $('#tripPickupAddress').val(),
            appt_time: epoch,
            destination_address: $('#tripDestinationAddress').val(),
            mobility_equipment: $('#mobilityEquipment').val(),
            additional_notes_pickup: $('#additionalNotespickup').val(),
            additional_notes_dropoff: $('#additionalNotesdropoff').val()
        };

        // 4. Send request to backend
        const $btn = $(this);
        const originalText = $btn.text();
        $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-2"></span>Submitting...');

        try {
            // NOTE: Ensure your API Gateway and CDK Stack have the '/book_trip' endpoint configured
            const response = await fetch(`${BASE_URL}/api/trip_booking`, {
                method: 'POST',
                headers: {
                    'Authorization': await getAccessToken(),
                    'X-Id-Token': await getIdToken(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(tripRequestData)
            });
            
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || "Failed to book trip");
            }
            
            toggleAlertMessage("Trip booked successfully!", "success");
            $('#booking-form').addClass('d-none');
            $('#booking-response').removeClass('d-none');

            const resData = data.data;
            const formatEta = (epochSec) => {
                if (!epochSec) return "N/A";
                return new Date(epochSec * 1000).toLocaleTimeString("en-US", {
                    timeZone: "America/Chicago",
                    hour:     "2-digit",
                    minute:   "2-digit",
                    hour12:   true,
                });
            };

            $('#result-name').text(`${tripRequestData.first_name} ${tripRequestData.last_name}`);
            $('#result-phone').text(tripRequestData.phone);
            $('#result-email').text(tripRequestData.email || "N/A");
            if (tripRequestData.trip_direction === 'To Appointment') {
                $('#result-direction').removeClass('from-appt').addClass('to-appt');
                $('#result-direction').find('.direction-label').text('To Appointment');
            } else {
                $('#result-direction').removeClass('to-appt').addClass('from-appt');
                $('#result-direction').find('.direction-label').text('From Appointment');
            }
            $('#result-pickup-address').text(resData.pickup?.description   || "-");
            $('#result-destination-address').text(resData.dropoff?.description || "-");
            $('#result-pickup-window').text(formatEta(resData.pickup_eta || "-"));
            $('#result-dropoff-time').text(formatEta(resData.dropoff_eta || "-"));
            $('#result-mobility-equipment').text(tripRequestData.mobility_equipment);
            $('#result-driver-pickup-notes').text(resData.pickup?.notes || "-");
            $('#result-driver-dropoff-notes').text(resData.dropoff?.notes || "-");

            $('#clearFormBtn').click();
        } catch (error) {
            console.error("Error booking trip:", error);
            toggleAlertMessage(error.message || "Error booking trip. Please try again.", "danger");
        } finally {
            $btn.prop('disabled', false).text(originalText);
        }
    });

    //result page home button logic
    $('#back-to-dashboard').click(function() {
        window.location.replace('dashboard.html');
    });
    $('#book-another-trip').click(function() {
        window.location.replace('bookTrip.html');
    });


    // Remove validation styling when typing in the trip fields
    $('#tripPickupAddress, #tripDropoffTime, #tripDestinationAddress').on('input change', function() {
        $(this).removeClass('is-invalid');
    });

    // Pre-fill form when arriving from the dashboard "Book Ride" button.
    // Data is stored in sessionStorage by dashboard.js before navigating here.
    const prefillRaw = sessionStorage.getItem("bookTrip_prefill");
    if (prefillRaw) {
        sessionStorage.removeItem("bookTrip_prefill");
        try {
            const { patient_id, direction, appt_location, appt_time } = JSON.parse(prefillRaw);

            // Set direction first — applyPatientToForm reads it to decide which address field to use.
            const tripDir = direction === "FROM APPT" ? "From Appointment" : "To Appointment";
            $('#tripDirection').val(tripDir).trigger('change');

            // Select the patient in the dropdown (updates the Select2 UI display).
            // Then directly call applyPatientToForm — avoids relying on Select2's change event
            // which does not reliably fire the jQuery handler when set programmatically.
            if (patient_id) {
                $('#patientSearch').val(String(patient_id)).trigger('change.select2');
                const patient = patientsList.find(p => String(p.patient_id) === String(patient_id));
                if (patient) applyPatientToForm(patient);
            }

            // Fill appointment location into the appropriate address field.
            // To Appointment  → appointment is the destination.
            // From Appointment → appointment is the pickup location.
            if (appt_location) {
                if (tripDir === "To Appointment") {
                    $('#tripDestinationAddress').val(appt_location);
                    $('#tripDestinationAddLabel').append(`<span class="ms-1" style="border: solid;padding-top: 0px;padding-left: 5px;padding-right: 5px;border-width: 0px;border-radius: 5px;background-color: #e8f0ff;color: #4272d0;">Auto-filled</span>`)
                    $('#tripDestContainer').append(`<div class="form-text">
                            Pre-filled from patient's facility -- edit if needed
                        </div>`)
                } else {
                    $('#tripPickupAddress').val(appt_location);
                    $('#tripPickupAddLabel').append(`<span class="ms-1" style="border: solid;padding-top: 0px;padding-left: 5px;padding-right: 5px;border-width: 0px;border-radius: 5px;background-color: #e8f0ff;color: #4272d0;">Auto-filled</span>`)
                    $('#tripPickupContainer').append(`<div class="form-text">
                            Pre-filled from patient's facility -- edit if needed
                        </div>`)
                }
            }


            // Pre-fill the time field from the appointment time.
            // start_time (TO APPT) or end_time (FROM APPT) is an ISO string; convert to HH:mm
            // in Chicago time so it matches what the <input type="time"> expects.
            if (appt_time && appt_time !== "TBD") {
                const d = new Date(appt_time);
                if (!isNaN(d.getTime())) {
                    const parts = new Intl.DateTimeFormat("en-US", {
                        timeZone: "America/Chicago",
                        hour:     "2-digit",
                        minute:   "2-digit",
                        hour12:   false,
                    }).formatToParts(d);
                    const hh = parts.find(p => p.type === "hour")?.value   || "00";
                    const mm = parts.find(p => p.type === "minute")?.value || "00";
                    $('#tripDropoffTime').val(`${hh}:${mm}`);
                }
            }
        } catch (e) {
            console.error("Failed to apply bookTrip prefill:", e);
        }
    }
})
