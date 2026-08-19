"use strict";

(function (global) {
  var BUILDER_NAV = [
    { href: "/builder/gigbar2/", id: "gigbar2", group: "Device presets", label: "GigBAR 2" },
    { href: "/builder/keobin/", id: "keobin", group: "Device presets", label: "Keobin" },
    { href: "/builder/dmx-presets/", id: "dmx-presets", group: "dmx_presets", label: "Pair" },
    { href: "/builder/dmx-preset-lists/", id: "dmx-preset-lists", group: "Cue lists", label: "DMX lists" },
    { href: "/builder/wled-preset-lists/", id: "wled-preset-lists", group: "Cue lists", label: "WLED lists" },
    { href: "/builder/scenes/", id: "scenes", group: "Show", label: "Scenes" },
  ];

  function topLinks(mode) {
    return [
      { href: "/performance/", id: "performance", label: "Performance" },
      { href: "/builder/gigbar2/", id: "builder", label: "Builder" },
      { href: "/diag/", id: "diag", label: "Diag" },
      { href: "/about/", id: "about", label: "About" },
    ]
      .map(function (link) {
        var current = link.id === mode ? " current" : "";
        return '<a class="' + current.trim() + '" href="' + link.href + '">' + link.label + "</a>";
      })
      .join("");
  }

  function showStopped() {
    document.body.innerHTML = '<main class="stopped"><p>Stopped</p></main>';
  }

  function bindStop(bar) {
    var btn = bar.querySelector("#stop-server");
    if (!btn) {
      return;
    }
    btn.onclick = function () {
      if (!window.confirm("Stop?")) {
        return;
      }
      btn.disabled = true;
      fetch("/api/shutdown", { method: "POST" }).finally(showStopped);
    };
  }

  function mountTopbar(mode, extra) {
    var bar = document.createElement("header");
    bar.className = "topbar";
    bar.innerHTML =
      '<a class="brand" href="/"><h1>Lights</h1></a>' +
      (extra || "") +
      "<nav>" +
      topLinks(mode) +
      "</nav>" +
      '<button type="button" id="stop-server" class="ghost">Stop</button>';
    document.body.prepend(bar);
    bindStop(bar);
    return bar;
  }

  function mountBuilder(current) {
    document.body.classList.add("mode-builder");
    mountTopbar("builder");
    var page = document.getElementById("page");
    var shell = document.createElement("div");
    shell.className = "builder-shell";
    var nav = document.createElement("nav");
    nav.className = "builder-nav";
    var html = "";
    BUILDER_NAV.forEach(function (item) {
      html +=
        '<a href="' +
        item.href +
        '"' +
        (item.id === current ? ' class="current"' : "") +
        ">" +
        item.label +
        "</a>";
    });
    nav.innerHTML = html;
    page.parentNode.insertBefore(shell, page);
    shell.appendChild(nav);
    shell.appendChild(page);
  }

  function banner(el, kind, message) {
    if (!el) {
      return;
    }
    el.className = "banner " + (kind || "") + (message ? " show" : "");
    el.textContent = message || "";
  }

  function shortId(id) {
    if (!id) {
      return "—";
    }
    return id.length > 18 ? id.slice(0, 16) + "…" : id;
  }

  async function confirmDelete(apiCollection, id) {
    var plan;
    try {
      plan = await apiCollection.deletePlan(id);
    } catch (err) {
      return window.confirm("Delete " + id + "?\n" + err.message);
    }
    var extraRemoves = (plan.removes || []).filter(function (row) {
      return row.id !== id;
    });
    var detaches = plan.detaches || [];
    var lines = ["Delete " + id + "?"];
    if (extraRemoves.length) {
      lines.push(
        "Also removes: " +
          extraRemoves
            .map(function (row) {
              return row.collection + "/" + row.id;
            })
            .join(", ")
      );
    }
    if (detaches.length) {
      lines.push(
        "Detaches from: " +
          detaches
            .map(function (row) {
              return row.collection + "/" + row.id;
            })
            .join(", ")
      );
    }
    if (!window.confirm(lines.join("\n"))) {
      return false;
    }
    var force = extraRemoves.length > 0 || detaches.length > 0;
    await apiCollection.remove(id, force);
    return true;
  }

  function bindList(container, items, selectedId, onPick) {
    container.textContent = "";
    if (!items.length) {
      var empty = document.createElement("span");
      empty.className = "empty";
      empty.textContent = "—";
      container.appendChild(empty);
      return;
    }
    items.forEach(function (item) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = item.id;
      button.title = item.id;
      if (item.id === selectedId) {
        button.classList.add("on");
      }
      button.onclick = function () {
        onPick(item);
      };
      container.appendChild(button);
    });
  }

  global.LightsChrome = {
    mountHome: function () {
      document.body.classList.add("mode-home");
      mountTopbar("home");
    },
    mountBuilder: mountBuilder,
    mountPerformance: function () {
      document.body.classList.add("mode-performance");
      var conn = document.createElement("span");
      conn.id = "conn";
      conn.className = "conn";
      conn.textContent = "…";
      var bar = mountTopbar("performance", conn.outerHTML);
      var beat = document.getElementById("beat-bar");
      if (beat && beat.parentNode === document.body) {
        document.body.insertBefore(beat, bar);
      }
    },
    mountDiag: function () {
      document.body.classList.add("mode-diag");
      var conn = document.createElement("span");
      conn.id = "conn";
      conn.className = "conn";
      conn.textContent = "…";
      mountTopbar("diag", conn.outerHTML);
    },
    mountAbout: function () {
      document.body.classList.add("mode-about");
      mountTopbar("about");
    },
    banner: banner,
    shortId: shortId,
    confirmDelete: confirmDelete,
    bindList: bindList,
    setConnection: function (text, cls) {
      var el = document.getElementById("conn");
      if (!el) {
        return;
      }
      el.textContent = text;
      el.className = "conn" + (cls ? " " + cls : "");
    },
  };
})(window);
