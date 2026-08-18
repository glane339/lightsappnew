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

  var parDimmer = [
    opt(0, 127, "RGB level", { slider: true }),
    opt(128, 239, "Strobe speed", { slider: true }),
    opt(240, 249, "Strobe to sound", { value: 244 }),
    opt(250, 255, "RGB 100%", { value: 255 }),
  ];

  var derbyColour = [
    opt(0, 24, "Blackout"),
    opt(25, 49, "Red"),
    opt(50, 74, "Green"),
    opt(75, 99, "Blue"),
    opt(100, 124, "Red + Green"),
    opt(125, 149, "Red + Blue"),
    opt(150, 174, "Green + Blue"),
    opt(175, 199, "Red + Green + Blue"),
    opt(200, 224, "Automatic, single colours"),
    opt(225, 255, "Automatic, two colours"),
  ];

  var derbyStrobe = [
    opt(0, 9, "No function"),
    opt(10, 239, "Strobe 0–30 Hz", { slider: true }),
    opt(240, 255, "Strobe to sound", { value: 247 }),
  ];

  var rotation = [
    opt(0, 4, "Stop", { also: [[128, 133]] }),
    opt(5, 127, "Clockwise (slow → fast)", { slider: true }),
    opt(134, 255, "Counter-clockwise (slow → fast)", { slider: true }),
  ];

  var laserColour = [
    opt(0, 39, "Blackout"),
    opt(40, 79, "Red on"),
    opt(80, 119, "Green on"),
    opt(120, 159, "Red + Green on"),
    opt(160, 199, "Red on, Green strobe"),
    opt(200, 239, "Green on, Red strobe"),
    opt(240, 255, "Red + Green, alternate strobe"),
  ];

  var laserStrobe = [
    opt(0, 9, "No function"),
    opt(10, 239, "Strobe speed", { slider: true }),
    opt(240, 255, "Strobe to sound", { value: 247 }),
  ];

  var strobePatterns = [
    opt(0, 9, "Blackout"),
    opt(10, 19, "White auto 1"),
    opt(20, 29, "White auto 2"),
    opt(30, 39, "White auto 3"),
    opt(40, 49, "White auto 4"),
    opt(50, 59, "White auto 5"),
    opt(60, 69, "White auto 6"),
    opt(70, 79, "White auto 7"),
    opt(80, 89, "White auto 8"),
    opt(90, 99, "White auto 9"),
    opt(100, 109, "White manual strobe"),
    opt(110, 119, "UV auto 1"),
    opt(120, 129, "UV auto 2"),
    opt(130, 139, "UV auto 3"),
    opt(140, 149, "UV auto 4"),
    opt(150, 159, "UV auto 5"),
    opt(160, 169, "UV auto 6"),
    opt(170, 179, "UV auto 7"),
    opt(180, 189, "UV auto 8"),
    opt(190, 199, "UV auto 9"),
    opt(200, 209, "UV manual strobe"),
    opt(210, 229, "UV strobe to sound"),
    opt(230, 255, "White strobe to sound"),
  ];

  function parSection(id, label, start) {
    return {
      id: id,
      label: label,
      toggleable: true,
      channels: [start, start + 1, start + 2, start + 3, start + 4],
      constraints: [
        {
          type: "max-nonzero",
          channels: [start, start + 1, start + 2, start + 3],
          max: 3,
          message: label + ": at most 3 of 4 colours may be active.",
        },
      ],
      controls: [
        { kind: "slider", channel: start, label: "Red", accent: "red" },
        { kind: "slider", channel: start + 1, label: "Green", accent: "green" },
        { kind: "slider", channel: start + 2, label: "Blue", accent: "blue" },
        { kind: "slider", channel: start + 3, label: "UV", accent: "uv" },
        { kind: "range-select", channel: start + 4, label: "Dimmer / strobe", options: parDimmer },
      ],
    };
  }

  function derbySection(id, label, start) {
    return {
      id: id,
      label: label,
      toggleable: true,
      channels: [start, start + 1, start + 2],
      controls: [
        { kind: "range-select", channel: start, label: "Colour", options: derbyColour },
        { kind: "range-select", channel: start + 1, label: "Strobe rate", options: derbyStrobe },
        { kind: "range-select", channel: start + 2, label: "Rotation", options: rotation },
      ],
    };
  }

  global.CHAUVET_GIGBAR_2 = {
    model: "chauvet_gigbar_2",
    mode: "23CH",
    channelCount: 23,
    sections: [
      parSection("par1", "Par 1", 0),
      parSection("par2", "Par 2", 5),
      derbySection("derby1", "Derby 1", 10),
      derbySection("derby2", "Derby 2", 13),
      {
        id: "laser",
        label: "Laser",
        toggleable: true,
        channels: [16, 17, 18],
        controls: [
          { kind: "range-select", channel: 16, label: "Colour", options: laserColour },
          { kind: "range-select", channel: 17, label: "Strobe", options: laserStrobe },
          { kind: "range-select", channel: 18, label: "Pattern / rotation", options: rotation },
        ],
      },
      {
        id: "strobe",
        label: "Strobe",
        toggleable: true,
        channels: [19, 20, 21, 22],
        constraints: [
          {
            type: "mutex",
            channels: [20, 21],
            message: "White and UV strobe cannot be used together.",
          },
        ],
        controls: [
          { kind: "range-select", channel: 19, label: "Pattern", options: strobePatterns },
          {
            kind: "mutex-pair",
            channels: [20, 21],
            label: "White or UV dimmer",
            labels: ["White", "UV"],
            accents: ["white", "uv"],
          },
          { kind: "slider", channel: 22, label: "Speed" },
        ],
      },
    ],
  };
})(window);
