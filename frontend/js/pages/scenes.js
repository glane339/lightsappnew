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
    banner("", "");
    renderLibrary();
  }

  async function loadScene(scene) {
    editingId = scene.id;
    idInput.value = scene.id;
    idInput.disabled = true;
    deleteBtn.hidden = false;
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
      banner("error", "Need DMX and WLED.");
      return;
    }
    try {
      var body = {
        dmx_preset_list_id: dmxListId,
        wled_preset_list_id: wledListId,
      };
      var saved;
      if (editingId) {
        body.ilda_frame_list_id = ildaByScene[editingId] || null;
        saved = await api.scenes.update(editingId, body);
      } else {
        var slug = idInput.value.trim();
        if (slug) {
          body.id = slug;
        }
        saved = await api.scenes.create(body);
      }
      editingId = saved.id;
      idInput.value = saved.id;
      idInput.disabled = true;
      deleteBtn.hidden = false;
      await refresh();
      renderLibrary();
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
      var ok = await chrome.confirmDelete(api.scenes, editingId);
      if (!ok) {
        return;
      }
      await refresh();
      newScene();
      banner("ok", "Deleted");
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
