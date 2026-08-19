"use strict";

(function (global) {
  function zeros(count) {
    var values = [];
    for (var i = 0; i < count; i += 1) {
      values.push(0);
    }
    return values;
  }

  function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function defaultState(profile) {
    var state = {};
    profile.sections.forEach(function (section) {
      if (section.exclusive === false) {
        state[section.id] = [];
      } else {
        state[section.id] = section.defaultMode || "off";
      }
    });
    return state;
  }

  function modeById(section, id) {
    for (var i = 0; i < section.modes.length; i += 1) {
      if (section.modes[i].id === id) {
        return section.modes[i];
      }
    }
    return null;
  }

  function writeMap(values, map, combineMax) {
    Object.keys(map).forEach(function (key) {
      var channel = Number(key) - 1;
      var next = map[key] | 0;
      if (channel < 0 || channel >= values.length) {
        return;
      }
      values[channel] = combineMax ? Math.max(values[channel], next) : next;
    });
  }

  function ownedMap(section, values) {
    var map = {};
    (section.owned || []).forEach(function (ch) {
      map[ch] = values[ch - 1] | 0;
    });
    return map;
  }

  function encode(profile, state, snapshots) {
    var values = zeros(profile.channelCount);
    profile.sections.forEach(function (section) {
      if (snapshots && snapshots[section.id]) {
        writeMap(values, snapshots[section.id], false);
        return;
      }
      if (section.exclusive === false) {
        (state[section.id] || []).forEach(function (id) {
          var mode = modeById(section, id);
          if (mode) {
            writeMap(values, mode.channels, true);
          }
        });
        return;
      }
      var mode = modeById(section, state[section.id]);
      if (mode) {
        writeMap(values, mode.channels, false);
      }
    });
    return values;
  }

  function ignored(section) {
    return (section.matchIgnore || []).map(Number);
  }

  function modeMatches(mode, values, ignore) {
    var keys = Object.keys(mode.channels);
    var compared = 0;
    for (var i = 0; i < keys.length; i += 1) {
      var ch = Number(keys[i]);
      if (ignore.indexOf(ch) !== -1) {
        continue;
      }
      compared += 1;
      if ((values[ch - 1] | 0) !== (mode.channels[keys[i]] | 0)) {
        return 0;
      }
    }
    return compared;
  }

  function ownedZero(section, values) {
    return (section.owned || Object.keys((section.modes[0] || {}).channels || {})).every(function (ch) {
      return (values[Number(ch) - 1] | 0) === 0;
    });
  }

  function decode(profile, values) {
    var state = defaultState(profile);
    var snapshots = {};
    profile.sections.forEach(function (section) {
      var ignore = ignored(section);
      if (section.exclusive === false) {
        var selected = [];
        section.modes.forEach(function (mode) {
          if (modeMatches(mode, values, ignore) > 0) {
            selected.push(mode.id);
          }
        });
        state[section.id] = selected;
        return;
      }

      var best = null;
      var bestScore = 0;
      section.modes.forEach(function (mode) {
        if (mode.id === "off" || mode.id === section.defaultMode) {
          return;
        }
        var score = modeMatches(mode, values, ignore);
        if (score > bestScore) {
          best = mode;
          bestScore = score;
        }
      });
      if (best) {
        state[section.id] = best.id;
        return;
      }
      var fallback = modeById(section, section.defaultMode || "off");
      if (fallback && modeMatches(fallback, values, ignore) > 0) {
        state[section.id] = fallback.id;
        return;
      }
      if (ownedZero(section, values)) {
        state[section.id] = section.defaultMode || "off";
        return;
      }
      snapshots[section.id] = ownedMap(section, values);
      state[section.id] = "custom";
    });
    return { state: state, snapshots: snapshots };
  }

  function mutexOk(values, channels) {
    var live = channels.filter(function (ch) {
      return values[ch - 1] > 0;
    });
    return live.length <= 1;
  }

  function mount(container, profile, initialValues) {
    var state = defaultState(profile);
    var snapshots = {};
    var noteEl = document.createElement("p");
    noteEl.className = "help";
    noteEl.hidden = true;
    var sectionsEl = document.createElement("div");
    var previewEl = document.createElement("div");

    function setNote(text) {
      noteEl.hidden = !text;
      noteEl.textContent = text || "";
    }

    function currentValues() {
      return encode(profile, state, snapshots);
    }

    function paintButtons() {
      container.querySelectorAll(".mode-group").forEach(function (group) {
        var sectionId = group.dataset.section;
        var section = profile.sections.find(function (item) {
          return item.id === sectionId;
        });
        if (!section) {
          return;
        }
        group.querySelectorAll(".mode-btn").forEach(function (btn) {
          var id = btn.dataset.mode;
          if (section.exclusive === false) {
            btn.classList.toggle("selected-multi", (state[section.id] || []).indexOf(id) !== -1);
            btn.classList.remove("selected");
          } else {
            btn.classList.toggle("selected", state[section.id] === id);
            btn.classList.remove("selected-multi");
          }
        });
      });
    }

    function paintPreview() {
      var values = currentValues();
      previewEl.textContent = "";
      var heading = document.createElement("h3");
      heading.textContent = "DMX";
      previewEl.appendChild(heading);
      var grid = document.createElement("div");
      grid.className = "dmx-preview";
      values.forEach(function (value, index) {
        var cell = document.createElement("div");
        cell.className = "dmx-channel" + (value > 0 ? " active" : "");
        cell.innerHTML =
          '<span class="ch-num">' + (index + 1) + "</span>" +
          '<span class="ch-val">' + value + "</span>";
        grid.appendChild(cell);
      });
      previewEl.appendChild(grid);
    }

    function refresh() {
      paintButtons();
      paintPreview();
      setNote("");
    }

    function selectExclusive(section, modeId) {
      if (modeId === "custom") {
        return;
      }
      delete snapshots[section.id];
      state[section.id] = modeId;
      render();
    }

    function toggleMulti(section, modeId) {
      delete snapshots[section.id];
      var selected = (state[section.id] || []).slice();
      var index = selected.indexOf(modeId);
      if (index === -1) {
        selected.push(modeId);
      } else {
        selected.splice(index, 1);
      }
      state[section.id] = selected;
      render();
    }

    function render() {
      container.textContent = "";
      container.appendChild(noteEl);
      sectionsEl.textContent = "";
      profile.sections.forEach(function (section) {
        var card = document.createElement("section");
        card.className = "section-card";
        var head = document.createElement("div");
        head.className = "section-head";
        var title = document.createElement("h3");
        title.textContent = section.label;
        head.appendChild(title);
        var group = document.createElement("div");
        group.className = "mode-group";
        group.dataset.section = section.id;
        var lastGroup = "";
        var modes = section.modes.slice();
        if (state[section.id] === "custom") {
          modes = [{ id: "custom", label: "Custom" }].concat(modes);
        }
        modes.forEach(function (mode) {
          if (mode.group && mode.group !== lastGroup) {
            var header = document.createElement("div");
            header.className = "strobe-header";
            header.textContent = mode.group;
            group.appendChild(header);
            lastGroup = mode.group;
          }
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "mode-btn" + (mode.accent ? " accent-" + mode.accent : "");
          btn.dataset.mode = mode.id;
          btn.textContent = mode.label;
          btn.title = mode.id;
          if (mode.id === "custom") {
            btn.disabled = true;
          }
          btn.addEventListener("click", function () {
            if (section.exclusive === false) {
              toggleMulti(section, mode.id);
            } else {
              selectExclusive(section, mode.id);
            }
          });
          group.appendChild(btn);
        });
        card.append(head, group);
        sectionsEl.appendChild(card);
      });
      previewEl.className = "section-card";
      container.append(sectionsEl, previewEl);
      refresh();
    }

    function setValues(next) {
      var loaded = zeros(profile.channelCount);
      (next || []).forEach(function (value, index) {
        if (index < loaded.length) {
          loaded[index] = Math.max(0, Math.min(255, value | 0));
        }
      });
      var decoded = decode(profile, loaded);
      state = decoded.state;
      snapshots = decoded.snapshots || {};
      render();
    }

    function validate() {
      var values = currentValues();
      var errors = [];
      profile.sections.forEach(function (section) {
        (section.constraints || []).forEach(function (constraint) {
          if (constraint.type === "mutex" && !mutexOk(values, constraint.channels)) {
            errors.push(constraint.message);
          }
        });
      });
      return { ok: errors.length === 0, errors: errors };
    }

    setValues(initialValues || zeros(profile.channelCount));

    return {
      getValues: currentValues,
      setValues: setValues,
      validate: validate,
      reset: function () {
        state = defaultState(profile);
        snapshots = {};
        render();
      },
    };
  }

  global.LightsFixtureEditor = {
    mount: mount,
    zeros: zeros,
    encode: encode,
    decode: decode,
    defaultState: defaultState,
    clone: clone,
  };
})(window);
