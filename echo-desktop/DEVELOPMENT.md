# Echo desktop source

The distributed Windows app is a standalone Electron application. Its renderer has no Node integration and no arbitrary shell or network API. Preload exposes only specific actions. The main process checks IPC sender identity, restricts model requests to the local Ollama service, and only reads/saves user-selected files. External help opens a fixed official download URL. Production content is bundled locally.

## Runtime
Electron 44.7.2 x64 from the official Electron release. Runtime SHA-256:
10a89447ef64ac5cb9f782af48ffd83734a40ae91681259d1048ca3c9e6c5da4

Branding changes the executable resources and removes its upstream signature; the Echo build is unsigned. Original Electron LICENSE and LICENSES.chromium.html are retained alongside the executable. Custom Echo source is supplied for the user's project; no third-party trademark ownership is implied.

## Edit and build
`src/main.tsx` is the React UI, `src/style.css` its styles, `main.cjs` the desktop entrypoint, and `preload.cjs` the narrow IPC bridge. `validation.cjs` checks local chat payloads. `echo-instructions.md` supplies agent behavior.

From the desktop source folder, run `npm install`, `npm run build`, then `npm start`. For code checking, run `npm run typecheck`. The prebuilt `ui/` is included, so launching the app with Electron does not require rebuilding the UI. The build also writes a standalone HTML companion to the parent `outputs/` folder.

The separate `agent-source/` folder, when provided in the source kit, is an eve agent configured for a Docker coding sandbox. It is not wired to the desktop chat, has no editor bridges, and needs its own host/model credentials. See its package scripts and the supplied ECHO_SETUP.md.

## Verification and limitations
TypeScript and syntax checks passed. UI state/navigation/draft persistence and chat validation were exercised in a DOM test environment; this is not a visual Windows test. A Windows machine was unavailable, and browser screenshot infrastructure could not be installed. Live model inference, native dialogs, Windows shortcuts and Windows executable launch require on-device validation.

References:
- https://www.electronjs.org/docs/latest/tutorial/security
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/api/tags
