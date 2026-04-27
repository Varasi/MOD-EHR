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
    getIdToken
} from "./common";

const VIA_LEG_MOCK = {
    trip_status: "Not Requested",
    dropoff: {},
    dropoff_eta: "TBD",
    pickup: {},
    pickup_eta: "TBD",
};

/**
 * Normalises the ride field into an array of per-leg descriptors.
 * Handles both the new two-leg format { to_appointment, from_appointment }
 * and the legacy flat format { trip_status, ... }.
 */
function getRideLegs(ride) {
    if (!ride || "trip_status" in ride) {
        return [{ direction: "TO APPT", dirClass: "to-appt", ride: ride || VIA_LEG_MOCK }];
    }
    return [
        { direction: "TO APPT",   dirClass: "to-appt",   ride: ride.to_appointment   || VIA_LEG_MOCK },
        { direction: "FROM APPT", dirClass: "from-appt", ride: ride.from_appointment || VIA_LEG_MOCK },
    ];
}

function appointmentStatusHtml(status) {
    const dangerStatuses = ["Cancelled", "Declined"];
    const cls = dangerStatuses.includes(status) ? "lozenge-danger" : "lozenge-success";
    return `<span class="${cls}">${status}</span>`;
}

/** Safe for embedding inside an HTML attribute (e.g. data-*="..."). */
function escapeAttr(str) {
    return String(str ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

/** Safe for embedding as textarea text content. */
function escapeHtml(str) {
    return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderHospitalColumn(accessToken, idToken) {
    return new Promise((resolve) => {
        let hospitals_map = {};
        const xhr = new XMLHttpRequest();
        xhr.open("GET", `${BASE_URL}/api/hospitals/`);
        xhr.setRequestHeader("Authorization", accessToken);
        xhr.setRequestHeader("X-Id-Token", idToken);
        xhr.onreadystatechange = function () {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                const hospitals = JSON.parse(xhr.responseText);
                for (let hospital of hospitals) {
                    hospitals_map[hospital.id] = hospital.name;
                }
                resolve(hospitals_map);
            } else if (xhr.status !== 200) {
                $("#Loader").remove();
                if ($("#StateChange .emptyState").length === 0) {
                    $("#StateChange").append(
                        `<div class="emptyState">
            <img src="./assets/ERROR.svg" alt="" />
            <h3 class="no-data">ERROR </h3>
            <p>An error occurred while retrieving data</p>
        </div>`
                    );
                }
            }
        };
        xhr.send();
    });
}

$(document).ready(async function () {
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
    preRender();
    toggleSideNavBar();
    const userRole = await getUserGroup();
    if (userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
        $("#appointments-nav").removeClass("invisible").addClass("visible");
        $("#patients-nav").removeClass("invisible").addClass("visible");
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("invisible").addClass("visible");
    }
    if (hospital_id === "admin") {
        $("#hospitals-nav").removeClass("invisible").addClass("visible");
    } else {
        $("#hospitals-nav").removeClass("visible").addClass("invisible");
    }
    $("#logout").click(logoutUser);

    let hospital_map = {};
    if (hospital_id === "admin") {
        hospital_map = await renderHospitalColumn(accessToken, idToken);
        console.log("Hospital Map: ", hospital_map);
    }
    $("#assistance-text-dashboard").append(HIRTA_CONTACT);
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/dashboard/?hospital_id=${hospital_id}`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("X-Id-Token", idToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            $("#Loader").remove();

            // Appointment-level cells are marked with "appt-span-col".
            // drawCallback uses this class to rowspan them across both ride legs
            // without depending on fragile column-index arithmetic.
            const APPT_SPAN_CLASS = "appt-span-col";

            let columns_data = [
                // Appointment-level columns: both leg rows share the same value,
                // so sorting by these is safe — pairs stay adjacent.
                { data: "customer",             title: "Customer",             className: APPT_SPAN_CLASS },
                { data: "appointment",          title: "Appointment",          className: APPT_SPAN_CLASS },
                // { data: "appointment_time",     title: "Appointment Time",     className: APPT_SPAN_CLASS },
                // { data: "appointment_location", title: "Appointment Location", className: APPT_SPAN_CLASS },
                // { data: "appointment_status",   title: "Appointment Status",   className: APPT_SPAN_CLASS },
                // Leg-specific / interactive columns: values differ between legs,
                // so sorting would break the TO/FROM pair adjacency — disabled.
                { data: "coordinator_notes",         title: "Coordinator Notes",    className: APPT_SPAN_CLASS, orderable: false },
                { data: "alt_transport_confirmed_to", orderable: false, title: `Alternative Transportation Confirmed <svg class="alt-transport-filter-icon" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" title="Toggle: hide confirmed"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>` },
                { data: "direction",            title: "Direction",            orderable: false },
                { data: "trip_status",          title: "Trip Status",          orderable: false },
                { data: "pickup_time",          title: "Pickup Time",          orderable: false },
                { data: "drop_off_time",        title: "Drop Off Time",        orderable: false },
                { data: "driver_vehicle_info",  title: "Driver/Vehicle",       orderable: false },
            ];
            if (hospital_id === "admin") {
                columns_data.push({
                    data: "hospital_id",
                    title: "Hospital",
                    render: function (data) { return hospital_map[data] || data; },
                });
            }
            if (userRole === "HIRTAOperationsStaff" || userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
                columns_data.push(
                    { data: "pick_up_note",  title: "Pick Up Note",  orderable: false },
                    { data: "pickup_spot",   title: "Pick Up Spot",  orderable: false },
                    { data: "drop_off_spot", title: "Drop Off Spot", orderable: false },
                    { data: "drop_off_note", title: "Drop Off Note", orderable: false }
                );
            }

            // Hidden columns used only as secondary sort keys to keep TO/FROM pairs
            // adjacent regardless of which appointment-level column the user sorts by.
            columns_data.push(
                { data: "_appointment_id", title: "", visible: false, searchable: false },
                { data: "_leg_order",      title: "", visible: false, searchable: false }
            );
            const apptIdColIdx  = columns_data.findIndex(c => c.data === "_appointment_id");
            const legOrderColIdx = columns_data.findIndex(c => c.data === "_leg_order");

            let data = [];
            const dashboardRawData = JSON.parse(xhr.responseText);

            for (const appointmentRecord of dashboardRawData) {
                console.log(appointmentRecord);
                const legs = getRideLegs(appointmentRecord.ride);

                for (const { direction, dirClass, ride } of legs) {
                    const isNotRequested = ride.trip_status === "Not Requested";

                    const driver_name = "driver_info" in ride
                        ? (ride.driver_info.first_name + " " + ride.driver_info.last_name).trim()
                        : "";
                    const vehicle_number = "vehicle_info" in ride
                        ? ride.vehicle_info.license_plate.trim()
                        : "";
                    const driver_vehicle_info = driver_name === "" && vehicle_number === ""
                        ? "TBD"
                        : driver_name + "/" + vehicle_number;

                    const tripStatusHtml = isNotRequested
                        ? `<div class="d-flex flex-column gap-1 align-items-start">
                             <span class="lozenge-danger">Not Requested</span>
                             <button class="book-ride-btn button-primary mt-1"
                                          data-appt-id="${appointmentRecord.id}"
                                          data-patient-id="${appointmentRecord.patient_id}">Book Ride</button>
                           </div>`
                        : `<span class="lozenge-success">${ride.trip_status}</span>`;
                    
                    const appointment_time = appointmentRecord.start_time === "TBD"
                            ? "TBD"
                            : new Date(appointmentRecord.start_time).toLocaleString("en-US", { timeZone: "America/Chicago" })
                    const appointment_location = appointmentRecord.location
                    const appointment_status = appointmentStatusHtml(appointmentRecord.status)


                    const row_data = {
                        // Internal fields — not mapped to a column, used in callbacks.
                        _appointment_id:     appointmentRecord.id || (appointmentRecord.patient_id + "_" + appointmentRecord.start_time),
                        _is_first_leg:       direction === "TO APPT",
                        _trip_not_requested: isNotRequested,
                        // Both legs carry the full appointment-level confirmed state so the
                        // hide-confirmed filter can evaluate either row independently.
                        _alt_confirmed_to:   appointmentRecord.alt_transport_confirmed_to   || false,
                        _alt_confirmed_from: appointmentRecord.alt_transport_confirmed_from || false,
                        _appointment_location: appointment_location,
                        // 0 = TO APPT, 1 = FROM APPT — used as a hidden secondary sort key
                        // to keep both leg rows of the same appointment adjacent after any sort.
                        _leg_order:          direction === "TO APPT" ? 0 : 1,

                        // Appointment-level columns (rowspanned across both legs).
                        customer:             appointmentRecord.patient_name,
                        // appointment_time:     appointmentRecord.start_time === "TBD"
                        //     ? "TBD"
                        //     : new Date(appointmentRecord.start_time).toLocaleString("en-US", { timeZone: "America/Chicago" }),
                        // appointment_location: appointmentRecord.location,
                        // appointment_status:   appointmentStatusHtml(appointmentRecord.status),
                        appointment: `<div class="appt-cell">
                                         <span class="appt-time">${appointment_time}</span>
                                         <span class="appt-location">${escapeHtml(String(appointment_location ?? ""))}</span>
                                         ${appointment_status}
                                     </div>`,

                        // Rendered as an editable textarea only on the first-leg row.
                        // The second-leg cell is hidden by drawCallback (rowspan), so its
                        // value is irrelevant — we leave it empty to avoid a duplicate textarea.
                        coordinator_notes: direction === "TO APPT"
                            ? `<textarea
                                   class="coordinator-notes-input form-control"
                                   rows="2"
                                   placeholder="Add notes…"
                                   data-appt-id="${escapeAttr(appointmentRecord.id)}"
                                   data-hospital-id="${escapeAttr(appointmentRecord.hospital_id)}"
                               >${escapeHtml(appointmentRecord.coordinator_notes)}</textarea>`
                            : "",

                        // Each leg gets its own checkbox mapped to its own model field.
                        alt_transport_confirmed_to: direction === "TO APPT"
                            ? `<div class="alt-transport-cell">
                                   <input type="checkbox"
                                          class="alt-transport-checkbox"
                                          data-appt-id="${escapeAttr(appointmentRecord.id)}"
                                          data-hospital-id="${escapeAttr(appointmentRecord.hospital_id)}"
                                          data-field="alt_transport_confirmed_to"
                                          ${appointmentRecord.alt_transport_confirmed_to ? "checked" : ""} />
                               </div>`
                            : `<div class="alt-transport-cell">
                                   <input type="checkbox"
                                          class="alt-transport-checkbox"
                                          data-appt-id="${escapeAttr(appointmentRecord.id)}"
                                          data-hospital-id="${escapeAttr(appointmentRecord.hospital_id)}"
                                          data-field="alt_transport_confirmed_from"
                                          ${appointmentRecord.alt_transport_confirmed_from ? "checked" : ""} />
                               </div>`,

                        // Leg-specific columns.
                        direction:           `<div class="direction-cell ${dirClass}"><span class="direction-label">${direction}</span></div>`,
                        trip_status:         tripStatusHtml,
                        pickup_time:         ride.pickup_eta === "TBD"
                            ? "N/A"
                            : new Date(ride.pickup_eta * 1000).toLocaleString("en-US", { timeZone: "America/Chicago" }),
                        drop_off_time:       ride.dropoff_eta === "TBD"
                            ? "N/A"
                            : new Date(ride.dropoff_eta * 1000).toLocaleString("en-US", { timeZone: "America/Chicago" }),
                        driver_vehicle_info,
                        hospital_id:         appointmentRecord.hospital_id,

                        // Role-specific columns — populated below when the user has access.
                        pick_up_note:  "N/A",
                        pickup_spot:   "N/A",
                        drop_off_spot: "N/A",
                        drop_off_note: "N/A",
                    };

                    if (userRole === "HIRTAOperationsStaff" || userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
                        row_data.pick_up_note  = "notes"   in ride.pickup  ? ride.pickup.notes    : "N/A";
                        row_data.pickup_spot   = "address" in ride.pickup  ? ride.pickup.address  : "N/A";
                        row_data.drop_off_note = "notes"   in ride.dropoff ? ride.dropoff.notes   : "N/A";
                        row_data.drop_off_spot = "address" in ride.dropoff ? ride.dropoff.address : "N/A";
                    }

                    data.push(row_data);
                }
            }

            // Tracks whether the "Hide Confirmed" filter is active.
            let hideConfirmedPatients = false;
            let filterApptLocation = "";
            let filterDropoffSpot = "";
            // Custom search: hide appointments where both legs are fully confirmed.
            // Custom search: handles hide confirmed, appointment location, and drop off spot filtering.
            // The settings.nTable guard prevents this from leaking into other tables.
            $.fn.dataTable.ext.search.push(function (settings, _data, _idx, rowData) {
                if (settings.nTable !== document.getElementById("mod_ehr")) return true;
                
                if (hideConfirmedPatients && (rowData._alt_confirmed_to && rowData._alt_confirmed_from)) {
                    return false;
                }

                if (filterApptLocation && !(String(rowData._appointment_location || "").toLowerCase().includes(filterApptLocation.toLowerCase()))) {
                    return false;
                }

                if (filterDropoffSpot && !(String(rowData.drop_off_spot || "").toLowerCase().includes(filterDropoffSpot.toLowerCase()))) {
                    return false;
                }

                return true;
            });

            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
            console.log(userRole);

            const table = $("#mod_ehr").DataTable({
                data: data,
                columns: columns_data,

                // After any user-driven sort, always secondary-sort by appointment ID
                // then leg order so TO/FROM pairs stay adjacent for the rowspan logic.
                orderFixed: { post: [[apptIdColIdx, "asc"], [legOrderColIdx, "asc"]] },

                createdRow: function (row, rowData) {
                    if (rowData._trip_not_requested) {
                        $(row).addClass("bg-danger-light");
                    } else {
                        $(row).addClass("bg-success-light");
                    }
                },

                drawCallback: function () {
                    const api = this.api();
                    let prevApptId   = null;
                    let prevFirstRow = null;
                    let prevLastRow  = null;

                    // Marks the end of the current appointment group with the separator border.
                    // Non-spanning cells: class on the last row. Spanning cells: class directly
                    // on the td elements of the first-leg row (where rowspan=2 places them visually).
                    function markApptEnd() {
                        if (!prevLastRow) return;
                        prevLastRow.addClass("appt-last-row");
                        if (prevFirstRow && prevFirstRow[0] !== prevLastRow[0]) {
                            prevFirstRow.children(`td.${APPT_SPAN_CLASS}`).addClass("appt-last-row");
                        }
                    }

                    api.rows({ page: "current" }).every(function () {
                        const rowData  = this.data();
                        const $row     = $(this.node());
                        // Select only the appointment-level cells via the CSS class added in columns_data.
                        const $apptCells = $row.children(`td.${APPT_SPAN_CLASS}`);

                        $row.removeClass("appt-last-row");
                        $apptCells.removeClass("appt-last-row");

                        if (rowData._appointment_id === prevApptId && !rowData._is_first_leg) {
                            // Second leg: hide its appointment-level cells and extend the first leg's rowspan.
                            $apptCells.hide();
                            prevFirstRow
                                .children(`td.${APPT_SPAN_CLASS}`)
                                .attr("rowspan", 2);
                            prevLastRow = $row;
                        } else {
                            // First leg (or standalone legacy record): reset any prior span state.
                            markApptEnd();
                            $apptCells.show().removeAttr("rowspan");
                            prevApptId   = rowData._appointment_id;
                            prevFirstRow = $row;
                            prevLastRow  = $row;
                        }
                    });
                    // Mark the final appointment's last row.
                    markApptEnd();

                    // Seed each visible textarea with its initial value so the blur
                    // handler can skip saves when nothing has actually changed.
                    $(`td.${APPT_SPAN_CLASS} .coordinator-notes-input`).each(function () {
                        if ($(this).data("last-saved") === undefined) {
                            $(this).data("last-saved", $(this).val());
                        }
                    });
                },

                dom: userRole === "AppointmentsAdmin"
                    ? 'Bfrt<"bottom"lip>'
                    : 'frt<"bottom"lip>',
                language: {
                    lengthMenu: "_MENU_",
                    searchPlaceholder: "Search",
                },

                initComplete: function () {
                    $("#mod_ehr_filter").appendTo("#table-filter");
                    $(".dt-buttons").appendTo("#table-filter");
                    $(".bottom").appendTo("#custom-pagination");
                    $('#mod_ehr_filter input[type="search"]').before(SearchIcon);
                    $("#table-filter").append(`<div class="position-relative">
                        <button id="custom_datatable_filter" class="btn"><i class="fa fa-filter"></i></button>
                        <div id="filter_options_container" class="d-none position-absolute bg-white border rounded p-3 shadow-sm mt-1" style="z-index: 1050; right: 0; min-width: 200px;">
                            <div class="mb-2">
                                <label class="form-label text-sm fw-bold">Trip Status</label>
                                <select id="filter_trip_status" class="form-select form-select-sm">
                                    <option value="">All</option>
                                    <option value="Not Requested">Not Requested</option>
                                    <option value="Scheduled">Scheduled</option>
                                    <option value="Completed">Completed</option>
                                    <option value="Cancelled">Cancelled</option>
                                </select>
                            </div>
                            <div class="mb-2">
                                <label class="form-label text-sm fw-bold">Appointment Location</label>
                                <input type="text" id="filter_appt_location" class="form-control form-control-sm" placeholder="Search location..." />
                            </div>
                            <div class="mb-2">
                                <label class="form-label text-sm fw-bold">Drop Off Spot</label>
                                <input type="text" id="filter_dropoff_spot" class="form-control form-control-sm" placeholder="Search spot..." />
                            </div>
                        </div>
                    </div>`);
                },
            });

            tablePaginationNavigationHandler(table);
            table.on("draw.dt", function () {
                tablePaginationNavigationHandler(table);
            });
            
            $("#custom_datatable_filter").on("click", function(e) {
                e.stopPropagation();
                $("#filter_options_container").toggleClass("d-none");
            });

            // Hide the filter dropdown if clicking outside
            $(document).on("click", function(e) {
                if (!$(e.target).closest('#filter_options_container, #custom_datatable_filter').length) {
                    $("#filter_options_container").addClass("d-none");
                }
            });

            // Perform DataTables filtering on the "Trip Status" column (index 5)
            $("#filter_trip_status").on("change", function() {
                const val = $.fn.dataTable.util.escapeRegex($(this).val());
                table.column(5).search(val, true, false).draw();
            });

            // Perform Custom search redraws for Appointment Location
            $("#filter_appt_location").on("keyup change", function() {
                filterApptLocation = $(this).val();
                table.draw();
            });

            // Perform Custom search redraws for Drop Off Spot
            $("#filter_dropoff_spot").on("keyup change", function() {
                filterDropoffSpot = $(this).val();
                table.draw();
            });

            // Toggle the hide-confirmed filter via the funnel icon in the column header.
            // stopPropagation prevents DataTables from treating the click as a column sort.
            $("#mod_ehr").on("click", ".alt-transport-filter-icon", function (e) {
                e.stopPropagation();
                hideConfirmedPatients = !hideConfirmedPatients;
                $(this).toggleClass("active");
                table.draw();
            });

            // Prevent DataTables column-sort from firing when interacting with
            // the notes textarea or the alt-transport checkbox.
            $("#mod_ehr").on("click mousedown", ".coordinator-notes-input, .alt-transport-checkbox", function (e) {
                e.stopPropagation();
            });

            // Save alt-transport confirmation immediately on toggle.
            // data-field tells us which model field to update (to vs from leg).
            $("#mod_ehr").on("change", ".alt-transport-checkbox", async function () {
                const $el        = $(this);
                const confirmed  = $el.prop("checked");
                const apptId     = $el.data("appt-id");
                const hospitalId = $el.data("hospital-id");
                const field      = $el.data("field"); // "alt_transport_confirmed_to" or "alt_transport_confirmed_from"

                $el.prop("disabled", true);

                try {
                    const res = await fetch(`${BASE_URL}/api/appointments/${apptId}`, {
                        method: "PUT",
                        headers: {
                            "Authorization": accessToken,
                            "X-Id-Token":    idToken,
                            "Content-Type":  "application/json",
                        },
                        body: JSON.stringify({ hospital_id: hospitalId, [field]: confirmed }),
                    });

                    if (res.ok) {
                        // Snapshot the live textarea value for this appointment so the
                        // upcoming draw (if active) doesn't wipe unsaved or saved notes.
                        const liveNotes = $(`textarea.coordinator-notes-input[data-appt-id="${escapeAttr(apptId)}"]`).val() ?? "";

                        // Sync the cached row data so any future redraw (sort, search,
                        // filter) renders both the checkbox and the notes in the correct state.
                        table.rows().every(function () {
                            const d = this.data();
                            if (d._appointment_id === apptId) {
                                // 1. Update the boolean flag for the changed field.
                                if (field === "alt_transport_confirmed_to") d._alt_confirmed_to = confirmed;
                                else d._alt_confirmed_from = confirmed;

                                // 2. Regenerate the checkbox HTML using the updated flag
                                //    so DataTables doesn't revert the visual state on redraw.
                                const dataField = d._is_first_leg ? "alt_transport_confirmed_to" : "alt_transport_confirmed_from";
                                const isChecked = d._is_first_leg ? d._alt_confirmed_to : d._alt_confirmed_from;
                                d.alt_transport_confirmed_to = `<div class="alt-transport-cell">
                                    <input type="checkbox"
                                           class="alt-transport-checkbox"
                                           data-appt-id="${escapeAttr(apptId)}"
                                           data-hospital-id="${escapeAttr(hospitalId)}"
                                           data-field="${dataField}"
                                           ${isChecked ? "checked" : ""} />
                                </div>`;

                                // 3. Preserve the current live notes value on the first-leg
                                //    row so a redraw doesn't reset the textarea content.
                                if (d._is_first_leg) {
                                    d.coordinator_notes = `<textarea
                                        class="coordinator-notes-input form-control"
                                        rows="2"
                                        placeholder="Add notes…"
                                        data-appt-id="${escapeAttr(apptId)}"
                                        data-hospital-id="${escapeAttr(hospitalId)}"
                                    >${escapeHtml(liveNotes)}</textarea>`;
                                }

                                this.data(d);
                            }
                        });
                        if (hideConfirmedPatients) table.draw();
                    } else {
                        $el.prop("checked", !confirmed);
                    }
                } catch {
                    $el.prop("checked", !confirmed);
                } finally {
                    $el.prop("disabled", false);
                }
            });

            // Save coordinator notes on blur, but only when the value has changed.
            $("#mod_ehr").on("blur", ".coordinator-notes-input", async function () {
                const $el      = $(this);
                const newNotes = $el.val();

                if (newNotes === $el.data("last-saved")) return;

                const apptId     = $el.data("appt-id");
                const hospitalId = $el.data("hospital-id");

                $el.prop("disabled", true).addClass("notes-saving");

                try {
                    const res = await fetch(`${BASE_URL}/api/appointments/${apptId}`, {
                        method: "PUT",
                        headers: {
                            "Authorization": accessToken,
                            "X-Id-Token":    idToken,
                            "Content-Type":  "application/json",
                        },
                        body: JSON.stringify({ hospital_id: hospitalId, coordinator_notes: newNotes }),
                    });

                    if (res.ok) {
                        $el.data("last-saved", newNotes).addClass("notes-saved");
                        setTimeout(() => $el.removeClass("notes-saved"), 1500);

                        // Update the cached HTML so any future redraw (sort, search,
                        // filter) renders the textarea with the saved value, not the
                        // stale value from page load.
                        table.rows().every(function () {
                            const d = this.data();
                            if (d._appointment_id === apptId && d._is_first_leg) {
                                d.coordinator_notes = `<textarea
                                    class="coordinator-notes-input form-control"
                                    rows="2"
                                    placeholder="Add notes…"
                                    data-appt-id="${escapeAttr(apptId)}"
                                    data-hospital-id="${escapeAttr(hospitalId)}"
                                >${escapeHtml(newNotes)}</textarea>`;
                                this.data(d);
                            }
                        });
                    } else {
                        $el.addClass("notes-error");
                        setTimeout(() => $el.removeClass("notes-error"), 2000);
                    }
                } catch {
                    $el.addClass("notes-error");
                    setTimeout(() => $el.removeClass("notes-error"), 2000);
                } finally {
                    $el.prop("disabled", false).removeClass("notes-saving");
                }
            });

            postRender();

        } else if (xhr.status !== 200) {
            $("#Loader").remove();
            if ($("#StateChange .emptyState").length === 0) {
                $("#StateChange").append(
                    `<div class="emptyState">
        <img src="./assets/ERROR.svg" alt="" />
        <h3 class="no-data">ERROR </h3>
        <p>An error occurred while retrieving data</p>
      </div>`
                );
            }
        }
    };
    xhr.send();
});
