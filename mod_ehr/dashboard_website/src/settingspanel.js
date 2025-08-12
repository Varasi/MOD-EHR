import {
  getAccessToken,
  logoutUser,
  preRender,
  BASE_URL,
  toggleSkeletonLoader,
  toggleLoder,
  toggleAlertMessage,
} from "./common";

var settingsDataStatus = false;
const xhr = new XMLHttpRequest();

const updateTextContent = async (elementId, value) => {
  const element = document.getElementById(elementId);
  if (element) {
    element.textContent = value;
  }
};

const toggler = (buttonId, modalID) => {
  const settingsToggler = document.getElementById(buttonId);
  const settingsModal = document.getElementById(modalID);

  if (settingsToggler && settingsModal) {
    if (settingsModal.classList.contains("d-none")) {
      settingsModal.classList.remove("d-none");
      settingsModal.classList.add("d-block");
    } else {
      settingsModal.classList.remove("d-none");
      settingsModal.classList.add("d-none");
    }
  } else {
    console.error("Settings toggler or modal not found.");
  }
};

const handleInputChange = async () => {
  const startValue = await document.getElementById("prior_period").value;
  const subsequentValue = await document.getElementById("subsequent_period")
    .value;
  const saveButton = await document.getElementById("settings-form-submit-btn");
  if (startValue >= 15 && subsequentValue >= 15) {
    updateTextContent("prior_period_text", startValue);
    updateTextContent("subsequent_period_text", subsequentValue);
    saveButton.removeAttribute("disabled");
  } else {
    saveButton.setAttribute("disabled", "disabled");
  }
};

const handleSettingsClick = async () => {
  toggler("settingsToggler", "settingsModal");
  const accessToken = await getAccessToken();
  if (settingsDataStatus === false) {
    toggleSkeletonLoader("settingsForm", "add");
    xhr.open("GET", `${BASE_URL}/api/settings/`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.onreadystatechange = async function () {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        if (xhr.status === 200) {
          let settings_records = JSON.parse(xhr.responseText);
          settingsDataStatus = true;
          toggleSkeletonLoader("settingsForm", "remove");
          for (let settings of settings_records) {
            $(`#${settings.name}`).val(settings.value);
            $(`#${settings.name}_text`).text(settings.value);
          }
        }
      }
    };
  } else {
    settingsDataStatus = false;
  }
  xhr.send();
};

const handleFormSubmit = async () => {
  const formData = {
    prior_period: document.getElementById("prior_period").value,
    subsequent_period: document.getElementById("subsequent_period").value,
  };
  const accessToken = await getAccessToken();
  const keys = Object.keys(formData);
  const link = `${BASE_URL}/api/settings`;

  for (const key of keys) {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${link}/${key}`);
    xhr.setRequestHeader("Authorization", accessToken);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({ name: key, value: formData[key] }));
  }

  settingsDataStatus = false;

  toggler("settings-form-submit-btn", "settingsModal");
  toggleAlertMessage("Settings has been Updated Successfully");
};

$(document).ready(async function () {
  preRender();
  $("#logout").click(logoutUser);

  $("#settingsToggler").click(() => {
    handleSettingsClick();
  });

  $("#closeSettingsModal").click(() => {
    settingsDataStatus = false;
    toggler("closeSettingsModal", "settingsModal");
  });

  $("#settings-form-submit-btn").click(handleFormSubmit);

  $("#prior_period").change(handleInputChange);
  $("#subsequent_period").change(handleInputChange);
});
