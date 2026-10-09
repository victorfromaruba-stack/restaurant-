/* Pidi's order system: where orders go, for the website and the kitchen app.
   The address and the key below are public on purpose. The key only lets a phone run the
   handful of order steps the database allows (place an order, read its status, the kitchen
   and driver steps behind their PINs). The same key is in driver/v2/config.js. */
(function () {
  'use strict';
  var URL = 'https://cdkopyphjvfxjqhasrae.supabase.co';
  var KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNka29weXBoanZmeGpxaGFzcmFlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY0OTY3ODAsImV4cCI6MjEwMjA3Mjc4MH0.eT4MtVYAY1_bopVwTkGXFhJhi7lpJNj9gx-DuIddl60';

  // One call. Errors carry the database's own sentence ("Food minimum is ƒ24 before delivery.").
  function rpc(name, args, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, ms || 15000) : 0;
    return fetch(URL + '/rest/v1/rpc/' + name, {
      method: 'POST',
      headers: { 'content-type': 'application/json', apikey: KEY, authorization: 'Bearer ' + KEY },
      body: JSON.stringify(args || {}),
      cache: 'no-store',
      signal: ctl ? ctl.signal : undefined
    }).then(function (res) {
      clearTimeout(timer);
      return res.text().then(function (t) {
        var body = null;
        try { body = t ? JSON.parse(t) : null; } catch (e) { body = null; }
        if (!res.ok) {
          var err = new Error((body && body.message) || 'Something went wrong. Try again.');
          err.status = res.status;
          throw err;
        }
        return body;
      });
    }, function (e) {
      clearTimeout(timer);
      var err = new Error(e && e.name === 'AbortError' ? 'No answer. Check your internet and try again.' : 'No connection. Check your internet and try again.');
      err.offline = true;
      throw err;
    });
  }

  // A live ping on a topic (the database sends {"ping":"changed"}; never order details).
  // Plain WebSocket, no library. Reconnects by itself; polling covers any gap.
  function listen(topic, onPing) {
    var ws = null, beat = 0, ref = 0, stopped = false, wait = 1000;
    function send(msg) { try { ws.send(JSON.stringify(msg)); } catch (e) { /* closed */ } }
    function connect() {
      if (stopped || !window.WebSocket) return;
      ws = new WebSocket(URL.replace(/^http/, 'ws') + '/realtime/v1/websocket?apikey=' + encodeURIComponent(KEY) + '&vsn=1.0.0');
      ws.onopen = function () {
        wait = 1000;
        send({ topic: 'realtime:' + topic, event: 'phx_join', ref: String(++ref), join_ref: String(ref),
          payload: { config: { broadcast: { ack: false, self: false }, presence: { key: '' }, private: false }, access_token: KEY } });
        clearInterval(beat);
        beat = setInterval(function () { send({ topic: 'phoenix', event: 'heartbeat', payload: {}, ref: String(++ref) }); }, 25000);
      };
      ws.onmessage = function (e) {
        var m = null;
        try { m = JSON.parse(e.data); } catch (err) { return; }
        if (m && m.event === 'broadcast' && m.topic === 'realtime:' + topic) onPing();
      };
      ws.onclose = function () {
        clearInterval(beat);
        if (stopped) return;
        setTimeout(connect, wait);
        wait = Math.min(wait * 2, 30000);
      };
      ws.onerror = function () { try { ws.close(); } catch (e) { /* already closed */ } };
    }
    connect();
    return function stop() { stopped = true; clearInterval(beat); try { ws && ws.close(); } catch (e) { /* closed */ } };
  }

  function money(c) {
    if (c == null || isNaN(c)) return '';
    return 'ƒ' + (Math.round(c) / 100).toFixed(2);
  }

  window.Pidi = { rpc: rpc, listen: listen, money: money, url: URL };
})();
