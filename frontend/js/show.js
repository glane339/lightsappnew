"use strict";

(function (global) {
  var RECONNECT_MS = 1500;

  function ShowClient() {
    this._socket = null;
    this._handlers = {};
    this._closed = false;
    this._reconnectTimer = null;
  }

  ShowClient.prototype.on = function (kind, handler) {
    this._handlers[kind] = handler;
    return this;
  };

  ShowClient.prototype.connect = function () {
    this._closed = false;
    this._open();
    return this;
  };

  ShowClient.prototype.close = function () {
    this._closed = true;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._socket) {
      this._socket.onclose = null;
      this._socket.close();
      this._socket = null;
    }
  };

  ShowClient.prototype.ready = function () {
    return this._socket && this._socket.readyState === WebSocket.OPEN;
  };

  ShowClient.prototype.send = function (message) {
    if (!this.ready()) {
      this._emit("status", { text: "not connected", cls: "dead" });
      return false;
    }
    this._socket.send(JSON.stringify(message));
    return true;
  };

  ShowClient.prototype.activate = function (id) {
    return this.send({ t: "activate", id: id });
  };

  ShowClient.prototype.deactivate = function () {
    return this.send({ t: "deactivate" });
  };

  ShowClient.prototype.blackout = function () {
    return this.send({ t: "blackout" });
  };

  ShowClient.prototype.beat = function () {
    return this.send({ t: "beat" });
  };

  ShowClient.prototype._open = function () {
    var self = this;
    var scheme = location.protocol === "https:" ? "wss" : "ws";
    var socket = new WebSocket(scheme + "://" + location.host + "/ws/show");
    this._socket = socket;

    socket.onopen = function () {
      self._emit("status", { text: "connected", cls: "live" });
    };
    socket.onclose = function () {
      self._emit("status", { text: "disconnected — retrying", cls: "dead" });
      if (!self._closed) {
        self._reconnectTimer = setTimeout(function () {
          self._open();
        }, RECONNECT_MS);
      }
    };
    socket.onmessage = function (event) {
      var msg;
      try {
        msg = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      self._emit(msg.t, msg);
    };
  };

  ShowClient.prototype._emit = function (kind, payload) {
    var handler = this._handlers[kind];
    if (handler) {
      handler(payload);
    }
  };

  global.LightsShow = {
    connect: function (handlers) {
      var client = new ShowClient();
      Object.keys(handlers || {}).forEach(function (kind) {
        client.on(kind, handlers[kind]);
      });
      return client.connect();
    },
  };
})(window);
