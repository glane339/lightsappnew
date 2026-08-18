"use strict";

(function (global) {
  function zeros(count) {
    var values = [];
    for (var i = 0; i < count; i += 1) {
      values.push(0);
    }
    return values;
  }

  function optionMatches(option, value) {
    if (value >= option.min && value <= option.max) {
      return true;
    }
    return (option.also || []).some(function (range) {
      return value >= range[0] && value <= range[1];
    });
  }

  function findOption(options, value) {
    for (var i = 0; i < options.length; i += 1) {
      if (optionMatches(options[i], value)) {
        return options[i];
      }
    }
    return options[0];
  }

  function nonzeroCount(values, channels) {
    return channels.reduce(function (count, ch) {
      return count + (values[ch] > 0 ? 1 : 0);
    }, 0);
  }

  function mount(container, profile, initialValues) {
    var values = zeros(profile.channelCount);
    var snapshots = {};
    var sectionOn = {};
    var syncers = [];
    var noteEl = document.createElement("p");
    noteEl.className = "help";
    noteEl.hidden = true;

    function setNote(text) {
      noteEl.hidden = !text;
      noteEl.textContent = text || "";
    }

    function applyConstraint(constraint, channel, nextValue) {
      if (constraint.type === "max-nonzero") {
        var wouldBe = nextValue > 0;
        var was = values[channel] > 0;
        if (wouldBe && !was && nonzeroCount(values, constraint.channels) >= constraint.max) {
          setNote(constraint.message);
          return values[channel];
        }
      }
      if (constraint.type === "mutex") {
        if (nextValue > 0) {
          constraint.channels.forEach(function (ch) {
            if (ch !== channel) {
              values[ch] = 0;
            }
          });
        }
      }
      return nextValue;
    }

    function writeChannel(channel, nextValue, section) {
      var constrained = nextValue;
      (section.constraints || []).forEach(function (constraint) {
        constrained = applyConstraint(constraint, channel, constrained);
      });
      values[channel] = Math.max(0, Math.min(255, constrained | 0));
      return values[channel];
    }

    function renderControl(control, section, body) {
      if (control.kind === "slider") {
        var row = document.createElement("div");
        row.className = "control-row";
        var label = document.createElement("span");
        label.textContent = control.label;
        var input = document.createElement("input");
        input.type = "range";
        input.min = String(control.min || 0);
        input.max = String(control.max || 255);
        input.value = String(values[control.channel]);
        if (control.accent) {
          input.className = "ch-" + control.accent;
        }
        var readout = document.createElement("span");
        readout.className = "value";
        readout.textContent = input.value;
        input.addEventListener("input", function () {
          var written = writeChannel(control.channel, Number(input.value), section);
          input.value = String(written);
          readout.textContent = String(written);
        });
        row.append(label, input, readout);
        body.appendChild(row);
        syncers.push(function () {
          input.value = String(values[control.channel]);
          readout.textContent = input.value;
        });
        return;
      }

      if (control.kind === "range-select") {
        var stack = document.createElement("div");
        stack.className = "control-stack";
        var field = document.createElement("label");
        field.className = "field";
        field.textContent = control.label;
        var select = document.createElement("select");
        control.options.forEach(function (option, index) {
          var opt = document.createElement("option");
          opt.value = String(index);
          opt.textContent = option.label;
          select.appendChild(opt);
        });
        field.appendChild(select);
        var sliderRow = document.createElement("div");
        sliderRow.className = "control-row";
        var sliderLabel = document.createElement("span");
        sliderLabel.textContent = "Value";
        var slider = document.createElement("input");
        slider.type = "range";
        var sliderReadout = document.createElement("span");
        sliderReadout.className = "value";
        sliderRow.append(sliderLabel, slider, sliderReadout);

        function applyOption(option, keepValue) {
          var current = values[control.channel];
          var next;
          if (option.slider) {
            slider.min = String(option.min);
            slider.max = String(option.max);
            sliderRow.hidden = false;
            if (keepValue && current >= option.min && current <= option.max) {
              next = current;
            } else {
              next = option.min;
            }
            slider.value = String(next);
            sliderReadout.textContent = String(next);
          } else {
            sliderRow.hidden = true;
            if (keepValue && optionMatches(option, current)) {
              next = current;
            } else {
              next = option.value !== undefined ? option.value : option.min;
            }
          }
          writeChannel(control.channel, next, section);
        }

        select.addEventListener("change", function () {
          applyOption(control.options[Number(select.value)], false);
        });
        slider.addEventListener("input", function () {
          var written = writeChannel(control.channel, Number(slider.value), section);
          slider.value = String(written);
          sliderReadout.textContent = String(written);
        });

        stack.append(field, sliderRow);
        body.appendChild(stack);

        function syncSelect() {
          var option = findOption(control.options, values[control.channel]);
          select.value = String(control.options.indexOf(option));
          applyOption(option, true);
        }
        syncers.push(syncSelect);
        syncSelect();
        return;
      }

      if (control.kind === "mutex-pair") {
        var wrap = document.createElement("div");
        wrap.className = "control-stack";
        var title = document.createElement("span");
        title.style.color = "var(--muted)";
        title.style.fontSize = "13px";
        title.textContent = control.label;
        var radios = document.createElement("div");
        radios.className = "mutex-row";
        var name = section.id + "-" + control.channels.join("-");
        var modes = [
          { id: "off", label: "Off" },
          { id: "a", label: control.labels[0] },
          { id: "b", label: control.labels[1] },
        ];
        var inputs = {};
        modes.forEach(function (mode) {
          var lab = document.createElement("label");
          var radio = document.createElement("input");
          radio.type = "radio";
          radio.name = name;
          radio.value = mode.id;
          inputs[mode.id] = radio;
          lab.append(radio, document.createTextNode(mode.label));
          radios.appendChild(lab);
        });
        var sliderRow = document.createElement("div");
        sliderRow.className = "control-row";
        var dimLabel = document.createElement("span");
        dimLabel.textContent = "Dimmer";
        var slider = document.createElement("input");
        slider.type = "range";
        slider.min = "0";
        slider.max = "255";
        var readout = document.createElement("span");
        readout.className = "value";
        sliderRow.append(dimLabel, slider, readout);

        function currentMode() {
          var a = values[control.channels[0]];
          var b = values[control.channels[1]];
          if (a > 0 && a >= b) {
            return "a";
          }
          if (b > 0) {
            return "b";
          }
          return "off";
        }

        function applyMode(mode, level) {
          if (mode === "off") {
            values[control.channels[0]] = 0;
            values[control.channels[1]] = 0;
            sliderRow.hidden = true;
            return;
          }
          sliderRow.hidden = false;
          var amount = level === undefined ? Number(slider.value) || 255 : level;
          if (mode === "a") {
            values[control.channels[0]] = amount;
            values[control.channels[1]] = 0;
            slider.className = control.accents ? "ch-" + control.accents[0] : "";
          } else {
            values[control.channels[0]] = 0;
            values[control.channels[1]] = amount;
            slider.className = control.accents ? "ch-" + control.accents[1] : "";
          }
          slider.value = String(amount);
          readout.textContent = String(amount);
        }

        radios.addEventListener("change", function (event) {
          applyMode(event.target.value, Number(slider.value) || 255);
        });
        slider.addEventListener("input", function () {
          var mode = inputs.a.checked ? "a" : inputs.b.checked ? "b" : "off";
          applyMode(mode, Number(slider.value));
        });

        wrap.append(title, radios, sliderRow);
        body.appendChild(wrap);
        function syncMutex() {
          var mode = currentMode();
          inputs[mode].checked = true;
          applyMode(mode, values[control.channels[0]] || values[control.channels[1]] || 0);
        }
        syncers.push(syncMutex);
        syncMutex();
      }
    }

    function sectionActive(section, source) {
      return section.channels.some(function (ch) {
        return source[ch] > 0;
      });
    }

    function setSectionEnabled(section, body, on) {
      sectionOn[section.id] = on;
      body.style.opacity = on || !section.toggleable ? "1" : "0.45";
      body.querySelectorAll("input, select, button").forEach(function (el) {
        if (el.dataset.toggle) {
          return;
        }
        el.disabled = section.toggleable && !on;
      });
    }

    function render() {
      syncers = [];
      container.textContent = "";
      container.appendChild(noteEl);
      profile.sections.forEach(function (section) {
        var card = document.createElement("section");
        card.className = "section-card";
        var head = document.createElement("div");
        head.className = "section-head";
        var title = document.createElement("h3");
        title.textContent = section.label;
        head.appendChild(title);
        var body = document.createElement("div");
        if (section.help) {
          var help = document.createElement("p");
          help.className = "help";
          help.textContent = section.help;
          body.appendChild(help);
        }
        if (section.toggleable) {
          var toggleLab = document.createElement("label");
          var toggle = document.createElement("input");
          toggle.type = "checkbox";
          toggle.dataset.toggle = "1";
          toggle.checked = sectionOn[section.id] !== false;
          toggleLab.append(toggle, document.createTextNode(" On"));
          head.appendChild(toggleLab);
          toggle.addEventListener("change", function () {
            if (toggle.checked) {
              var snap = snapshots[section.id];
              if (snap) {
                section.channels.forEach(function (ch, i) {
                  values[ch] = snap[i];
                });
              }
              setSectionEnabled(section, body, true);
              syncControls();
            } else {
              snapshots[section.id] = section.channels.map(function (ch) {
                return values[ch];
              });
              section.channels.forEach(function (ch) {
                values[ch] = 0;
              });
              setSectionEnabled(section, body, false);
            }
          });
        }
        section.controls.forEach(function (control) {
          renderControl(control, section, body);
        });
        card.append(head, body);
        container.appendChild(card);
        setSectionEnabled(section, body, !section.toggleable || sectionOn[section.id] !== false);
      });
    }

    function syncControls() {
      syncers.forEach(function (sync) {
        sync();
      });
    }

    function setValues(next) {
      values = zeros(profile.channelCount);
      (next || []).forEach(function (value, index) {
        if (index < values.length) {
          values[index] = Math.max(0, Math.min(255, value | 0));
        }
      });
      snapshots = {};
      profile.sections.forEach(function (section) {
        sectionOn[section.id] = !section.toggleable || sectionActive(section, values);
      });
      render();
      setNote("");
    }

    function validate() {
      var errors = [];
      profile.sections.forEach(function (section) {
        (section.constraints || []).forEach(function (constraint) {
          if (constraint.type === "max-nonzero" && nonzeroCount(values, constraint.channels) > constraint.max) {
            errors.push(constraint.message);
          }
          if (constraint.type === "mutex") {
            var live = constraint.channels.filter(function (ch) {
              return values[ch] > 0;
            });
            if (live.length > 1) {
              errors.push(constraint.message);
            }
          }
        });
      });
      return { ok: errors.length === 0, errors: errors };
    }

    profile.sections.forEach(function (section) {
      sectionOn[section.id] = !section.toggleable;
    });
    setValues(initialValues || zeros(profile.channelCount));

    return {
      getValues: function () {
        return values.slice();
      },
      setValues: setValues,
      validate: validate,
      reset: function () {
        setValues(zeros(profile.channelCount));
      },
    };
  }

  global.LightsFixtureEditor = { mount: mount, zeros: zeros };
})(window);
