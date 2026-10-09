/* One install page. iPhone and Android add the web app. Store builds come later. */
(function () {
  Pidi.registerSW();
  Pidi.watchSignal();

  var ua = navigator.userAgent || "";
  var ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var android = /Android/.test(ua);
  var main = document.getElementById("screen");
  var dock = document.getElementById("dock");
  dock.appendChild(Pidi.el("a", { class: "btn secondary", href: "../index.html", text: "Open Pidi" }));

  main.appendChild(Pidi.el("img", {
    class: "icon-preview",
    src: "../brand/icon-192.png",
    alt: "Pidi"
  }));
  main.appendChild(Pidi.el("h1", { text: "Add Pidi" }));

  function steps(lines) {
    var ol = Pidi.el("ol", { class: "steps" });
    lines.forEach(function (line, i) {
      var li = Pidi.el("li");
      li.appendChild(Pidi.el("span", { class: "num", text: String(i + 1) }));
      li.appendChild(Pidi.el("span", { text: line }));
      ol.appendChild(li);
    });
    return ol;
  }

  if (ios) {
    main.appendChild(Pidi.el("p", { text: "On iPhone, add it from Safari. It opens full screen, like an app." }));
    main.appendChild(steps([
      "Open this page in Safari",
      "Tap Share",
      "Tap Add to Home Screen, then Add"
    ]));
    main.appendChild(Pidi.el("p", { class: "quiet", text: "TestFlight comes later, once the Apple account is ready. Until then, the home screen icon is the app." }));
  } else if (android) {
    main.appendChild(Pidi.el("p", { text: "On Android, add it from Chrome. It opens full screen, like an app." }));
    main.appendChild(steps([
      "Open this page in Chrome",
      "Tap the menu, the three dots",
      "Tap Install app, or Add to Home Screen"
    ]));
    main.appendChild(Pidi.el("p", { class: "quiet", text: "A downloadable Android file comes later. Until then, the home screen icon is the app." }));
    var promptEvent = null;
    window.addEventListener("beforeinstallprompt", function (ev) {
      ev.preventDefault();
      promptEvent = ev;
      var btn = Pidi.el("button", { class: "btn", type: "button", text: "Install app", style: "margin-top:12px" });
      btn.addEventListener("click", function () {
        if (!promptEvent) return;
        promptEvent.prompt();
      });
      document.getElementById("dock").appendChild(btn);
    });
  } else {
    main.appendChild(Pidi.el("p", { text: "Open this page on the phone, then add it to the home screen." }));
    main.appendChild(Pidi.el("img", {
      class: "qr",
      src: "qr.svg",
      alt: "QR code for the Pidi driver install page"
    }));
    main.appendChild(Pidi.el("p", { class: "quiet", text: "https://victorfromaruba-stack.github.io/restaurant-/driver/install/" }));
  }
})();
