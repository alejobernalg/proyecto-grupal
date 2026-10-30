// Cliente del modo en vivo: recibe frames de `robot-exp play --live` y se reconecta solo.
export function connectLive(url, { onEpisode, onFrame, onStatus }) {
  let socket = null;
  let closed = false;

  function open() {
    onStatus('connecting');
    socket = new WebSocket(url);
    socket.addEventListener('open', () => onStatus('connected'));
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'episode') onEpisode(message.episode);
      else if (message.type === 'frame') onFrame(message.frame);
    });
    socket.addEventListener('close', () => {
      if (closed) return;
      onStatus('waiting');
      setTimeout(open, 1500);
    });
  }

  open();
  return () => {
    closed = true;
    socket?.close();
  };
}
