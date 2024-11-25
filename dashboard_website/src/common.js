
import { fetchAuthSession, signOut, } from "aws-amplify/auth";
import { Amplify } from "aws-amplify";

// export const BASE_URL = process.env.BASE_URL || window.location.origin
// export const { REGION } = process.env;
// export const { POOL_ID } = process.env;
// export const { CLIENT_ID } = process.env;
// export const { IDENTITY_POOL_ID } = process.env;

export const BASE_URL = process.env.BASE_URL || window.location.origin;
export const POOL_ID= process.env.POOL_ID;
export const CLIENT_ID= process.env.CLIENT_ID;
export const IDENTITY_POOL_ID = process.env.IDENTITY_POOL_ID;
export const REGION = process.env.REGION;
export const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/
export const GOOGLE_MAPS_KEY = process.env.GOOGLE_MAPS_KEY
Amplify.configure({
    Auth: {
        mandatorySignIn: true,
        authenticationFlowType: "USER_PASSWORD_AUTH",
        Cognito: {
            region: REGION,
            userPoolId: POOL_ID,
            userPoolClientId: CLIENT_ID,
            identityPoolId: IDENTITY_POOL_ID,
            identityPoolRegion: REGION,
        },
    },
});
export const COGNITO_PARAMS = {
    UserPoolId: POOL_ID,
};
export async function getUserSession(redirect = true) {
    const session = await fetchAuthSession({ forceRefresh: false });
    if (!session.tokens && redirect) {
        window.location.href = "index.html";
    }
    return session;
}
export async function getAccessToken() {
    const session = await getUserSession();
    return session.tokens.accessToken.toString();
}
export async function getIdToken() {
    const session = await getUserSession();
    return session.tokens.idToken.toString()
}
export function getIss() {
    return `cognito-idp.${REGION}.amazonaws.com/${POOL_ID}`
}
export async function getUserGroup() {
    const session = await getUserSession();
    return session.tokens.idToken.payload["cognito:groups"][0];
}
export async function logoutUser() {
    $(this).html(
        `<div class="d-flex gap-1 align-items-center justify-content-center">
            <div> Logging out</div>
            <div class="loader-small" />
        </div`
    );
    try {
        await signOut({ global: true });
        window.location.reload();
    } catch (error) {
        console.log("error signing in", error);
    }
}

export function tablePaginationNavigationHandler(table) {
    let pageInfo = table.page.info();
    if (pageInfo.pages <= 1) {
        $("#mod_ehr_paginate").hide();
    } else {
        $("#mod_ehr_paginate").show();
    }
}

export function preRender() {
    $("#table-filter").hide();
    $("#spinner").show();
}

export function postRender() {
    $("#table-filter").show();
    $("#spinner").hide();
}

export function toggleSkeletonLoader(elementId, action) {
    const targetBody = document.getElementById(elementId);
    if (targetBody) {
        const elements = targetBody.querySelectorAll("*");

        elements.forEach((element) => {
            if (element.classList.contains("skeleton-text")) {
                if (action === "add") {
                    element.classList.add("skeleton");
                    element.style.setProperty("margin-bottom", "4px", "important");
                } else if (action === "remove") {
                    element.classList.remove("skeleton");
                    element.removeAttribute("style");
                }
            }
        });
    }
};
export function getUserGroupNameForUser(cognitoIdentityServiceProvider, username) {
    return new Promise((resolve, reject) => {
        cognitoIdentityServiceProvider.adminListGroupsForUser(
            { ...COGNITO_PARAMS, Username: username, Limit: 1 },
            (err, data) => {
                if (err) {
                    resolve("N/A");
                } else if (data.Groups && data.Groups.length > 0) {
                    resolve(data.Groups[0].GroupName);
                } else {
                    resolve("N/A");
                }
            }
        );
    });
}
