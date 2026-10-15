# Echo — implementation and connection status

Echo is a private game-development workspace with an eve agent source project in `echo/`.

## What is implemented
- Responsive assistant interface with four task modes: programming, game design, studio planning and trailers.
- Roblox Studio / Unreal Engine 5 target selection.
- Browser-local project brief, editable drafts, downloads and workspace backup export.
- Protected server adapter for the eve runtime. The adapter sends task context and waits for real agent events; it never fabricates replies.
- Agent instructions covering Luau, UE5 C++/Blueprint workflows, practical game design, production and trailer shot planning.
- Separate Docker sandbox configuration with outbound network disabled.
- Production service authentication; no browser-visible agent credential.

## What is not connected
No AI model credentials, running agent host, Docker daemon, Windows/GPU computer, Roblox editor plugin or Unreal editor bridge were supplied. The website explicitly shows these states. No render or engine test has been run. The browser file drafts are not synchronized to the agent computer. Each web task creates a fresh agent session with the last 20 messages; durable cross-task workspace synchronization is future work.

## Run the agent
Use Node 24 and a machine with Docker available. From `echo/`, install using its lockfile and run `npm run dev` for local development. Supply model access via `AI_GATEWAY_API_KEY` in a private runtime environment. Local development is for trusted local access only.

For production, follow the installed eve docs at `node_modules/eve/docs/guides/deployment/self-hosting.mdx`. Configure HTTPS and a secret `ECHO_AGENT_TOKEN` with at least 32 random characters. The website and agent must share that server-only token. Set website environment variables `ECHO_AGENT_URL` to the agent's HTTPS origin and `ECHO_AGENT_TOKEN` to the shared secret; redeploy the website after configuring them. A health check alone confirms reachability, not successful model access. Verify a real conversation and sandbox write/read operation before considering setup complete.

The initial Docker sandbox is for code and files. Roblox Studio / UE5 require a separately connected supported desktop/workstation and verified plugin protocol. No plugin protocol was invented here. Evaluate an actual plugin before adding its MCP or HTTP connection. Do not expose an unauthenticated shell or public remote-control endpoint.

## Verification
Frontend TypeScript and production builds can run without credentials. The agent typecheck verifies its authored configuration. End-to-end AI, sandbox, editor and render tests require the actual connected runtime and editors.
