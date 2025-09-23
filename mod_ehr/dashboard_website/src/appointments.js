import { formatInTimeZone } from "date-fns-tz";
import { DateTime } from "luxon";

import {
  BASE_URL,
  getAccessToken,
  logoutUser,
  getUserGroup,
  tablePaginationNavigationHandler,
  preRender,
  postRender,
  GOOGLE_MAPS_KEY,
  toggleLoder,
  toggleSideNavBar,
  toggleSkeletonLoader,
} from "./common";

async function EditAppointment() {
    const accessToken = await getAccessToken();
    $("#appointmentModal").css({
      display: "block",
    });
    toggleSkeletonLoader("appointmentModal", "add");
    const id = $(this).data("id");
    let xhr1 = new XMLHttpRequest();
    xhr1.open("GET", `${BASE_URL}/api/patients/`);
    xhr1.setRequestHeader("Authorization", accessToken);
    xhr1.onreadystatechange = async function () {
        if (xhr1.readyState === XMLHttpRequest.DONE && xhr1.status === 200) {
            const patient_records = JSON.parse(xhr1.responseText);
            await $("#patientName").empty();
            for (let patient of patient_records) {
                console.log(patient);
                let option = $("<option>", {
                    value: `${patient["name"]}-${patient["patient_id"]}`,
                    text: `${patient["name"]} (${patient["patient_id"]})`,
                });
                $("#patientName").append(option);
            }
            let xhr = new XMLHttpRequest();
            xhr.open(
                "GET",
                `${BASE_URL}/api/appointments/` + id
            );
            xhr.setRequestHeader("Authorization", accessToken);
            xhr.onreadystatechange = function () {
                if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                    toggleSkeletonLoader("appointmentModal", "remove");
                    let appointment = JSON.parse(xhr.responseText);
                    let start_time = new Date(appointment["start_time"]);
                    start_time = formatInTimeZone(
                        start_time,
                        "America/Chicago",
                        "yyyy-MM-dd'T'HH:mm:ss"
                    );
                    let end_time = new Date(appointment["end_time"]);
                    end_time = formatInTimeZone(
                        end_time,
                        "America/Chicago",
                        "yyyy-MM-dd'T'HH:mm:ss"
                    );
                    $("#patientName").val(
                        `${appointment["patient_name"]}-${appointment["patient_id"]}`
                    );
                    $("#startTime").val(start_time);
                    $("#endTime").val(end_time);
                    $("#location").val(appointment["location"]);
                    $("#status").val(appointment["status"]);
                    $(".save").data("id", id);
                }
            };
            xhr.send();
        }
    };
    xhr1.send();
}
async function saveAppointment() {
    toggleLoder("button-primary", "add");
    const id = $(this).data("id");
    let url = `${BASE_URL}/api/appointments/`;
    let type = "POST";
    const is_valid = $("#appointmentForm").valid();
    if (is_valid) {
        // $("#appointmentModal").css({
        //     display: "none",
        // });
        let formData = {
            end_time:
                DateTime.fromISO($("#endTime").val() + ":00.000-05:00")
                    .toUTC()
                    .toISO({ includeOffset: false }) + "000+0000",
            location: $("#location").val(),
            patient_id: $("#patientName").val().split("-")[1],
            patient_name: $("#patientName").val().split("-")[0],
            start_time:
                DateTime.fromISO($("#startTime").val() + ":00.000-05:00")
                    .toUTC()
                    .toISO({ includeOffset: false }) + "000+0000",
            status: $("#status").val(),
            provider: "epic",
        };
        console.log(formData);
        if (id !== undefined) {
            url += id;
            type = "PUT";
            formData["id"] = id;
            console.log(id);
        }
        const accessToken = await getAccessToken();
        let reload_required = false;
        const xhr = new XMLHttpRequest();
        xhr.open(type, url);
        xhr.setRequestHeader("Authorization", accessToken);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.onreadystatechange = async function () {
            $("#appointmentModal").css({
              display: "none",
            });
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) { 
                if (type == "POST") {
                    $("#root").append(
                        `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Appointment created successfully</div></div>`
                    );
                } else {
                    $("#root").append(
                        `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Appointment Updated successfully </div></div>`
                    );
                }
                reload_required = true;
            } else {
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Appointment</div></div>`
                );

            }
            setTimeout(function () {
                $("#customAlert").remove();
                $("#appointmentForm").trigger("reset");
                if (reload_required) { window.location.reload(); }
            }, 1000);
        };
        xhr.send(JSON.stringify(formData));
    }
    else {
        toggleLoder("button-primary", "remove");
    }
}
async function DeleteAppointment() {
    const accessToken = await getAccessToken();
    $("#spinner").show();
    const id = $(this).data("id");
    const xhr = new XMLHttpRequest();
    xhr.open(
        "DELETE",
        `${BASE_URL}/api/appointments/` + id
    );
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 204) {
            $("#root")
                .append(`<div id="customAlert" class="custom-alert-success">
      <div class="flex-1">Appointment Deleted successfully</div>
    </div>`);
            setTimeout(function () {
                $("#customAlert").remove();
                window.location.reload();
            }, 1000);
        }
    };
    xhr.send();
}
async function addAppointment() {
    const accessToken = await getAccessToken();
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/patients/`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            let patient_records = JSON.parse(xhr.responseText);
            $("#patientName").empty();
            patient_records.sort((a, b) => a.name.localeCompare(b.name));
            for (let patient of patient_records) {
                console.log(patient);
                let option = $("<option>", {
                    // value: `${patient["name"]}-${patient["epic_id"]}`,
                    // text: `${patient["name"]} (${patient["epic_id"]})`,
                    value: `${patient["name"]}-${patient["patient_id"]}`,
                    text: `${patient["name"]} (${patient["patient_id"]})`,
                });
                $("#patientName").append(option);
            }
            $("#appointmentModal").css({
                display: "block",
            });
            $("#patientName").select2({
                width: '100%',
                placeholder: "Select a patient",
                allowClear: true
            });
        }
    };
    xhr.send();
}
$(document).ready(async function () {
    $('head').append(`<script src = "https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}&libraries=places&callback=googleMapsAutoComplete" async defer></script>`);
    preRender();
    toggleSideNavBar();
    $("#logout").click(logoutUser);
    $("#location").keydown(function (event) {
        if (event.keyCode === 13 ) { event.preventDefault() };
    });
    const userRole = await getUserGroup();
    if (userRole !== "AppointmentsAdmin" && userRole !== "UserManagementAdmin") {
        window.location.href = "dashboard.html";
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("invisible")
        $("#user-management-nav").addClass("visible")
    }
    $("#appointmentForm").validate({
        rules: {
            patient_name: {
                required: true,
            },
            start_time: {
                required: true,
            },
            end_time: {
                required: true,
            },
            location: {
                required: true,
            },
            status: {
                required: true,
            },
        },
        messages: {
            patient_name: {
                required: "Please select a Patient",
            },
            start_time: {
                required: "Please enter Start Time",
            },
            end_time: {
                required: "Please enter End Time",
            },
            location: {
                required: "Please enter Location",
            },
            status: {
                required: "Please select a Status",
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    const accessToken = await getAccessToken();

    $(".add-appointment").click(addAppointment);
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/appointments/`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            let columns_data = [
                { data: "id", title: "ID" },
                { data: "patient_name", title: "Patient Name" },
                { data: "start_time", title: "Start Time" },
                { data: "end_time", title: "End Time" },
                { data: "location", title: "Location" },
                { data: "status", title: "Status" },
                {
                    data: null,
                    render: function (data, type, row) {
                        return (
                            `<div class="d-flex"><button title="edit" class="editBtn btn flex-1" data-id="` +
                            row.id +
                            `" ><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none">
  <path d="M14 7.33326L10.6667 3.99993M1.08331 16.9166L3.90362 16.6032C4.24819 16.5649 4.42048 16.5458 4.58152 16.4937C4.72439 16.4474 4.86035 16.3821 4.98572 16.2994C5.12702 16.2062 5.2496 16.0836 5.49475 15.8385L16.5 4.83326C17.4205 3.91279 17.4205 2.4204 16.5 1.49993C15.5795 0.579452 14.0871 0.579451 13.1667 1.49992L2.16142 12.5052C1.91627 12.7503 1.79369 12.8729 1.70051 13.0142C1.61784 13.1396 1.55249 13.2755 1.50624 13.4184C1.45411 13.5794 1.43497 13.7517 1.39668 14.0963L1.08331 16.9166Z" stroke="#111827" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg></button>` +
                            `<button title="delete" class="deleteBtn btn flex-1" data-id="` +
                            row.id +
                            `"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">
  <path d="M13.3333 4.99984V4.33317C13.3333 3.39975 13.3333 2.93304 13.1517 2.57652C12.9919 2.26292 12.7369 2.00795 12.4233 1.84816C12.0668 1.6665 11.6001 1.6665 10.6667 1.6665H9.33333C8.39991 1.6665 7.9332 1.6665 7.57668 1.84816C7.26308 2.00795 7.00811 2.26292 6.84832 2.57652C6.66667 2.93304 6.66667 3.39975 6.66667 4.33317V4.99984M8.33333 9.58317V13.7498M11.6667 9.58317V13.7498M2.5 4.99984H17.5M15.8333 4.99984V14.3332C15.8333 15.7333 15.8333 16.4334 15.5608 16.9681C15.3212 17.4386 14.9387 17.821 14.4683 18.0607C13.9335 18.3332 13.2335 18.3332 11.8333 18.3332H8.16667C6.76654 18.3332 6.06647 18.3332 5.53169 18.0607C5.06129 17.821 4.67883 17.4386 4.43915 16.9681C4.16667 16.4334 4.16667 15.7333 4.16667 14.3332V4.99984" stroke="#111827" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg></i></button><div>`
                        );
                    },
                },
            ];
            let appointmentRecords = JSON.parse(xhr.responseText);
            console.log(appointmentRecords);
            for (let appointmentRecord of appointmentRecords) {
                appointmentRecord["start_time"] = new Date(
                    appointmentRecord["start_time"]
                ).toLocaleString("en-US", { timeZone: "America/Chicago" });
                appointmentRecord["end_time"] = new Date(
                    appointmentRecord["end_time"]
                ).toLocaleString("en-US", { timeZone: "America/Chicago" });
            }
            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
            console.log(userRole);

            let table = $("#mod_ehr").DataTable({
                data: appointmentRecords,
                columns: columns_data,
                language: {
                    lengthMenu: "_MENU_",
                    searchPlaceholder: "Search",
                },
                dom:
                    userRole === "AppointmentsAdmin"
                        ? 'Bfrt<"bottom"lip>'
                        : 'frt<"bottom"lip>',
                initComplete: function (settings, json) {
                    $("#mod_ehr_filter").appendTo("#table-filter");
                    $(".dt-buttons").appendTo("#table-filter");
                    $(".bottom").appendTo("#custom-pagination");
                    $('#mod_ehr_filter input[type="search"]').before(
                        SearchIcon
                    );
                },
            });
            tablePaginationNavigationHandler(table);
            table.on("draw.dt", function () {
                $(".editBtn").click(EditAppointment);
                $(".deleteBtn").click(DeleteAppointment);
                tablePaginationNavigationHandler(table);
            });
            postRender();
            $(".editBtn").click(EditAppointment);
            $(".deleteBtn").click(DeleteAppointment);
            $(".close").click(async function () {
                $('label.error').remove();
                $("#appointmentModal").css({
                    display: "none",
                });
                $("#appointmentForm").trigger("reset");
            });
            $(".save").click(saveAppointment);
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
