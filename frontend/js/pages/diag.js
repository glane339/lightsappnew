"use strict";

(function () {
  var BUDGET_US = 13000;
  var api = window.LightsApi;
  var chrome = window.LightsChrome;
  chrome.mountDiag();

  var els = function (id) {
    return document.getElementById(id);
  };
  var activeSceneId = null;

  function log(line) {
    var box = els("log");
    var stamp = new Date().toLocaleTimeString();
    box.textContent = stamp + "  " + line + "\n" + box.textContent;
  }

  function showLatency(us) {
    var node = els("last");
    node.textContent = us.toLocaleString() + " µs";
    node.className = "big " + (us <= BUDGET_US ? "good" : "bad");
  }

  function applyState(state) {
    activeSceneId = state.active_scene_id;
    els("state").textContent = state.is_active ? "active: " + chrome.shortId(activeSceneId) : "idle";
    document.querySelectorAll("[data-scene]").forEach(function (button) {
      button.classList.toggle("on", button.dataset.scene === activeSceneId);
    });
  }

  var show = window.LightsShow.connect({
    status: function (payload) {
      chrome.setConnection(payload.text, payload.cls);
    },
    state: applyState,
    ack: function (msg) {
      showLatency(msg.latency_us);
    },
    error: function (msg) {
      log("error: " + msg.message);
    },
  });

  async function refreshStatus() {
    try {
      var status = await api.status();
      els("count").textContent = status.latency.count;
      els("p50").textContent = status.latency.count ? status.latency.p50_us + " µs" : "—";
      els("p99").textContent = status.latency.count ? status.latency.p99_us + " µs" : "—";
      els("sender").textContent =
        status.sender.transport + (status.sender.running ? "" : " (stopped)");
      els("frames").textContent = status.sender.frames_sent ?? "—";
      els("ledfx").textContent = status.ledfx.enabled
        ? status.ledfx.reachable
          ? "reachable"
          : "unreachable"
        : "disabled";
    } catch (err) {
      chrome.setConnection("status fetch failed", "dead");
    }
  }

  async function loadScenes() {
    var box = els("scenes");
    try {
      var scenes = await api.scenes.list();
      box.textContent = "";
      if (!scenes.length) {
        box.innerHTML = '<span class="empty">No scenes in the library yet.</span>';
        return;
      }
      scenes.forEach(function (scene) {
        var button = document.createElement("button");
        button.textContent = chrome.shortId(scene.id);
        button.title = scene.id + " — sensitivity " + scene.sensitivity;
        button.dataset.scene = scene.id;
        button.classList.toggle("on", scene.id === activeSceneId);
        button.onclick = function () {
          show.activate(scene.id);
        };
        box.appendChild(button);
      });
    } catch (err) {
      box.innerHTML = '<span class="empty">Could not load scenes.</span>';
    }
  }

  els("beat").onclick = function () {
    show.beat();
  };
  els("deactivate").onclick = function () {
    show.deactivate();
  };
  els("blackout").onclick = function () {
    show.blackout();
  };
  els("reload").onclick = function () {
    loadScenes();
    refreshStatus();
  };

  document.addEventListener("keydown", function (event) {
    if (event.code === "Space" && event.target === document.body) {
      event.preventDefault();
      show.beat();
    }
  });

  loadScenes();
  refreshStatus();
  setInterval(refreshStatus, 2000);
})();
