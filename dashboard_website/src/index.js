

import { getUserSession,PASSWORD_REGEX } from "./common";
import { signIn,confirmSignIn,signOut } from "../node_modules/aws-amplify/auth";

$(document).ready(async function () {
    $("#login").click(async function () {
        const username = $("#email").val();
        const password = $("#password").val();
        
        console.log("username->"+username);
        console.log("password->"+password);
        $(this).html(
            `<div class="d-flex gap-1 align-items-center justify-content-center">
        <div> Log in</div>
        <div class="loader-small" />
      </div`
        );
        try {
            const {nextStep} = await signIn({ 
                username, 
                password
            });
            console.log("nextStep->"+JSON.stringify(nextStep));
            console.log("signinstep->"+JSON.stringify(nextStep["signInStep"]));
            if(nextStep["signInStep"] === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"){
                $("#dashboard_login_subtitle").text(
                    "Please change your Password"
                )
                console.log("nextStep->"+JSON.stringify(nextStep));
                $("#changepassword").removeClass("hide-div");
                $("#usernameinput").addClass("hide-div");
            }else if(nextStep["signInStep"] === "DONE"){ 
                console.log("loggedin");
                window.location.href = "dashboard.html";
            }else{
                
                const err_msg = "Please contact Administrator. ISSUE: "+nextStep["signInStep"];
                $("#root")
                    .append(`<div id="customAlert" class=" alert custom-alert-danger">
                                <div class="flex-1">${err_msg} </div>
                            </div>
                        `);
                setTimeout(function () {
                    $("#customAlert").remove();
                }, 2000);
                $(this).html(
                    `<div class="d-flex gap-1 align-items-center justify-content-center">
                <div> Login</div>
              </div`
                );
            }
        } catch (error) {
            $(this).text("Log in");
            console.log(error);
            let mod_err_msg = error.message;
            if(error.message.includes("There is already a signed in user")){
                mod_err_msg = "Please reload the page and try again.";
            }
            $("#root")
                .append(`<div id="customAlert" class=" alert custom-alert-danger">
                            <div class="flex-1">${mod_err_msg} </div>
                          </div>
                      `);
            setTimeout(function () {
                $("#customAlert").remove();
            }, 2000);
            $(this).html(
                `<div class="d-flex gap-1 align-items-center justify-content-center">
            <div> Login</div>
          </div`
            );
        }
    });
    $("#confirmpasswordval").on("input", function () {
        const newPassword = $("#newpasswordval").val();
        const confirmPassword = $(this).val();
        const message = $("#matchMessage");

        if (confirmPassword === newPassword) {
            message.text("Passwords match!").css("color", "green");
        } else {
            message.text("Passwords do not match.").css("color", "red");
        }
    });
    $("#newpasswordval").on("input",function () {
        const newpassword = $(this).val();
        const message = $("#matchMessage");
        if(PASSWORD_REGEX.test(newpassword)){
            message.text("Password is valid!").css("color", "green");
            $("#passwordformat").addClass("hide-div");
            
        }else{
            message.text("Password is not valid.").css("color", "red");
            $("#passwordformat").removeClass("hide-div");
        }
    });
    $("#newpassword").click(async function () {
        console.log("newpassword clicked");
        const new_password = $("#newpasswordval").val();
        const confirm_password = $("#confirmpasswordval").val();
        console.log("new_password->"+new_password);
        console.log("confirm_password->"+confirm_password);
        if (new_password !== confirm_password) {
            $("#matchMessage").text("Passwords do not match.").css("color", "red");
            return;
        }
        $(this).html(
            `<div class="d-flex gap-1 align-items-center justify-content-center">
        <div> Change Password</div>
        <div class="loader-small" />
      </div`
        );
        try{
            await confirmSignIn({
                challengeResponse : new_password
            })
            console.log("loggedin");
            window.location.href = "dashboard.html"
        }
        catch (error) {
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
            $(this).html(
                `<div class="d-flex gap-1 align-items-center justify-content-center">
            <div> Change Password</div>
          </div`
            );
        }
    });
    console.log("checking user session");
    let auth = await getUserSession(false);
    if (auth.tokens) {
        window.location.href = "dashboard.html";
    }
});
