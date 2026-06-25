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
  getAccesstokenAndCustomAttribute,
  loadTenantBranding,
  CUSTOM_DOMAIN,
  getIdToken
} from "./common";

function resetRiderForm() {
    $("#riderForm").trigger("reset");
    $('label.error').remove();
    const fp = document.querySelector("#dob")._flatpickr;
    if (fp) {
        fp.clear();
    }
}

async function editRider() {
    const accessToken = await getAccessToken();
    resetRiderForm();
    $("#riderModal").css({
        display: "block",
    });
    toggleSkeletonLoader("riderModal", "add");
    const id = $(this).attr("data-id");
    let xhr1 = new XMLHttpRequest();
    xhr1.open("GET", `${BASE_URL}/api/riders/${id}`);
    xhr1.setRequestHeader("Authorization", accessToken);
    xhr1.setRequestHeader("X-Id-Token", await getIdToken());
    xhr1.onreadystatechange = async function () {
        if (xhr1.readyState === XMLHttpRequest.DONE && xhr1.status === 200) {
            toggleSkeletonLoader("riderModal", "remove");
            let rider = JSON.parse(xhr1.responseText);
            $("#rider_id").val(rider.rider_id);
            $("#first_name").val(rider.first_name);
            $("#last_name").val(rider.last_name);
            $("#phone_no").val(rider.phone_no);
            let dobVal = rider.dob || "";
            if (dobVal.includes("-")) {
                const parts = dobVal.split("-");
                if (parts.length === 3 && parts[0].length === 4) {
                    dobVal = `${parts[1]}-${parts[2]}-${parts[0]}`;
                }
            }
            const fp = document.querySelector("#dob")._flatpickr;
            if (fp) {
                fp.setDate(dobVal, true);
            } else {
                $("#dob").val(dobVal);
            }
            $("#status").val(rider.status);
            $("#riderModal .save").data("id", id);
        }
    };
    xhr1.send();
}

async function deleteRider() {
    const accessToken = await getAccessToken();
    $("#spinner").show();
    const id = $(this).data("id");
    const xhr = new XMLHttpRequest();
    xhr.open("DELETE", `${BASE_URL}/api/riders/${id}`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("X-Id-Token", await getIdToken());
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 204) {
            $("#root").append(`<div id="customAlert" class="custom-alert-success"><div class="flex-1">Rider Deleted successfully</div></div>`);
            setTimeout(() => window.location.reload(), 1000);
        }
    };
    xhr.send();
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
    console.log("User Role:", userRole);
    if (userRole === "BookingAdmin" || userRole === "UserManagementAdmin" || userRole === "ViewOnly") {
        $("#appointments-nav").removeClass("invisible").addClass("visible");
        $("#patients-nav").removeClass("invisible").addClass("visible");
    }
    if (userRole === "ViewOnly") {
        $("#book-trip-nav").removeClass("visible").addClass("d-none");
    }
    if (userRole === "UserManagementAdmin") {
        $("#user-management-nav").removeClass("d-none").addClass("visible");
    }else{
        $("#user-management-nav").removeClass("visible").addClass("d-none");
    }
    console.log("Hospital ID:", hospital_id);
    if (hospital_id === "admin") {
       $("#hospitals-nav").removeClass("d-none").addClass("visible");
       $("#riders-nav").removeClass("d-none").addClass("visible");
    } else {
       $("#hospitals-nav").removeClass("visible").addClass("d-none");
       $("#riders-nav").removeClass("visible").addClass("d-none");
       window.location.href = "dashboard.html";
       return;
    }
    $("#logout").click(logoutUser);

    // Custom date validation method for MM-DD-YYYY
    $.validator.addMethod("mmDdYyyyDate", function (value, element) {
        if (this.optional(element)) {
            return true;
        }
        const regex = /^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-\d{4}$/;
        if (!regex.test(value)) {
            return false;
        }
        const parts = value.split("-");
        const mm = parseInt(parts[0], 10);
        const dd = parseInt(parts[1], 10);
        const yyyy = parseInt(parts[2], 10);
        const date = new Date(yyyy, mm - 1, dd);
        if (date.getFullYear() !== yyyy || date.getMonth() !== mm - 1 || date.getDate() !== dd) {
            return false;
        }
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (date > today) {
            return false;
        }
        return true;
    }, "Please enter a valid Date of Birth (MM-DD-YYYY)");

    // Auto-formatting for dob MM-DD-YYYY input
    $("#dob").on("input", function (e) {
        let val = $(this).val();
        if (e.originalEvent && (e.originalEvent.inputType === "deleteContentBackward" || e.originalEvent.inputType === "deleteContentForward")) {
            return;
        }
        let clean = val.replace(/\D/g, "");
        if (clean.length > 8) {
            clean = clean.substring(0, 8);
        }
        let formatted = "";
        if (clean.length > 0) {
            formatted += clean.substring(0, 2);
        }
        if (clean.length > 2) {
            formatted += "-" + clean.substring(2, 4);
        }
        if (clean.length > 4) {
            formatted += "-" + clean.substring(4, 8);
        }
        $(this).val(formatted);
    });

    // Initialize Flatpickr datepicker on dob field
    flatpickr("#dob", {
        dateFormat: "m-d-Y",
        maxDate: "today",
        allowInput: true,
        onChange: function (selectedDates, dateStr, instance) {
            $("#dob").trigger("change");
        }
    });

    $("#riderForm").validate({
        rules: {
            rider_id: { required: true },
            first_name: { required: true },
            last_name: { required: true },
            phone_no: { required: true },
            dob: { 
                required: true,
                mmDdYyyyDate: true
            },
            status: { required: true }
        },
        messages: {
            rider_id: { required: "Please enter Rider ID" },
            first_name: { required: "Please enter First Name" },
            last_name: { required: "Please enter Last Name" },
            phone_no: { required: "Please enter Phone Number" },
            dob: { 
                required: "Please enter Date of Birth",
                mmDdYyyyDate: "Please enter a valid Date of Birth (MM-DD-YYYY)"
            },
            status: { required: "Please select Status" }
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");
        },
    });

    $(".add-rider").click(async function () {
        resetRiderForm();
        $("#riderModal .save").removeData("id");
        $("#riderModal").css({ display: "block" });
    });

    $("#close-add-rider, .close").click(async function () {
        resetRiderForm();
        $("#riderModal").css({ display: "none" });
        $("#riderModal .save").removeData("id");
    });

    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/riders/`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("X-Id-Token", idToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            $("#Loader").remove();
            let columns_data = [
                { data: "rider_id", title: "Rider ID" },
                { data: "first_name", title: "First Name" },
                { data: "last_name", title: "Last Name" },
                { data: "phone_no", title: "Phone Number" },
                { 
                    data: "dob", 
                    title: "Date of Birth",
                    render: function(data) {
                        if (!data) return "";
                        const parts = data.split("-");
                        if (parts.length === 3) {
                            return `${parts[1]}-${parts[2]}-${parts[0]}`;
                        }
                        return data;
                    }
                },
                {
                    data: "matches",
                    title: "Matched Hospitals",
                    orderable: false,
                    render: function (data) {
                        if (!data || data.length === 0) return `<span class="text-muted">No matches</span>`;
                        return data.map(m => {
                            if (!m.epic_verification_needed) {
                                return `<span class="badge bg-success me-1" title="Patient ID: ${m.epic_patient_id}">${m.hospital_name}</span>`;
                            } else {
                                return `<span class="badge bg-warning text-dark me-1" title="Verification Needed">${m.hospital_name} (Pending)</span>`;
                            }
                        }).join("");
                    }
                },
                { 
                    data: "status", 
                    title: "Status",
                    render: function (data, type, row) {
                        if (!data) return "";
                        if (data.toLowerCase() === "active") {
                            return `<span class="status-active">Active</span>`;
                        } else if (data.toLowerCase() === "inactive") {
                            return `<span class="status-inactive">Inactive</span>`;
                        }
                        return data;
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        return (
                            `<div class="d-flex"><button title="edit" class="editBtn btn flex-1" data-id="${row.rider_id}"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M14 7.33326L10.6667 3.99993M1.08331 16.9166L3.90362 16.6032C4.24819 16.5649 4.42048 16.5458 4.58152 16.4937C4.72439 16.4474 4.86035 16.3821 4.98572 16.2994C5.12702 16.2062 5.2496 16.0836 5.49475 15.8385L16.5 4.83326C17.4205 3.91279 17.4205 2.4204 16.5 1.49993C15.5795 0.579452 14.0871 0.579451 13.1667 1.49992L2.16142 12.5052C1.91627 12.7503 1.79369 12.8729 1.70051 13.0142C1.61784 13.1396 1.55249 13.2755 1.50624 13.4184C1.45411 13.5794 1.43497 13.7517 1.39668 14.0963L1.08331 16.9166Z" stroke="#111827" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>` +
                            `<button title="delete" class="deleteBtn btn flex-1" data-id="${row.rider_id}"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M13.3333 4.99984V4.33317C13.3333 3.39975 13.3333 2.93304 13.1517 2.57652C12.9919 2.26292 12.7369 2.00795 12.4233 1.84816C12.0668 1.6665 11.6001 1.6665 10.6667 1.6665H9.33333C8.39991 1.6665 7.9332 1.6665 7.57668 1.84816C7.26308 2.00795 7.00811 2.26292 6.84832 2.57652C6.66667 2.93304 6.66667 3.39975 6.66667 4.33317V4.99984M8.33333 9.58317V13.7498M11.6667 9.58317V13.7498M2.5 4.99984H17.5M15.8333 4.99984V14.3332C15.8333 15.7333 15.8333 16.4334 15.5608 16.9681C15.3212 17.4386 14.9387 17.821 14.4683 18.0607C13.9335 18.3332 13.2335 18.3332 11.8333 18.3332H8.16667C6.76654 18.3332 6.06647 18.3332 5.53169 18.0607C5.06129 17.821 4.67883 17.4386 4.43915 16.9681C4.16667 16.4334 4.16667 15.7333 4.16667 14.3332V4.99984" stroke="#111827" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div>`
                        );
                    },
                },
            ];

            let rider_records = JSON.parse(xhr.responseText);
            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg></span>"
            );

            let table = $("#mod_ehr").DataTable({
                data: rider_records,
                columns: columns_data,
                language: {
                    lengthMenu: "_MENU_",
                    searchPlaceholder: "Search",
                },
                dom: 'Bfrt<"bottom"lip>',
                initComplete: function (settings, json) {
                    $("#mod_ehr_filter").appendTo("#table-filter");
                    $(".dt-buttons").appendTo("#table-filter");
                    $(".bottom").appendTo("#custom-pagination");
                    $('#mod_ehr_filter input[type="search"]').before(SearchIcon);
                },
            });
            
            tablePaginationNavigationHandler(table);
            table.on("draw.dt", function () {
                tablePaginationNavigationHandler(table);
                $(".editBtn").click(editRider);
                $(".deleteBtn").click(deleteRider);
            });
            
            $(".editBtn").click(editRider);
            $(".deleteBtn").click(deleteRider);
            postRender();

            $("#riderModal .save").click(async function () {
                toggleLoder("button-primary", "add");
                if ($("#riderForm").valid()) {
                    let url = `${BASE_URL}/api/riders/`;
                    let type = "POST";
                    const id = $(this).data("id");
                    
                    let dobVal = $("#dob").val() || "";
                    if (dobVal.includes("-")) {
                        const parts = dobVal.split("-");
                        if (parts.length === 3 && parts[2].length === 4) {
                            dobVal = `${parts[2]}-${parts[0]}-${parts[1]}`;
                        }
                    }
                    let formData = {
                        rider_id: $("#rider_id").val(),
                        first_name: $("#first_name").val(),
                        last_name: $("#last_name").val(),
                        phone_no: $("#phone_no").val(),
                        dob: dobVal,
                        status: $("#status").val(),
                    };
                    
                    if (id !== undefined) {
                        url += `${id}`;
                        type = "PUT";
                    }
                    
                    const saveXhr = new XMLHttpRequest();
                    saveXhr.open(type, url);
                    saveXhr.setRequestHeader("Authorization", accessToken);
                    saveXhr.setRequestHeader("X-Id-Token", await getIdToken());
                    saveXhr.setRequestHeader("Content-Type", "application/json");
                    saveXhr.onreadystatechange = function () {
                        if (saveXhr.readyState === XMLHttpRequest.DONE) {
                            $("#riderModal").css({ display: "none" });
                            resetRiderForm();
                            if (saveXhr.status === 200 || saveXhr.status === 201) {
                                $("#root").append(`<div id="customAlert" class="custom-alert-success"><div class="flex-1">${type === "POST" ? "Saved" : "Updated"} Rider Details successfully</div></div>`);
                                setTimeout(() => window.location.reload(), 1000);
                            } else {
                                $("#root").append(`<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Saving Rider</div></div>`);
                                setTimeout(() => $("#customAlert").remove(), 1000);
                                toggleLoder("button-primary", "remove");
                            }
                        }
                    };
                    saveXhr.send(JSON.stringify(formData));
                } else {
                    toggleLoder("button-primary", "remove");
                }
            });

        } else if (xhr.status !== 200) {
            $("#Loader").remove();
            if ($("#StateChange .emptyState").length === 0) {
                $("#StateChange").append(
                    `<div class="emptyState"><img src="./assets/ERROR.svg" alt="" /><h3 class="no-data">ERROR </h3><p>An error occurred while retrieving data</p></div>`
                );
            }
        }
    };
    xhr.send();
});