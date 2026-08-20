"use strict";

(function (global) {
  function encodeId(id) {
    return encodeURIComponent(String(id));
  }

  function errorMessage(data, fallback) {
    if (data && data.error && data.error.message) {
      return data.error.message;
    }
    if (data && typeof data.detail === "string") {
      return data.detail;
    }
    if (data && Array.isArray(data.detail)) {
      return data.detail
        .map(function (item) {
          return item.msg || JSON.stringify(item);
        })
        .join("; ");
    }
    return fallback || "request failed";
  }

  async function request(method, path, body, query) {
    var url = path;
    if (query) {
      var params = new URLSearchParams();
      Object.keys(query).forEach(function (key) {
        if (query[key] !== undefined && query[key] !== null) {
          params.set(key, String(query[key]));
        }
      });
      var qs = params.toString();
      if (qs) {
        url += (path.indexOf("?") === -1 ? "?" : "&") + qs;
      }
    }

    var options = { method: method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }

    var response = await fetch(url, options);
    var data = null;
    var text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (err) {
        data = { raw: text };
      }
    }

    if (!response.ok) {
      var error = new Error(errorMessage(data, response.statusText));
      error.code = data && data.error ? data.error.code : "http";
      error.status = response.status;
      error.payload = data;
      throw error;
    }
    return data;
  }

  function collection(basePath, listKey) {
    return {
      list: function () {
        return request("GET", basePath).then(function (data) {
          return (data && data[listKey]) || [];
        });
      },
      get: function (id) {
        return request("GET", basePath + "/" + encodeId(id));
      },
      create: function (body) {
        return request("POST", basePath, body);
      },
      update: function (id, body) {
        return request("PUT", basePath + "/" + encodeId(id), body);
      },
      remove: function (id, force) {
        return request(
          "DELETE",
          basePath + "/" + encodeId(id),
          undefined,
          force ? { force: "true" } : undefined
        );
      },
      deletePlan: function (id) {
        return request("GET", basePath + "/" + encodeId(id) + "/delete-plan");
      },
    };
  }

  global.LightsApi = {
    request: request,
    encodeId: encodeId,
    devices: function () {
      return request("GET", "/api/dmx-devices").then(function (data) {
        return (data && data.dmx_devices) || [];
      });
    },
    status: function () {
      return request("GET", "/api/status");
    },
    devicePresets: collection("/api/dmx-device-presets", "dmx_device_presets"),
    dmxPresets: collection("/api/dmx-presets", "dmx_presets"),
    dmxLists: collection("/api/dmx-preset-lists", "dmx_preset_lists"),
    wledPresets: {
      list: function () {
        return request("GET", "/api/wled-presets").then(function (data) {
          return (data && data.wled_presets) || [];
        });
      },
      register: function (name) {
        return request("POST", "/api/wled-presets", { name: name });
      },
      refreshLedfx: function () {
        return request("POST", "/api/ledfx/refresh");
      },
      remove: function (id, force) {
        return request(
          "DELETE",
          "/api/wled-presets/" + encodeId(id),
          undefined,
          force ? { force: "true" } : undefined
        );
      },
      deletePlan: function (id) {
        return request("GET", "/api/wled-presets/" + encodeId(id) + "/delete-plan");
      },
    },
    wledLists: collection("/api/wled-preset-lists", "wled_preset_lists"),
    presets: collection("/api/presets", "presets"),
    scenes: collection("/api/scenes", "scenes"),
  };
})(window);
