import {
    getAccessToken,
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

function renderHospitalColumn(accessToken) {
    return new Promise((resolve) => {
        let hospitals_map = {};
        const xhr = new XMLHttpRequest();
        xhr.open("GET", `${BASE_URL}/api/hospitals/`);
        xhr.setRequestHeader("Authorization", accessToken);
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
        window.location.replace(`https://${config.subdomain}${CUSTOM_DOMAIN}/logs.html`);
    }
    const userRole = await getUserGroup();
    let hospital_map = {};
    if (hospital_id === "admin"){
        hospital_map = await renderHospitalColumn(accessToken);
        console.log("Hospital Map: ", hospital_map);
    }
    if(hospital_id === "admin"){
        $("#hospitals-nav").removeClass("invisible")
        $("#hospitals-nav").addClass("visible")

    }else{
        $("#hospitals-nav").removeClass("visible")
        $("#hospitals-nav").addClass("invisible")
    }
    
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${BASE_URL}/api/logs/?hospital_id=${hospital_id}`,
    );
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            const log_records = JSON.parse(xhr.responseText);
            for (let log of log_records) {
                console.log("log retrived")
                log["server_last_modified"] = new Date(
                    log["server_last_modified"]*1000
                ).toLocaleString("en-US", { timeZone: "America/Chicago" });
            }
            const columns_data = [
                { data: "name", title: "NAME" },
                { data: "server_last_modified", title: "Received Time" },
            ]
            if (hospital_id === "admin") {
                columns_data.push({ data: "hospital_id", title: "Hospital", render: function(data, type, row) { return hospital_map[data] || data; } });
            }
            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
            $("#mod_ehr").DataTable({
                data: log_records,
                columns: columns_data,
                language: {
                    lengthMenu: "_MENU_",
                    searchPlaceholder: "Search",
                },
                dom: userRole === "AppointmentsAdmin"
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
            postRender();

        }
        else if (xhr.status !== 200) {
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

})