"use strict";

(function (global) {
  function row(id, label, onRemove, onUp, onDown) {
    var item = document.createElement("div");
    item.className = "drag-item";
    item.draggable = true;
    item.dataset.id = id;

    var handle = document.createElement("span");
    handle.textContent = "⋮⋮";
    handle.style.color = "var(--muted)";

    var name = document.createElement("span");
    name.className = "name";
    name.textContent = label || id;

    var up = document.createElement("button");
    up.type = "button";
    up.className = "ghost";
    up.textContent = "↑";
    up.onclick = onUp;

    var down = document.createElement("button");
    down.type = "button";
    down.className = "ghost";
    down.textContent = "↓";
    down.onclick = onDown;

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost";
    remove.textContent = "Remove";
    remove.onclick = onRemove;

    item.append(handle, name, up, down, remove);
    return item;
  }

  function mount(listEl, paletteEl, options) {
    var ids = [];
    var labels = {};
    var dragging = null;

    function emit() {
      if (options && options.onChange) {
        options.onChange(ids.slice());
      }
    }

    function renderList() {
      listEl.textContent = "";
      if (!ids.length) {
        var empty = document.createElement("span");
        empty.className = "empty";
        empty.textContent = "Empty — add from the palette. Empty lists cannot be saved.";
        listEl.appendChild(empty);
        return;
      }
      ids.forEach(function (id, index) {
        var item = row(
          id,
          labels[id] || id,
          function () {
            ids.splice(index, 1);
            renderList();
            emit();
          },
          function () {
            if (index === 0) {
              return;
            }
            ids.splice(index - 1, 0, ids.splice(index, 1)[0]);
            renderList();
            emit();
          },
          function () {
            if (index === ids.length - 1) {
              return;
            }
            ids.splice(index + 1, 0, ids.splice(index, 1)[0]);
            renderList();
            emit();
          }
        );
        item.addEventListener("dragstart", function () {
          dragging = index;
          item.classList.add("ghost");
        });
        item.addEventListener("dragend", function () {
          dragging = null;
          item.classList.remove("ghost");
        });
        item.addEventListener("dragover", function (event) {
          event.preventDefault();
        });
        item.addEventListener("drop", function (event) {
          event.preventDefault();
          if (dragging === null || dragging === index) {
            return;
          }
          var from = dragging;
          var moved = ids.splice(from, 1)[0];
          var target = from < index ? index - 1 : index;
          ids.splice(target, 0, moved);
          dragging = null;
          renderList();
          emit();
        });
        listEl.appendChild(item);
      });
    }

    function renderPalette(items) {
      paletteEl.textContent = "";
      if (!items.length) {
        var empty = document.createElement("span");
        empty.className = "empty";
        empty.textContent = "Nothing in the palette yet.";
        paletteEl.appendChild(empty);
        return;
      }
      items.forEach(function (item) {
        labels[item.id] = item.label || item.id;
        var button = document.createElement("button");
        button.type = "button";
        button.textContent = item.label || item.id;
        button.title = "Add " + item.id;
        button.onclick = function () {
          ids.push(item.id);
          renderList();
          emit();
        };
        paletteEl.appendChild(button);
      });
    }

    return {
      setPalette: renderPalette,
      setIds: function (nextIds, nextLabels) {
        ids = (nextIds || []).slice();
        Object.assign(labels, nextLabels || {});
        renderList();
      },
      getIds: function () {
        return ids.slice();
      },
      clear: function () {
        ids = [];
        renderList();
      },
    };
  }

  global.LightsDragList = { mount: mount };
})(window);
