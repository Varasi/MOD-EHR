import {
  getIss,
  getIdToken,
  REGION,
  IDENTITY_POOL_ID,
  preRender,
  logoutUser,
  postRender,
  getUserGroup,
  tablePaginationNavigationHandler,
  getAccesstokenAndCustomAttribute,
  getAccessToken,
  BASE_URL,
  getUserGroupNameForUser,
  getCustomAttributeForUser,
  getUserIdAndCustomAttribute,
  COGNITO_PARAMS,
  PASSWORD_REGEX,
  toggleLoder,
  togglePasswordVisibility,
  toggleSideNavBar,
  toggleAlertMessage,
  loadTenantBranding,
  CUSTOM_DOMAIN,
} from "./common";
import AWS from 'aws-sdk';
const iss = getIss()
AWS.config.region = REGION;
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
    IdentityPoolId: IDENTITY_POOL_ID, // Cognito Identity Pool ID
    Logins: {
        [iss]: await getIdToken(),
    }
});
const cognitoIdentityServiceProvider = new AWS.CognitoIdentityServiceProvider()
async function removeUserFromGroup(username, group) {
    return new Promise((resolve, reject) => {
        const group_params = {
            GroupName: group,
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username
        }
        cognitoIdentityServiceProvider.adminRemoveUserFromGroup(group_params, (err, data) => {
            if (err) {
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">${err.message}</div></div>`
                );
                resolve(false);
            }
            resolve(true)
        });
    })
}
async function deleteUser(username) {
    try{
        const user_params = {
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username
        }
        await cognitoIdentityServiceProvider.adminUserGlobalSignOut({
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username
        }).promise();
        await cognitoIdentityServiceProvider
            .adminDeleteUser(user_params)
            .promise();
        return true;
    } catch(err){
        console.log(err)
        $("#root").append(
            `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">${err.message}</div></div>`
        );
        setTimeout(function () {
            $("#customAlert").remove();
        }, 1000);
        return false;
    }
}
async function addCustomAttributeToUser(username, attributeName, attributeValue) {
    return new Promise((resolve, reject) => {
        const attribute_params = {
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username,
            UserAttributes: [
                {
                    Name: attributeName,
                    Value: attributeValue
                }
            ]
        }
        cognitoIdentityServiceProvider.adminUpdateUserAttributes(attribute_params, (err, data) => {
            if (err) {
                console.log(err.message)
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">${err.message}</div></div>`
                );
                resolve(false);
            }
            resolve(true)
        });
    })
}
async function addUserToGroup(username, group) {
    return new Promise((resolve, reject) => {
        const group_params = {
            GroupName: group,
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username
        }
        cognitoIdentityServiceProvider.adminAddUserToGroup(group_params, (err, data) => {
            if (err) {
                $("#root").append(
                    `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">${err.message}</div></div>`
                );
                resolve(false);
            }

            resolve(true)
        });
    })
}

async function changePassword(username, password) {
    return new Promise((resolve, reject) => {
        cognitoIdentityServiceProvider.adminSetUserPassword({
            Password: password,
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: username,
            Permanent: true
        }, (err, data) => {
            if (err) {
                toggleAlertMessage(err.message, "danger" );
                resolve(false);
            }
            resolve(true)
        });
    })
}
async function addUserToCognito() {
    toggleLoder("saveUser", "add");
    let validator = $("#appointmentForm").validate();
    const is_valid = $("#appointmentForm").valid();
    if (is_valid) {
        let username = $("#userName").val()
        // $("#addUserModal").hide()

        const user_params = {
            UserPoolId: COGNITO_PARAMS.UserPoolId,
            Username: $("#userName").val(),
            MessageAction: 'SUPPRESS'
        }
        return new Promise((resolve, reject) => {
            cognitoIdentityServiceProvider.adminCreateUser(user_params, async (err, data) => {
                if (err) {
                    validator.showErrors({
                        "user_name": err.message
                    });
                        toggleLoder("saveUser", "remove");
                } else {
                    let change_pass_status = await changePassword(username, $("#password").val())
                    console.log(change_pass_status)
                    if (!change_pass_status) {
                        await deleteUser(username);
                        resolve(false)
                    }
                    let add_to_group_status = await addUserToGroup(username, $("#role").val())
                    if (!add_to_group_status) {
                        await deleteUser(username);
                        resolve(false)
                    }
                    let add_hospital_attribute_status = await addCustomAttributeToUser(username, "custom:hospital_id", $("#hospital").val())
                    if (!add_hospital_attribute_status) {
                        await deleteUser(username);
                        resolve(false)
                    }
                    $("#addUserModal").hide()
                    $("#root").append(
                        `<div id="customAlert" class="custom-alert-success"><div class="flex-1">User added successfully</div></div>`
                    );
                    setTimeout(function () {
                        $("#customAlert").remove();
                        $("#appointmentForm").trigger("reset");
                        window.location.reload();
                    }, 1000);
                    resolve(true)

                }
            }
            )
        });
    }
};

async function deleteUserButtonAction() {
    const username = $(this).data("username");
    if (await deleteUser(username)) {
        $("#root")
            .append(`<div id="customAlert" class="custom-alert-success">
      <div class="flex-1">User Deleted successfully</div>
    </div>`);
        setTimeout(function () {
            $("#customAlert").remove();
            window.location.reload();
        }, 1000);
    }
    else {
        $("#root").append(
            `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error Deleting User</div></div>`
        );
        setTimeout(function () {
            $("#customAlert").remove();
        }, 1000);
    }
}
async function updatePassword() {
    toggleLoder("updatePassword", "add");
    const is_valid = $("#changePassForm").valid();
    if (is_valid) {
        const username = $(this).data("username");
        const password = $("#password2").val();
        if (await changePassword(username, password)) {
            $("#changePassModal").hide();
            toggleAlertMessage("Password updated successfully", "success");
        }
    }
    toggleLoder("updatePassword", "remove");
    
}
async function changePasswordButtonAction() {
    const username = $(this).data("username");
    console.log(username)
    $("#updatePassword").data("username", username);
    $("#updatePassword").click(updatePassword);
    $("#changePassModal").show()
}
async function addUserButtonAction() {
    const [user_id, user_tenant_id] = await getUserIdAndCustomAttribute("custom:hospital_id");
    
    if(user_tenant_id === "admin"){
        $("#userMgmtAdminOption").removeClass("d-none");
    } else {
        $("#userMgmtAdminOption").addClass("d-none");
        $("#hospital").val(user_tenant_id).prop("disabled", true);
    }
    $("#addUserModal").show();
    
}
async function closeUserModal() {
    $("#addUserModal").hide()
    $('label.error').remove();
    $("#appointmentForm").trigger("reset");

}
async function closeUserEditModal() {
    $("#changeUserModal").hide()
    $('label.error').remove();
    $("#changeUserForm").trigger("reset");

}
async function editUser() {
    toggleLoder("saveChangeUser", "add");
    const username = $("#changeUsername").val()
    const group = await getUserGroupNameForUser(cognitoIdentityServiceProvider, username);
    const hospital = $("#changeHospital").val()
    await removeUserFromGroup(username, group)
    console.log(group)
    const new_group = $("#changeRole").val()
    console.log(new_group)
    if (await addUserToGroup(username, new_group) && await addCustomAttributeToUser(username, "custom:hospital_id", hospital)) {
        $("#root")
            .append(`<div id="customAlert" class="custom-alert-success">
      <div class="flex-1">User Role Changed successfully</div>
    </div>`);
    }
    else {
        $("#root").append(
            `<div id="customAlert" class="custom-alert-danger"><div class="flex-1">Error changing Group</div></div>`
        );
    }
    setTimeout(function () {
        $("#customAlert").remove();
        window.location.reload();
    }, 1000);

}
async function closeChangePassModal() {
    $('label.error').remove();
    $("#changePassModal").hide()
    $("#changePassForm").trigger("reset");

}
async function editUserButtonAction(hospitalList) {
    const username = $(this).data("username");
    const group = await getUserGroupNameForUser(cognitoIdentityServiceProvider, username);
    const hospital = await getCustomAttributeForUser(cognitoIdentityServiceProvider, username, "custom:hospital_id");
    const [user_id, user_tenant_id] = await getUserIdAndCustomAttribute("custom:hospital_id");
    $("#changeUsername").val(username)
    $("#changeRole").val(group)
    if(user_tenant_id == "admin"){
        $("#changeHospital").val(hospital)
        $("#changeUserMgmtAdminOption").removeClass("d-none");
    }else{
        $("#changeHospital").val(hospital).prop("readonly", true);
        $("#changeUserMgmtAdminOption").addClass("d-none");
    }
    $("#changeUserModal").show()


}
$(document).ready(async function () {
    await initAWS();
    const hostname = window.location.hostname;
    const dns_tenant = hostname.split('.')[0];
    const [accessToken, hospital_id] = await getAccesstokenAndCustomAttribute("custom:hospital_id");
    const config = await loadTenantBranding(hospital_id);
    if (config.subdomain !== dns_tenant){
        alert("You are not authorized for this hospital.");
        await logoutUser();
        window.location.replace(`https://${config.subdomain}${CUSTOM_DOMAIN}/userManagement.html`);
    }
    preRender();
    toggleSideNavBar();
    $("#logout").click(logoutUser);
    $("#password-toggler").click(function () {
      togglePasswordVisibility("password", "password-toggler");
    });
    $("#password1-toggler").click(function () {
      togglePasswordVisibility("password1", "password1-toggler");
    });$("#password2-toggler").click(function () {
      togglePasswordVisibility("password2", "password2-toggler");
    });
    let hospitalMap = {};
    let hospitalList = [];
    const userRole = await getUserGroup();
    if (userRole !== "UserManagementAdmin") {
        window.location.href = "dashboard.html";
    }
    if(hospital_id === "admin"){
        $("#hospitals-nav").removeClass("invisible")
        $("#hospitals-nav").addClass("visible")

    }else{
        $("#hospitals-nav").removeClass("visible")
        $("#hospitals-nav").addClass("invisible")
    }
    const xhr = new XMLHttpRequest();
    if (hospital_id === "admin") {
        xhr.open("GET", `${BASE_URL}/api/hospitals/`);
    } else {
        xhr.open("GET", `${BASE_URL}/api/hospitals/${hospital_id}`);
    }
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("X-Id-Token", await getIdToken());
    xhr.onreadystatechange = async function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            const hospitals = JSON.parse(xhr.responseText);
            if (hospital_id === "admin"){
                hospitalList = hospitals;
            }else{
                hospitalList = [hospitals]
            }
            const hospitalSelect = document.getElementById("hospital");
            const hospitalSelect2 = document.getElementById("changeHospital");
            //set hospital options in add user modal
            for (let hospital of hospitalList) {
                hospitalMap[hospital.id] = hospital.name;
                const option = document.createElement("option");
                const option2 = document.createElement("option");

                option.value = hospital.id;
                option.textContent = hospital.name;

                option2.value = hospital.id;
                option2.textContent = hospital.name;

                hospitalSelect.appendChild(option);
                hospitalSelect2.appendChild(option2);
            }
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
    $(".closeChangePass").click(closeChangePassModal)
    $(".closeAdduser").click(closeUserModal)
    $("#add-user").click(addUserButtonAction);
    $("#saveUser").click(addUserToCognito);
    $(".closeEditUser").click(closeUserEditModal);
    $("#saveChangeUser").click(editUser);
    $("#appointmentForm").validate({
        rules: {
            user_name: {
                required: true,
            },
            password: {
                required: true,
                minlength: 8,
                pattern: PASSWORD_REGEX

            },
            hospital: {
                required: true,
            },
            role: {
                required: true,

            }
        },
        messages: {
            user_name: {
                required: "Please enter a Username",
            },
            password: {
                required: "Please enter your password.",
                minlength: "Your password must be at least 8 characters long.",
                pattern: "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character."
            },
            role: {
                required: "Please select a role",
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    $("#changePassForm").validate({
        rules: {
            role: {
                required: true,

            }
        },
        messages: {
            role: {
                required: "Please select a role",
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });

    $("#changePassForm").validate({
        rules: {
            password1: {
                required: true,
                minlength: 8,
                pattern: PASSWORD_REGEX

            },
            password2: {
                required: true,
                equalTo: "#password1"

            },
        },
        messages: {
            password1: {
                required: "Please enter your password.",
                minlength: "Your password must be at least 8 characters long.",
                pattern: "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character."
            },
            password2: {
                required: "Please confirm your password.",
                equalTo: "Passwords should be matched."
            },
        },
        errorPlacement: function (error, element) {
            error.insertAfter(element);
            error.addClass("text-danger");

        },
    });
    cognitoIdentityServiceProvider.listUsers(COGNITO_PARAMS, async (err, data) => {
        if (err) {
            console.error('Error listing users:', err);
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

        } else {
            let columns_data = [
                // { data: "Username", title: "Username" },
                { data: "Email", title: "Username" },
                { data: "Hospital", title: "Hospital", render: function (data, type, row) { return hospitalMap[data] || data; }},
                {
                    data: "Group",
                    title: "Group",
                },
                {
                    data: "Enabled", title: "Enabled", render: function (data, type, row) {
                        return data ? 'Yes' : 'No';
                    }
                },
                { data: "UserStatus", title: "User Status" },
                {
                    data: null,
                    render: function (data, type, row) {
                        return (
                            `<div class="d-flex" id="tableButtons">
                <div class="d-flex gap-2">
                  <button class="button-secondary changePassword" data-username=${row.Username} >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="17"
                      height="16"
                      viewBox="0 0 17 16"
                      fill="none"
                    >
                      <g clip-path="url(#clip0_395_3454)">
                        <path
                          d="M12.3334 6.66622L9.66668 3.99955M2 14.3329L4.25625 14.0822C4.53191 14.0516 4.66974 14.0362 4.79856 13.9945C4.91286 13.9575 5.02163 13.9053 5.12192 13.8391C5.23497 13.7646 5.33303 13.6665 5.52915 13.4704L14.3333 4.66622C15.0697 3.92984 15.0697 2.73593 14.3333 1.99955C13.597 1.26317 12.4031 1.26317 11.6667 1.99955L2.86249 10.8037C2.66636 10.9999 2.5683 11.0979 2.49376 11.211C2.42762 11.3113 2.37534 11.42 2.33834 11.5343C2.29664 11.6631 2.28132 11.801 2.25069 12.0766L2 14.3329Z"
                          stroke="#2464E4"
                          stroke-width="2"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </g>
                      <defs>
                        <clipPath id="clip0_395_3454">
                          <rect
                            width="16"
                            height="16"
                            fill="white"
                            transform="translate(0.333252)"
                          />
                        </clipPath>
                      </defs>
                    </svg>
                    Change Password
                  </button>
                  <button
                    title="edit"
                    class="button-tertiary editUser"
                    data-username=${row.Username}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="18"
                      height="18"
                      viewBox="0 0 18 18"
                      fill="none"
                    >
                      <path
                        d="M14 7.33326L10.6667 3.99993M1.08331 16.9166L3.90362 16.6032C4.24819 16.5649 4.42048 16.5458 4.58152 16.4937C4.72439 16.4474 4.86035 16.3821 4.98572 16.2994C5.12702 16.2062 5.2496 16.0836 5.49475 15.8385L16.5 4.83326C17.4205 3.91279 17.4205 2.4204 16.5 1.49993C15.5795 0.579452 14.0871 0.579451 13.1667 1.49992L2.16142 12.5052C1.91627 12.7503 1.79369 12.8729 1.70051 13.0142C1.61784 13.1396 1.55249 13.2755 1.50624 13.4184C1.45411 13.5794 1.43497 13.7517 1.39668 14.0963L1.08331 16.9166Z"
                        stroke="#111827"
                        stroke-width="1.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      ></path>
                    </svg>
                  </button>
                  <button
                    title="delete"
                    class="button-tertiary deleteUser"
                    data-username=${row.Username}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 20 20"
                      fill="none"
                    >
                      <path
                        d="M13.3333 4.99984V4.33317C13.3333 3.39975 13.3333 2.93304 13.1517 2.57652C12.9919 2.26292 12.7369 2.00795 12.4233 1.84816C12.0668 1.6665 11.6001 1.6665 10.6667 1.6665H9.33333C8.39991 1.6665 7.9332 1.6665 7.57668 1.84816C7.26308 2.00795 7.00811 2.26292 6.84832 2.57652C6.66667 2.93304 6.66667 3.39975 6.66667 4.33317V4.99984M8.33333 9.58317V13.7498M11.6667 9.58317V13.7498M2.5 4.99984H17.5M15.8333 4.99984V14.3332C15.8333 15.7333 15.8333 16.4334 15.5608 16.9681C15.3212 17.4386 14.9387 17.821 14.4683 18.0607C13.9335 18.3332 13.2335 18.3332 11.8333 18.3332H8.16667C6.76654 18.3332 6.06647 18.3332 5.53169 18.0607C5.06129 17.821 4.67883 17.4386 4.43915 16.9681C4.16667 16.4334 4.16667 15.7333 4.16667 14.3332V4.99984"
                        stroke="#111827"
                        stroke-width="1.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      ></path>
                    </svg>
                  </button>
                </div>
              </div>`
                        );
                    },
                },
            ];
            let users_list = [];
            for (let user of data.Users) {
                for(let attribute of user.Attributes){
                    if(attribute.Name === "custom:hospital_id"){
                        user["Hospital"] = attribute.Value;
                    }
                    if(attribute.Name === "email"){
                        user["Email"] = attribute.Value;
                    }
                }
                user["Group"] = await getUserGroupNameForUser(cognitoIdentityServiceProvider, user["Username"]);
                // user["Hospital"] = await getCustomAttributeForUser(cognitoIdentityServiceProvider, user["Username"], "custom:hospital_id");
                if (user["Hospital"] && user["Email"] && user["Group"]) {
                    if((user["Hospital"] == hospital_id) || (hospital_id == "admin")){
                        users_list.push(user);
                    }
                }else{
                    console.log(`Skipping user ${user.Username} due to missing attributes`);
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
            console.log(data)
            const SearchIcon = $(
                '<span id="searchIconSvg">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">' +
                '<path d="M16.6666 16.6667L13.4444 13.4445M15.1851 9.25927C15.1851 12.5321 12.532 15.1852 9.25918 15.1852C5.98638 15.1852 3.33325 12.5321 3.33325 9.25927C3.33325 5.98647 5.98638 3.33334 9.25918 3.33334C12.532 3.33334 15.1851 5.98647 15.1851 9.25927Z" stroke="#374151" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
                "</svg>" +
                "</span>"
            );
            let table = $("#mod_ehr").DataTable({
                data: users_list,
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

            })
            tablePaginationNavigationHandler(table);
            table.on("draw.dt", function () {
                tablePaginationNavigationHandler(table);
                $(".changePassword").click(changePasswordButtonAction)
                $(".deleteUser").click(deleteUserButtonAction)
                $(".editUser").click(function(){
                    editUserButtonAction.call(this, hospitalList)
                })
            });
            $(".changePassword").click(changePasswordButtonAction)
            $(".deleteUser").click(deleteUserButtonAction)
            $(".editUser").click(function(){
                    editUserButtonAction.call(this, hospitalList)
                })
            postRender();

        }
    });
})
