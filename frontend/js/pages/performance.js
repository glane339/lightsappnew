"use strict";

(function () {
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountPerformance();

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
        empty.textContent = "No scenes yet. Author them in Builder.";
        grid.appendChild(empty);
        return;
      }
      scenes.forEach(function (scene) {
        var tile = document.createElement("button");
        tile.type = "button";
        tile.className = "scene-tile";
        tile.textContent = scene.id;
        tile.dataset.scene = scene.id;
        tile.title = scene.id + " — sensitivity " + scene.sensitivity;
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
      empty.textContent = "Could not load scenes: " + err.message;
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
    if (event.code !== "Space") {
      return;
    }
    if (event.target && event.target.closest("input, textarea, select, button, a")) {
      return;
    }
    event.preventDefault();
    show.beat();
  });

  loadScenes();
})();
