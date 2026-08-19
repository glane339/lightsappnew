"use strict";

(function () {
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountBuilder("dmx-presets");

  var bannerEl = document.getElementById("banner");
  var libraryEl = document.getElementById("library");
  var form = document.getElementById("form");
  var idInput = document.getElementById("preset-id");
  var gigbarSelect = document.getElementById("gigbar");
  var keobinSelect = document.getElementById("keobin");
  var deleteBtn = document.getElementById("delete-btn");
  var missingEl = document.getElementById("missing");

  var gigbarDevice = null;
  var keobinDevice = null;
  var editingId = null;
  var looks = [];
  var devicePresets = [];

  function banner(kind, message) {
    chrome.banner(bannerEl, kind, message);
  }

  function optionsFor(deviceId) {
    return devicePresets.filter(function (preset) {
      return preset.device_id === deviceId;
    });
  }

  function fillSelect(select, items, selected) {
    select.textContent = "";
    var blank = document.createElement("option");
    blank.value = "";
    blank.textContent = items.length ? "Select…" : "—";
    select.appendChild(blank);
    items.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = item.id;
      if (item.id === selected) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  }

  function refreshDropdowns(selectedGigbar, selectedKeobin) {
    fillSelect(gigbarSelect, optionsFor(gigbarDevice.id), selectedGigbar);
    fillSelect(keobinSelect, optionsFor(keobinDevice.id), selectedKeobin);
  }

  function renderLibrary() {
    chrome.bindList(libraryEl, looks, editingId, loadLook);
  }

  function newLook() {
    editingId = null;
    idInput.value = "";
    idInput.disabled = false;
    deleteBtn.hidden = true;
    refreshDropdowns("", "");
    banner("", "");
    renderLibrary();
  }

  function idsForLook(look) {
    var gigbarId = "";
    var keobinId = "";
    (look.dmx_device_preset_ids || []).forEach(function (id) {
      var preset = devicePresets.find(function (row) {
        return row.id === id;
      });
      if (!preset) {
        return;
      }
      if (preset.device_id === gigbarDevice.id) {
        gigbarId = id;
      }
      if (preset.device_id === keobinDevice.id) {
        keobinId = id;
      }
    });
    return { gigbarId: gigbarId, keobinId: keobinId };
  }

  function loadLook(look) {
    editingId = look.id;
    idInput.value = look.id;
    idInput.disabled = true;
    deleteBtn.hidden = false;
    var ids = idsForLook(look);
    refreshDropdowns(ids.gigbarId, ids.keobinId);
    banner("", "");
    renderLibrary();
  }

  async function refresh() {
    devicePresets = await api.devicePresets.list();
    looks = await api.dmxPresets.list();
    var selected = idsForLook({
      dmx_device_preset_ids: [gigbarSelect.value, keobinSelect.value],
    });
    refreshDropdowns(
      editingId ? selected.gigbarId || gigbarSelect.value : gigbarSelect.value,
      editingId ? selected.keobinId || keobinSelect.value : keobinSelect.value
    );
    renderLibrary();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    save();
  });
  document.getElementById("new-btn").addEventListener("click", newLook);
  deleteBtn.addEventListener("click", function () {
    removeCurrent();
  });

  async function save() {
    var gigbarId = gigbarSelect.value;
    var keobinId = keobinSelect.value;
    if (!gigbarId || !keobinId) {
      banner("error", "Need both.");
      return;
    }
    var ids = [gigbarId, keobinId];
    try {
      var saved;
      if (editingId) {
        saved = await api.dmxPresets.update(editingId, { dmx_device_preset_ids: ids });
      } else {
        var body = { dmx_device_preset_ids: ids };
        var slug = idInput.value.trim();
        if (slug) {
          body.id = slug;
        }
        saved = await api.dmxPresets.create(body);
      }
      editingId = saved.id;
      idInput.value = saved.id;
      idInput.disabled = true;
      deleteBtn.hidden = false;
      await refresh();
      banner("ok", "Saved");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function removeCurrent() {
    if (!editingId) {
      return;
    }
    try {
      var ok = await chrome.confirmDelete(api.dmxPresets, editingId);
      if (!ok) {
        return;
      }
      await refresh();
      newLook();
      banner("ok", "Deleted");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function start() {
    try {
      var devices = await api.devices();
      gigbarDevice = devices.find(function (item) {
        return item.model === "chauvet_gigbar_2";
      });
      keobinDevice = devices.find(function (item) {
        return item.model === "keobin_light_bar";
      });
      if (!gigbarDevice || !keobinDevice) {
        missingEl.className = "banner error show";
        missingEl.hidden = false;
        missingEl.textContent =
          "GigBAR and Keobin not in patch.";
        form.hidden = true;
        return;
      }
      await refresh();
      newLook();
    } catch (err) {
      banner("error", err.message);
    }
  }

  start();
})();
