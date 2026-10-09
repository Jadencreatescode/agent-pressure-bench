(() => {
  const button = document.querySelector('#share-button');
  const status = document.querySelector('#share-status');
  if (!button || !status) return;

  button.addEventListener('click', async () => {
    const url = button.dataset.shareUrl;
    try {
      await navigator.clipboard.writeText(url);
      button.textContent = 'Link copied';
      status.textContent = url;
    } catch {
      const input = document.createElement('input');
      input.value = url;
      input.setAttribute('aria-label', 'Page link');
      document.body.append(input);
      input.select();
      const copied = document.execCommand('copy');
      input.remove();
      button.textContent = copied ? 'Link copied' : 'Copy unavailable';
      status.textContent = copied ? url : `Copy this link: ${url}`;
    }
  });
})();
