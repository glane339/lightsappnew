"use strict";

(function () {
  var cfg = window.CUE_LIST_PAGE;
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountBuilder(cfg.nav);

  var bannerEl = document.getElementById("banner");
  var libraryEl = document.getElementById("library");
  var form = document.getElementById("form");
  var idInput = document.getElementById("list-id");
  var beatsInput = document.getElementById("beats");
  var deleteBtn = document.getElementById("delete-btn");
  var registerWrap = document.getElementById("register-wrap");
  var registerName = document.getElementById("register-name");
  var registerBtn = document.getElementById("register-btn");

  var collection = api[cfg.collection];
  var paletteApi = api[cfg.palette];
  var editingId = null;
  var lists = [];
  var drag = window.LightsDragList.mount(
    document.getElementById("cue-list"),
    document.getElementById("palette"),
    {
      onChange: function () {
        banner("", "");
      },
    }
  );

  function banner(kind, message) {
    chrome.banner(bannerEl, kind, message);
  }

  function renderLibrary() {
    chrome.bindList(libraryEl, lists, editingId, loadList);
  }

  function newList() {
    editingId = null;
    idInput.value = "";
    idInput.disabled = false;
    beatsInput.value = "1";
    deleteBtn.hidden = true;
    drag.clear();
    banner("", "");
    renderLibrary();
  }

  function loadList(item) {
    editingId = item.id;
    idInput.value = item.id;
    idInput.disabled = true;
    beatsInput.value = String(item.beats);
    deleteBtn.hidden = false;
    drag.setIds(item[cfg.idsField] || []);
    banner("", "");
    renderLibrary();
  }

  async function loadPalette() {
    var items = await paletteApi.list();
    drag.setPalette(
      items.map(function (item) {
        return { id: item.id, label: item.id };
      })
    );
  }

  async function refresh() {
    await loadPalette();
    lists = await collection.list();
    renderLibrary();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    save();
  });
  document.getElementById("new-btn").addEventListener("click", newList);
  deleteBtn.addEventListener("click", function () {
    removeCurrent();
  });

  if (cfg.allowRegister) {
    registerWrap.hidden = false;
    registerBtn.addEventListener("click", function () {
      register();
    });
    registerName.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        register();
      }
    });
    var refreshBtn = document.getElementById("refresh-ledfx");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        refreshLedfx();
      });
    }
  }

  async function refreshLedfx() {
    try {
      var result = await api.wledPresets.refreshLedfx();
      await loadPalette();
      banner("ok", "LEDfx +" + (result.added || 0));
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function register() {
    var name = registerName.value.trim();
    if (!name) {
      banner("error", "Need a name.");
      return;
    }
    try {
      await api.wledPresets.register(name);
      registerName.value = "";
      await loadPalette();
      banner("ok", "Saved");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function save() {
    var ids = drag.getIds();
    var beats = Number(beatsInput.value);
    if (!ids.length) {
      banner("error", "Empty.");
      return;
    }
    if (!Number.isInteger(beats) || beats < 1) {
      banner("error", "Beats ≥ 1.");
      return;
    }
    var body = { beats: beats };
    body[cfg.idsField] = ids;
    try {
      var saved;
      if (editingId) {
        saved = await collection.update(editingId, body);
      } else {
        var slug = idInput.value.trim();
        if (slug) {
          body.id = slug;
        }
        saved = await collection.create(body);
      }
      editingId = saved.id;
      idInput.value = saved.id;
      idInput.disabled = true;
      deleteBtn.hidden = false;
      await refresh();
      loadList(saved);
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
      var ok = await chrome.confirmDelete(collection, editingId);
      if (!ok) {
        return;
      }
      await refresh();
      newList();
      banner("ok", "Deleted");
    } catch (err) {
      banner("error", err.message);
    }
  }

  async function start() {
    try {
      await refresh();
      newList();
    } catch (err) {
      banner("error", err.message);
    }
    if (cfg.pollMs) {
      setInterval(function () {
        loadPalette().catch(function (err) {
          banner("warn", err.message);
        });
      }, cfg.pollMs);
    }
  }

  start();
})();
