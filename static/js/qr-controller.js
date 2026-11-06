/* Serializes camera/file operations; stale asynchronous results never navigate. */
(function (root) {
  "use strict";
  function createController({makeReader, onResult, onError, onReady = () => {}, releaseMedia = () => {}}) {
    let queue = Promise.resolve(), generation = 0, reader = null, running = false;
    const enqueue = action => {
      const result = queue.then(action);
      queue = result.catch(() => {});
      return result;
    };
    async function cleanup() {
      try {
        if (running) await reader.stop();
      } catch (error) {
        onError(error);
      } finally {
        releaseMedia();
        running = false;
        if (reader) {
          try { reader.clear(); } catch (error) { onError(error); }
        }
        reader = null;
      }
    }
    return {
      start() {
        const token = ++generation;
        let consumed = false;
        return enqueue(async () => {
          await cleanup();
          if (token !== generation) return;
          try {
            reader = makeReader("camera");
            await reader.start({facingMode: "environment"}, {fps: 8}, text => {
              if (token !== generation || consumed) return;
              consumed = true;
              enqueue(async () => {
                await cleanup();
                if (token === generation) onResult(text);
              });
            }, () => {});
            running = true;
            if (token !== generation) await cleanup();
            else onReady();
          } catch (error) {
            await cleanup();
            if (token === generation) onError(error);
          }
        });
      },
      file(file) {
        const token = ++generation;
        return enqueue(async () => {
          await cleanup();
          if (token !== generation) return;
          try {
            reader = makeReader("file");
            const text = await reader.scanFile(file, false);
            await cleanup();
            if (token === generation) onResult(text);
          } catch (error) {
            await cleanup();
            if (token === generation) onError(error);
          }
        });
      },
      stop() {
        generation++;
        releaseMedia();
        return enqueue(cleanup);
      },
      idle() { return queue; }
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {createController};
  else root.BitacoraQR = {createController};
})(typeof globalThis !== "undefined" ? globalThis : this);
