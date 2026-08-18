"use strict";

(function () {
  var cfg = window.DEVICE_PAGE;
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  var bannerEl = document.getElementById("banner");
  var libraryEl = document.getElementById("library");
  var form = document.getElementById("form");
  var idInput = document.getElementById("preset-id");
  var fixtureEl = document.getElementById("fixture");
  var deleteBtn = document.getElementById("delete-btn");
  var missingEl = document.getElementById("missing");

  var profile = window[cfg.profileGlobal];
  var editor = null;
  var device = null;
  var editingId = null;
  var presets = [];

  chrome.mountBuilder(cfg.nav);

  function banner(kind, message) {
    chrome.banner(bannerEl, kind, message);
  }

  function filtered() {
    return presets.filter(function (preset) {
      return preset.device_id === device.id;
    });
  }

  function renderLibrary() {
    chrome.bindList(libraryEl, filtered(), editingId, function (preset) {
      loadPreset(preset);
    });
  }

  function newPreset() {
    editingId = null;
    idInput.value = "";
    idInput.disabled = false;
    deleteBtn.hidden = true;
    editor.reset();
    banner("", "");
    renderLibrary();
    idInput.focus();
  }

  function loadPreset(preset) {
    editingId = preset.id;
    idInput.value = preset.id;
    idInput.disabled = true;
    deleteBtn.hidden = false;
    editor.setValues(preset.channel_values);
    banner("", "");
    renderLibrary();
  }

  async function refresh() {
    presets = await api.devicePresets.list();
    renderLibrary();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    save();
  });

  document.getElementById("new-btn").addEventListener("click", newPreset);
  deleteBtn.addEventListener("click", function () {
    removeCurrent();
  });

  async function save() {
    var check = editor.validate();
    if (!check.ok) {
      banner("error", check.errors.join(" "));
      return;
    }
    var body = {
      device_id: device.id,
      channel_values: editor.getValues(),
    };
    var slug = idInput.value.trim();
    try {
      var saved;
      if (editingId) {
        saved = await api.devicePresets.update(editingId, {
          channel_values: body.channel_values,
        });
      } else {
        if (slug) {
          body.id = slug;
        }
        saved = await api.devicePresets.create(body);
      }
      editingId = saved.id;
      idInput.value = saved.id;
      idInput.disabled = true;
      deleteBtn.hidden = false;
      await refresh();
      banner("ok", "Saved " + saved.id);
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function removeCurrent() {
    if (!editingId) {
      return;
    }
    try {
      var ok = await chrome.confirmDelete(api.devicePresets, editingId);
      if (!ok) {
        return;
      }
      await refresh();
      newPreset();
      banner("ok", "Deleted.");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function start() {
    if (!profile) {
      missingEl.className = "banner error show";
      missingEl.hidden = false;
      missingEl.textContent = "Missing fixture profile " + cfg.profileGlobal + ".";
      form.hidden = true;
      return;
    }
    try {
      var devices = await api.devices();
      device = devices.find(function (item) {
        return item.model === cfg.model && item.mode === cfg.mode;
      });
      if (!device) {
        missingEl.className = "banner error show";
        missingEl.hidden = false;
        missingEl.textContent = cfg.missingHint;
        form.hidden = true;
        return;
      }
      editor = window.LightsFixtureEditor.mount(fixtureEl, profile);
      await refresh();
      newPreset();
    } catch (err) {
      banner("error", err.message);
    }
  }

  start();
})();
