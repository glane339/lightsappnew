"use strict";

(function (global) {
  function opt(min, max, label, extra) {
    var option = { min: min, max: max, label: label };
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        option[key] = extra[key];
      });
    }
    if (!option.slider && option.value === undefined) {
      option.value = min;
    }
    return option;
  }

  global.KEOBIN_LIGHT_BAR = {
    model: "keobin_light_bar",
    mode: "18CH",
    channelCount: 18,
    sections: [
      {
        id: "mode",
        label: "Special access",
        toggleable: false,
        channels: [0],
        help: "Keep this in a Not used range so the fixture stays on app beats, not its own auto/sound programs.",
        controls: [
          {
            kind: "range-select",
            channel: 0,
            label: "Channel 1",
            options: [
              opt(0, 30, "Not used (000–030)", { value: 0 }),
              opt(31, 60, "Self-running 1"),
              opt(61, 90, "Self-running 2"),
              opt(91, 120, "Self-running 3"),
              opt(121, 150, "Sound control 1"),
              opt(151, 180, "Sound control 2"),
              opt(181, 210, "Sound control 3"),
              opt(211, 255, "Not used (211–255)", { value: 255 }),
            ],
          },
        ],
      },
      {
        id: "lasers",
        label: "Lasers",
        toggleable: true,
        channels: [1, 2, 3, 4, 5],
        controls: [
          { kind: "slider", channel: 1, label: "Green laser 1", accent: "green" },
          { kind: "slider", channel: 2, label: "Red laser 2", accent: "red" },
          { kind: "slider", channel: 3, label: "Blue laser 3", accent: "blue" },
          { kind: "slider", channel: 4, label: "Red laser 4", accent: "red" },
          { kind: "slider", channel: 5, label: "Motors" },
        ],
      },
      {
        id: "ball1",
        label: "Magic ball 1",
        toggleable: true,
        channels: [6, 7, 8, 9],
        controls: [
          { kind: "slider", channel: 6, label: "Red", accent: "red" },
          { kind: "slider", channel: 7, label: "Green", accent: "green" },
          { kind: "slider", channel: 8, label: "Blue", accent: "blue" },
          { kind: "slider", channel: 9, label: "White", accent: "white" },
        ],
      },
      {
        id: "ball2",
        label: "Magic ball 2",
        toggleable: true,
        channels: [10, 11, 12],
        controls: [
          { kind: "slider", channel: 10, label: "Red", accent: "red" },
          { kind: "slider", channel: 11, label: "Green", accent: "green" },
          { kind: "slider", channel: 12, label: "Blue", accent: "blue" },
        ],
      },
      {
        id: "strobe",
        label: "Strobe",
        toggleable: true,
        channels: [13, 14, 15, 16, 17],
        help: "Channels 15/16 (red/green) follow the fixture doc default; confirm on hardware if a colour looks swapped.",
        controls: [
          {
            kind: "range-select",
            channel: 13,
            label: "Mode",
            options: [
              opt(0, 0, "None", { value: 0 }),
              opt(1, 4, "On", { value: 2 }),
              opt(5, 29, "Random", { value: 16 }),
              opt(30, 255, "Speed (slow → fast)", { slider: true }),
            ],
          },
          { kind: "slider", channel: 14, label: "Red", accent: "red" },
          { kind: "slider", channel: 15, label: "Green", accent: "green" },
          { kind: "slider", channel: 16, label: "Blue", accent: "blue" },
          { kind: "slider", channel: 17, label: "Violet", accent: "violet" },
        ],
      },
    ],
  };
})(window);
