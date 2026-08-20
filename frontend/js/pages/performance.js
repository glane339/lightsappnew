"use strict";

(function () {
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountPerformance();

  var KEYS = "1234567890QWERTYUIOPASDFGHJKLZXCVBNM";
  var grid = document.getElementById("scenes");
  var beatBar = document.getElementById("beat-bar");
  var activeSceneId = null;
  var flashTimer = null;

  function flashBeat() {
    beatBar.classList.remove("flash");
    void beatBar.offsetWidth;
    beatBar.classList.add("flash");
    if (flashTimer) {
      clearTimeout(flashTimer);
    }
    flashTimer = setTimeout(function () {
      beatBar.classList.remove("flash");
    }, 200);
  }

  function paintActive() {
    grid.querySelectorAll("[data-scene]").forEach(function (tile) {
      tile.classList.toggle("on", tile.dataset.scene === activeSceneId);
    });
  }

  async function loadScenes() {
    try {
      var scenes = await api.scenes.list();
      grid.textContent = "";
      if (!scenes.length) {
        var empty = document.createElement("span");
        empty.className = "empty";
        empty.textContent = "—";
        grid.appendChild(empty);
        return;
      }
      scenes.forEach(function (scene, index) {
        var tile = document.createElement("button");
        tile.type = "button";
        tile.className = "scene-tile";
        tile.dataset.scene = scene.id;
        var key = KEYS.charAt(index);
        if (key) {
          tile.dataset.hotkey = key;
          var badge = document.createElement("span");
          badge.className = "hotkey";
          badge.textContent = key;
          tile.appendChild(badge);
        }
        var name = document.createElement("span");
        name.className = "scene-name";
        name.textContent = scene.id;
        tile.appendChild(name);
        tile.classList.toggle("on", scene.id === activeSceneId);
        tile.onclick = function () {
          show.activate(scene.id);
        };
        grid.appendChild(tile);
      });
    } catch (err) {
      grid.innerHTML = "";
      var empty = document.createElement("span");
      empty.className = "empty";
      empty.textContent = err.message;
      grid.appendChild(empty);
    }
  }

  var show = window.LightsShow.connect({
    status: function (payload) {
      chrome.setConnection(payload.text, payload.cls);
    },
    state: function (state) {
      activeSceneId = state.is_active ? state.active_scene_id : null;
      paintActive();
    },
    beat: function () {
      flashBeat();
    },
    error: function (msg) {
      chrome.setConnection(msg.message || "error", "dead");
    },
  });

  document.getElementById("deactivate").onclick = function () {
    show.deactivate();
  };
  document.getElementById("blackout").onclick = function () {
    show.blackout();
  };
  document.getElementById("beat").onclick = function () {
    show.beat();
  };
  document.getElementById("reload").onclick = function () {
    loadScenes();
  };

  document.addEventListener("keydown", function (event) {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (event.target && event.target.closest("input, textarea, select")) {
      return;
    }
    if (event.code === "Space") {
      event.preventDefault();
      show.beat();
      return;
    }
    if (event.repeat || event.key.length !== 1) {
      return;
    }
    var tile = grid.querySelector('[data-hotkey="' + event.key.toUpperCase() + '"]');
    if (!tile) {
      return;
    }
    event.preventDefault();
    show.activate(tile.dataset.scene);
  });

  loadScenes();
})();
