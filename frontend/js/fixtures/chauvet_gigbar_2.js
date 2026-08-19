"use strict";

(function (global) {
  function parModes(r, g, b, uv, dim) {
    function look(id, label, accent, rv, gv, bv, uvv, dv, group) {
      var mode = { id: id, label: label, accent: accent, channels: {} };
      mode.channels[r] = rv;
      mode.channels[g] = gv;
      mode.channels[b] = bv;
      mode.channels[uv] = uvv;
      mode.channels[dim] = dv;
      if (group) {
        mode.group = group;
      }
      return mode;
    }
    return [
      look("off", "Off", "", 0, 0, 0, 0, 0),
      look("red", "Red", "red", 255, 0, 0, 0, 79),
      look("green", "Green", "green", 0, 255, 0, 0, 79),
      look("blue", "Blue", "blue", 0, 0, 255, 0, 79),
      look("uv", "UV", "uv", 0, 0, 0, 255, 79),
      look("red_strobe", "R Strobe", "red", 255, 0, 0, 0, 249, "Strobe"),
      look("green_strobe", "G Strobe", "green", 0, 255, 0, 0, 249, "Strobe"),
      look("blue_strobe", "B Strobe", "blue", 0, 0, 255, 0, 249, "Strobe"),
      look("uv_strobe", "UV Strobe", "uv", 0, 0, 0, 255, 249, "Strobe"),
    ];
  }

  function derbyModes(colour, strobe, rotation) {
    var colours = [
      ["red", "R", "red", 49],
      ["green", "G", "green", 74],
      ["blue", "B", "blue", 99],
      ["rg", "RG", "mixed", 124],
      ["rb", "RB", "mixed", 149],
      ["gb", "GB", "mixed", 174],
      ["rgb", "RGB", "mixed", 199],
    ];
    var spins = [
      ["cw", "CW", 127],
      ["cc", "CC", 255],
    ];
    var off = { id: "off", label: "Off", channels: {} };
    off.channels[colour] = 0;
    off.channels[strobe] = 0;
    off.channels[rotation] = 0;
    var modes = [off];

    function add(id, label, accent, cv, sv, rv, group) {
      var mode = { id: id, label: label, accent: accent, channels: {} };
      mode.channels[colour] = cv;
      mode.channels[strobe] = sv;
      mode.channels[rotation] = rv;
      if (group) {
        mode.group = group;
      }
      modes.push(mode);
    }

    spins.forEach(function (spin) {
      colours.forEach(function (item) {
        add(item[0] + "_" + spin[0], item[1] + " " + spin[1], item[2], item[3], 0, spin[2]);
      });
    });
    spins.forEach(function (spin) {
      colours.forEach(function (item) {
        add(
          "strobe_" + item[0] + "_" + spin[0],
          item[1] + " " + spin[1],
          item[2],
          item[3],
          250,
          spin[2],
          "Strobe"
        );
      });
    });
    return modes;
  }

  function ch(map) {
    return map;
  }

  global.CHAUVET_GIGBAR_2 = {
    model: "chauvet_gigbar_2",
    mode: "23CH",
    channelCount: 23,
    sections: [
      {
        id: "par_1",
        label: "Par 1",
        owned: [1, 2, 3, 4, 5],
        modes: parModes(1, 2, 3, 4, 5),
      },
      {
        id: "par_2",
        label: "Par 2",
        owned: [6, 7, 8, 9, 10],
        modes: parModes(6, 7, 8, 9, 10),
      },
      {
        id: "derby_1",
        label: "Derby 1",
        owned: [11, 12, 13],
        modes: derbyModes(11, 12, 13),
      },
      {
        id: "derby_2",
        label: "Derby 2",
        owned: [14, 15, 16],
        modes: derbyModes(14, 15, 16),
      },
      {
        id: "laser",
        label: "Laser",
        owned: [17, 18, 19],
        modes: [
          { id: "off", label: "Off", channels: ch({ 17: 0, 18: 0, 19: 0 }) },
          { id: "red_cw", label: "R CW", accent: "red", channels: ch({ 17: 79, 18: 0, 19: 127 }) },
          { id: "red_cc", label: "R CC", accent: "red", channels: ch({ 17: 79, 18: 0, 19: 255 }) },
          { id: "green_cw", label: "G CW", accent: "green", channels: ch({ 17: 119, 18: 0, 19: 127 }) },
          { id: "green_cc", label: "G CC", accent: "green", channels: ch({ 17: 119, 18: 0, 19: 255 }) },
          { id: "rg_cw", label: "RG CW", accent: "mixed", channels: ch({ 17: 159, 18: 0, 19: 127 }) },
          { id: "rg_cc", label: "RG CC", accent: "mixed", channels: ch({ 17: 159, 18: 0, 19: 255 }) },
          { id: "r_gstrobe_cw", label: "R+Gs CW", accent: "mixed", channels: ch({ 17: 199, 18: 0, 19: 127 }) },
          { id: "r_gstrobe_cc", label: "R+Gs CC", accent: "mixed", channels: ch({ 17: 199, 18: 0, 19: 255 }) },
          { id: "rstrobe_g_cw", label: "Rs+G CW", accent: "mixed", channels: ch({ 17: 239, 18: 0, 19: 127 }) },
          { id: "rstrobe_g_cc", label: "Rs+G CC", accent: "mixed", channels: ch({ 17: 239, 18: 0, 19: 255 }) },
          { id: "auto_cw", label: "Auto CW", channels: ch({ 17: 255, 18: 0, 19: 127 }) },
          { id: "auto_cc", label: "Auto CC", channels: ch({ 17: 255, 18: 0, 19: 255 }) },
        ],
      },
      {
        id: "strobe",
        label: "Strobe",
        owned: [20, 21, 22, 23],
        constraints: [
          {
            type: "mutex",
            channels: [21, 22],
            message: "White/UV exclusive",
          },
        ],
        modes: [
          { id: "off", label: "Off", channels: ch({ 20: 0, 21: 0, 22: 0, 23: 0 }) },
          { id: "slowW", label: "Slow W", accent: "white", channels: ch({ 20: 190, 21: 75, 22: 0, 23: 0 }) },
          { id: "slowUV", label: "Slow UV", accent: "uv", channels: ch({ 20: 190, 21: 0, 22: 100, 23: 0 }) },
          { id: "fastW", label: "Fast W", accent: "white", channels: ch({ 20: 209, 21: 75, 22: 0, 23: 0 }) },
          { id: "fastUV", label: "Fast UV", accent: "uv", channels: ch({ 20: 209, 21: 0, 22: 100, 23: 0 }) },
          { id: "soundW", label: "Sound W", accent: "white", channels: ch({ 20: 255, 21: 75, 22: 0, 23: 0 }) },
          { id: "soundUV", label: "Sound UV", accent: "uv", channels: ch({ 20: 255, 21: 0, 22: 100, 23: 0 }) },
        ],
      },
    ],
  };
})(window);
