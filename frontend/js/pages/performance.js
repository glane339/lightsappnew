"use strict";

(function () {
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountPerformance();

  var KEYS = "1234567890QWERTYUIOPASDFGHJKLZXCVBNM";
  var grid = document.getElementById("scenes");
  var beatBar = document.getElementById("beat-bar");
  var activeSceneId = null;
  var showError = document.getElementById("show-error");
  var healthAudio = document.getElementById("health-audio");
  var healthDmx = document.getElementById("health-dmx");
  var healthLedfx = document.getElementById("health-ledfx");
  var flashTimer = null;

  function setChip(el, text, cls) {
    if (!el) {
      return;
    }
    el.textContent = text;
    el.className = cls || "";
  }

  function paintHealth(status) {
    var audio = status.audio || {};
    var capture = audio.capture || "off";
    var bpm = audio.bpm;
    if (capture === "live") {
      var live = "audio live";
      if (typeof bpm === "number") {
        live += " " + Math.round(bpm) + " BPM";
      }
      if (typeof audio.level === "number") {
        live += " L" + audio.level.toFixed(2);
      }
      setChip(healthAudio, live, "ok");
    } else if (capture === "silent") {
      setChip(healthAudio, "audio silent", "warn");
    } else if (capture === "dead") {
      setChip(healthAudio, "audio dead", "bad");
    } else {
      setChip(healthAudio, "audio off", "");
    }

    var sender = status.sender || {};
    if (!sender.running) {
      setChip(healthDmx, "dmx sender down", "bad");
    } else if (sender.reachable === false) {
      setChip(healthDmx, "dmx unreachable", "bad");
    } else {
      setChip(healthDmx, "dmx " + (sender.transport || "ok"), "ok");
    }

    var ledfx = status.ledfx || {};
    if (!ledfx.enabled) {
      setChip(healthLedfx, "ledfx off", "");
    } else if (ledfx.reachable) {
      setChip(healthLedfx, "ledfx ok", "ok");
    } else {
      setChip(healthLedfx, "ledfx down", "bad");
    }

    if (status.last_error) {
      chrome.banner(showError, "error", status.last_error);
    } else if (showError && showError.classList.contains("error")) {
      chrome.banner(showError, "", "");
    }
  }

  function pollStatus() {
    api.status()
      .then(paintHealth)
      .catch(function (err) {
        setChip(healthAudio, "audio ?", "bad");
        setChip(healthDmx, "dmx ?", "bad");
        setChip(healthLedfx, "ledfx ?", "bad");
        chrome.banner(showError, "error", err.message || "status failed");
      });
  }

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
      chrome.banner(showError, "error", msg.message || "error");
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
  pollStatus();
  setInterval(pollStatus, 1000);
})();
