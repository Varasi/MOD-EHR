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
    $("#assistance-text-dashboard").append(HIRTA_CONTACT);
})