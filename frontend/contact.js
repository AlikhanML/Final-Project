/* Contact actions share the selected call and the existing Streamlit bridge. */
(() => {
  const callButton = document.getElementById('contact-call');
  const chatButton = document.getElementById('contact-chat');
  if (!callButton || !chatButton) return;

  const dialog = document.getElementById('quick-contact');
  const frames = document.getElementById('quick-frames');
  const close = document.getElementById('quick-close');
  let prepared = '';
  function prepare(room) {
    if (!dialog || !frames) return;
    const identity = room?.dispatcher || '';
    const version = identity ? identity + ':' + p.theme : '';
    if (version === prepared) return;
    if (dialog.open) dialog.close();
    frames.replaceChildren();
    prepared = '';
    if (!identity) return;
    let address = document.referrer;
    try { address = window.parent.location.href; } catch (error) { /* Use referrer. */ }
    if (!address) return;
    const base = new URL(address);
    if (base.origin !== location.origin) return;
    for (const mode of ['call','chat']) {
      const url = new URL(base);
      url.search = '';
      url.hash = '';
      url.searchParams.set('dispatch_chat', identity);
      url.searchParams.set('contact_view', mode);
      url.searchParams.set('embed', 'true');
      url.searchParams.set('embed_options', p.theme === 'light' ? 'light_theme' : 'dark_theme');
      if (mode === 'chat') url.searchParams.set('invite', room.caller);
      const frame = document.createElement('iframe');
      frame.dataset.mode = mode;
      frame.title = mode === 'call' ? 'Қоңырау шалу' : 'Чат';
      frame.referrerPolicy = 'no-referrer';
      frame.hidden = true;
      frame.dataset.url = url.href;
      frames.appendChild(frame);
    }
    prepared = version;
  }
  if (close) close.onclick = () => dialog.close();

  function updateContactActions() {
    const disabled = !p.b || Boolean(pending);
    callButton.disabled = disabled;
    chatButton.disabled = disabled;
  }

  function openContact(mode) {
    if (!p.b || pending) return;
    if (prepared && dialog && frames) {
      for (const frame of frames.children) {
        frame.hidden = frame.dataset.mode !== mode;
        if (!frame.hidden && frame.src !== frame.dataset.url) frame.src = frame.dataset.url;
      }
      document.getElementById('quick-title').textContent = mode === 'chat' ? 'Чат' : 'Қоңырау шалу';
      dialog.showModal();
      return;
    }
    let pageUrl = document.referrer;
    try { pageUrl = window.parent.location.href; } catch (error) { /* Use referrer. */ }
    emit('contact', {mode, page_url: pageUrl});
    updateContactActions();
  }

  callButton.addEventListener('click', () => openContact('call'));
  chatButton.addEventListener('click', () => openContact('chat'));
  const originalRender = render;
  render = function (payload) {
    originalRender(payload);
    prepare(p.b ? p.contact_room : null);
    updateContactActions();
  };
  updateContactActions();
})();
