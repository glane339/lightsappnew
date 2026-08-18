"use strict";

(function () {
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountBuilder("scenes");

  var bannerEl = document.getElementById("banner");
  var libraryEl = document.getElementById("library");
  var form = document.getElementById("form");
  var idInput = document.getElementById("scene-id");
  var dmxSelect = document.getElementById("dmx-list");
  var wledSelect = document.getElementById("wled-list");
  var sensitivityInput = document.getElementById("sensitivity");
  var deleteBtn = document.getElementById("delete-btn");

  var editingId = null;
  var scenes = [];
  var dmxLists = [];
  var wledLists = [];
  var presets = [];
  var ildaByScene = {};

  function banner(kind, message) {
    chrome.banner(bannerEl, kind, message);
  }

  function fillSelect(select, items, selected) {
    select.textContent = "";
    var blank = document.createElement("option");
    blank.value = "";
    blank.textContent = items.length ? "Select…" : "None available";
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

  function renderLibrary() {
    chrome.bindList(libraryEl, scenes, editingId, function (scene) {
      loadScene(scene);
    });
  }

  function listsForPreset(presetId) {
    var preset = presets.find(function (row) {
      return row.id === presetId;
    });
    if (!preset) {
      return { dmx: "", wled: "" };
    }
    return { dmx: preset.dmx_preset_list_id, wled: preset.wled_preset_list_id };
  }

  function newScene() {
    editingId = null;
    idInput.value = "";
    idInput.disabled = false;
    deleteBtn.hidden = true;
    fillSelect(dmxSelect, dmxLists, "");
    fillSelect(wledSelect, wledLists, "");
    sensitivityInput.value = "";
    banner("", "");
    renderLibrary();
  }

  async function loadScene(scene) {
    editingId = scene.id;
    idInput.value = scene.id;
    idInput.disabled = true;
    deleteBtn.hidden = false;
    sensitivityInput.value = String(scene.sensitivity);
    var lists = listsForPreset(scene.preset_id);
    fillSelect(dmxSelect, dmxLists, lists.dmx);
    fillSelect(wledSelect, wledLists, lists.wled);
    banner("", "");
    renderLibrary();
    try {
      var full = await api.scenes.get(scene.id);
      ildaByScene[scene.id] = full.ilda_frame_list_id || null;
    } catch (err) {
      ildaByScene[scene.id] = null;
    }
  }

  async function findOrCreatePreset(dmxListId, wledListId) {
    var found = presets.find(function (preset) {
      return preset.dmx_preset_list_id === dmxListId && preset.wled_preset_list_id === wledListId;
    });
    if (found) {
      return found;
    }
    var created = await api.presets.create({
      dmx_preset_list_id: dmxListId,
      wled_preset_list_id: wledListId,
    });
    presets.push(created);
    return created;
  }

  async function refresh() {
    dmxLists = await api.dmxLists.list();
    wledLists = await api.wledLists.list();
    presets = await api.presets.list();
    scenes = await api.scenes.list();
    fillSelect(dmxSelect, dmxLists, dmxSelect.value);
    fillSelect(wledSelect, wledLists, wledSelect.value);
    renderLibrary();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    save();
  });
  document.getElementById("new-btn").addEventListener("click", newScene);
  deleteBtn.addEventListener("click", function () {
    removeCurrent();
  });

  async function save() {
    var dmxListId = dmxSelect.value;
    var wledListId = wledSelect.value;
    if (!dmxListId || !wledListId) {
      banner("error", "Both a DMX list and a WLED list are required.");
      return;
    }
    var sensitivityRaw = sensitivityInput.value.trim();
    var sensitivity;
    if (sensitivityRaw !== "") {
      sensitivity = Number(sensitivityRaw);
      if (!(sensitivity >= 0 && sensitivity <= 1)) {
        banner("error", "Sensitivity must be between 0.0 and 1.0.");
        return;
      }
    }
    try {
      var preset = await findOrCreatePreset(dmxListId, wledListId);
      var saved;
      if (editingId) {
        saved = await api.scenes.update(editingId, {
          preset_id: preset.id,
          sensitivity: sensitivity === undefined ? 0.5 : sensitivity,
          ilda_frame_list_id: ildaByScene[editingId] || null,
        });
      } else {
        var body = { preset_id: preset.id };
        var slug = idInput.value.trim();
        if (slug) {
          body.id = slug;
        }
        if (sensitivity !== undefined) {
          body.sensitivity = sensitivity;
        }
        saved = await api.scenes.create(body);
      }
      editingId = saved.id;
      idInput.value = saved.id;
      idInput.disabled = true;
      deleteBtn.hidden = false;
      sensitivityInput.value = String(saved.sensitivity);
      await refresh();
      renderLibrary();
      banner("ok", "Saved " + saved.id + ". Test it in Performance.");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function removeCurrent() {
    if (!editingId) {
      return;
    }
    try {
      var ok = await chrome.confirmDelete(api.scenes, editingId);
      if (!ok) {
        return;
      }
      await refresh();
      newScene();
      banner("ok", "Deleted.");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function start() {
    try {
      await refresh();
      newScene();
    } catch (err) {
      banner("error", err.message);
    }
  }

  start();
})();
