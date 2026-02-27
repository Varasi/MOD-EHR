
import { getUserSession, togglePasswordVisibility, getAccesstokenAndCustomAttribute, CUSTOM_DOMAIN, loadTenantBranding } from "./common";
import { signIn } from "aws-amplify/auth";

$(document).ready(async function () {
    const hostname = window.location.hostname;
    const tenantId = hostname.split('.')[0];
    const session = await getUserSession(false);
    if(session && session.tokens){
        const hospital_id = session.tokens.idToken.payload["custom:hospital_id"];
        if (hospital_id !== tenantId){
            window.location.replace(`https://${hospital_id}${CUSTOM_DOMAIN}/dashboard.html`);
        }else{
            window.location.href = "dashboard.html";
        }
    }
    
    $("#login").click(async function () {
        const username = $("#email").val();
        const password = $("#password").val();
        $(this).html(
            `<div class="d-flex gap-1 align-items-center justify-content-center">
        <div> Log in</div>
        <div class="loader-small" />
      </div`
        );
        try {
            const user = await signIn({ username, password });

            window.location.href = "dashboard.html";
            // window.location.replace(`https://hospital1001.hirtahealthconnector.com/dashboard.html`);
        } catch (error) {
            $(this).text("Log in");
            console.log(error);
            $("#root")
                .append(`<div id="customAlert" class=" alert custom-alert-danger">
                            <div class="flex-1">${error.message} </div>
                          </div>
                      `);
            setTimeout(function () {
                $("#customAlert").remove();
            }, 2000);
        }
    });

    $("#password-toggler").click(function () {
       togglePasswordVisibility("password", "password-toggler");
    });
    // let auth = await getUserSession(false);
    // if (auth.tokens) {
    //     window.location.href = "dashboard.html";
    // }
});
