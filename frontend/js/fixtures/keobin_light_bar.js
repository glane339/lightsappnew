"use strict";

(function (global) {
  function ch(map) {
    return map;
  }

  function laserSection(id, label, channel, accent) {
    var off = { id: "off", label: "Off", channels: {} };
    off.channels[channel] = 0;
    var on = { id: "on", label: "On", accent: accent, channels: {} };
    on.channels[channel] = 255;
    on.channels[6] = 255;
    return {
      id: id,
      label: label,
      owned: [channel],
      matchIgnore: [6],
      modes: [off, on],
    };
  }

  global.KEOBIN_LIGHT_BAR = {
    model: "keobin_light_bar",
    mode: "18CH",
    channelCount: 18,
    sections: [
      {
        id: "special",
        label: "Special access",
        help: "Keep Not used so the bar follows app beats, not its own auto/sound programs.",
        owned: [1],
        defaultMode: "unused",
        modes: [
          { id: "unused", label: "Not used", channels: ch({ 1: 0 }) },
          { id: "self1", label: "Self-run 1", channels: ch({ 1: 45 }) },
          { id: "self2", label: "Self-run 2", channels: ch({ 1: 75 }) },
          { id: "self3", label: "Self-run 3", channels: ch({ 1: 105 }) },
          { id: "sound1", label: "Sound 1", channels: ch({ 1: 135 }) },
          { id: "sound2", label: "Sound 2", channels: ch({ 1: 165 }) },
          { id: "sound3", label: "Sound 3", channels: ch({ 1: 195 }) },
          { id: "unused_high", label: "Not used (high)", channels: ch({ 1: 255 }) },
        ],
      },
      laserSection("green_laser", "Green laser", 2, "green"),
      laserSection("red_laser_1", "Red laser 1", 3, "red"),
      laserSection("blue_laser", "Blue laser", 4, "blue"),
      laserSection("red_laser_2", "Red laser 2", 5, "red"),
      {
        id: "magic_ball",
        label: "Magic ball",
        exclusive: false,
        owned: [7, 8, 9, 10, 11, 12, 13],
        help: "Multi-select. Each colour is independent.",
        modes: [
          { id: "red_1", label: "Red 1", accent: "red", channels: ch({ 7: 255 }) },
          { id: "green_1", label: "Green 1", accent: "green", channels: ch({ 8: 255 }) },
          { id: "blue_1", label: "Blue 1", accent: "blue", channels: ch({ 9: 255 }) },
          { id: "white_1", label: "White 1", accent: "white", channels: ch({ 10: 255 }) },
          { id: "red_2", label: "Red 2", accent: "red", channels: ch({ 11: 255 }) },
          { id: "green_2", label: "Green 2", accent: "green", channels: ch({ 12: 255 }) },
          { id: "blue_2", label: "Blue 2", accent: "blue", channels: ch({ 13: 255 }) },
        ],
      },
      {
        id: "strobe",
        label: "Strobe",
        owned: [14, 15, 16, 17, 18],
        help: "Channels 15/16 follow the fixture doc default (15 red, 16 green).",
        modes: [
          { id: "off", label: "Off", channels: ch({ 14: 0, 15: 0, 16: 0, 17: 0, 18: 0 }) },
          { id: "red_strobe_slow", label: "R Slow", accent: "red", group: "Slow", channels: ch({ 14: 30, 15: 255, 16: 0, 17: 0, 18: 0 }) },
          { id: "green_strobe_slow", label: "G Slow", accent: "green", group: "Slow", channels: ch({ 14: 30, 15: 0, 16: 255, 17: 0, 18: 0 }) },
          { id: "blue_strobe_slow", label: "B Slow", accent: "blue", group: "Slow", channels: ch({ 14: 30, 15: 0, 16: 0, 17: 255, 18: 0 }) },
          { id: "white_strobe_slow", label: "W Slow", accent: "white", group: "Slow", channels: ch({ 14: 30, 15: 255, 16: 255, 17: 255, 18: 0 }) },
          { id: "red_UV_strobe_slow", label: "R+UV Slow", accent: "uv", group: "Slow", channels: ch({ 14: 30, 15: 255, 16: 0, 17: 0, 18: 255 }) },
          { id: "green_UV_strobe_slow", label: "G+UV Slow", accent: "uv", group: "Slow", channels: ch({ 14: 30, 15: 0, 16: 255, 17: 0, 18: 255 }) },
          { id: "blue_UV_strobe_slow", label: "B+UV Slow", accent: "uv", group: "Slow", channels: ch({ 14: 30, 15: 0, 16: 0, 17: 255, 18: 255 }) },
          { id: "white_UV_strobe_slow", label: "W+UV Slow", accent: "uv", group: "Slow", channels: ch({ 14: 30, 15: 255, 16: 255, 17: 255, 18: 255 }) },
          { id: "red_strobe_fast", label: "R Fast", accent: "red", group: "Fast", channels: ch({ 14: 255, 15: 255, 16: 0, 17: 0, 18: 0 }) },
          { id: "green_strobe_fast", label: "G Fast", accent: "green", group: "Fast", channels: ch({ 14: 255, 15: 0, 16: 255, 17: 0, 18: 0 }) },
          { id: "blue_strobe_fast", label: "B Fast", accent: "blue", group: "Fast", channels: ch({ 14: 255, 15: 0, 16: 0, 17: 255, 18: 0 }) },
          { id: "white_strobe_fast", label: "W Fast", accent: "white", group: "Fast", channels: ch({ 14: 255, 15: 255, 16: 255, 17: 255, 18: 0 }) },
          { id: "red_UV_strobe_fast", label: "R+UV Fast", accent: "uv", group: "Fast", channels: ch({ 14: 255, 15: 255, 16: 0, 17: 0, 18: 255 }) },
          { id: "green_UV_strobe_fast", label: "G+UV Fast", accent: "uv", group: "Fast", channels: ch({ 14: 255, 15: 0, 16: 255, 17: 0, 18: 255 }) },
          { id: "blue_UV_strobe_fast", label: "B+UV Fast", accent: "uv", group: "Fast", channels: ch({ 14: 255, 15: 0, 16: 0, 17: 255, 18: 255 }) },
          { id: "white_UV_strobe_fast", label: "W+UV Fast", accent: "uv", group: "Fast", channels: ch({ 14: 255, 15: 255, 16: 255, 17: 255, 18: 255 }) },
        ],
      },
    ],
  };
})(window);
