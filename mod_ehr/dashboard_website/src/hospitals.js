import {
    getAccessToken,
    logoutUser,
    getUserGroup,
    tablePaginationNavigationHandler,
    preRender,
    postRender,
    BASE_URL,
    toggleSideNavBar,
    getAccesstokenAndCustomAttribute,
    loadTenantBranding,
    toggleSkeletonLoader,
    toggleLoder,
    GOOGLE_MAPS_KEY,
    CUSTOM_DOMAIN,
} from "./common";
async function EditHospital(){
    $("#saveEditHospital").removeClass("d-none");
    $("#saveNewHospital").addClass("d-none");
    $("#hospitalModal").css({
      display: "block",
    });
    toggleSkeletonLoader("hospitalModal", "add");
    const id = $(this).data("id");
    console.log(id);
    const hospital = JSON.parse(atob($(this).attr("data-hospital")));
    $("#hospitalNameForm").val(hospital.name);
    $("#hospitalIdForm").val(hospital.id).prop("disabled", true);
    $("#hospitalSubdomainForm").val(hospital.subdomain);
    $("#hospitalLocationForm").val(hospital.location);
    $("#hospitalProviderForm").val(hospital.provider).trigger("change");
    if (hospital.provider === "epic") {
        $("#hospitalEPICClientIdForm").val(hospital.epic_client_id);
        $("#hospitalEPICPrivateKeyForm").val(hospital.epic_private_key);
        $("#hospitalEPICJwksUrlForm").val(hospital.epic_jwks_url);
        $("#hospitalEPICJwksKidForm").val(hospital.epic_jwks_kid);
    } else {
        $("#hospitalVeradigmProviderForm").val(hospital.s3_subfolder_name);
        $("#hospitalSFTPUsernameForm").val(hospital.sftp_username);
        $("#hospitalSFTPPasswordForm").val(hospital.sftp_password);
    }
    $("#hospitalStatusForm").val(hospital.status);
    $("#saveEditHospital").data("id", id);
    toggleSkeletonLoader("hospitalModal", "remove");
}
async function deleteHospital(){
    const accessToken = await getAccessToken();
    $("#spinner").show();
    const id = $(this).data("id");
    const xhr = new XMLHttpRequest();
    xhr.open(
        "DELETE",
        `${BASE_URL}/api/hospitals/` + id
    );
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 204) {
            $("#root")
                .append(`<div id="customAlert" class="custom-alert-success">
        <div class="flex-1">Hospital Deleted successfully</div>
    </div>`);
            setTimeout(function () {
                $("#customAlert").remove();
                window.location.reload();
            }, 1000);
        }
    };
    xhr.send();
}
async function saveEditHospital(){
    toggleLoder("button-primary", "add");
    const is_valid = $("#hospitalForm").valid();
    const id = $(this).data("id");
    const accessToken = await getAccessToken();
    if (is_valid) {
        let formData = {
            name: $("#hospitalNameForm").val(),
            subdomain: $("#hospitalSubdomainForm").val(),
            location: $("#hospitalLocationForm").val(),
            provider: $("#hospitalProviderForm").val(),
            status: $("#hospitalStatusForm").val(),
        }
        if ($("#hospitalProviderForm").val() === "epic") {
            formData["epic_client_id"] = $("#hospitalEPICClientIdForm").val();
            formData["epic_private_key"] = $("#hospitalEPICPrivateKeyForm").val();
            formData["epic_jwks_url"] = $("#hospitalEPICJwksUrlForm").val();
            formData["epic_jwks_kid"] = $("#hospitalEPICJwksKidForm").val();
        }else{
            formData["s3_subfolder_name"] = $("#hospitalVeradigmProviderForm").val();
            formData["sftp_username"] = $("#hospitalSFTPUsernameForm").val();
            formData["sftp_password"] = $("#hospitalSFTPPasswordForm").val();
        }
        let reload_required = false;
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", `${BASE_URL}/api/hospitals/` + id);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.setRequestHeader("Authorization", accessToken);
        xhr.onreadystatechange = async function () {
            $("#hospitalModal").css({
              display: "none",
            });
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200){
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Hospital updated successfully</div></div>`
                );
                reload_required = true;

            }else {
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Hospital</div></div>`
                );

            }
            
            setTimeout(function () {
                $("#customAlert").remove();
                $("#hospitalForm").trigger("reset");
                if (reload_required) { window.location.reload(); }
            }, 1000);
        }
        xhr.send(JSON.stringify(formData));
    }else {
        toggleLoder("button-primary", "remove");
    }
    // $("#saveEditHospital").addClass("d-none");
    
    
}
async function addHospital(){
    $("#hospitalIdForm").prop("disabled", false);
    $("#hospitalProviderForm").trigger("change");
    $("#saveNewHospital").removeClass("d-none");
    $("#saveEditHospital").addClass("d-none");
    $("#hospitalModal").css({
      display: "block",
    });
    

}
async function saveNewHospital(){
    toggleLoder("button-primary", "add");
    const is_valid = $("#hospitalForm").valid();
    const accessToken = await getAccessToken();
    if (is_valid) {
        const fileInput = document.getElementById('hospitalLogoForm');
        let logo_data = null;
        if (fileInput && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            logo_data = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result.split(",")[1]);
                reader.readAsDataURL(file);
            });
        }
        let formData = {
            id: $("#hospitalIdForm").val(),
            name: $("#hospitalNameForm").val(),
            subdomain: $("#hospitalSubdomainForm").val(),
            location: $("#hospitalLocationForm").val(),
            provider: $("#hospitalProviderForm").val(),
            status: $("#hospitalStatusForm").val(),
            logo_data: logo_data,
        }
        if ($("#hospitalProviderForm").val() === "epic") {
            formData["epic_client_id"] = $("#hospitalEPICClientIdForm").val();
            formData["epic_private_key"] = $("#hospitalEPICPrivateKeyForm").val();
            formData["epic_jwks_url"] = $("#hospitalEPICJwksUrlForm").val();
            formData["epic_jwks_kid"] = $("#hospitalEPICJwksKidForm").val();
        }else{
            formData["s3_subfolder_name"] = $("#hospitalVeradigmProviderForm").val();
            formData["sftp_username"] = $("#hospitalSFTPUsernameForm").val();
            formData["sftp_password"] = $("#hospitalSFTPPasswordForm").val();
        }
        let reload_required = false;
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${BASE_URL}/api/hospitals/`);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.setRequestHeader("Authorization", accessToken);
        xhr.onreadystatechange = async function () {
            $("#hospitalModal").css({
              display: "none",
            });
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200){
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-success"><div class="flex-1">Hospital created successfully</div></div>`
                );
                reload_required = true;

            }else {
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Hospital</div></div>`
                );

            }
            
            setTimeout(function () {
                $("#customAlert").remove();
                $("#hospitalForm").trigger("reset");
                if (reload_required) { window.location.reload(); }
            }, 1000);
        }
        xhr.send(JSON.stringify(formData));
    }else {
        toggleLoder("button-primary", "remove");
    }
    // $("#saveNewHospital").addClass("d-none");
}
$(document).ready(async function () {
    $('head').append(`<script src = "https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}&libraries=places&callback=googleMapsAutoComplete" async defer></script>`);
    const hostname = window.location.hostname;
    const dns_tenant = hostname.split('.')[0];
    const [accessToken, hospital_id] = await getAccesstokenAndCustomAttribute("custom:hospital_id");
    const config = await loadTenantBranding(hospital_id);
    if (config.subdomain !== dns_tenant){
        alert("You are not authorized for this hospital.");
        await logoutUser();
        window.location.replace(`https://${config.subdomain}${CUSTOM_DOMAIN}/hospitals.html`);
    }
    preRender();
    toggleSideNavBar();
    $("#hospitalLocationForm").keydown(function (event) {
        if (event.keyCode === 13 ) { event.preventDefault() };
    });
    $("#hospitalProviderForm").on("change", function () {
        const selectedValue = $(this).val();
        console.log(selectedValue);
        if (selectedValue === "epic") {
            $("#epicInputBlock").removeClass("d-none");
            $("#veradigmInputBlock").addClass("d-none");
        } else if (selectedValue === "veradigm") {
            $("#epicInputBlock").addClass("d-none");
            $("#veradigmInputBlock").removeClass("d-none");
        }
    });
    $(".add-hospital").click(addHospital);
    const userRole = await getUserGroup();
    if (hospital_id === "admin") {
        $("#user-management-nav").removeClass("invisible")
        $("#user-management-nav").addClass("visible")
        $("#appointments-nav").removeClass("invisible")
        $("#appointments-nav").addClass("visible")
        $("#patients-nav").removeClass("invisible")
        $("#patients-nav").addClass("visible")
    }else{
        window.location.href = "dashboard.html";
    }
    $("#logout").click(logoutUser);
    $("#hospitalForm").validate({
        rules: {
            hospitalNameForm: {
                required: true,
            },
            hospitalIdForm: {
                required: true,
            },
            hospitalSubdomainForm: {
                required: true,
            },
            hospitalLocationForm: {
                required: true,
            },
            hospitalProviderForm: {
                required: true,
            },
            hospitalStatusForm: {
                required: true,
            },
            hospitalVeradigmProviderForm: {
                required: function () {
                    return $("#hospitalProviderForm").val() === "veradigm";
                },
            },
            hospitalSFTPUsernameForm: {
                required: function () {
                    return $("#hospitalProviderForm").val() === "veradigm";
                },
            },
            hospitalSFTPPasswordForm: {
                required: function () {
                    return $("#hospitalProviderForm").val() === "veradigm";
                },
            },
            hospitalEPICProviderForm: {
                required: function(){
                    return $("#hospitalProviderForm").val() === "epic";
                }
            },
            hospitalEPICClientIdForm: {
                required: function(){
                    return $("#hospitalProviderForm").val() === "epic";
                }
            },
            hospitalEPICPrivateKeyForm: {
                required: function(){
                    return $("#hospitalProviderForm").val() === "epic";
                }
            }
        },
        messages: {
            hospitalNameForm: {
                required: "Please enter Hospital Name",
            },
            hospitalIdForm: {
                required: "Please enter Hospital ID",
            },
            hospitalSubdomainForm: {
                required: "Please enter Hospital Subdomain",
            },
            hospitalLocationForm: {
                required: "Please enter Hospital Location",
            },
            hospitalStatusForm: {
                required: "Please select a Status",
            },
            hospitalVeradigmProviderForm: {
                required: "Please enter S3 subfolder name",
            },
            hospitalSFTPUsernameForm: {
                required: "Please enter SFTP Username",
            },
            hospitalSFTPPasswordForm: {
                required: "Please enter SFTP Password",
            },
            hospitalEPICProviderForm: {
                required: "Please enter Epic API",
            },
            hospitalEPICClientIdForm: {
                required: "Please enter Epic Client ID",
            },
            hospitalEPICPrivateKeyForm: {
                required: "Please enter Epic Private Key",
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    let columns_data = [
        { data: "id", title: "ID" },
        { data: "name", title: "Hospital Name" },
        { data: "subdomain", title: "Subdomain" },
        { data: "status", title: "Status" },
        { data: "provider", title: "Provider" },
        {
            data: null,
            title: "Subfolder Name",
            render: function (data, type, row) {
                if (row.provider === "epic") {
                    return "N/A";
                } else if (row.provider === "veradigm") {
                    return row.s3_subfolder_name || "N/A";
                }
                return "N/A";
            }
        },
        {
            data: null,
            title: "SFTP Username",
            render: function (data, type, row) {
                if (row.provider === "veradigm") {
                    return row.sftp_username || "N/A";
                }
                return "N/A";
            }
        },
        {
            data: null,
            title: "SFTP Password",
            render: function (data, type, row) {
                if (row.provider === "veradigm") {
                    return row.sftp_password || "N/A";
                }
                return "N/A";
            }
        },
        { data: null,
            title: "EPIC Client ID",
            render: function (data, type, row) {
                if (row.provider === "epic") {
                    return  row.epic_client_id || "N/A";
                } else if (row.provider === "veradigm") {
                    return "N/A";
                }
                return "N/A";
            }
        },
        { data: null,
            title: "EPIC PRIVATE KEY",
            render: function (data, type, row) {
                if (row.provider === "epic") {
                    const key = row.epic_private_key || "N/A";
                    return `<div title="${key}" style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${key}</div>`;
                } else if (row.provider === "veradigm") {
                    return "N/A";
                }
                return "N/A";
            }
        },
        { data: null,
            title: "EPIC JWKS URL",
            render: function (data, type, row) {
                if (row.provider === "epic") {
                    return  row.epic_jwks_url || "N/A";
                } else if (row.provider === "veradigm") {
                    return "N/A";
                }
                return "N/A";
            }
        },
        { data: null,
            title: "EPIC Key ID",
            render: function (data, type, row) {
                if (row.provider === "epic") {
                    return  row.epic_jwks_kid || "N/A";
                } else if (row.provider === "veradigm") {
                    return "N/A";
                }
                return "N/A";
            }
        },
        { data: "location", title: "location" },
        {
                    data: null,
                    render: function (data, type, row) {
                        const HospitalData = btoa(JSON.stringify({
                            id: row.id,
                            name: row.name,
                            patient_id: row.patient_id,
                            subdomain: row.subdomain,
                            status: row.status,
                            location: row.location,
                            provider: row.provider,
                            s3_subfolder_name: row.s3_subfolder_name,
                            sftp_username: row.sftp_username,
                            sftp_password: row.sftp_password,
                            epic_client_id: row.epic_client_id,
                            epic_private_key: row.epic_private_key,
                            epic_jwks_url: row.epic_jwks_url,
                            epic_jwks_kid: row.epic_jwks_kid,
                        }));
                        return (
                            `<div class="d-flex"><button title="edit" class="editBtn btn flex-1" data-id="` +
                            row.id +
                            `" data-hospital="${HospitalData}" ><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none">
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
    var SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/hospitals`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function (){
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            $("#Loader").remove();
            const hospitals = JSON.parse(xhr.responseText);
            console.log(hospitals)
            const table = $("#mod_ehr").DataTable({
                data: hospitals,
                columns: columns_data,
                order: [],
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
                $(".editBtn").click(EditHospital);
                $(".deleteBtn").click(DeleteHospital);
                tablePaginationNavigationHandler(table);
            });
            postRender();
            $(".editBtn").click(EditHospital);
            $(".deleteBtn").click(deleteHospital);
            $(".close").click(async function () {
                $('label.error').remove();
                $("#hospitalModal").css({
                    display: "none",
                });
                $("#hospitalForm").trigger("reset");
            });
            $("#saveEditHospital").click(saveEditHospital);
            $("#saveNewHospital").click(saveNewHospital);
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
    }
    xhr.send();
});