import {
    getAccessToken,
    logoutUser,
    getUserGroup,
    tablePaginationNavigationHandler,
    preRender,
    postRender,
    BASE_URL,
    getIdToken
} from "./common";


$(document).ready(async function () {
    preRender();
    $("#logout").click(logoutUser);
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
            epic_id: {
                required: true,
            },
            via_rider_id: {
                required: true,
            },
        },
        messages: {
            patient_name: {
                required: "Please enter Patient Name",
            },
            epic_id: {
                required: "Please enter Patient ID",
            },
            via_rider_id: {
                required: "Please enter VIA rider ID",
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    $(".add-patient").click(async function () {
        $("#appointmentModal").css({
            display: "block",
        });
    });
    $("#close-add-patient").click(async function () {
        $("#appointmentModal").css({
            display: "none",
        });
    });
    // const accessToken = await getAccessToken()
    const idToken = await getIdToken()
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/patients/`);
    // xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("Authorization", idToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            let columns_data = [
                { data: "name", title: "Patient Name" },
                { data: "epic_id", title: "Patient ID" },
                { data: "via_rider_id", title: "Via Rider ID" },
            ];
            let patient_records = JSON.parse(xhr.responseText);
            console.log(patient_records);
            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
            console.log(userRole);

            let table = $("#mod_ehr").DataTable({
                data: patient_records,
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
                tablePaginationNavigationHandler(table);
            });
            postRender();
            $(".close").click(async function () {
                $('label.error').remove();
                $("#appointmentModal").css({
                    display: "none",
                });
                $("#appointmentForm").trigger("reset");
            });
            $(".save").click(async function () {
                const is_valid = $("#appointmentForm").valid();
                if (is_valid) {
                    $("#appointmentModal").css({
                        display: "none",
                    });
                    $("#spinner").show();
                    let url = `${BASE_URL}/api/patients/`;
                    let type = "POST";
                    let formData = {
                        name: $("#patient_name").val(),
                        epic_id: $("#epic_id").val(),
                        via_rider_id: $("#via_rider_id").val(),
                    };
                    console.log(formData);

                    // const accessToken = await getAccessToken();
                    const idToken = await getIdToken();
                    let reload_required = false;
                    const xhr = new XMLHttpRequest();
                    xhr.open(type, url);
                    // xhr.setRequestHeader("Authorization", accessToken);
                    xhr.setRequestHeader("Authorization", idToken);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = async function () {
                        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                            if (type == "POST") {
                                $("#root").append(
                                    `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Added Patient successfully</div></div>`
                                );
                            }
                            reload_required = true;
                        } else {
                            $("#root").append(
                                `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Patient</div></div>`
                            );

                        }
                        // $("#appointmentModal").css({
                        //     display: "none",
                        // });
                        setTimeout(function () {
                            $("#customAlert").remove();
                            $("#appointmentForm").trigger("reset");
                            if (reload_required) { window.location.reload(); }
                        }, 1000);
                    };
                    xhr.send(JSON.stringify(formData));
                }
            });


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
