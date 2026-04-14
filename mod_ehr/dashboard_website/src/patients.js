import {
    getAccessToken,
    getIdToken,
    logoutUser,
    getUserGroup,
    tablePaginationNavigationHandler,
    preRender,
    postRender,
    BASE_URL,
    toggleLoder,
    toggleSideNavBar,
    toggleSkeletonLoader,
    getAccesstokenAndCustomAttribute,
    loadTenantBranding,
    CUSTOM_DOMAIN,
} from "./common";
async function editPatient() {
    const [accessToken, hospital_id] = await getAccesstokenAndCustomAttribute("custom:hospital_id");
    if (hospital_id === 'admin') {
        $('#hospital_select_block').removeClass('d-none');
    } else {
        $('#hospital_select_block').addClass('d-none');
    }
    $("#appointmentModal").css({
        display: "block",
    });
    toggleSkeletonLoader("appointmentModal", "add");
    const id = $(this).attr("data-id");
    const req_hospital_id = $(this).attr("data-hospital-id") || hospital_id;
    let xhr1 = new XMLHttpRequest();
    xhr1.open("GET", `${BASE_URL}/api/patients/${id}?hospital_id=${req_hospital_id}`);
    xhr1.setRequestHeader("Authorization", accessToken);
    xhr1.setRequestHeader("X-Id-Token", await getIdToken());
    xhr1.onreadystatechange = async function () {
        if (xhr1.readyState === XMLHttpRequest.DONE && xhr1.status === 200) {
            toggleSkeletonLoader("appointmentModal", "remove");
            let patient = JSON.parse(xhr1.responseText);
            $("#patient_name").val(patient.name);
            $("#patient_id").val(patient.patient_id);
            $("#via_rider_id").val(patient.via_rider_id);
            $("#provider").val(patient.provider);
            if (hospital_id === 'admin') {
                $("#hospital_id_form").val(patient.hospital_id);
                $('#hospital_select_block').removeClass('d-none');
            } else {
                $("#hospital_id_form").val(patient.hospital_id);
                $('#hospital_select_block').addClass('d-none');
            }
            $("#appointmentModal .save").data("id", id);
            
        }
    };
    xhr1.send();
}

async function renderHospitalColumn(accessToken) {
    const idToken = await getIdToken();
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
            }
        }
        xhr.send();
    })
}

$(document).ready(async function () {
    const hostname = window.location.hostname;
    const dns_tenant = hostname.split('.')[0];
    const [accessToken, hospital_id] = await getAccesstokenAndCustomAttribute("custom:hospital_id");
    const config = await loadTenantBranding(hospital_id);
    if (config.subdomain !== dns_tenant){
        alert("You are not authorized for this hospital.");
        await logoutUser();
        window.location.replace(`https://${config.subdomain}${CUSTOM_DOMAIN}/patients.html`);
    }
    preRender();
    toggleSideNavBar();
    $("#logout").click(logoutUser);
    const userRole = await getUserGroup();
    if (userRole !== "AppointmentsAdmin" && userRole !== "UserManagementAdmin") {
        window.location.href = "dashboard.html";
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("invisible")
        $("#user-management-nav").addClass("visible")
    }
    if(hospital_id === "admin"){
        $("#hospitals-nav").removeClass("invisible")
        $("#hospitals-nav").addClass("visible")

    }else{
        $("#hospitals-nav").removeClass("visible")
        $("#hospitals-nav").addClass("invisible")
    }

    let hospital_map = {};
    if (hospital_id === "admin") {
        hospital_map = await renderHospitalColumn(accessToken);
        
        const hospitalSelect = document.getElementById("hospital_id_form");
        for (const [id, name] of Object.entries(hospital_map)) {
            const option = document.createElement("option");
            option.value = id;
            option.textContent = name;
            hospitalSelect.appendChild(option);
        }
    }

    $("#appointmentForm").validate({
        rules: {
            patient_name: {
                required: true,
            },
            patient_id: {
                required: true,
            },
            via_rider_id: {
                required: true,
            },
            hospital_id_form: {
                required: function () {
                    return hospital_id === 'admin';
                }
            }
        },
        messages: {
            patient_name: {
                required: "Please enter Patient Name",
            },
            patient_id: {
                required: "Please enter Patient ID",
            },
            via_rider_id: {
                required: "Please enter VIA rider ID",
            },
            hospital_id_form: {
                required: "Please select a hospital",
            }
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    $(".add-patient").click(async function () {
        if (hospital_id === 'admin') {
            $('#hospital_select_block').removeClass('d-none');
        } else {
            $('#hospital_select_block').addClass('d-none');
        }
        $("#appointmentModal .save").removeData("id");
        $("#appointmentModal").css({
            display: "block",
        });
    });
    $("#close-add-patient").click(async function () {
        $("#appointmentModal").css({
            display: "none",
        });
        $("#appointmentModal .save").removeData("id");
    });    
    const xhr = new XMLHttpRequest();    
    xhr.open("GET", `${BASE_URL}/api/patients/?hospital_id=${hospital_id}`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("X-Id-Token", await getIdToken());
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            let columns_data = [
                { data: "name", title: "Patient Name" },
                { data: "patient_id", title: "Patient ID" },
                {
                    data: "via_rider_id", title: "Via Rider ID", render: function (data, type, row) {
                        return row.via_rider_id || "N/A"
                    }
                },
                { data: "provider", title: "Provider", },
            ];
            if (hospital_id === "admin") {
                columns_data.push({ data: "hospital_id", title: "Hospital", render: function(data, type, row) { return hospital_map[data] || data; } });
            }
            columns_data.push(
                {
                    data: null,
                    render: function (data, type, row) {
                        return (
                            `<div class="d-flex"><button title="edit" class="editBtn btn flex-1" data-id="` +
                            row.patient_id +  `" data-hospital-id="` + row.hospital_id +
                            `" ><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none">
  <path d="M14 7.33326L10.6667 3.99993M1.08331 16.9166L3.90362 16.6032C4.24819 16.5649 4.42048 16.5458 4.58152 16.4937C4.72439 16.4474 4.86035 16.3821 4.98572 16.2994C5.12702 16.2062 5.2496 16.0836 5.49475 15.8385L16.5 4.83326C17.4205 3.91279 17.4205 2.4204 16.5 1.49993C15.5795 0.579452 14.0871 0.579451 13.1667 1.49992L2.16142 12.5052C1.91627 12.7503 1.79369 12.8729 1.70051 13.0142C1.61784 13.1396 1.55249 13.2755 1.50624 13.4184C1.45411 13.5794 1.43497 13.7517 1.39668 14.0963L1.08331 16.9166Z" stroke="#111827" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg></button>`
                        );
                    },
                },
            );
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
                $(".editBtn").click(editPatient);
            });
            $(".editBtn").click(editPatient);
            postRender();
            $(".close").click(async function () {
                $('label.error').remove();
                $("#appointmentModal").css({
                    display: "none",
                });
                $("#appointmentForm").trigger("reset");
                $("#appointmentModal .save").removeData("id");
            });
            $("#appointmentModal .save").click(async function () {
                toggleLoder("button-primary", "add");
                const is_valid = $("#appointmentForm").valid();
                if (is_valid) {
                    let url = `${BASE_URL}/api/patients/`;
                    let type = "POST";
                    const id = $(this).data("id");
                    let formData = {
                        name: $("#patient_name").val(),
                        patient_id: $("#patient_id").val(),
                        via_rider_id: $("#via_rider_id").val(),
                        provider: $("#provider").val(),
                    };
                    if (hospital_id === 'admin') {
                        formData['hospital_id'] = $('#hospital_id_form').val();
                    }else{
                        formData['hospital_id'] = hospital_id;
                    }
                    if (id !== undefined) {
                        url += `${id}?hospital_id=${formData['hospital_id']}`;
                        type = "PUT";
                        formData["id"] = id;
                        console.log(id);
                    }
                    const accessToken = await getAccessToken();
                    let reload_required = false;
                    const xhr = new XMLHttpRequest();
                    xhr.open(type, url);
                    xhr.setRequestHeader("Authorization", accessToken);
                    xhr.setRequestHeader("X-Id-Token", await getIdToken());
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = async function () {
                        if (xhr.readyState === XMLHttpRequest.DONE) {
                            $("#appointmentModal").css({
                                display: "none",
                            });
                            if (xhr.status === 200 || xhr.status === 201) {
                                if (type == "POST") {
                                    $("#root").append(
                                        `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Saved Patient Details successfully</div></div>`
                                    );
                                } else {
                                    $("#root").append(
                                        `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Updated Patient Details successfully</div></div>`
                                    );
                                }
                                reload_required = true;
                            } else {
                                $("#root").append(
                                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Patient</div></div>`
                                );
                            }
                            setTimeout(function () {
                                $("#customAlert").remove();
                                $("#appointmentForm").trigger("reset");
                                if (reload_required) { window.location.reload(); }
                            }, 1000);
                        }
                    };
                    xhr.send(JSON.stringify(formData));
                }
                else {
                    toggleLoder("button-primary", "remove");
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
