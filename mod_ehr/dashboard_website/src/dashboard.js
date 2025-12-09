import {
    getAccessToken,
    logoutUser,
    getUserGroup,
    tablePaginationNavigationHandler,
    preRender,
    postRender,
    BASE_URL,
    toggleSideNavBar

} from "./common";

$(document).ready(async function () {
    let time1 = new Date().getTime();
    preRender();
    toggleSideNavBar();
    const userRole = await getUserGroup();
    if (userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
        $("#appointments-nav").removeClass("invisible")
        $("#appointments-nav").addClass("visible")
        $("#patients-nav").removeClass("invisible")
        $("#patients-nav").addClass("visible")
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("invisible")
        $("#user-management-nav").addClass("visible")
    }
    $("#logout").click(logoutUser);
    const accessToken = await getAccessToken();
    const xhr = new XMLHttpRequest();
    let time2 = new Date().getTime();
    console.log("Time taken to get user role:", time2 - time1);
    xhr.open("GET", `${BASE_URL}/api/dashboard/`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function () {
        let time2_1 = new Date().getTime();
        console.log("Time taken for dashboard API response:", time2_1 - time2);
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            $("#Loader").remove();
            let data = [];
            let columns_data = [
                { data: "customer", title: "Customer" },
                { data: "appointment_time", title: "Appointment Time" },
                { data: "appointment_location", title: "Appointment Location" },
                { data: "appointment_status", title: "Appointment Status" },
                { data: "trip_status", title: "Trip Status" },
                { data: "pickup_time", title: "Pickup Time" },
                { data: "drop_off_time", title: "Drop Off Time" },
                { data: "driver_vehicle_info", title: "Driver/Vehicle" },
            ];
            if (userRole === "HIRTAOperationsStaff" || userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
                columns_data.push(
                    { data: "pick_up_note", title: "Pick Up Note" },
                    { data: "pickup_spot", title: "Pick Up Spot" },
                    { data: "drop_off_spot", title: "Drop Off Spot" },
                    { data: "drop_off_note", title: "Drop Off Note" }
                );
            }
            let dashboardRawData = JSON.parse(xhr.responseText);
            for (let appointmentRecord of dashboardRawData) {
                console.log(appointmentRecord);
                let driver_name =
                    "driver_info" in appointmentRecord["ride"]
                        ? (
                            appointmentRecord["ride"]["driver_info"][
                            "first_name"
                            ] +
                            " " +
                            appointmentRecord["ride"]["driver_info"][
                            "last_name"
                            ]
                        ).trim()
                        : "";
                let vehicle_number =
                    "vehicle_info" in appointmentRecord["ride"]
                        ? appointmentRecord["ride"]["vehicle_info"][
                            "license_plate"
                        ].trim()
                        : "";
                let driver_vehicle_info =
                    driver_name == "" && vehicle_number == ""
                        ? "TBD"
                        : driver_name + "/" + vehicle_number;
                var row_data = {
                    customer: appointmentRecord["patient_name"],
                    appointment_time:
                        appointmentRecord["start_time"] == "TBD"
                            ? "TBD"
                            : new Date(
                                appointmentRecord["start_time"]
                            ).toLocaleString("en-US", {
                                timeZone: "America/Chicago",
                            }),
                    appointment_location: appointmentRecord["location"],
                    appointment_status: appointmentRecord["status"],
                    trip_status:
                        appointmentRecord["ride"]["trip_status"] ==
                            "Not Requested"
                            ? "<span class='lozenge-danger'>Not Requested</span>"
                            : "<span class='lozenge-success'>" +
                            appointmentRecord["ride"]["trip_status"] +
                            "</span>",
                    pickup_time:
                        appointmentRecord["ride"]["pickup_eta"] == "TBD"
                            ? "N/A"
                            : new Date(
                                appointmentRecord["ride"]["pickup_eta"] * 1000
                            ).toLocaleString("en-US", {
                                timeZone: "America/Chicago",
                            }),
                    drop_off_time:
                        appointmentRecord["ride"]["dropoff_eta"] == "TBD"
                            ? "N/A"
                            : new Date(
                                appointmentRecord["ride"]["dropoff_eta"] *
                                1000
                            ).toLocaleString("en-US", {
                                timeZone: "America/Chicago",
                            }),
                    driver_vehicle_info: driver_vehicle_info,
                };

                if (userRole === "HIRTAOperationsStaff" || userRole === "AppointmentsAdmin" || userRole === "UserManagementAdmin") {
                    row_data["pick_up_note"] =
                        "notes" in appointmentRecord["ride"]["pickup"]
                            ? appointmentRecord["ride"]["pickup"]["notes"]
                            : "N/A";
                    row_data["pickup_spot"] =
                        "address" in appointmentRecord["ride"]["pickup"]
                            ? appointmentRecord["ride"]["pickup"]["address"]
                            : "N/A";
                    row_data["drop_off_note"] =
                        "notes" in appointmentRecord["ride"]["dropoff"]
                            ? appointmentRecord["ride"]["dropoff"]["notes"]
                            : "N/A";
                    row_data["drop_off_spot"] =
                        "address" in appointmentRecord["ride"]["dropoff"]
                            ? appointmentRecord["ride"]["dropoff"]["address"]
                            : "N/A";
                }
                data.push(row_data);
            }

            var SearchIcon = $(
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
                createdRow: function (row, data, dataIndex) {

                    if (
                        data["trip_status"] ==
                        "<span class='lozenge-danger'>Not Requested</span>"
                    ) {
                        $(row).addClass("bg-danger-light");
                    } else {
                        $(row).addClass("bg-success-light");
                    }
                },
                dom:
                    userRole === "AppointmentsAdmin"
                        ? 'Bfrt<"bottom"lip>'
                        : 'frt<"bottom"lip>',
                language: {
                    lengthMenu: "_MENU_",
                    searchPlaceholder: "Search",
                },

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
                tablePaginationNavigationHandler(table);
            });
            postRender();
            let time2_2 = new Date().getTime();
            console.log("Time taken to render dashboard table from api response:", time2_2 - time2_1);
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
